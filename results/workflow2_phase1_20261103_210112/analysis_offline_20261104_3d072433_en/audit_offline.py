"""Read-only audit and report adapter; run with Python 3.9, repository path as argv[1]."""
import sys,json,csv,hashlib,subprocess,re,statistics
from pathlib import Path
from collections import Counter,defaultdict
ROOT=Path(sys.argv[1]).resolve();sys.path.insert(0,str(ROOT))
OUT=Path(__file__).resolve().parent; RUN=ROOT/'results/workflow2_phase1_20261103_210112'
from workflow2_phase1 import read,sha,validate_manifest,CRITERIA
from infrastructure_continuation import validate_plan,tree_hashes
from run_recovery_smoke_pilot import sanity,answers
from csa_workflow.dataset import load_cases
from csa_workflow.cost_metrics import summarize

def dump(name,x): (OUT/name).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def csvout(name,rows,fields=None):
 with (OUT/name).open('w',newline='',encoding='utf-8-sig') as f:
  w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)
def jsonlines(p):return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]
def flatten_diff(a,b,path=''):
 if isinstance(a,dict) and isinstance(b,dict):
  return [v for k in a.keys()|b.keys() for v in flatten_diff(a.get(k),b.get(k),path+'.'+k)]
 return [] if a==b else [{'field':path,'saved':a,'recomputed':b,'absolute_delta':abs(a-b) if isinstance(a,(float,int)) and isinstance(b,(float,int)) else None}]
manifest=read(RUN/'manifest.json');slots=manifest['run_order'];before={k:v for k,v in tree_hashes(RUN).items() if not k.split('/')[0].startswith('analysis')}
checks=[];slotrows=[];runids=[];eventids=[];revisions=Counter();modelconfigs=Counter();returned=Counter();raw={}
plans=[]
for p in sorted(RUN.glob('continuation*.json')):
 try:
  plan=validate_plan(p,RUN,manifest);validate_manifest(manifest,source_hashes=plan['source_hashes'])
  assert tree_hashes(RUN/plan['archive_relative_path'])==plan['original_evidence']
  plans.append({'plan':p.name,'slot_id':plan['slot_id'],'passed':True,'completed_evidence_slots':len(plan['completed_evidence']),'source_changes':plan['source_changes']})
 except Exception as e:plans.append({'plan':p.name,'passed':False,'error':str(e)})
assert (RUN/'manifest.json').read_bytes()==(ROOT/'phase1_v1/full_manifest.json').read_bytes()
for s in slots:
 d=RUN/s['slot_id'];errs=[]
 state='not_run' if not d.exists() else 'partial' if not (d/'complete.json').exists() else read(d/'complete.json')['execution']
 if (d/'result.json').exists():
  r=read(d/'result.json');raw[s['slot_id']]=r;u=read(d/'provider_usage.json');receipt=read(d/'complete.json');identity=read(d/'identity.json')
  tests={'identity_manifest':identity['manifest_id']==manifest['manifest_id'],'identity_slot':identity['slot']==s,'receipt_identity':receipt['manifest_id']==manifest['manifest_id'] and receipt['slot_id']==s['slot_id'],'receipt_hash':receipt['result_sha256']==sha(d/'result.json'),'result_identity':r['case_id']==s['case_id'] and r['mode']==s['policy'] and r['fault_type']==s['scenario'].lower(),'execution':r['status']==state,'recorded_sanity':receipt['sanity_passed'] and read(d/'logging_sanity.json')['passed'],'recomputed_sanity':sanity(r,u)['passed'],'trace_matches_result':jsonlines(d/'trace.jsonl')==r['events'],'metrics_matches_result':read(d/'metrics.json')==r['metrics'],'answers_recomputed':read(d/'answers.json')==answers(r),'model_config':r['model_config']=={'model':manifest['model'],'temperature':manifest['temperature']},'retry_config':r['sdk_retry_config']['max_retries']==0,'budget':r['budget_config']==manifest['per_run_budget'],'iterations':r['max_iterations']==s['max_iterations'],'source_files':all(sha(ROOT/k)==v for k,v in r['source_revision']['file_sha256'].items())}
  journal=jsonlines(d/'provider_requests.jsonl');terminal=[x for x in journal if x['status']!='started'];tests['journal_terminal_matches_usage']=terminal==u
  tests['event_run_linkage']=all(e['run_id']==r['run_id'] for e in r['events'])
  tests['single_shot']=r['actual_mutation_count']==(0 if s['scenario']=='NONE' else 1)
  errs=[k for k,v in tests.items() if not v];checks.append({'slot_id':s['slot_id'],'checks':tests,'sanity':sanity(r,u)})
  runids.append(r['run_id']);eventids.extend(e['event_id'] for e in r['events']);revisions[r['source_revision']['git_head']]+=1;modelconfigs[json.dumps(r['model_config'],sort_keys=True)]+=1;returned.update(x.get('returned_model','unavailable') for x in u)
 slotrows.append(dict(s,execution=state,integrity='PASS' if not errs else 'FAIL',issues='; '.join(errs)))
