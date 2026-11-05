"""Workflow 1: paired live fault/recovery study (or explicitly scripted smoke test).

Run from project root: python -m experiments.run_live_fault_recovery --help
Creates NEW output dir, records each result incrementally, and stops on infrastructure/budget failures.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
import sys

from core.api_budget import BudgetedModelClient
from core.budget import RunBudget
from core.config import Settings, load_settings
from core.model_client import INFRASTRUCTURE_ERRORS, TritonModelClient
from data.loader import DEFAULT_DATASET_PATH
from experiments.clean_baseline import USER_KEY_BUDGET_USD, key_usage, public_price
from experiments.compare_recovery import trial
from experiments.records import manifest, write_json
from experiments.scripted_model import ScriptedModelClient
from workflows.fulfillment.faults import FaultSpec, default_faults
from workflows.fulfillment.dataset import FulfillmentDataset
from workflows.fulfillment.workflow import FulfillmentWorkflow

MODES = ('unprotected', 'full_restart', 'always_verify')
STOP_ERRORS = INFRASTRUCTURE_ERRORS | {
    'InferenceBudgetExceeded', 'BudgetExceeded', 'BadRequestError',
    'NotFoundError', 'UnprocessableEntityError', 'FaultConfigurationError',
}


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', required=True, help='New directory; never overwrites existing results')
    p.add_argument('--scripted', action='store_true', help='Offline mechanics-only smoke test; NOT LLM evidence')
    p.add_argument('--dataset', type=Path, default=DEFAULT_DATASET_PATH)
    p.add_argument('--faults-file', type=Path, help='JSON array of FaultSpec definitions for the selected dataset')
    p.add_argument('--fault-id', action='append', help='Select a fault (repeatable); default: all 10')
    p.add_argument('--mode', action='append', choices=MODES,
                   help='Select a mode (repeatable); default: all three')
    p.add_argument('--repetitions', type=int, default=1)
    p.add_argument('--seed', type=int, default=20261103)
    p.add_argument('--max-api-calls', type=int, default=150)
    p.add_argument('--max-cost-usd', type=float, default=0.10,
                   help='Conservative estimated cap, not guaranteed actual billing')
    p.add_argument('--max-model-calls-per-trial', type=int, default=15)
    p.add_argument('--max-tool-calls-per-trial', type=int, default=60)
    p.add_argument('--no-shuffle', action='store_true')
    args = p.parse_args(argv)
    if (args.repetitions < 1 or args.max_api_calls < 1
            or not math.isfinite(args.max_cost_usd) or args.max_cost_usd <= 0):
        p.error('Repetitions, API limit and spending limit must be positive')
    if args.max_model_calls_per_trial < 1 or args.max_tool_calls_per_trial < 1:
        p.error('Per-trial budgets must be positive')
    if len(set(args.mode or [])) != len(args.mode or []):
        p.error('Do not repeat --mode')
    if len(set(args.fault_id or [])) != len(args.fault_id or []):
        p.error('Do not repeat --fault-id')
    return args


def schedule(faults, modes, repetitions, seed, shuffle):
    """Every clean/fault pair uses one order and mode. All conditions are predeclared."""
    slots = []
    for iteration in range(1, repetitions + 1):
        for fault in faults:
            for mode in modes:
                pair_id = f'{iteration}:{fault.fault_id}:{mode}'
                conditions = ['clean', 'fault']
                # Balance condition ordering without adapting to outcomes.
                if (sum(ord(c) for c in pair_id) + seed) % 2:
                    conditions.reverse()
                slots.extend(dict(pair_id=pair_id, repetition=iteration,
                                  case_id=fault.case_id, fault_id=fault.fault_id,
                                  fault_type=fault.fault_type, fault_class=fault.fault_class,
                                  stage=fault.stage, surface=fault.surface,
                                  mode=mode, condition=condition) for condition in conditions)
    # Shuffle by PAIR, keeping adjacent clean/fault controls.
    pairs = [slots[i:i+2] for i in range(0, len(slots), 2)]
    if shuffle:
        random.Random(seed).shuffle(pairs)
    return [slot for pair in pairs for slot in pair]


def flatten(record):
    prop = record.get('propagation') or {}
    metrics = record.get('metrics') or {}
    wasted = record.get('wasted_work') or {}
    return {
        **{k: record.get(k) for k in ('slot', 'pair_id', 'repetition', 'case_id', 'fault_id',
                                      'fault_type', 'fault_class', 'mode', 'condition', 'run_status',
                                      'error_type', 'checker_passed', 'task_passed', 'fault_activated',
                                      'attempt_count', 'recovery_detected', 'experiment_error')},
        'model_calls': metrics.get('model_calls'), 'tool_calls': metrics.get('tool_calls'),
        'verification_calls': metrics.get('verification_calls'),
        'total_tokens': metrics.get('total_tokens'),
        'reported_total_tokens': metrics.get('reported_total_tokens'),
        'unknown_usage_calls': metrics.get('unknown_usage_calls'),
        'e2e_latency_ms': metrics.get('e2e_latency_ms'),
        'recovery_latency_ms': record.get('recovery_latency_ms'),
        'discarded_model_calls': wasted.get('discarded_model_calls'),
        'recomputed_model_calls': wasted.get('recomputed_model_calls'),
        'unauthorized_attempts': prop.get('unauthorized_attempts'),
        'unauthorized_dispatched': prop.get('unauthorized_dispatched'),
        'unauthorized_executed': prop.get('unauthorized_executed'),
        'exposed_agents': ','.join(prop.get('delivered_to_agents') or []),
        'affected_stages': ','.join(prop.get('dependency_affected_stages') or []),
        'corrupted_stages': ','.join(prop.get('observed_corrupted_stages') or []),
        'downstream_corrupted_stages': ','.join(prop.get('downstream_corrupted_stages') or []),
        'controlled_interruption': prop.get('controlled_interruption'),
    }


def paired(rows):
    grouped = {}
    for r in rows:
        grouped.setdefault(r['pair_id'], {})[r['condition']] = r
    result = []
    for pair_id, pair in grouped.items():
        clean, fault = pair.get('clean'), pair.get('fault')
        complete = bool(clean and fault and clean.get('experiment_error') is None
                        and fault.get('experiment_error') is None
                        and clean.get('error_type') not in STOP_ERRORS
                        and fault.get('error_type') not in STOP_ERRORS)
        baseline_ok = bool(clean and clean.get('task_passed') is True
                           and clean.get('checker_passed') is True
                           and clean.get('run_status') == 'completed')
        activated = bool(fault and fault.get('fault_activated'))
        eligible = complete and baseline_ok and activated
        delta = {}
        for key in ('model_calls', 'tool_calls', 'verification_calls',
                    'e2e_latency_ms', 'reported_total_tokens'):
            a = flatten(clean).get(key) if clean else None
            b = flatten(fault).get(key) if fault else None
            delta['delta_' + key] = b - a if a is not None and b is not None else None
        result.append({
            'pair_id': pair_id, 'case_id': (clean or fault)['case_id'],
            'fault_id': (clean or fault)['fault_id'], 'fault_class': (clean or fault)['fault_class'],
            'mode': (clean or fault)['mode'], 'complete': complete,
            'clean_pass': baseline_ok, 'activated': activated,
            'eligible_fault_comparison': eligible,
            'fault_task_passed': fault.get('task_passed') if fault else None,
            'fault_checker_passed': fault.get('checker_passed') if fault else None,
            'fault_run_status': fault.get('run_status') if fault else None,
            **delta,
        })
    return result


def save_outputs(destination, rows):
    # Incremental checkpoint: other slots may remain NOT ATTEMPTED if an error occurs.
    flat = [flatten(r) for r in rows]
    with (destination / 'trials.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(flat[0]) if flat else ['slot'])
        w.writeheader()
        w.writerows(flat)
    with (destination / 'paired.csv').open('w', newline='', encoding='utf-8') as f:
        pair_rows = paired(rows)
        w = csv.DictWriter(f, fieldnames=list(pair_rows[0]) if pair_rows else ['pair_id'])
        w.writeheader()
        w.writerows(pair_rows)
    write_json(destination / 'summary.json', {
        'attempted_slots': len(rows),
        'completed_workflows': sum(r.get('run_status') == 'completed' for r in rows),
        'activated_fault_runs': sum(r.get('condition') == 'fault' and r.get('fault_activated') is True for r in rows),
        'eligible_pairs': sum(r['eligible_fault_comparison'] for r in paired(rows)),
        'pair_count_attempted': len(paired(rows)),
        'eligible_fault_task_passes': sum(r['eligible_fault_comparison'] and r['fault_task_passed'] is True
                                          for r in paired(rows)),
        'by_class_and_mode': [
            {'fault_class': klass, 'mode': mode,
             'eligible_pairs': sum(p['eligible_fault_comparison'] and p['fault_class'] == klass and p['mode'] == mode
                                   for p in paired(rows)),
             'successful_eligible_fault_runs': sum(p['eligible_fault_comparison'] and p['fault_class'] == klass
                                         and p['mode'] == mode and p['fault_task_passed'] is True
                                         for p in paired(rows))}
            for klass in ('accidental', 'adversarial') for mode in MODES
        ],
        'caution': 'Eligible comparisons require paired passing clean controls and actual fault activation. '
                   'Do not pool adversarial with accidental faults or count skipped faults as recovery.',
    })


def main(argv=None):
    args = parse_args(argv)
    if args.dataset.resolve() != DEFAULT_DATASET_PATH.resolve() and not args.faults_file:
        raise SystemExit('A custom dataset requires --faults-file with matching cases.')
    specs = ([FaultSpec(**row) for row in json.loads(args.faults_file.read_text())]
             if args.faults_file else default_faults())
    if not specs or len({f.fault_id for f in specs}) != len(specs):
        raise SystemExit('Fault definitions must be nonempty and have unique IDs.')
    dataset = FulfillmentDataset(args.dataset)
    if any(f.case_id not in dataset.orders for f in specs):
        raise SystemExit('Fault definitions reference cases outside the selected dataset.')
    all_faults = {f.fault_id: f for f in specs}
    unknown = sorted(set(args.fault_id or []) - set(all_faults))
    if unknown:
        raise SystemExit(f'Unknown fault IDs: {unknown}. Available: {sorted(all_faults)}')
    faults = [all_faults[x] for x in (args.fault_id or sorted(all_faults))]
    modes = [m for m in MODES if m in (args.mode or MODES)]
    slots = schedule(faults, modes, args.repetitions, args.seed, not args.no_shuffle)
    destination = Path(args.output_dir)
    if destination.exists():
        raise SystemExit('Output directory already exists. Choose a new path to preserve results.')
    # Initialize and validate live access/prices BEFORE creating experiment state.
    settings = None
    price = before = None
    if args.scripted:
        client = ScriptedModelClient()
    else:
        settings = load_settings()
        before = key_usage(settings)
        price = public_price(settings.model_name)
        if before['blocked'] or before['spend'] is None or before['max_budget'] is None:
            raise SystemExit('Provider key spend/budget unavailable or key blocked; aborting.')
        if args.max_cost_usd > min(USER_KEY_BUDGET_USD, before['max_budget']) - before['spend']:
            raise SystemExit('Requested local cost cap exceeds remaining provider key budget.')
        client = BudgetedModelClient(
            TritonModelClient(settings), max_calls=args.max_api_calls,
            max_cost_usd=args.max_cost_usd,
            input_cost_per_token=price['input_cost_per_token'],
            output_cost_per_token=price['output_cost_per_token'],
            max_completion_tokens=settings.max_completion_tokens,
        )
    destination.mkdir(parents=True, exist_ok=False)
    workflow = FulfillmentWorkflow(model_client=client, dataset_path=args.dataset,
                                   log_dir=destination / 'traces')
    metadata = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'kind': 'workflow1_live_fault_recovery', 'backend': 'scripted_offline' if args.scripted else 'live',
        'simulation_only': args.scripted, 'seed': args.seed,
        'repetitions': args.repetitions, 'modes': modes,
        'fault_specs': [asdict(f) for f in faults], 'dataset_file': args.dataset.name,
        'planned_slots': slots, 'source_manifest': manifest(settings, cases=sorted({f.case_id for f in faults}),
            repetitions=args.repetitions, condition='paired_fault_recovery',
            dataset_path=args.dataset) if settings else manifest(
                Settings(api_key='', base_url='', model_name='scripted_offline'),
                cases=sorted({f.case_id for f in faults}), repetitions=args.repetitions,
                condition='scripted_paired_fault_recovery', dataset_path=args.dataset),
        'provider_prices': price, 'key_before': before,
        'max_api_calls': None if args.scripted else args.max_api_calls,
        'max_estimated_cost_usd': None if args.scripted else args.max_cost_usd,
        'per_trial_model_budget': args.max_model_calls_per_trial,
        'per_trial_tool_budget': args.max_tool_calls_per_trial,
        'notes': ['No production side effects; fulfillment tool actions operate on copied simulated state.',
                  'Full restart uses an oracle fault-applied trigger, subject to non-retryable error guards.',
                  'Always verify uses deterministic reference-artifact checks.',
                  'Held-out data is NOT automatically supplied; use this matrix as a pilot unless cases are independent.',
                  'No outcome-dependent resampling or substitution.'],
    }
    write_json(destination / 'manifest.json', metadata)
    with (destination / 'plan.jsonl').open('w', encoding='utf-8') as f:
        for slot in slots:
            f.write(json.dumps(slot) + '\n')
    rows = []
    stop_reason = None
    for i, slot in enumerate(slots, 1):
        fault = all_faults[slot['fault_id']] if slot['condition'] == 'fault' else None
        print(f'[{i}/{len(slots)}] {slot["case_id"]} {slot["fault_id"]} '
              f'{slot["mode"]} {slot["condition"]}', flush=True)
        try:
            trial_data = trial(workflow, slot['case_id'], mode=slot['mode'], fault=fault,
                               budget=RunBudget(max_model_calls=args.max_model_calls_per_trial,
                                                max_tool_calls=args.max_tool_calls_per_trial))
            attempts = trial_data.get('attempts') or []
            activation = any(a['propagation']['fault_activated'] for a in attempts)
            # Aggregate distinct stages across attempts, do not interpret mere exposure as corruption.
            prop = {}
            for field in ('delivered_to_agents', 'dependency_affected_stages', 'observed_corrupted_stages',
                          'downstream_corrupted_stages'):
                prop[field] = sorted({v for a in attempts for v in a['propagation'].get(field, [])})
            for field in ('unauthorized_attempts', 'unauthorized_dispatched', 'unauthorized_executed'):
                values = [a['propagation'].get(field) for a in attempts]
                prop[field] = sum(values) if all(isinstance(v, (int, float)) for v in values) else None
            prop['controlled_interruption'] = any(a['propagation'].get('controlled_interruption') for a in attempts)
            row = {**slot, 'slot': i, **trial_data, 'condition': slot['condition'],
                   'fault_id': slot['fault_id'], 'fault_type': slot['fault_type'],
                   'fault_class': slot['fault_class'],
                   'fault_activated': activation, 'attempt_count': len(attempts),
                   'recovery_detected': any(a['recovery_detected'] for a in attempts),
                   'propagation': prop, 'experiment_error': None}
            if row.get('error_type') in STOP_ERRORS:
                stop_reason = row['error_type']
        except Exception as exc:
            row = {**slot, 'slot': i, 'run_status': 'experiment_error', 'experiment_error': type(exc).__name__,
                   'error_type': type(exc).__name__, 'checker_passed': None, 'task_passed': None,
                   'fault_activated': None, 'propagation': None, 'metrics': None, 'wasted_work': None}
            stop_reason = type(exc).__name__
        rows.append(row)
        with (destination / 'trials.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps(row, default=str) + '\n')
        save_outputs(destination, rows)
        if hasattr(client, 'budget_snapshot'):
            write_json(destination / 'spend.json', client.budget_snapshot())
        if stop_reason:
            break
    if not args.scripted:
        spend = {**client.budget_snapshot(), 'key_before': before, 'public_prices': price}
        try:
            spend['key_after'] = key_usage(settings)
        except Exception as exc:
            spend['key_after_error'] = type(exc).__name__
        write_json(destination / 'spend.json', spend)
    write_json(destination / 'completion.json', {
        'planned_slots': len(slots), 'attempted_slots': len(rows),
        'not_attempted_slots': len(slots) - len(rows), 'stop_reason': stop_reason,
        'finished_utc': datetime.now(timezone.utc).isoformat(),
    })
    print(f'Output: {destination}; attempted {len(rows)}/{len(slots)}; stop_reason={stop_reason}')
    return 1 if stop_reason else 0


if __name__ == '__main__':
    sys.exit(main())
