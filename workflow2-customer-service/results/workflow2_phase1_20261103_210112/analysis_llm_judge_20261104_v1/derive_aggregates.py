"""Offline deterministic overall aggregation, retaining original model responses.
Does not change a criterion label, explanation, quote or source value. Reuses
only responses whose complete evidence passes the unchanged strict validator
once the overall verdict is recomputed by the repository's aggregation rule.
"""
import json,copy
import judge_workflow2 as j
P=j.HERE
with j.lock():
 jobs=j.verified_inputs();cfg=j.read(P/'judge_config.json');ch=j.contract_hash(cfg);done=j.successful_jobs(jobs);ledger=j.read(P/'budget_ledger.json');actions=[]
 assert not any(e['state']=='reserved' for e in ledger['requests']), 'Pending requests: stop before local aggregation'
 for jid,job in jobs.items():
  if jid in done:continue
  candidates=[e for e in ledger['requests'] if e['job_id']==jid and e['config_hash']==ch and e['state']=='settled']
  for e in reversed(candidates):
   try:
    response=j.read(P/'responses'/str(e['request_id']));choice=response['choices'][0]
    if choice.get('finish_reason')!='stop':continue
    original=json.loads(choice['message']['content']);obj=copy.deepcopy(original)
    # Only deterministic overall aggregation is changed. Every other strict
    # schema/evidence check remains in the original validator.
    obj['overall_verdict']=j.aggregate(obj['criteria'],job['context'])
    if obj['overall_verdict']==original['overall_verdict']:continue
    j.validate(obj,job['context'])
   except (ValueError,KeyError,TypeError,IndexError):continue
   action={'job_id':jid,'request_id':e['request_id'],'original_model_overall':original['overall_verdict'],'locally_derived_overall':obj['overall_verdict'],'criterion_labels_and_evidence_unchanged':True,'method':'Existing aggregate(criteria, context), followed by unchanged strict validate; no API call'}
   j.atomic(P/'judgments'/(jid+'.json'),{'job_id':jid,'input_hash':job['input_hash'],'prompt_hash':e['prompt_hash'],'config_hash':ch,'request_id':e['request_id'],'evaluated_at':j.now(),'model':cfg['model'],'returned_model':response.get('model'),'endpoint':cfg['endpoint'],'judgment':obj,'provenance':'LLM criterion assessment with locally derived repository aggregation; not human-verified','local_aggregation':action})
   actions.append(action);break
 old=j.read(P/'local_aggregation_audit.json') if (P/'local_aggregation_audit.json').exists() else []
 j.atomic(P/'local_aggregation_audit.json',old+actions);j.report()
 print('Locally derived overall verdicts from strictly valid unchanged criteria:',len(actions))
