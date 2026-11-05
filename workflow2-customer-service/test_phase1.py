"""Phase 1 tests use saved traces and scripted fixtures only; sockets blocked."""
import copy,json,socket,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from dataclasses import replace
from phase1_metrics import measure,rates,unauthorized
from workflow2_phase1 import ROOT,prepare,resume_state,write,sha,review_quality,applicability,validate_manifest,effective
from csa_workflow.dataset import load_cases
from csa_workflow.recovery import run_recovery_case
from run_fault_audit import ScriptedLLM
PILOT=ROOT/'results/workflow2_recovery_smoke_local_20261103_194234'

def result(n):return json.loads(next(PILOT.glob('%02d_*/result.json'%n)).read_text())
class PhaseTests(unittest.TestCase):
 def setUp(self):
  self.net=patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden'));self.net.start();self.addCleanup(self.net.stop)
 def test_consumption_not_completion_or_absence(self):
  self.assertEqual(measure(result(4))['consumption'],'CONSUMED')
  self.assertEqual(measure(result(6))['consumption'],'BLOCKED')
  self.assertEqual(measure(result(8))['consumption'],'CONSUMED')
  r=result(4);r['events']=[e for e in r['events'] if e['event'] not in ('router_selection','helper_accepted')]
  self.assertEqual(measure(r)['consumption'],'UNKNOWN')
 def test_timeout_is_real_status_mutation_not_label(self):
  for n in (10,11,12):
   m=measure(result(n));self.assertEqual(m['activation'],'ACTIVATED');self.assertEqual(m['paths'][0]['after']['status'],'timeout');self.assertTrue(m['policy_detection'])
 def test_stage_counts_and_union(self):
  m=measure(result(4));self.assertEqual(m['affected_stage_types'],['helper','router']);self.assertEqual(m['affected_stage_execution_count'],2)
  self.assertEqual(m['waste']['union_count'],len(set(m['waste']['discarded_call_ids'])|set(m['waste']['repeated_call_ids'])))
  r=result(4)
  for c in r['calls']:
   if c['call_id'] in m['waste']['repeated_call_ids']:c['discarded_reason']=['output_replaced','verification_rejected']
  overlap=measure(r)['waste']
  self.assertLess(overlap['union_count'],len(overlap['discarded_call_ids'])+len(overlap['repeated_call_ids']))
 def test_no_semantic_inference(self):
  m=measure(result(7));self.assertEqual(m['structural_validity'],'PASS');self.assertEqual(m['final_answer_quality'],'UNREVIEWED');self.assertIsNone(m['recovery_success']);self.assertEqual(m['propagation'],'PROPAGATED')
 def test_authorization_states(self):
  self.assertEqual(unauthorized(False)['status'],'N/A');self.assertIsNone(unauthorized(True)['executed']);self.assertEqual(unauthorized(True,[])['executed'],0)
 def test_denominators(self):
  clean=measure(result(1));fault=measure(result(4));inactive=copy.deepcopy(fault);inactive['activation']='NOT_ACTIVATED'
  a=rates([clean,fault,inactive]);self.assertIsNone(a['clean_success_reviewed']['value']);self.assertEqual(a['fault_activation_all_planned']['value'],.5);self.assertEqual(a['conditional_clean_success_eligible'],0)
  clean['final_answer_quality']='FAIL';a=rates([clean,fault]);self.assertEqual(a['clean_failures'],1);self.assertEqual(a['clean_success_reviewed']['value'],0)
 def test_single_shot_all_faults_all_policies(self):
  cases=[effective(c) for c in load_cases(ROOT/'support_cases_unique40.jsonl') if c.case_id.startswith('BASE-0004-')]
  for c in cases:
   for mode in ('unprotected','full_restart','always_verify'):
    r=run_recovery_case(c,mode=mode,llm=ScriptedLLM(c.expected_issues))
    self.assertEqual(r['actual_mutation_count'],0 if c.fault_type=='none' else 1)
    self.assertFalse(any(e.get('mutated') and e['attempt_id']>1 for e in r['events']))
 def test_manifest_and_resume(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);cfg=t/'cfg.json';write(cfg,dict(base_case_ids=['BASE-0004'],scenarios=['NONE','QA_CORRUPTION'],repetitions=1,order='clean_first',seed=None,request_limit=150))
   m=prepare(cfg,t/'manifest.json');validate_manifest(m);self.assertEqual(m['expected_run_count'],6)
   changed=copy.deepcopy(m);changed['run_order'].reverse()
   with self.assertRaises(ValueError):validate_manifest(changed)
   out=t/'runs';out.mkdir();self.assertEqual(resume_state(out,m),[])
   slot=m['run_order'][0];d=out/slot['slot_id'];d.mkdir()
   with self.assertRaises(ValueError):resume_state(out,m)
   write(d/'result.json',result(1));write(d/'complete.json',dict(manifest_id=m['manifest_id'],slot_id=slot['slot_id'],result_sha256=sha(d/'result.json'),execution='completed',sanity_passed=True))
   self.assertEqual(resume_state(out,m),[slot['slot_id']])
   with self.assertRaises(FileExistsError):prepare(cfg,t/'manifest.json')
 def test_full_runner_executes_once_and_resumes_without_calls(self):
  from workflow2_phase1 import execute
  from test_recovery_smoke_pilot import FakeSDK,client
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);write(t/'cfg.json',dict(base_case_ids=['BASE-0004'],scenarios=['NONE','QA_CORRUPTION','HELPER_CORRUPTION','TIMEOUT'],repetitions=1,order='clean_first',seed=None,request_limit=150))
   m=prepare(t/'cfg.json',t/'manifest.json');sdk=FakeSDK()
   with patch('workflow2_phase1.OpenAIClient',return_value=client(sdk)):
    execute(t/'manifest.json',t/'runs')
   self.assertEqual(len(list((t/'runs').glob('*/complete.json'))),12)
   with patch('workflow2_phase1.OpenAIClient',side_effect=AssertionError('No new calls on complete resume')):
    execute(t/'manifest.json',t/'runs',True)
 def test_no_guessed_repetitions(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t);write(t/'cfg.json',dict(base_case_ids=None,scenarios=None,repetitions=None,order=None,request_limit=150))
   with self.assertRaisesRegex(ValueError,'Unresolved'):prepare(t/'cfg.json',t/'m.json')
 def test_review_does_not_promote_blank_to_pass(self):
  items=[dict(event_id='x',issue='app_crash')]
  self.assertEqual(review_quality(items,{},True,['app_crash']),'UNREVIEWED')
  self.assertEqual(review_quality(items,{},False,['app_crash']),'FAIL')
 def test_dataset(self):
  a=applicability();self.assertEqual(len(a),200);self.assertEqual(len({x['base_case_id'] for x in a}),40)
  self.assertEqual(sum(x['static_applicable'] for x in a if x['fault_type']=='qa_corruption'),20)
if __name__=='__main__':unittest.main()
