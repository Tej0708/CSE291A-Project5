"""Offline profile mechanics; scripted answers do not model LLM susceptibility."""
import json
from pathlib import Path
import unittest
from dataclasses import replace

from csa_workflow.dataset import load_cases
from csa_workflow.faults import FaultInjector, QAFeedback, QA_FIRST_MISSING_ONCE_V1 as PROFILE
from csa_workflow.state import WorkflowState, IssueStatus
from run_fault_audit import audit, ScriptedLLM


class QAProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {c.case_id: c for c in load_cases('support_cases_unique40.jsonl')}
        cls.case = cls.cases['BASE-0003-QA_CORRUPTION']

    def injector(self):
        return FaultInjector('qa_corruption', {'profile': PROFILE, 'target_stage': 'qa_to_router'})

    def state(self):
        s = WorkflowState('test', 'test', 4, iteration=1)
        s.ensure_issue('app_crash')
        s.ensure_issue('duplicate_charge').status = IssueStatus.RESOLVED
        return s

    def test_both_orders_receipt_and_natural_subsequent_feedback(self):
        for order in (self.case.expected_issues, list(reversed(self.case.expected_issues))):
            with self.subTest(order=order):
                r = audit(self.case, ScriptedLLM(order), profile=PROFILE)
                self.assertEqual(r['actual_mutation_count'], 1)
                e = r['events'][0]
                self.assertEqual(e['original_label'], order[1])
                self.assertEqual(e['replacement_label'], order[0])
                self.assertEqual(e['original_value']['passed'], e['injected_value']['passed'])
                self.assertEqual(e['original_value']['reason'], e['injected_value']['reason'])
                self.assertEqual(e['next_router']['input'], e['injected_value'])
                self.assertEqual(e['next_router']['selected_issue'], order[0])
                self.assertTrue(e['behavioral_effect'])
                self.assertTrue(any(a['stage'] == 'helper_result' for a in e['next_router']['actions']))
                self.assertEqual(r['events'][1]['injected_value']['missing_issue'], order[1])
                self.assertEqual(r['events'][1]['skip_reason'], 'already_injected_once')
                self.assertIsNone(r['recovery_success'])

    def test_completed_single_issue(self):
        c = self.cases['BASE-0001-QA_CORRUPTION']
        r = audit(c, ScriptedLLM(c.expected_issues), profile=PROFILE)
        self.assertEqual(r['actual_mutation_count'], 0)
        self.assertEqual(r['skip_reasons'], ['no_missing_issue'])

    def test_no_resolved_candidate(self):
        s = self.state()
        s.issues['duplicate_charge'].status = IssueStatus.OPEN
        i = self.injector()
        f = QAFeedback(False, 'app_crash', 'unchanged')
        self.assertIs(i.on_qa_feedback(1, f, s), f)
        self.assertEqual(i.last_profile_event['skip_reason'], 'no_resolved_replacement_candidate')

    def test_no_remaining_router_iteration(self):
        r = audit(replace(self.case, max_iterations=1), ScriptedLLM(self.case.expected_issues), profile=PROFILE)
        self.assertFalse(r['eligible'])
        self.assertEqual(r['skip_reasons'], ['no_remaining_router_iteration'])
        self.assertEqual(r['actual_mutation_count'], 0)

    def test_exactly_once_and_isolated_runs(self):
        runs = [audit(self.case, ScriptedLLM(self.case.expected_issues), profile=PROFILE) for _ in range(2)]
        self.assertNotEqual(runs[0]['run_id'], runs[1]['run_id'])
        for r in runs:
            self.assertEqual(r['actual_mutation_count'], 1)
            self.assertGreater(len(r['events']), 1)
            self.assertTrue(all(not e['effective_mutation'] for e in r['events'][1:]))
        self.assertEqual(self.case.fault_config['trigger_iteration'], 2)
        self.assertNotIn('profile', self.case.fault_config)

    def test_recent_resolution_and_lexical_tie_break(self):
        s = self.state()
        s.ensure_issue('refund_status')
        i = self.injector()
        # No missing label allows us to observe resolutions without injection.
        i.on_qa_feedback(1, QAFeedback(True, None, 'observation'), s)
        s.issues['app_crash'].status = IssueStatus.RESOLVED
        s.ensure_issue('installation_failure').status = IssueStatus.RESOLVED
        s.iteration = 2
        f = QAFeedback(False, 'refund_status', 'preserve verbatim')
        out = i.on_qa_feedback(2, f, s)
        self.assertEqual(out.missing_issue, 'app_crash')
        self.assertEqual(out.reason, f.reason)
        self.assertEqual(i.last_profile_event['resolved_candidates'],
                         ['app_crash', 'installation_failure', 'duplicate_charge'])

    def test_invalid_or_resolved_missing_label(self):
        for label, reason in [('technical', 'invalid_missing_issue_label'),
                              ('duplicate_charge', 'missing_issue_not_unresolved_in_case'),
                              ('refund_status', 'missing_issue_not_unresolved_in_case')]:
            i = self.injector()
            f = QAFeedback(False, label, 'unchanged')
            self.assertIs(i.on_qa_feedback(1, f, self.state()), f)
            self.assertEqual(i.last_profile_event['skip_reason'], reason)

    def test_disabled_all_variants_match_saved_original_histories(self):
        for backend in ('rule', 'scripted'):
            saved = json.loads(Path(f'fault_audit/observed_{backend}_None.json').read_text())
            for old in saved['cases']:
                c = self.cases[old['case_id']]
                with self.subTest(backend=backend, case=c.case_id):
                    r = audit(c, ScriptedLLM(c.expected_issues) if backend == 'scripted' else None)
                    self.assertEqual(r['result'], old['result'])
                    self.assertEqual(r['effective_mutation'], old['effective_mutation'])
                    self.assertEqual(r['effective_consumed'], old['effective_consumed'])

    def test_profile_rejects_non_qa_and_legacy_override(self):
        with self.assertRaises(ValueError):
            audit(self.case, qa_trigger=1, profile=PROFILE)
        with self.assertRaises(ValueError):
            audit(self.cases['BASE-0003-TIMEOUT'], profile=PROFILE)

if __name__ == '__main__': unittest.main()
