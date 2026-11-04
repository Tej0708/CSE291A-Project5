import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from data.loader import DEFAULT_DATASET_PATH, load_dataset
from experiments.scripted_model import ScriptedModelClient
from experiments.run_live_fault_recovery import main
from workflows.fulfillment.workflow import FulfillmentWorkflow

EVAL = Path(__file__).resolve().parents[1] / 'data/fulfillment_eval.json'
FAULTS = EVAL.with_name('fulfillment_eval_faults.json')


@pytest.mark.parametrize('mode', ['unprotected', 'full_restart', 'always_verify'])
def test_eval_clean_cases(mode, tmp_path):
    raw = load_dataset(EVAL)
    assert len(raw['orders']) == 30
    assert Counter(g['expected_decision'] for g in raw['fulfillment_ground_truth']) == {
        'approve_fulfillment': 10, 'reject_insufficient_stock': 10,
        'reject_shipping_constraint': 10}
    for section, key in [('orders', 'order_id'), ('products', 'product_id')]:
        assert not ({r[key] for r in raw[section]} &
                    {r[key] for r in load_dataset(DEFAULT_DATASET_PATH)[section]})
    workflow = FulfillmentWorkflow(model_client=ScriptedModelClient(), dataset_path=EVAL,
                                   log_dir=tmp_path)
    for case in workflow.list_task_ids():
        result = workflow.run(case, mode=mode)
        assert result.check.passed, (case, result.check.errors)
        assert result.task_check.passed, (case, result.task_check.errors)


def test_eval_matrix(tmp_path, monkeypatch):
    # Actual delays are covered elsewhere; keep this harness test fast.
    from experiments import run_live_fault_recovery as runner
    real_trial = runner.trial
    def fast_trial(*args, fault=None, **kwargs):
        return real_trial(*args, fault=replace(fault, timeout_ms=0) if fault else None, **kwargs)
    monkeypatch.setattr(runner, 'trial', fast_trial)
    out = tmp_path / 'matrix'
    assert main(['--scripted', '--dataset', str(EVAL), '--faults-file', str(FAULTS),
                 '--output-dir', str(out)]) == 0
    summary = json.loads((out / 'summary.json').read_text())
    assert summary['attempted_slots'] == 60
    assert summary['eligible_pairs'] == 30
    import hashlib
    metadata = json.loads((out / 'manifest.json').read_text())
    assert metadata['source_manifest']['dataset_sha256'] == hashlib.sha256(EVAL.read_bytes()).hexdigest()
