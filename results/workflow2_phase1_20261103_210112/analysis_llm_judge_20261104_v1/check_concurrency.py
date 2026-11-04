import sys,tempfile,time,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import judge_workflow2 as j
from test_judge import context,valid,config
with tempfile.TemporaryDirectory() as d:
 p=Path(d)
 for n in ['judgments','errors','requests','responses']:(p/n).mkdir()
 (p/'system_prompt.txt').write_text('prompt');c=config();c.update(endpoint='https://tritonai-api.ucsd.edu/v1',model='api-glm-5.3-flash');j.atomic(p/'judge_config.json',c)
 ph=j.filehash(p/'system_prompt.txt');ch=j.contract_hash(c)
 j.atomic(p/'pilot_plan.json',{'job_ids':[],'prompt_hash':ph});j.atomic(p/'pilot_inspection.json',{'approved':True,'config_hash':ch,'prompt_hash':ph});j.atomic(p/'budget_ledger.json',j.new_ledger());j.atomic(p/'cost_estimate.json',{'heuristic_total_usd':'.01'})
 jobs={str(n):{'job_id':str(n),'input_hash':str(n),'context':context()} for n in range(12)}
 def fake(*a,**kw):
  time.sleep(.02);return {'usage':{'prompt_tokens':100,'completion_tokens':100},'choices':[{'finish_reason':'stop','message':{'content':json.dumps(valid())}}],'model':c['model']}
 with patch.object(j,'HERE',p),patch.object(j,'lock',return_value=j.lock(p)),patch.object(j,'verified_inputs',return_value=jobs),patch.object(j,'preflight',return_value={'blockers':[]}),patch.object(j,'credentials',return_value=('SECRET',c['endpoint'])),patch.object(j,'report'),patch.object(j,'http',side_effect=fake):j.execute(None)
 l=j.read(p/'budget_ledger.json');assert len(l['requests'])==12;assert len({e['request_id'] for e in l['requests']})==12;assert all(e['state']=='settled' for e in l['requests']);assert len(list((p/'judgments').iterdir()))==12
 print('PASS: 12 concurrent simulated calls, unique durable reservations, all settlements preserved, no network.')