expected={s['slot_id'] for s in slots};actual={d.name for d in RUN.iterdir() if d.is_dir() and (d/'result.json').exists()}
summary={'repo':'https://github.com/Tej0708/CSE291A-Project5.git','branch':'Billing_loop_structure','commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'source_root':str(ROOT),'raw_results':str(RUN),'output':str(OUT),'runtime':sys.version,'manifest_sha256':sha(RUN/'manifest.json'),'manifest_source_sha':manifest['source_sha'],'counts':{k:sum(x['execution']==k for x in slotrows) for k in ['completed','failed','error','budget_exhausted','partial','not_run']},'planned_unique_slots':len(expected),'unique_tuples':len({(s['base_case_id'],s['scenario'],s['policy'],s['repetition']) for s in slots}),'extra_slots':sorted(actual-expected),'duplicate_run_ids':len(runids)-len(set(runids)),'duplicate_event_ids':len(eventids)-len(set(eventids)),'slot_integrity_failures':[x for x in slotrows if x['integrity']=='FAIL'],'plans':plans,'runtime_git_revisions':dict(revisions),'model_configs':dict(modelconfigs),'provider_returned_models':dict(returned),'human_review_files_in_current_results':[str(p) for p in RUN.rglob('*') if p.is_file() and 'review' in p.name.lower()]}
dump('integrity.json',summary);dump('slot_checks.json',checks);csvout('slots_240.csv',slotrows)
ver=subprocess.run(['/usr/bin/python3',str(ROOT/'verify_workflow2_handoff.py'),'--run-dir',str(RUN),'--require-complete'],cwd=ROOT,text=True,capture_output=True)
(OUT/'verifier_python39.txt').write_text(ver.stdout+ver.stderr+'\nexit_code='+str(ver.returncode)+'\n')
ver14=subprocess.run(['python3',str(ROOT/'verify_workflow2_handoff.py'),'--run-dir',str(RUN),'--require-complete'],cwd=ROOT,text=True,capture_output=True)
(OUT/'verifier_python314.txt').write_text(ver14.stdout+ver14.stderr+'\nexit_code='+str(ver14.returncode)+'\n')
# Independent Python 3.14 reducer diagnostic, without weakening checks or modifying evidence.
code="""import json,sys;from pathlib import Path;from csa_workflow.cost_metrics import summarize
out=[]
for p in Path(sys.argv[1]).glob('BASE*/result.json'):
 r=json.loads(p.read_text());n=summarize(r['calls'],r['recoveries'],r['events'][-1]['elapsed_ms'])
 if n!=r['metrics']:out.append(dict(slot_id=p.parent.name,differences=[dict(field=k,saved=r['metrics'][k],recomputed=v,absolute_delta=abs(v-r['metrics'][k])) for k,v in n.items() if v!=r['metrics'][k]]))
print(json.dumps(out,indent=2))"""
(OUT/'python314_float_differences.json').write_text(subprocess.check_output(['python3','-c',code,str(RUN)],cwd=ROOT,text=True))
rows=read(OUT/'existing_analysis/measurements.json');by_slot={r['slot_id']:r for r in rows};groups=[];pairrows=[]
metricnames=['model_calls','business_tool_calls','verification_calls','e2e_latency_ms','repair_latency_ms','discarded_calls']
for scenario in manifest['config']['scenarios']:
 for policy in manifest['config']['policies']:
  a=[r for r in rows if r['fault_type']==scenario.lower() and r['policy']==policy];g={'scenario':scenario,'policy':policy,'planned_n':20,'observed_n':len(a)}
  for state in summary['counts']:g[state]=sum(r['execution']==state for r in a)
  for status in ['ACTIVATED','NOT_ACTIVATED','UNKNOWN','N/A']:g['activation_'+status]=sum(r['activation']==status for r in a)
  g.update(detected_n=sum(r['policy_detection'] is True for r in a),detection_observable_n=sum(r['policy_detection'] is not None for r in a),policy_repair_n=sum(bool(r['policy_recovery']) for r in a),natural_continuation_n=sum(r['continuation']=='NATURAL_CONTINUATION' for r in a),semantic_recovery_success='unavailable: human review pending',reviewed_decisive_n=0)
  g['recovery_intervals']=sum(len(r['policy_recovery']) for r in a);g['recovery_outcomes']=json.dumps(Counter(rec['outcome'] for r in a for rec in r['policy_recovery']))
  for name in metricnames:
   vals=[r['metrics'].get(name) for r in a];known=[v for v in vals if v is not None];g[name+'_available_n']=len(known);g[name+'_sum']=sum(known) if len(known)==len(a) else None;g[name+'_mean']=statistics.mean(known) if known else None;g[name+'_median']=statistics.median(known) if known else None
  for name in ['input_tokens','output_tokens','total_tokens','known_total_tokens','unknown_usage_calls']:
   vals=[r['metrics']['provider_usage'].get(name) for r in a];g[name+'_available_n']=sum(v is not None for v in vals);g[name+'_sum']=sum(vals) if all(v is not None for v in vals) else None
  g['estimated_usd']=None;g['waste_union_calls_sum']=sum(r['waste']['union_count'] for r in a);groups.append(g)
  for comp in ['vs_unprotected','vs_own_clean']:
   for metric in ['model_calls','business_tool_calls','verification_calls','e2e_latency_ms','input_tokens','output_tokens','total_tokens']:
    vals=[r['paired_differences'][comp][metric]['delta'] for r in a];known=[v for v in vals if v is not None]
    pairrows.append(dict(scenario=scenario,policy=policy,comparison=comp,metric=metric,planned_pairs=20,available_pairs=len(known),mean_delta=statistics.mean(known) if known else None,median_delta=statistics.median(known) if known else None,lower_n=sum(v<0 for v in known),equal_n=sum(v==0 for v in known),higher_n=sum(v>0 for v in known)))
csvout('scenario_policy_summary.csv',groups);dump('scenario_policy_summary.json',groups);csvout('paired_summary.csv',pairrows)
csvout('paired_slots.csv',[dict(slot_id=r['slot_id'],comparison=c,metric=k,delta=v['delta'],percent=v['percent']) for r in rows for c,m in r['paired_differences'].items() for k,v in m.items()])
archives=read(OUT/'existing_analysis/infrastructure_attempts.json');ar=[]
for r in archives:
 p=RUN/r['archive'];rr=read(p/'result.json');u=r['provider_usage'];receipt=read(p/'complete.json')
 ar.append(dict(slot_id=r['slot_id'],run_id=r['run_id'],archive=str(p),execution=r['execution'],receipt_hash_ok=receipt['result_sha256']==sha(p/'result.json'),sanity=sanity(rr,u),model_calls=rr['metrics']['model_calls'],provider_usage=rr['metrics']['provider_usage'],errors=[{k:x.get(k) for k in ['call_id','status','error_type','status_code','provider_error_code','provider_error_type','provider_error_message','retry_after']} for x in u if x['status']!='completed']))
dump('infrastructure_audit.json',ar)
# Complete draft export: immutable identity, explicit unreviewed criteria, query and contextual fields.
cases={c.case_id:c for c in load_cases(ROOT/'support_cases_unique40.jsonl')}
reviews=list(csv.DictReader((OUT/'existing_analysis/review_template.csv').open()));priority=[]
for r in reviews:
 c=cases[r['case_id']];r['base_case_id']=by_slot[r['slot_id']]['base_case_id'];r['repetition']=1;r['user_question']=c.user_query;r['expected_issues']=json.dumps(c.expected_issues);r['retained_discarded']='retained' if r['retained']=='True' else 'discarded';r['review_scope']='primary_experiment';r['human_verdict']='UNREVIEWED'
 for k in CRITERIA:r[k]='UNREVIEWED'
 assert hashlib.sha256(r['answer'].encode()).hexdigest()==r['answer_sha256']
 original=json.loads(r['original_record']);observed=json.loads(r['observed_record']);a=r['answer'];flags=[];quotes=[]
 patterns=[('Check refund timing/destination',r'(?i)(?:\b(?:business|working) days\b|\bfew days\b|processing time|\bto your (?:account|original|card|payment)|\b(?:within|in) \d+.{0,12}days)'),('Check new-ticket requirement/responsibility transfer',r'(?i)(?:new|separate|another).{0,25}(?:ticket|request)'),('Check premature closure or definite repair claims',r'(?i)(?:fixed on our|resolved on our|(?:issue|problem|case).{0,20}(?:resolved|closed)|everything.{0,15}(?:fixed|resolved))')]
 for label,pat in patterns:
  hits=re.findall(pat,a)
  if hits:flags.append(label);quotes.extend(hits)
 nums=re.findall(r'(?<![\w])\d+(?:\.\d+)?',a)
 unsupported=[n for n in nums if n not in json.dumps(original) and n not in c.user_query]
 if unsupported:flags.append('Check amounts/versions/numeric facts');quotes.append('answer numbers absent from original/query: '+','.join(unsupported))
 if original!=observed:flags.append('Check residual record contamination');quotes.append('original_record != observed_record; semantic alignment needs review')
 if by_slot[r['slot_id']]['policy_recovery'] and r['retained']=='True':flags.append('Retained answer requiring review for semantic recovery success');quotes.append('policy repair present; semantic success requires all retained issues reviewed')
 if r['issue'] not in c.expected_issues:flags.append('Check additional issue')
 retained_issues={x['issue'] for x in reviews if x['slot_id']==r['slot_id'] and x['retained']=='True'}
 if set(c.expected_issues)-retained_issues:flags.append('Missing expected issue')
 r['machine_screening_flags']='; '.join(flags);r['machine_screening_evidence']=' | '.join(quotes);r['machine_screening_note']='Screening for review order only, not a semantic verdict; no flag does not imply PASS'
 if flags:priority.append(dict(r,priority=1 if any('contamination' in f or 'refund' in f or 'facts' in f or 'ticket' in f for f in flags) else 2))
assert len(reviews)==len({r['event_id'] for r in reviews})==560
csvout('human_review_complete.csv',reviews);priority.sort(key=lambda x:(x['priority'],x['slot_id'],x['event_id']));csvout('human_review_priority.csv',priority)
# Archived drafts are separate operational evidence, never part of the 560 study drafts.
archive_reviews=[]
for item in ar:
 p=Path(item['archive']);rr=read(p/'result.json');aa=read(p/'answers.json')
 for retained,key in [(True,'retained'),(False,'discarded_intermediate')]:
  for e in aa[key]:archive_reviews.append({'slot_id':item['slot_id'],'run_id':rr['run_id'],'event_id':e['event_id'],'answer_sha256':hashlib.sha256(e['answer'].encode()).hexdigest(),'case_id':rr['case_id'],'scenario':rr['fault_type'],'policy':rr['mode'],'issue':e['issue'],'user_question':cases[rr['case_id']].user_query,'original_record':next((r['original_record'] for r in reviews if r['case_id']==rr['case_id'] and r['issue']==e['issue']), 'unavailable'),'observed_record':json.dumps(e['record']),'answer':e['answer'],'retained_within_interrupted_attempt':retained,'review_scope':'infrastructure_archive_excluded_from_240','trace':str(p/'trace.jsonl'),**{k:'UNREVIEWED' for k in CRITERIA},'reviewer':'','review_timestamp':'','rationale':''})
if archive_reviews:csvout('infrastructure_review_separate.csv',archive_reviews)
dump('review_inventory.json',{'primary_drafts':len(reviews),'retained':sum(r['retained']=='True' for r in reviews),'discarded':sum(r['retained']=='False' for r in reviews),'priority_rows':len(priority),'priority_retained':sum(r['retained']=='True' for r in priority),'priority_discarded':sum(r['retained']=='False' for r in priority),'archive_drafts_separate':len(archive_reviews),'existing_current_experiment_human_reviews':summary['human_review_files_in_current_results'],'historical_reviews':'Different run/event identities; retained unchanged, not transferred to these runs.'})
assert {k:v for k,v in tree_hashes(RUN).items() if not k.split('/')[0].startswith('analysis')}==before
dump('preservation.json',{'unchanged':True,'raw_file_count':len(before),'raw_sha256':before,'source_git_status':subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)})
print(json.dumps({'integrity_failures':summary['slot_integrity_failures'],'plan_results':[(p['plan'],p['passed']) for p in plans],'review_inventory':read(OUT/'review_inventory.json')},ensure_ascii=False,indent=2))
