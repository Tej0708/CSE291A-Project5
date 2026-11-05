"""One clean baseline pass with a small, explicit API allowance."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from core.api_budget import BudgetedModelClient
from core.config import load_settings
from core.model_client import TritonModelClient
from experiments.records import experiment_directory, save_source, write_json
from experiments.run_clean import run_clean_workflow

GATEWAY = 'https://tritonai-api.ucsd.edu'
USER_KEY_BUDGET_USD = 50.0


def key_usage(settings):
    if urlsplit(settings.base_url).hostname != 'tritonai-api.ucsd.edu':
        raise ValueError('This spend checker requires the configured TritonAI gateway')
    request = Request(GATEWAY + '/key/info', headers={
        'Authorization': 'Bearer ' + settings.api_key, 'Accept': 'application/json',
    })
    try:
        with urlopen(request, timeout=20) as response:
            info = json.load(response).get('info', {})
    except HTTPError as error:
        raise RuntimeError(f'Key usage check returned HTTP {error.code}') from None
    # Do not retain the key, key hash/name, user ID, or unrelated account data.
    return {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
            **{key: info.get(key) for key in ('spend', 'max_budget', 'rpm_limit', 'tpm_limit', 'blocked')}}


def public_price(model):
    with urlopen(GATEWAY + '/public/model_hub', timeout=20) as response:
        data = json.load(response)
    rows = data if isinstance(data, list) else data.get('data', [])
    matches = [row for row in rows if row.get('model_group') == model
               and row.get('is_public_model_group') is True]
    if len(matches) != 1:
        raise ValueError('A unique public price is required before running the baseline')
    model_info = matches[0]
    if 'max_completion_tokens' not in model_info.get('supported_openai_params', []):
        raise ValueError('The model does not report support for a completion-token cap')
    return {'model': model,
            'input_cost_per_token': model_info['input_cost_per_token'],
            'output_cost_per_token': model_info['output_cost_per_token'],
            'source_url': GATEWAY + '/public/model_hub',
            'fetched_at_utc': datetime.now(timezone.utc).isoformat()}


def write_analysis(destination, rows, spend):
    passed = sum(row.task_passed is True for row in rows)
    lines = [
        '# Step 2: clean fulfillment baseline', '',
        f'Completed {sum(row.run_status == "completed" for row in rows)}/{len(rows)} attempted orders. '
        f'Task correctness: {passed}/{len(rows)}. Artifact/state checker: {sum(row.passed for row in rows)}/{len(rows)}.',
        '', 'One repetition on the current prompt/schema version. Earlier clean_pilot_1 results are development evidence and are not pooled with this baseline.',
        'Every order starts from an independent copy of the fixed inventory snapshot. The gold table is used only for evaluation.',
        '', '## API usage', '',
        f"- New API requests: {spend['api_calls_sent']} (limit {spend['max_api_calls']}).",
        f"- Reported input/output tokens: {spend['provider_input_tokens']} / {spend['provider_output_tokens']}.",
        f"- Estimated charge from published rates: ${spend['estimated_cost_from_reported_usage_usd']:.8f} (local limit ${spend['max_estimated_cost_usd']:.2f}).",
        f"- Unknown-usage calls: {spend['unknown_usage_calls']}. Conservative reservations remain separate from measured charges.",
        f"- Provider key spend before/after: {spend['key_before']['spend']} / {spend.get('key_after', {}).get('spend')}. The change is key-wide and can include other concurrent use.",
        '- Published prices and provider usage snapshots are saved in spend.json. Local estimates are not a substitute for provider billing.',
        f"- Requests are paced, SDK retries are disabled, and each response is capped at {spend['max_completion_tokens']:,} completion tokens.",
        '', '## Per-order results', '',
        '| Order | Task correct | Checker passed | Outcome | Calls | Tokens | End-to-end ms |',
        '|---|---|---|---|---:|---:|---:|',
    ]
    for row in rows:
        lines.append(f'| {row.task_id} | {row.task_passed} | {row.passed} | {row.outcome} | '
                     f'{row.metrics.model_calls} | {row.metrics.total_tokens} | {row.metrics.e2e_latency_ms:.2f} |')
    lines += ['', '## Interpretation', '',
              'This is a pilot over 30 synthetic cases, not an estimate of reliability across arbitrary orders or repeated stochastic runs. End-to-end latency includes pacing and logging; model-call latency is recorded separately in runs.jsonl.',
              'manifest.json fixes source hashes, model settings, package versions, dataset, and spending limits. source/ preserves the executed code/data without credentials. traces/ contains every input, raw response, artifact, dependency, action, and terminal result.',
              'Next recommended step: review the existing fault-injection harness and confirm controlled activation/consumption before any live fault experiment. No fault/recovery matrix is part of this baseline step.']
    (destination / 'analysis.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--max-api-calls', type=int, default=150)
    parser.add_argument('--max-cost-usd', type=float, default=0.05)
    args = parser.parse_args()
    settings = load_settings()
    destination = args.output_dir or experiment_directory('clean_baseline')
    if destination.exists():
        raise ValueError('Use a new output directory; existing experiments are immutable')
    before, prices = key_usage(settings), public_price(settings.model_name)
    if before['blocked'] or before['spend'] is None or before['max_budget'] is None:
        raise ValueError('An active key with a known spend/budget is required')
    remaining = min(USER_KEY_BUDGET_USD, before['max_budget']) - before['spend']
    if args.max_cost_usd > remaining:
        raise ValueError('Requested local allowance exceeds the remaining key budget')
    client = BudgetedModelClient(
        TritonModelClient(settings), max_calls=args.max_api_calls,
        max_cost_usd=args.max_cost_usd, max_completion_tokens=settings.max_completion_tokens,
        input_cost_per_token=prices['input_cost_per_token'], output_cost_per_token=prices['output_cost_per_token'],
    )
    print(f'Key spend ${before["spend"]:.8f}/${before["max_budget"]:.2f}; '
          f'local limit {args.max_api_calls} calls / ${args.max_cost_usd:.2f}.', flush=True)
    rows = run_clean_workflow(
        workflow_name='fulfillment', settings=settings, repetitions=1,
        output_dir=destination, progress=True, model_client=client,
        budget_metadata={'configuration': client.budget_snapshot(), 'key_before': before,
                         'public_prices': prices, 'user_key_budget_usd': USER_KEY_BUDGET_USD},
    )
    spend = {**client.budget_snapshot(), 'key_before': before, 'public_prices': prices}
    try:
        spend['key_after'] = key_usage(settings)
    except Exception as error:
        spend['key_after_error'] = type(error).__name__
    write_json(destination / 'spend.json', spend)
    save_source(destination)
    write_analysis(destination, rows, spend)
    print(json.dumps(spend, indent=2))
    return int(len(rows) != 30 or not all(row.passed and row.task_passed for row in rows))


if __name__ == '__main__':
    raise SystemExit(main())
