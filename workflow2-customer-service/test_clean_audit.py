"""Offline regression checks. No SDK installation or API key is required."""
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from csa_workflow.dataset import load_cases
from csa_workflow.orchestrator import run_case
from run_clean_audit import ObservedOpenAI, run_one


class FakeCompletions:
    def __init__(self, classification='["duplicate_charge", "app_crash"]', fail=False):
        self.classification = classification
        self.fail = fail

    def create(self, **kwargs):
        if self.fail:
            raise RuntimeError("Synthetic failure")
        system = kwargs['messages'][0]['content']
        if 'classifier' in system:
            text = self.classification
        elif 'QA reviewer' in system:
            text = '{"missing_issue":"app_crash","reason":"Crash remains open"}'
        else:
            text = 'Synthetic answer for instrumentation testing.'
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=text), finish_reason='stop')],
            usage=SimpleNamespace(model_dump=lambda: {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}),
            model='offline-fake-model', id='offline-response',
        )


def fake_client(**kwargs):
    client = object.__new__(ObservedOpenAI)
    client.model = 'offline-requested-model'
    client.temperature = 0.0
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions(**kwargs)))
    return client


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.case = next(c for c in load_cases() if c.case_id == 'BASE-0003-NONE')

    def execute(self, case, client):
        with tempfile.TemporaryDirectory() as directory:
            report = run_one(case, client, Path(directory))
            trace = (Path(directory) / f'{case.case_id}.trace.jsonl').read_text()
        return report, trace

    def test_rule_workflow_is_unchanged(self):
        expected = run_case(self.case)
        report, trace = self.execute(self.case, None)
        self.assertEqual(report['result']['history'], expected.history)
        self.assertTrue(report['checks']['structural_pass'])
        self.assertIn('raw_tool_result', trace)

    def test_model_calls_answers_usage_and_model_are_recorded(self):
        report, trace = self.execute(self.case, fake_client())
        self.assertEqual(report['metrics']['llm_call_count'], 4)
        self.assertEqual(report['metrics']['total_tokens'], 60)
        self.assertIn('offline-fake-model', trace)
        self.assertIn('Synthetic answer', trace)
        self.assertIsNone(report['checks']['task_success'])

    def test_missing_issue_fails_despite_resolved(self):
        report, _ = self.execute(self.case, fake_client(classification='["duplicate_charge"]'))
        self.assertEqual(report['result']['final_status'], 'resolved')
        self.assertEqual(report['checks']['missing_issues'], ['app_crash'])
        self.assertFalse(report['checks']['structural_pass'])

    def test_corrupted_record_fails_independent_check(self):
        case = replace(self.case, fault_type='helper_corruption',
                       fault_config={'target_agent': 'billing'})
        report, _ = self.execute(case, None)
        self.assertEqual(report['result']['final_status'], 'resolved')
        self.assertFalse(report['checks']['structured_evidence_pass'])

    def test_api_failure_preserves_trace_and_unknown_usage(self):
        report, trace = self.execute(self.case, fake_client(fail=True))
        self.assertEqual(report['run_status'], 'error')
        self.assertIsNone(report['metrics']['total_tokens'])
        self.assertIn('llm_error', trace)
        self.assertNotIn('Synthetic failure', trace)


if __name__ == '__main__':
    unittest.main()
