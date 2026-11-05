import json

from experiments import run_live_fault_recovery as runner


def test_smoke_and_immutable_output(tmp_path):
    destination = tmp_path / 'study'
    args = ['--scripted', '--fault-id', 'F-FUL-01', '--output-dir', str(destination)]
    assert runner.main(args) == 0
    completion = json.loads((destination / 'completion.json').read_text())
    assert completion['attempted_slots'] == completion['planned_slots'] == 6
    summary = json.loads((destination / 'summary.json').read_text())
    assert summary['eligible_pairs'] == 3
    import pytest
    with pytest.raises(SystemExit, match='already exists'):
        runner.main(args)


def test_error_preserves_partial_reports(tmp_path, monkeypatch):
    def broken_trial(*args, **kwargs):
        raise RuntimeError('internal detail')

    monkeypatch.setattr(runner, 'trial', broken_trial)
    destination = tmp_path / 'failed'
    assert runner.main(['--scripted', '--fault-id', 'F-FUL-01',
                        '--output-dir', str(destination)]) == 1
    completion = json.loads((destination / 'completion.json').read_text())
    assert completion['attempted_slots'] == 1
    assert completion['not_attempted_slots'] == 5
    assert completion['stop_reason'] == 'RuntimeError'
    assert json.loads((destination / 'summary.json').read_text())['eligible_pairs'] == 0


def test_budget_failure_excluded_from_eligible_pairs():
    common = dict(pair_id='pair', case_id='ORD-1001', fault_id='F-FUL-01',
                  fault_class='accidental', mode='unprotected', experiment_error=None)
    clean = dict(common, condition='clean', task_passed=True, checker_passed=True,
                 run_status='completed')
    fault = dict(common, condition='fault', fault_activated=True,
                 error_type='InferenceBudgetExceeded', run_status='error')
    assert not runner.paired([clean, fault])[0]['eligible_fault_comparison']
