"""Offline tests only: network and original experiment execution are never needed."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import judge_workflow2 as j

def context(kind='draft'):
 return {'kind':kind,'answers':[{'text':'Refund issued.','assigned_issue':'refund'}],'user_request':'Where is my refund?','expected_issues':['refund'],'original_authoritative_records':{'refund':{'state':'issued'}},'observed_records':{'refund':{'state':'issued'}},'workflow_context':{},'execution_completed':True}
def valid(ctx=None):
 ctx=ctx or context();v={'criteria':{k:{'label':'PASS','explanation':'Supported by the issued state.','answer_excerpts':[{'answer_index':0,'quote':'Refund issued.'}],'source_fields':[{'path':'/original_authoritative_records/refund/state','value':'issued'}],'omissions':[],'insufficient_evidence':[]} for k in j.CRITERIA},'overall_verdict':'PASS','human_followup_needed':False};return v

def config():return {'max_input_tokens':922000,'max_completion_tokens':3000,'input_usd_per_token':'0.0000001','output_usd_per_token':'0.0000005','max_billable_attempt_multiplier':'1','per_request_fee_usd':'0','billing_contract_verified':True}
class SchemaTests(unittest.TestCase):
 def test_valid(self):self.assertEqual(j.validate(valid(),context())['overall_verdict'],'PASS')
 def test_fabricated_quote(self):
  v=valid();v['criteria']['grounding']['answer_excerpts'][0]['quote']='Tomorrow'
  with self.assertRaisesRegex(ValueError,'Fabricated'):j.validate(v,context())
 def test_fabricated_record(self):
  v=valid();v['criteria']['grounding']['source_fields'][0]['value']='tomorrow'
  with self.assertRaisesRegex(ValueError,'Fabricated'):j.validate(v,context())
 def test_malformed(self):
  with self.assertRaises(ValueError):j.validate({'overall_verdict':'FAIL'},context())
 def test_overall_not_model_authority(self):
  v=valid();v['criteria']['grounding']['label']='FAIL';v['human_followup_needed']=True
  with self.assertRaisesRegex(ValueError,'aggregation'):j.validate(v,context())
 def test_record_alignment_separate_draft(self):
  v=valid();v['criteria']['record_alignment']['label']='FAIL';v['human_followup_needed']=True
  self.assertEqual(j.validate(v,context())['overall_verdict'],'PASS')
 def test_bundle_data_issue(self):
  v=valid();v['criteria']['record_alignment']['label']='FAIL';v['human_followup_needed']=True;v['overall_verdict']='DATA_ISSUE'
  self.assertEqual(j.validate(v,context('bundle'))['overall_verdict'],'DATA_ISSUE')
 def test_uncertain_requires_explanation(self):
  v=valid();v['criteria']['coverage']['label']='UNCERTAIN';v['overall_verdict']='UNCERTAIN';v['human_followup_needed']=True
  with self.assertRaisesRegex(ValueError,'insufficient'):j.validate(v,context())
 def test_omission_no_fake_quote(self):
  v=valid();v['criteria']['coverage'].update(label='FAIL',answer_excerpts=[],omissions=[{'required':'Report refund state','missing':'Refund conclusion absent','requirement_source_path':'/original_authoritative_records/refund/state'}]);v['overall_verdict']='FAIL';v['human_followup_needed']=True
  self.assertEqual(j.validate(v,context())['overall_verdict'],'FAIL')
 def test_corrupt_only_grounding_rejected(self):
  v=valid();v['criteria']['grounding']['source_fields'][0]['path']='/observed_records/refund/state'
  with self.assertRaisesRegex(ValueError,'original authoritative'):j.validate(v,context())
 def test_context_dedup_changes(self):
  a=context();b=copy.deepcopy(a);b['workflow_context']['disposition']='discarded'
  self.assertNotEqual(j.digest(a),j.digest(b));self.assertEqual(j.digest(a),j.digest(copy.deepcopy(a)))
class BudgetTests(unittest.TestCase):
 def test_over_budget_no_dispatch(self):
  l=j.new_ledger();j.reserve(l,'a','2.99','c','p')
  with self.assertRaises(ValueError):j.reserve(l,'b','.02','c','p')
  self.assertEqual(len(l['requests']),1)
 def test_exact_ceiling(self):
  l=j.new_ledger();j.reserve(l,'a','3','c','p');self.assertEqual(j.balance(l),j.CEILING)
 def test_unknown_retains(self):
  l=j.new_ledger();e=j.reserve(l,'a','.1','c','p')
  with self.assertRaises(ValueError):j.settle(e,None,config())
  self.assertEqual(j.balance(l),j.D('.1'));self.assertEqual(e['state'],'reserved')
 def test_reasoning_charged_in_total(self):
  l=j.new_ledger();e=j.reserve(l,'a','.1','c','p');j.settle(e,{'prompt_tokens':100,'completion_tokens':1000,'completion_tokens_details':{'reasoning_tokens':700}},config());self.assertEqual(j.balance(l),j.D('.00051'))
 def test_unknown_category_retains(self):
  l=j.new_ledger();e=j.reserve(l,'a','.1','c','p')
  with self.assertRaises(ValueError):j.settle(e,{'prompt_tokens':100,'completion_tokens':10,'new_billable_category':1},config())
  self.assertEqual(j.balance(l),j.D('.1'))
 def test_above_output_cap(self):
  l=j.new_ledger();e=j.reserve(l,'a','.1','c','p')
  with self.assertRaises(ValueError):j.settle(e,{'prompt_tokens':100,'completion_tokens':3001},config())
 def test_crash_resume_retains(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'ledger.json';l=j.new_ledger();j.reserve(l,'a','.1','c','p');j.atomic(p,l);resumed=j.read(p)
   self.assertEqual(j.balance(resumed),j.D('.1'))
   with self.assertRaisesRegex(ValueError,'Unresolved'):j.reserve(resumed,'a','.1','c','p')
 def test_billing_gate(self):
  c=config();c['billing_contract_verified']=False
  with self.assertRaisesRegex(ValueError,'unverified'):j.reservation(c)
 def test_reservation_uses_full_input_cap(self):self.assertEqual(j.reservation(config()),j.D('.0937'))
 def test_lock(self):
  with tempfile.TemporaryDirectory() as d:
   with j.lock(Path(d)):
    with self.assertRaises(ValueError):
     with j.lock(Path(d)):pass
 def test_transport_zero_retries_no_secret_argv(self):
  from types import SimpleNamespace
  with patch.object(j.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='{"data":[]}\n200',stderr='')) as run:
   j.http('https://tritonai-api.ucsd.edu/v1/models','SECRET')
   args=run.call_args[0][0];self.assertNotIn('SECRET',str(args));self.assertEqual(args[args.index('--retry')+1],'0')

class ResumeTests(unittest.TestCase):
 def test_resume_skips_valid_paid_judgment(self):
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d);(folder/'judgments').mkdir();(folder/'errors').mkdir();(folder/'system_prompt.txt').write_text('prompt')
   c=config();c.update(endpoint='https://tritonai-api.ucsd.edu/v1',model='gpt-6-luna');j.atomic(folder/'judge_config.json',c)
   ctx=context();jid=j.digest(ctx);jobs={jid:{'job_id':jid,'input_hash':jid,'context':ctx}};ph=j.filehash(folder/'system_prompt.txt');ch=j.contract_hash(c)
   j.atomic(folder/'pilot_plan.json',{'job_ids':[jid],'prompt_hash':ph});j.atomic(folder/'budget_ledger.json',j.new_ledger())
   j.atomic(folder/'judgments'/(jid+'.json'),{'input_hash':jid,'prompt_hash':ph,'config_hash':ch,'judgment':valid()})
   with patch.object(j,'HERE',folder),patch.object(j,'lock',return_value=j.lock(folder)),patch.object(j,'verified_inputs',return_value=jobs),patch.object(j,'preflight',return_value={'blockers':[]}),patch.object(j,'credentials',return_value=('SECRET',c['endpoint'])),patch.object(j,'report'),patch.object(j,'http') as transport:
    j.execute(None,pilot=True);transport.assert_not_called()
   self.assertEqual(j.read(folder/'budget_ledger.json')['requests'],[])
 def test_no_gpt_preflight_blocks_paid_dispatch(self):
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d);j.atomic(folder/'judge_config.json',config())
   with patch.object(j,'HERE',folder),patch.object(j,'lock',return_value=j.lock(folder)),patch.object(j,'verified_inputs',return_value={}),patch.object(j,'preflight',return_value={'blockers':['No GPT access']}),patch.object(j,'report'),patch.object(j,'http') as transport:
    with self.assertRaisesRegex(ValueError,'No GPT access'):j.execute(None,pilot=True)
    transport.assert_not_called()
 def test_stale_prompt_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d);(folder/'judgments').mkdir();(folder/'system_prompt.txt').write_text('new prompt');j.atomic(folder/'judge_config.json',config())
   jid=j.digest(context());j.atomic(folder/'judgments'/(jid+'.json'),{'input_hash':jid,'prompt_hash':'old','config_hash':j.contract_hash(config()),'judgment':valid()})
   with patch.object(j,'HERE',folder):
    with self.assertRaisesRegex(ValueError,'Stale'):j.successful_jobs({jid:{'input_hash':jid,'context':context()}})


class AvailableModelTests(unittest.TestCase):
 def test_cached_input_conservatively_full_price(self):
  l=j.new_ledger();e=j.reserve(l,'a','.1','c','p');j.settle(e,{'prompt_tokens':100,'completion_tokens':1000,'total_tokens':1100,'prompt_tokens_details':{'cached_tokens':50,'created_cache_tokens':30},'cache_read_input_tokens':50},config());self.assertEqual(j.balance(l),j.D('.00051'))
 def test_cache_cannot_exceed_prompt(self):
  l=j.new_ledger();e=j.reserve(l,'a','.1','c','p')
  with self.assertRaises(ValueError):j.settle(e,{'prompt_tokens':100,'completion_tokens':10,'prompt_tokens_details':{'created_cache_tokens':101}},config())
 def test_safety_holdback(self):
  l=j.new_ledger();l['safety_holdback_usd']='1.00';j.reserve(l,'a','1.99','c','p')
  with self.assertRaises(ValueError):j.reserve(l,'b','.02','c','p')
 def test_execution_completed_source_pointer(self):
  v=valid();v['criteria']['coverage']['source_fields']=[{'path':'/execution_completed','value':True}];self.assertEqual(j.validate(v,context('bundle'))['overall_verdict'],'PASS')
 def test_root_array_source_pointer(self):
  v=valid();v['criteria']['relevance']['source_fields']=[{'path':'/expected_issues','value':['refund']}];self.assertEqual(j.validate(v,context())['overall_verdict'],'PASS')

if __name__=='__main__':unittest.main()
