import unittest
from dataclasses import replace
from csa_workflow.dataset import load_cases
from csa_workflow.faults import FaultInjector, QAFeedback
from run_fault_audit import audit, ScriptedLLM

class FaultAuditTests(unittest.TestCase):
    def setUp(self):
        self.cases = {c.case_id: c for c in load_cases('support_cases_unique40.jsonl')}
        self.case = self.cases['BASE-0003-QA_CORRUPTION']

    def test_eligible_reversed_order_explicit_timing_profile(self):
        r = audit(self.case, ScriptedLLM(['app_crash', 'duplicate_charge']), 1)
        e = r['events'][0]
        self.assertTrue(e['effective_consumed'])
        self.assertEqual(e['original_value']['missing_issue'], 'duplicate_charge')
        self.assertEqual(e['received_value']['missing_issue'], 'technical')
        self.assertEqual(r['result']['terminated_by'], 'budget_exhausted')
        self.assertEqual(r['original_config']['trigger_iteration'], 2)
        self.assertIsNone(r['recovery_success'])
        self.assertTrue(all(x['injected_value']['missing_issue'] == 'technical' for x in r['events']))

    def test_original_trigger_remains_ineligible_even_reversed(self):
        r = audit(self.case, ScriptedLLM(['app_crash', 'duplicate_charge']))
        self.assertFalse(r['effective_mutation'])
        self.assertEqual(r['events'][0]['skip_reason'], 'before_trigger_iteration')

    def test_single_issue_and_original_order_are_ineligible(self):
        for c in (self.case, self.cases['BASE-0001-QA_CORRUPTION']):
            r = audit(c, ScriptedLLM(c.expected_issues), 1)
            self.assertFalse(r['effective_mutation'])
            self.assertIsNone(r['recovery_success'])

    def test_last_iteration_mutation_not_consumed(self):
        r = audit(replace(self.case, max_iterations=1), ScriptedLLM(['app_crash', 'duplicate_charge']), 1)
        self.assertTrue(r['effective_mutation'])
        self.assertFalse(r['effective_consumed'])

    def test_noop_and_invalid_fields_do_not_mutate(self):
        for mutation in ({'field':'missing_issue','original':'x','injected':'x'},
                         {'field':'reason','original':'x','injected':'y'}):
            i = FaultInjector('qa_corruption', dict(target_stage='qa_to_router', trigger_iteration=1, mutation=mutation))
            f = QAFeedback(False, 'x', 'original')
            self.assertIs(i.on_qa_feedback(1, f), f)

    def test_unreachable_stage_and_ignored_document(self):
        r = audit(replace(self.case, max_iterations=0))
        self.assertFalse(r['events'][0]['injection_point_reached'])
        r = audit(self.cases['BASE-0001-PROMPT_INJECTION'])
        self.assertTrue(r['effective_mutation'])
        self.assertFalse(r['effective_consumed'])

if __name__ == '__main__': unittest.main()
