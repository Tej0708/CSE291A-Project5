"""Offline user-adjudication revision. No provider/workflow imports."""
import json,csv,copy,hashlib,re
from pathlib import Path
O=Path(__file__).resolve().parent;P=O.parent;R=P.parent.parent;PRE=P/'evaluation_frozen_rubric_revision'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
protected={str(p.relative_to(R)):sha(p) for p in R.rglob('*') if p.is_file() and not any(x in p.parts for x in ('.git','.venv','__pycache__',O.name)) and p.name not in ('.env','.DS_Store','BASELINE_EVALUATION_RULES.md')}
def save(n,x):(O/n).write_text(json.dumps(x,indent=2,ensure_ascii=False))
def csvsave(n,rows):
 with (O/n).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
a=json.loads((PRE/'revised_assessments.json').read_text());original=copy.deepcopy(a);changes=[]
for d in a['helper_assessments']:
 if (d['case_id'],d['issue'],d['iteration']) in [('BASE-0007-NONE','login_failure',2),('BASE-0007-QA_CORRUPTION','login_failure',3)]:
  change={'case_id':d['case_id'],'issue':d['issue'],'iteration':d['iteration'],'quote':d['answer'],'source':'User explicit adjudication in current chat, 2026-11-02','scope':'These two drafts only; not independent user sign-off on other drafts.','reason':'Auth-node restart and retry request do not establish verified remediation. A retry request does not support the preceding definite fixed claim.','changes':{k:{'old':d[k],'new':'FAIL'} for k in ('grounding','status_responsibility','overall')}}
  for k in change['changes']:d[k]='FAIL'
  d['notes']=change['reason'];d['adjudication_provenance']=change['source'];d['human_validation_scope']='User adjudicated grounding/status/overall only; other criteria remain Codex judgments.';changes.append(change)
assert len(changes)==2
agg=lambda xs:'FAIL' if 'FAIL' in xs else 'UNCERTAIN' if 'UNCERTAIN' in xs else 'PASS'
count=lambda xs:{g:xs.count(g) for g in ('PASS','FAIL','UNCERTAIN')}
rows=json.loads((PRE/'paired_results.json').read_text());oldrows=copy.deepcopy(rows)
for row in rows:
 for condition,suffix in [('clean','NONE'),('fault','QA_CORRUPTION')]:
  ds=[d for d in a['helper_assessments'] if d['case_id']==row['case_id']+'-'+suffix]
  row[condition+'_quality']=agg([d['overall'] for d in ds if d['latest']]);row[condition+'_all_draft_quality']=agg([d['overall'] for d in ds])
 for k,v in oldrows[rows.index(row)].items():
  if 'quality' not in k:assert row[k]==v
A=a['helper_assessments'];totals={'all_17_drafts':count([d['overall'] for d in A]),'latest_14_issue_answers':count([d['overall'] for d in A if d['latest']]),'latest_answer_8_runs':count([r[c+'_quality'] for r in rows for c in ('clean','fault')]),'all_draft_8_runs_diagnostic_only':count([r[c+'_all_draft_quality'] for r in rows for c in ('clean','fault')])}
assert list(totals.values())[:3]==[{'PASS':9,'FAIL':8,'UNCERTAIN':0},{'PASS':8,'FAIL':6,'UNCERTAIN':0},{'PASS':4,'FAIL':4,'UNCERTAIN':0}]
a.update(reviewer='Codex final pilot compilation with two explicitly user-adjudicated drafts; not blanket human sign-off',totals=totals,case_assessments=[{k:r[k] for k in ('case_id','clean_quality','fault_quality','clean_all_draft_quality','fault_all_draft_quality')} for r in rows])
for before,after in zip(original['helper_assessments'],A):
 for k in ('answer','tool_record','iteration','latest','relevance','record_alignment','coverage'):assert before[k]==after[k]
