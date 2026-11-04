"""Local, opt-in, bounded Workflow 2 smoke pilot. No network without --execute."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, replace
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace

from csa_workflow.dataset import load_cases
from csa_workflow.llm import OpenAIClient, load_dotenv
from csa_workflow.recovery import BudgetExceeded, RecoveryRunner, RunBudget
from csa_workflow.cost_metrics import summarize
from csa_workflow.services import scenario_for, call_tool
from csa_workflow.taxonomy import ISSUE_ROUTE

ROOT = Path(__file__).resolve().parent
SAVED = ROOT / 'results/workflow2_step3_pilot_local_20261102_120737/selected_case_manifest.json'
POLICIES = ('unprotected', 'full_restart', 'always_verify')
SUFFIXES = ('NONE', 'QA_CORRUPTION', 'HELPER_CORRUPTION', 'TIMEOUT')
REQUEST_LIMIT = 150
USD_LIMIT = Decimal('3')


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    try:
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def matrix():
    cases = {c.case_id: c for c in load_cases(ROOT / 'support_cases_unique40.jsonl')}
    selected = [cases['BASE-0004-' + suffix] for suffix in SUFFIXES]
    selected[1] = replace(selected[1], fault_config={
        'profile': 'qa_first_missing_once_v1', 'target_stage': 'qa_to_router'})
    clean = selected[0]
    scenario = scenario_for(clean.case_id, clean.user_query)
    for case in selected:
        if case.user_query != clean.user_query or case.max_iterations != clean.max_iterations:
            raise ValueError('Frozen variants disagree on request or iterations')
        if scenario_for(case.case_id, case.user_query) != scenario:
            raise ValueError('Frozen variants disagree on scenario')
    for issue in scenario['records']:
        record = call_tool(issue, case_id=clean.case_id, user_query=clean.user_query)
        if record.status != 'ok' or not record.record:
            raise ValueError('Scenario record unavailable')
    if {ISSUE_ROUTE[i] for i in scenario['records']} != {'technical', 'billing'}:
        raise ValueError('Both helpers must be reachable')
    if selected[2].fault_config['target_agent'] not in {'technical', 'billing'}:
        raise ValueError('Helper target unavailable')
    return [(case, mode) for case in selected for mode in POLICIES], scenario


def pricing_config(path, model):
    if path is None or not Path(path).is_file():
        return {'verified': False, 'pricing_status': 'unavailable'}
    cfg = json.loads(Path(path).read_text())
    required = ('input_usd_per_million', 'output_usd_per_million', 'input_token_ceiling', 'completion_cap', 'completion_cap_parameter')
    if cfg.get('verified') is not True or any(cfg.get(k) is None for k in required):
        return {'verified': False, 'pricing_status': 'unavailable', 'supplied_metadata': cfg}
    if cfg.get('model') != model or cfg.get('verified') is not True:
        raise ValueError('Pricing must be verified for the saved exact model')
    for key in ('provider_host', 'pricing_source', 'limits_source', 'verified_at'):
        if not isinstance(cfg.get(key), str) or not cfg[key].strip():
            raise ValueError('Missing verified configuration field: ' + key)
    for key in ('input_usd_per_million', 'output_usd_per_million'):
        try:
            value = Decimal(str(cfg[key]))
        except (KeyError, InvalidOperation):
            raise ValueError('Supply verified rate: ' + key)
        if not value.is_finite() or value < 0:
            raise ValueError('Invalid rate: ' + key)
    for key in ('input_token_ceiling', 'completion_cap'):
        if type(cfg.get(key)) is not int or cfg[key] <= 0:
            raise ValueError('Supply a verified positive integer: ' + key)
    if cfg.get('completion_cap_parameter') not in ('max_tokens', 'max_completion_tokens'):
        raise ValueError('Supply a provider-supported completion cap parameter')
    # Optional lower project ceilings may only reduce the user ceilings.
    if 'project_request_limit' in cfg:
        if type(cfg['project_request_limit']) is not int or cfg['project_request_limit'] < 0:
            raise ValueError('Invalid project_request_limit')
    if 'project_usd_limit' in cfg:
        value = Decimal(str(cfg['project_usd_limit']))
        if not value.is_finite() or value < 0:
            raise ValueError('Invalid project_usd_limit')
    return cfg


class SpendGate:
    """Never release reservations: missing usage/failures remain fully charged here."""
    def __init__(self, cfg, *, pilot_ceiling=True):
        self.cfg = cfg
        limit = cfg.get('project_request_limit', REQUEST_LIMIT)
        self.request_limit = min(REQUEST_LIMIT, limit) if pilot_ceiling else limit
        self.usd_limit = min(USD_LIMIT, Decimal(str(cfg.get('project_usd_limit', USD_LIMIT))))
        self.per_request = (Decimal(str(cfg['input_usd_per_million'])) * cfg['input_token_ceiling']
                            + Decimal(str(cfg['output_usd_per_million'])) * cfg['completion_cap']) / Decimal(1000000) if cfg.get('verified') else None
        self.requests = 0
        self.reserved = Decimal(0) if self.per_request is not None else None
        self.blocked = False
        self.violation = False

    def reserve(self):
        if self.violation or (self.request_limit is not None and self.requests >= self.request_limit) or (self.per_request is not None and self.reserved + self.per_request > self.usd_limit):
            self.blocked = True
            raise BudgetExceeded('pilot-wide request or conservative USD reservation limit')
        self.requests += 1
        if self.per_request is not None:
            self.reserved += self.per_request
        return self.requests

    def snapshot(self):
        return {'provider_requests': self.requests, 'request_limit': self.request_limit,
                'reserved_usd': str(self.reserved) if self.reserved is not None else None, 'usd_limit': str(self.usd_limit) if self.per_request is not None else None,
                'per_request_reserved_usd': str(self.per_request) if self.per_request is not None else None,
                'reservation_policy': 'Conservative reservations when verified; otherwise cost unknown and USD gate inactive',
                'blocked': self.blocked, 'configuration_violation': self.violation}


def sanitized_provider_error(exc, sdk):
    """Allowlisted provider fields only; never serialize exception/request/headers."""
    import os, re
    secrets = [v for k,v in os.environ.items()
               if any(part in k.upper() for part in ('KEY','TOKEN','SECRET','PASSWORD')) and len(v)>3]
    key = getattr(sdk, 'api_key', None)
    if isinstance(key, str) and key:secrets.append(key)
    def clean(value):
        if not isinstance(value, (str,int,float)):return None
        text = str(value)
        for secret in sorted(secrets,key=len,reverse=True):text=text.replace(secret,'[REDACTED]')
        text=re.sub(r'https?://[^\s]+','[URL REDACTED]',text)
        text=re.sub(r'(?i)bearer\s+[^\s,;]+','Bearer [REDACTED]',text)
        text=re.sub(r'(?i)(api[_-]?key|authorization|token|password|secret)\s*[=:]\s*[^\s,;]+',r'\1=[REDACTED]',text)
        text=re.sub(r'\b(?:sk-|gh[pousr]_)[A-Za-z0-9_-]+','[REDACTED]',text)
        return ''.join(c if c.isprintable() else ' ' for c in text)[:2000]
    body=getattr(exc,'body',None)
    if isinstance(body,dict) and isinstance(body.get('error'),dict):body=body['error']
    body=body if isinstance(body,dict) else {}
    response=getattr(exc,'response',None)
    headers=getattr(response,'headers',{}) or {}
    return dict(provider_error_code=clean(body.get('code',getattr(exc,'code',None))),
                provider_error_type=clean(body.get('type',getattr(exc,'type',None))),
                provider_error_message=clean(body.get('message')),
                retry_after=clean(headers.get('retry-after')))


class ProviderBoundary:
    """One SDK dispatch per request, with saved SDK retries=0; no hidden retries."""
    def __init__(self, sdk, gate, runner, path):
        if sdk.max_retries != 0:
            raise ValueError('Observable request bound requires saved SDK max_retries=0')
        self.sdk, self.gate, self.runner = sdk, gate, runner
        self.rows = []
        self.file = path.open('x', encoding='utf-8')

    def record(self, row):
        self.file.write(json.dumps(row, ensure_ascii=True) + '\n')
        self.file.flush()

    def create(self, **kwargs):
        cfg = self.gate.cfg
        # The outer accounting adapter invokes this original SDK boundary.
        number = self.gate.reserve()
        if cfg.get('verified'):
            kwargs[cfg['completion_cap_parameter']] = cfg['completion_cap']
        call_id = self.runner.call_stack[-1]
        row = {'provider_request_number': number, 'call_id': call_id,
               'run_id': self.runner.run_id, 'attempt_id': self.runner.attempt,
               'reserved_usd': str(self.gate.per_request) if self.gate.per_request is not None else None, 'status': 'started'}
        self.rows.append(row)
        self.record(dict(row))
        started = time.perf_counter()
        try:
            response = self.sdk.chat.completions.create(**kwargs)
            usage = getattr(response, 'usage', None)
            usage = usage.model_dump() if usage is not None else None
            row.update(status='completed', usage=usage,
                       response_id=getattr(response, 'id', None),
                       returned_model=getattr(response, 'model', None))
            if usage is not None and cfg.get('verified'):
                inp, output = usage.get('prompt_tokens'), usage.get('completion_tokens')
                if ((inp is not None and inp > cfg['input_token_ceiling']) or
                        (output is not None and output > cfg['completion_cap'])):
                    self.gate.violation = True
                    row['configuration_violation'] = 'Provider usage exceeds verified reservation bound'
                row['estimated_observed_usd'] = (str((Decimal(str(cfg['input_usd_per_million'])) * inp
                    + Decimal(str(cfg['output_usd_per_million'])) * output) / Decimal(1000000))
                    if inp is not None and output is not None else None)
            else:
                row['estimated_observed_usd'] = None
            return response
        except BaseException as exc:
            row.update(status='failed', usage=None, estimated_observed_usd=None,
                       error_type=type(exc).__name__, status_code=getattr(exc, 'status_code', None),
                       **sanitized_provider_error(exc, self.sdk))
            raise
        finally:
            row['duration_ms'] = (time.perf_counter() - started) * 1000
            self.record(dict(row))

    def proxy(self):
        return SimpleNamespace(max_retries=0, chat=SimpleNamespace(
            completions=SimpleNamespace(create=self.create)))


def sanity(result, provider_rows):
    """Omitted usage is valid; mismatched IDs or captured usage is not."""
    errors = []
    calls = result['calls']
    models = [c for c in calls if c['kind'] == 'model']
    by_id = {p['call_id']: p for p in provider_rows}
    if not models or len(by_id) != len(provider_rows) or {c['call_id'] for c in models} != set(by_id):
        errors.append('Provider/application identity linkage mismatch')
    if len({c['call_id'] for c in calls}) != len(calls):
        errors.append('Duplicate call IDs')
    for call in models:
        p = by_id.get(call['call_id'])
        if not p:
            continue
        if p['run_id'] != result['run_id'] or p['attempt_id'] != call['attempt_id']:
            errors.append('Run/attempt linkage mismatch')
        usage = p.get('usage') or {}
        expected = {k: usage.get(v) for k, v in (
            ('input_tokens', 'prompt_tokens'), ('output_tokens', 'completion_tokens'),
            ('total_tokens', 'total_tokens'))}
        if usage and call['token_usage'] != expected:
            errors.append('Provider usage capture mismatch')
    if not result['events'] or result['events'][-1]['event'] != 'run_finished':
        errors.append('Missing run endpoint')
    elif summarize(calls, result['recoveries'], result['events'][-1]['elapsed_ms']) != result['metrics']:
        errors.append('Metric reconciliation failed')
    return {'passed': not errors, 'errors': errors,
            'unknown_usage_calls': result['metrics']['provider_usage']['unknown_usage_calls']}


def answers(result):
    retained = {}
    accepted = [e for e in result['events'] if e['event'] == 'helper_accepted']
    final_attempt = result['attempts'][-1]['attempt_id']
    for e in accepted:
        if e['attempt_id'] == final_attempt:
            retained[e['issue']] = e
    kept = {e['event_id'] for e in retained.values()}
    return {'retained': list(retained.values()),
            'discarded_intermediate': [e for e in accepted if e['event_id'] not in kept],
            'quality': 'UNREVIEWED', 'quality_note': 'Provisional human review required; no paid judge calls.'}


def save_summary(out, rows):
    with (out / 'summary.csv').open('w', newline='', encoding='utf-8') as f:
        fields = list(rows[0])
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def execute_one(case, mode, client, gate, folder):
    runner = RecoveryRunner(case, mode, client, RunBudget())
    boundary = ProviderBoundary(client._client, gate, runner, folder / 'provider_requests.jsonl')
    original_sdk = client._client
    client._client = boundary.proxy()
    original_emit = runner.emit
    with (folder / 'trace.jsonl').open('x', encoding='utf-8') as trace:
        def emit(event, **data):
            event_id = original_emit(event, **data)
            trace.write(json.dumps(runner.events[-1], ensure_ascii=True) + '\n')
            trace.flush()
            return event_id
        runner.emit = emit
        runner.fault.emit = emit
        try:
            result = runner.run()
        finally:
            client._client = original_sdk
            boundary.file.close()
    result['provider_request_count'] = len(boundary.rows)
    result['provider_attempt_observability'] = 'SDK retries fixed at saved value 0; one dispatch per observable SDK request; gateway-internal attempts not observable'
    write_json(folder / 'result.json', result)
    write_json(folder / 'metrics.json', result['metrics'])
    write_json(folder / 'provider_usage.json', boundary.rows)
    write_json(folder / 'answers.json', answers(result))
    check = sanity(result, boundary.rows)
    streamed = [json.loads(line) for line in (folder / 'trace.jsonl').read_text().splitlines()]
    if streamed != json.loads(json.dumps(result['events'])):
        check['passed'] = False
        check['errors'].append('Streamed trace does not match complete event ledger')
    write_json(folder / 'logging_sanity.json', check)
    return result, boundary.rows, check


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--output', required=True)
    p.add_argument('--pricing-config', help='Verified local JSON; environment variables still load from repository .env')
    args = p.parse_args(argv)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    plan, scenario = matrix()
    saved = json.loads(SAVED.read_text())
    if saved['transport']['max_retries'] != 0:
        raise ValueError('Saved retry setting changed; request-counting adapter requires revalidation')
    rows = [dict(order=n+1, case_id=c.case_id, policy=m, status='NOT_RUN',
                 structural_status='', quality='UNREVIEWED', actual_mutation_count='',
                 model_calls='', provider_requests='', business_tool_calls='', verification_calls='',
                 tool_calls='', input_tokens='', output_tokens='', total_tokens='', unknown_usage_calls='',
                 e2e_latency_ms='', verification_latency_ms='', repair_latency_ms='', discarded_calls='',
                 restarts='', stage_retries='', reason='') for n,(c,m) in enumerate(plan)]
    manifest = {'source_sha': git('rev-parse','HEAD'), 'working_tree_status': git('status','--short'),
        'accounting_import': json.loads((ROOT/'recovery_smoke_source.json').read_text()),
        'source_hashes': {str(path.relative_to(ROOT)): sha(path) for path in
            [Path(__file__).resolve(), *sorted((ROOT/'csa_workflow').glob('*.py'))]},
        'dataset_sha256': sha(ROOT/'support_cases_unique40.jsonl'),
        'scenario_sha256': sha(ROOT/'csa_workflow/scenario_records.json'),
        'saved_config_path': str(SAVED), 'saved_config_sha256': sha(SAVED),
        'model': saved['model'], 'temperature': saved['temperature'],
        'transport': saved['transport'], 'pacing': 'serial, no explicit delay; same as saved pilot',
        'per_run_budget': asdict(RunBudget()), 'request_limit': REQUEST_LIMIT, 'usd_limit': str(USD_LIMIT),
        'run_order': [dict(order=n+1,case_id=c.case_id,policy=m,fault_config=c.fault_config,
                           max_iterations=c.max_iterations) for n,(c,m) in enumerate(plan)],
        'execute_requested': args.execute}
    write_json(out/'supporting_records.json', scenario)
    shutil_source = ROOT/'BASELINE_EVALUATION_RULES.md'
    (out/'BASELINE_EVALUATION_RULES.md').write_bytes(shutil_source.read_bytes())
    try:
        cfg = pricing_config(args.pricing_config, saved['model'])
        manifest['pricing_and_completion_config'] = cfg
        manifest['usd_limit_enforced'] = bool(cfg.get('verified'))
        if not cfg.get('verified'):
            manifest['usd_limit'] = None
    except (ValueError, KeyError, OSError) as exc:
        manifest['configuration_error'] = str(exc)
        cfg = None
    write_json(out/'manifest.json', manifest)
    status = 'NOT_RUN_CONFIGURATION' if cfg is None else 'NOT_RUN_DRY_RUN'
    for row in rows:
        row.update(status=status,reason=manifest.get('configuration_error','Execution requires --execute'))
    save_summary(out, rows)
    if not args.execute or cfg is None:
        write_json(out/'pilot_status.json', {'status': status, 'provider_requests':0,
            'reserved_usd':None, 'reason':manifest.get('configuration_error','No API calls without --execute')})
        print(status + ': ' + str(out))
        return 2 if args.execute and cfg is None else 0
    gate = SpendGate(cfg)
    try:
        # Exactly the original pilot's environment loading and provider construction.
        load_dotenv()
        client = OpenAIClient(model=saved['model'], temperature=saved['temperature'])
        client._client = client._client.with_options(max_retries=saved['transport']['max_retries'],
                                                    timeout=saved['transport']['timeout_seconds'])
        if cfg.get('verified') and client._client.base_url.host != cfg['provider_host']:
            raise ValueError('Verified pricing host does not match configured provider')
    except Exception as exc:
        for row in rows:
            row.update(status='NOT_RUN_CONFIGURATION', reason=type(exc).__name__)
        save_summary(out, rows)
        write_json(out/'pilot_status.json',dict(gate.snapshot(),status='NOT_RUN_CONFIGURATION',error_type=type(exc).__name__))
        return 2
    for row in rows:
        row.update(status='NOT_RUN_INTERRUPTED', reason='Not yet dispatched')
    save_summary(out, rows)
    stop = None
    for n, (case, mode) in enumerate(plan):
        if stop:
            rows[n].update(status=stop,reason='Pilot stopped before this logical run')
            continue
        folder = out / ('%02d_%s__%s' % (n+1,case.case_id,mode))
        folder.mkdir()
        rows[n].update(status='RUNNING', reason='Logical run dispatched')
        save_summary(out, rows)
        try:
            result, usage, check = execute_one(case, mode, client, gate, folder)
        except (Exception, KeyboardInterrupt) as exc:
            rows[n].update(status='INTERRUPTED' if isinstance(exc, KeyboardInterrupt) else 'HARNESS_ERROR',
                           reason=type(exc).__name__)
            stop='NOT_RUN_INTERRUPTED' if isinstance(exc, KeyboardInterrupt) else 'NOT_RUN_HARNESS_ERROR'
            write_json(folder/'interruption.json', dict(error_type=type(exc).__name__,
                note='Partial trace and provider request journal retained; never retry this logical run automatically.'))
            save_summary(out, rows)
            write_json(out/'pilot_status.json', dict(gate.snapshot(), stop_reason=stop))
            continue
        metrics = result['metrics']
        row = rows[n]
        row.update(status=result['status'].upper(),structural_status=result['status'],
                   actual_mutation_count=result['actual_mutation_count'],provider_requests=len(usage),
                   restarts=result['restart_count'],stage_retries=result['stage_retry_count'],reason='')
        for key in ('model_calls','business_tool_calls','verification_calls','tool_calls',
                    'e2e_latency_ms','verification_latency_ms','repair_latency_ms','discarded_calls'):
            row[key]=metrics[key]
        for key in ('input_tokens','output_tokens','total_tokens','unknown_usage_calls'):
            row[key]=metrics['provider_usage'][key]
        if gate.blocked:
            row['status']='BUDGET_EXHAUSTED'
            stop='NOT_RUN_BUDGET'
        elif gate.violation:
            stop='NOT_RUN_CONFIGURATION'
            row['reason']='Provider exceeded verified cost-reservation assumptions'
        elif not check['passed']:
            stop='NOT_RUN_SANITY_CHECK'
            row['reason']='; '.join(check['errors'])
        elif result['status']=='error':
            stop='NOT_RUN_PROVIDER_ERROR'
        save_summary(out, rows)
        write_json(out/'pilot_status.json', dict(gate.snapshot(),stop_reason=stop))
        print('%02d %s %s %s' % (n+1,case.case_id,mode,row['status']),flush=True)
    save_summary(out, rows)
    write_json(out/'pilot_status.json',dict(gate.snapshot(),stop_reason=stop,executed_runs=sum(r['structural_status']!='' for r in rows)))
    review = []
    for folder in sorted(out.glob('[0-9][0-9]_*')):
        answer_path = folder / 'answers.json'
        if answer_path.exists():
            review.append({'run': folder.name, 'answers': json.loads(answer_path.read_text()),
                           'supporting_records': scenario['records'],
                           'judgment': 'UNREVIEWED', 'human_review_required': True})
    write_json(out/'human_review.json', review)
    return 0 if stop is None else 2


if __name__ == '__main__':
    raise SystemExit(main())
