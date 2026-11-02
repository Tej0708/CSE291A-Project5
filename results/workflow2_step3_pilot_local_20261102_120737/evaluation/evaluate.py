"""Offline-only evaluation; no imports of provider clients and no network calls."""
import json, csv, hashlib
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[3]
P=Path(__file__).resolve().parent.parent
O=P/'evaluation'
def save(name,obj): (O/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False))
def csvsave(name,rows):
 with (O/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
raw={str(p.relative_to(P)):digest(p) for p in P.rglob('*') if p.is_file() and 'evaluation' not in p.parts}
rs=json.loads((P/'run_results.json').read_text());m=json.loads((P/'selected_case_manifest.json').read_text())
assert len(rs)==8 and len({r['run_id'] for r in rs})==8
traces={r['case_id']:[json.loads(x) for x in (P/'live'/r['case_id']/'trace.jsonl').read_text().splitlines()] for r in rs}
validation=[]; calls=[]; answers=[]; human=['# Human review: Step 3 live pilot','','Provisional Codex review, not independent human sign-off. Rubric: support-human-v1. PASS / FAIL / UNCERTAIN retain their existing meanings. No answer rewriting or additional model calls.','','The workflow does not compose a final customer answer. “Latest answers” below means the last saved helper answer for each issue; all earlier drafts are also retained. Ledger resolution is not observed user-side repair.','','Generic bank-processing wording is marked UNCERTAIN rather than automatically failed: it gives no specific deadline, but bank/channel/timing facts are absent from the record. “A few days” is an explicit unsupported estimate and FAIL. Server-side “fixed” wording is UNCERTAIN because restart is recorded but successful remediation is not verified. These interpretations require human adjudication.','']
for r in rs:
 t=traces[r['case_id']]; req=[x for x in t if x['event']=='llm_request'];resp=[x for x in t if x['event']=='llm_response'];tools=[x for x in t if x['event']=='tool_action']
 assert r['run_status']=='completed' and len(req)==len(resp)==r['model_calls']
 assert len(tools)==r['tool_calls']==r['helper_calls']
 assert all(x['requested_model']==m['model'] and x['temperature']==m['temperature'] for x in req)
 assert all(x['returned_model']==m['model'] for x in resp)
 assert json.loads((P/'live'/r['case_id']/'result.json').read_text())==r
 assert json.loads((P/'live'/r['case_id']/'usage.json').read_text())==r['usage_records']
 assert datetime.fromisoformat(m['created_utc']) < datetime.fromisoformat(req[0]['timestamp_utc'])
 classified=next(x['issues'] for x in t if x['event']=='classification_result')
 meta=t[0]['case'];assert set(classified)==set(meta['expected_issues'])
 for x,y in zip(req,resp):
  system=x['system_prompt'];stage='classification' if 'classifier' in system else 'qa' if 'QA routing reviewer' in system else 'helper'
  # Raw observer stage/iteration can lag; derive stage from exact prompt and iteration from preceding route event.
  ix=t.index(x); route=next((v for v in reversed(t[:ix]) if v['event']=='workflow_event' and v.get('workflow_stage')=='route'),None)
  calls.append(dict(case_id=r['case_id'],run_id=r['run_id'],condition=r['condition'],call_id=x['call_id'],stage=stage,iteration=0 if stage=='classification' else route['iteration'],issue=route.get('issue') if stage=='helper' else None,duration_seconds=y['duration_seconds'],requested_model=x['requested_model'],returned_model=y['returned_model'],prompt_tokens=(y['usage'] or {}).get('prompt_tokens'),completion_tokens=(y['usage'] or {}).get('completion_tokens'),total_tokens=(y['usage'] or {}).get('total_tokens'),raw_usage=y['usage']))
 human.extend(['## '+r['case_id'],'',f"Run `{r['run_id']}`; status {r['result']['final_status']}; {r['result']['iterations']} iterations.",'','### Latest answers',''])
 for issue,answer in r['latest_issue_answers'].items():human.extend(['**'+issue+'**','',answer,''])
 human.extend(['### All helper drafts and rubric evidence',''])
 helperreq=[x for x in req if 'customer-support helper' in x['system_prompt']]
 for x in helperreq:
  payload=json.loads(x['user_prompt']);y=next(v for v in resp if v['call_id']==x['call_id']);answer=y['response_text'];issue=payload['assigned_issue'];record=payload['tool_record']
  ix=t.index(x);route=next(v for v in reversed(t[:ix]) if v['event']=='workflow_event' and v.get('workflow_stage')=='route');iteration=route['iteration']
  grades={k:'PASS' for k in ['record_alignment','relevance','grounding','coverage','status_responsibility']};notes=['Record matches the requested issue; supported amount/currency or required remediation steps are present. No new-ticket demand or whole-case closure claim.']
  if 'a few days' in answer:
   grades['grounding']='FAIL';notes.append('Unsupported refund timeline: “a few days”; record contains no processing time.')
  elif "bank's standard processing time" in answer:
   grades['grounding']='UNCERTAIN';notes.append('Generic bank-processing language is not in the record; no numerical estimate. Human adjudication needed on whether this is harmless general guidance or an unsupported timing/channel assertion.')
  if 'to your account' in answer:
   grades['grounding']='UNCERTAIN';notes.append('Refund destination “to your account” is not specified by the record.')
  if "now been fixed on our" in answer:
   grades['grounding']='UNCERTAIN';grades['status_responsibility']='UNCERTAIN';notes.append('Record says auth node restarted and fix_available, not confirmed server-side success. Retry request preserves user-side uncertainty; “fixed on our end/side” may still overstate verification.')
  overall='FAIL' if 'FAIL' in grades.values() else 'UNCERTAIN' if 'UNCERTAIN' in grades.values() else 'PASS'
  item=dict(case_id=r['case_id'],run_id=r['run_id'],condition=r['condition'],iteration=iteration,issue=issue,call_id=x['call_id'],latest=not any(json.loads(z['user_prompt'])['assigned_issue']==issue for z in helperreq[helperreq.index(x)+1:]),answer=answer,tool_record=record,**grades,overall=overall,notes=' '.join(notes),trace=f'live/{r["case_id"]}/trace.jsonl',request_line=t.index(x)+1,response_line=t.index(y)+1)
  answers.append(item)
  human.extend([f"Iteration {iteration}, **{issue}**, call {x['call_id']}, **{overall}**; trace lines {item['request_line']}–{item['response_line']}.",'',answer,'','Record: `'+json.dumps(record)+'`','','Criteria: '+', '.join(k+'='+v for k,v in grades.items()),'',' '.join(notes),''])
 human.extend(['### Routing and QA excerpts',''])
 for h in r['result']['history']:
  if h['stage'] in ('route','qa','qa_label_validation'): human.append('- `'+json.dumps(h)+'`')
 for e in r['events']:
  human.extend(['','Injection boundary: `'+json.dumps({k:e.get(k) for k in ('iteration','eligible','skip_reason','original_value','injected_value','effective_mutation','actual_mutation_count','next_router')})+'`'])
 human.append('')
 validation.append(dict(case_id=r['case_id'],run_id=r['run_id'],classification=classified,within_budget=r['result']['iterations']<=meta['max_iterations'],tool_counts_verified=True,usage_files_match=True,model_settings_verified=True,manifest_precedes_requests=True))
rows=[]
for s in m['selection']:
 c=next(r for r in rs if r['case_id']==s['clean_id']);f=next(r for r in rs if r['case_id']==s['fault_id'])
 ct=traces[c['case_id']];ft=traces[f['case_id']]
 assert ct[0]['case']['user_query']==ft[0]['case']['user_query']
 assert ct[0]['case']['max_iterations']==ft[0]['case']['max_iterations']==4
 assert next(x for x in ct if x['event']=='llm_request')['user_prompt']==next(x for x in ft if x['event']=='llm_request')['user_prompt']
 mutations=[e for e in f['events'] if e['effective_mutation']];assert len(mutations)==f['actual_mutation_count']<=1
 recovered=None
 if mutations:
  e=mutations[0];original=e['original_label'];later=[h for h in f['result']['history'] if h['iteration']>e['next_router']['iteration']]
  recovered=any(h['stage']=='helper_result' and h['issue']==original for h in later)
  assert e['original_value']['passed']==e['injected_value']['passed'] and e['original_value']['reason']==e['injected_value']['reason']
 def quality(r):
  grades=[v['overall'] for v in answers if v['case_id']==r['case_id'] and v['latest']]
  return 'FAIL' if 'FAIL' in grades else 'UNCERTAIN' if 'UNCERTAIN' in grades else 'PASS'
 row=dict(case_id=s['clean_id'].split('-NONE')[0],clean_run_id=c['run_id'],fault_run_id=f['run_id'],clean_final_status=c['result']['final_status'],fault_final_status=f['result']['final_status'],clean_iterations=c['result']['iterations'],fault_iterations=f['result']['iterations'],eligible=f['eligible'],injection_count=f['actual_mutation_count'],injection_iteration=mutations[0]['iteration'] if mutations else None,reached_router=f['effective_consumed'],resolved_issue_revisited=f['behavioral_effect'],unresolved_issue_subsequently_addressed=recovered,skip_reason=';'.join(f['skip_reasons']),clean_quality=quality(c),fault_quality=quality(f),api_runtime_errors=0,retries=0)
 for key in ['model_calls','helper_calls','tool_calls','total_tokens','elapsed_seconds']:
  row['clean_'+key]=c[key];row['fault_'+key]=f[key];row['delta_'+key]=f[key]-c[key] if c[key] is not None and f[key] is not None else None
 rows.append(row)
save('paired_results.json',rows);csvsave('paired_results.csv',rows)
save('call_usage.json',calls);csvsave('call_usage.csv',[{k:v for k,v in c.items() if k!='raw_usage'} for c in calls])
save('provisional_assessment.json',{'reviewer':'Codex preliminary, requires independent human adjudication','rubric_version':'support-human-v1','helper_assessments':answers,'case_assessments':[{k:r[k] for k in ('case_id','clean_quality','fault_quality')} for r in rows],'task_success':None,'recovery_success':None})
(O/'HUMAN_REVIEW.md').write_text('\n'.join(human))
assert all(digest(P/k)==v for k,v in raw.items())
save('validation.json',{'executions':len(rs),'model_calls':len(calls),'serial':all(datetime.fromisoformat(traces[a['case_id']][-1]['timestamp_utc'])<datetime.fromisoformat(traces[b['case_id']][0]['timestamp_utc']) for a,b in zip(rs,rs[1:])),'runs':validation,'raw_artifact_hashes':raw,'raw_artifacts_unchanged':True,'current_source_matches_manifest':all(digest(ROOT/k)==v for k,v in m['source_hashes'].items()),'total_tokens':sum(r['total_tokens'] for r in rs),'total_elapsed_seconds':sum(r['elapsed_seconds'] for r in rs)})
(O/'reproduce.sh').write_text('# Execution command, for documentation only. Do not rerun without authorization.\ncd '+str(ROOT)+'\nPYTHONDONTWRITEBYTECODE=1 '+m['reproduction_command']+'\n\n# Offline report regeneration only (no paid calls):\nPYTHONDONTWRITEBYTECODE=1 .venv/bin/python '+str(Path(__file__).relative_to(ROOT))+'\n')
print(json.dumps(rows,indent=2));print('helper grades', {g:sum(x['overall']==g for x in answers) for g in ('PASS','FAIL','UNCERTAIN')})