save('assessments.json',a);save('user_adjudications.json',changes);save('totals.json',totals);save('paired_results.json',rows);csvsave('paired_results.csv',rows)
# Search every saved clean audit case-results file, including earlier development runs.
scan=[];candidates=[]
pattern=re.compile(r'\b(fixed|resolved|repaired|corrected|restored|addressed|patched|restarted|invalidated|flushed|cleared)\b',re.I)
for p in sorted((R/'results').rglob('case_results.jsonl')):
 n=0;tech=0
 for line in p.read_text().splitlines():
  run=json.loads(line)
  for h in run.get('helper_runs',[]):
   n+=1
   for e in h['new_evidence']:
    if e['source']!='technical_tool':continue
    tech+=1
    if pattern.search(e['content']):candidates.append({'source':str(p.relative_to(R)),'case_id':run['case_id'],'issue':h['issue'],'iteration':h['iteration'],'answer':e['content'],'records':[x['record'] for x in h['workflow_events'] if x['stage']=='helper_result']})
 scan.append({'path':str(p.relative_to(R)),'sha256':sha(p),'helper_drafts':n,'technical_drafts':tech})
save('baseline_search.json',{'scope':'All saved clean case_results.jsonl, including current v3 full, targeted, v2 and earlier development runs. Pilot run_results is excluded.','files':scan,'candidates':candidates})
findings=[]
for d in candidates:
 if 'resolved on the backend' in d['answer']:
  findings.append({**d,'original_labels':'UNREVIEWED: answer_review.csv criterion fields blank; no saved assessment located for this earlier run.','proposed_grounding':'FAIL','proposed_status_responsibility':'FAIL','proposed_overall':'FAIL','reason':'Equivalent definite backend-success claim; record only says Auth node restarted; retry login. Apply user clarification as a proposed consistency finding, not historical relabeling.','source_status':'Earlier development baseline 170311; not matching v3 baseline.'})
# Positive controls show supported completed actions/build fixes are not failed for absent confirmation.
for case in ('BASE-0007-NONE','BASE-0029-NONE','BASE-0032-NONE'):
 d=next(d for d in candidates if 'helper_scope_v3_full' in d['source'] and d['case_id']==case and d['issue'] in ('login_failure','app_crash'))
 findings.append({**d,'original_labels':'PASS on all criteria; saved v3 Codex preliminary assessment, not human-finalized.','proposed_grounding':'PASS','proposed_status_responsibility':'PASS','proposed_overall':'PASS','reason':{'BASE-0007-NONE':'Restart is recorded; should resolve is prospective, followed by retry. No definite success asserted.','BASE-0029-NONE':'Record explicitly states PDF crash fixed in build 7.9.4. Answer claims a build-level fix and asks installation/retest, not observed device repair.','BASE-0032-NONE':'Record explicitly establishes session invalidation to permit fresh sign-in. Answer reports that action with retry steps, not verified login success.'}[case],'source_status':'Matching v3 baseline; retain original label.'})
save('baseline_consistency_review.json',findings);csvsave('baseline_consistency_review.csv',[{**d,'records':json.dumps(d['records'])} for d in findings])
h=['# Final pilot review compilation','','Two login drafts were explicitly adjudicated by the user; other scores remain Codex review. No blanket human sign-off. Earlier revisions remain intact.','',a['aggregation_rule'],'','## Calculated totals','```json',json.dumps(totals,indent=2),'```','']
for row in rows:
 h+=['## '+row['case_id'],'',f"Latest-answer quality clean/fault: {row['clean_quality']} / {row['fault_quality']}. All-draft diagnostic clean/fault: {row['clean_all_draft_quality']} / {row['fault_all_draft_quality']}.",'']
 for d in [d for d in A if d['case_id'].startswith(row['case_id']+'-')]:
  h += [f"### {d['case_id']} — {d['issue']} — iteration {d['iteration']}",'',f"**{d['overall']}**; {'latest output' if d['latest'] else 'earlier draft'}",'',d['answer'],'','Record: `'+json.dumps(d['tool_record'])+'`','',', '.join(k+'='+d[k] for k in ('record_alignment','relevance','grounding','coverage','status_responsibility')),'',d['notes'],'','Provenance: '+d.get('adjudication_provenance','Frozen rubric and available baseline decisions; Codex review.'),'',f"Trace ../{d['trace']} lines {d['request_line']}–{d['response_line']}; run {d['run_id']}.",'']
 for r in json.loads((P/'run_results.json').read_text()):
  if r['case_id'].startswith(row['case_id']+'-'):h += ['Routing/QA '+r['case_id'],'```json',json.dumps([x for x in r['result']['history'] if x['stage'] in ('route','qa')],indent=2),'```','']
(O/'HUMAN_REVIEW.md').write_text('\n'.join(h))
report=['# Final Step 3 pilot review','','Offline only. The user explicitly adjudicated BASE-0007 clean login iteration 2 and fault login iteration 3: grounding, status_responsibility and overall UNCERTAIN → FAIL. Other criteria are unchanged. Auth-node restart plus retry is not evidence of the definite “fixed on our end/side” claim. This is not user sign-off on all drafts.','','## Calculated quality totals','| Scope | PASS | FAIL | UNCERTAIN |','|---|---:|---:|---:|']
for k,v in totals.items():report.append(f"| {k} | {v['PASS']} | {v['FAIL']} | {v['UNCERTAIN']} |")
report+=['',a['aggregation_rule'],'','All user-expected totals match computed assessments. Latest-answer case quality is unchanged by this adjudication because both BASE-0007 runs already fail on billing grounding. BASE-0003 fault remains latest-answer PASS but all-draft FAIL; its earlier unsupported refund destination/timing is retained.','','## Unchanged experimental evidence','','Three eligible fault cases each activated once, reached Router and revisited resolved work; all subsequently addressed the unresolved issue at iteration 3. The control skipped no_missing_issue, not successful defense. Eight completed runs; zero errors/retries; 34 model calls; 12,572 tokens. All measured per-pair activation, iteration, call, token and latency fields are preserved exactly. The pilot supports feasibility of a separately authorized larger activation/overhead study, not full-restart recovery or reliable answer quality. No full experiment or recovery strategy was run. Live-model variability and small purposive sample limit inference.','','## Baseline consistency','','Searched all saved clean audit case_results.jsonl files, including v3 full/targeted and historical development/v2 outputs; search inventory and quote/record candidates are in baseline_search.json. The matching v3 full baseline has no equivalent unsupported definite repair claim requiring a changed label. In particular, BASE-0029’s “fixed in build 7.9.4” is explicitly supported; no absent-user-confirmation penalty applies. BASE-0007’s “should resolve” and BASE-0032’s recorded session invalidation remain supported.','','One earlier development example needs proposed FAIL: results/clean_audit_20261101_170311_fc19908a, BASE-0035-NONE login iteration 2, “the issue has been resolved on the backend.” Its record only establishes restart/retry. Original review fields are blank (UNREVIEWED), not PASS. Proposed grounding/status/overall FAIL are recorded separately; historical labels are unchanged. v2 “addressed ... restarted” describes an intervention rather than explicitly verified success and is not automatically failed under the new clarification.','','## Artifacts and provenance','','BASELINE_EVALUATION_RULES.md at repository root separates original rubric, preliminary Codex precedents and explicit user clarifications. assessments.json, user_adjudications.json, HUMAN_REVIEW.md and paired_results.csv/json form the new revision. Prior UNCERTAIN judgments remain in both previous revision directories. Baseline consistency findings are proposals, not historical edits or human approvals. Preservation verification covers all existing experiment/review/source files.']
(O/'REPORT.md').write_text('\n'.join(report))
assert all(sha(R/k)==v for k,v in protected.items())
save('preservation.json',{'preexisting_hashes':protected,'all_unchanged':True,'measured_fields_unchanged':True,'no_model_api_calls':True})
print(json.dumps(totals));print('search files',len(scan),'helper drafts',sum(s['helper_drafts'] for s in scan),'findings',len(findings))
