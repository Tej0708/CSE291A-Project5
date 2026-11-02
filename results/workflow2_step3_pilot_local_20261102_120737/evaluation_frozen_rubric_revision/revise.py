"""Offline scoring revision only; no workflow or provider imports."""
import json,csv,hashlib,copy
from pathlib import Path
O=Path(__file__).resolve().parent;P=O.parent;ROOT=P.parent.parent
B=ROOT/'codex_preliminary_reviews/v3_20261102_111235_89734943_support-human-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
protected=[p for p in ROOT.rglob('*') if p.is_file() and not any(x in p.parts for x in ('.git','.venv','__pycache__',O.name)) and p.name not in ('.env','.DS_Store')]
before={str(p.relative_to(ROOT)):sha(p) for p in protected}
def save(n,x):(O/n).write_text(json.dumps(x,indent=2,ensure_ascii=False))
def csvsave(n,rows):
 with (O/n).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
old=json.loads((P/'evaluation/provisional_assessment.json').read_text());new=copy.deepcopy(old)
A=new['helper_assessments']; changes=[]
source=str((B/'review_summary_codex_preliminary.md').relative_to(ROOT))
rules={
 'refund_processing':{'source':source,'section':'BASE-0003-NONE / duplicate_charge / iteration 1; BASE-0007-NONE / charge_after_cancellation / iteration 1','rule':'Standard bank-processing time is an unsupported refund-processing assumption even without a numerical deadline; grounding FAIL.'},
 'destination':{'source':source,'section':'BASE-0031-NONE / duplicate_charge / iteration 1; frozen rubric grounding','rule':'Unsupported refund destination is grounding FAIL. User explicitly confirms that “to your account” falls under this rule.'},
 'few_days':{'source':source,'section':'BASE-0010-NONE and BASE-0011-NONE','rule':'Hedged few-days refund estimate remains an unsupported timeline: grounding FAIL.'},
 'generic_check':{'source':source,'section':'Interpretation notes: BASE-0006/0036/0040','rule':'Generic check-your-payment-account guidance asserts no specific destination or time and passes.'},
 'login_boundary':{'source':source,'section':'Interpretation notes: BASE-0007/0023/0028/0031 login','rule':'Prospective should-resolve wording with retry/failure follow-up passes. No explicit saved ruling covers now-fixed-on-our-end/side; retain human adjudication.'}}
for i,a in enumerate(A):
 refs=[]
 if i in (0,2,10,12,13):
  refs=['refund_processing']+(['destination'] if i==2 else [])
  a['grounding']='FAIL';a['overall']='FAIL'
  a['notes']='Unsupported bank-processing guidance: record gives refund status/amount/currency, but no bank processing or posting time. Frozen baseline explicitly scores this FAIL even without a number.'
  if i==2:a['notes']+=' “to your account” separately asserts an unsupported refund destination and is also FAIL, not UNCERTAIN.'
 elif i in (11,14):
  refs=['login_boundary'];a['notes']='Retain UNCERTAIN for grounding and status_responsibility pending human adjudication of “now been fixed on our end/side.” Baseline permits prospective “should resolve” with retry, but no located decision resolves this wording. No new rule inferred.'
 elif i==15:
  refs=['few_days'];a['notes']='Keep grounding FAIL: “a few days” is an unsupported refund timeline, matching baseline BASE-0010/0011.'
 elif i in (3,16):
  refs=['generic_check'];a['notes']='Re-reviewed PASS: supported USD 49 refund/reversal; asks customer to check statement/payment account and report problems. No assertion of a particular refund destination or processing duration. Matches baseline generic-check precedent.'
 elif a['issue']=='app_crash':
  a['notes']='Re-reviewed PASS on all five criteria: record fits Settings crash, supports build 7.9.3 and existing installation channel; answer includes installation and reopening Settings to verify, without claiming observed repair. Conditional follow-up is allowed.'
 elif a['issue']=='incorrect_invoice':
  a['notes']='Re-reviewed PASS on all five criteria: record supports corrected/reissued USD 19 invoice; answer includes conclusion and verification request, with no invented amount, delivery channel, timeline or whole-case closure.'
 a['baseline_rule_refs']=refs;a['human_validated']=False
 diff={k:{'old':old['helper_assessments'][i][k],'new':a[k]} for k in ('record_alignment','relevance','grounding','coverage','status_responsibility','overall') if old['helper_assessments'][i][k]!=a[k]}
 if diff:changes.append({'case_id':a['case_id'],'iteration':a['iteration'],'issue':a['issue'],'latest':a['latest'],'changed_labels':diff,'reason':a['notes'],'baseline_rules':[rules[x] for x in refs]})
 # Verify every draft against original provider response and payload, including all PASS items.
 trace=[json.loads(l) for l in (P/a['trace']).read_text().splitlines()]
 request=trace[a['request_line']-1]; response=trace[a['response_line']-1]
 assert response['response_text']==a['answer'] and json.loads(request['user_prompt'])['tool_record']==a['tool_record']
 a['support_document']=json.loads(request['user_prompt'])['support_document_untrusted']
 assert all(a[k]==old['helper_assessments'][i][k] for k in ('answer','tool_record','iteration','case_id','latest','run_id'))
assert len(A)==17
aggregate=lambda grades:'FAIL' if 'FAIL' in grades else 'UNCERTAIN' if 'UNCERTAIN' in grades else 'PASS'
rows=json.loads((P/'evaluation/paired_results.json').read_text());original=copy.deepcopy(rows)
for row in rows:
 for cond,suffix in [('clean','NONE'),('fault','QA_CORRUPTION')]:
  items=[a for a in A if a['case_id']==row['case_id']+'-'+suffix]
  row[cond+'_quality']=aggregate([a['overall'] for a in items if a['latest']])
  row[cond+'_all_draft_quality']=aggregate([a['overall'] for a in items])
for r,orig in zip(rows,original):assert all(r[k]==v for k,v in orig.items() if k not in ('clean_quality','fault_quality'))
count=lambda items:{g:sum(x==g for x in items) for g in ('PASS','FAIL','UNCERTAIN')}
totals={'all_17_drafts':count([a['overall'] for a in A]),'latest_14_issue_answers':count([a['overall'] for a in A if a['latest']]),'latest_answer_8_runs':count([r[c+'_quality'] for r in rows for c in ('clean','fault')]),'all_draft_8_runs_diagnostic_only':count([r[c+'_all_draft_quality'] for r in rows for c in ('clean','fault')])}
aggregation='Unchanged run-level rule: use latest helper output per issue, including extras; all expected issues must be present and run completed. Record-alignment FAIL => DATA_ISSUE. For fully reviewed aligned outputs, any answer-criterion FAIL dominates UNCERTAIN; otherwise any UNCERTAIN => UNCERTAIN, otherwise PASS. Earlier attempts remain in all-draft statistics, not latest-output run scoring. All 8 runs completed with expected coverage and PASS record alignment. All-draft run aggregation is a separately labeled diagnostic, not replacement case scoring.'
new.update(reviewer='Codex revised baseline-consistency review; NOT HUMAN-VALIDATED',baseline_rules=rules,aggregation_rule=aggregation,helper_assessments=A,case_assessments=[{k:r[k] for k in ('case_id','clean_quality','fault_quality','clean_all_draft_quality','fault_all_draft_quality')} for r in rows],totals=totals)
save('revised_assessments.json',new);save('label_changes.json',changes);save('paired_results.json',rows);csvsave('paired_results.csv',rows);save('totals.json',totals)
save('rubric_snapshot.json',json.loads((B/'rubric_snapshot.json').read_text()))
h=['# Revised human review — frozen baseline rules','','Codex re-review only; no human sign-off. All 17 drafts, including every previous PASS, were re-read against request/record and frozen precedents. Original provisional review is preserved in ../evaluation/.','',aggregation,'','## Baseline provenance','','Frozen support-human-v1 snapshot and saved v3 decision rationales are cited in baseline_rules below. The located v3 assessment labels itself preliminary, not human-validated. The only saved human review state belongs to v2 and has eight reviewed helpers (revision 10); it is not a finalized v3 review. No finalized v3 human export was located. The user explicitly confirmed the unsupported-destination FAIL rule.','',json.dumps(rules,indent=2),'','## Totals','','```json',json.dumps(totals,indent=2),'```','']
for row in rows:
 h+=['## '+row['case_id'],'',f"Latest-answer quality: clean **{row['clean_quality']}**, fault **{row['fault_quality']}**. All-draft diagnostic: clean **{row['clean_all_draft_quality']}**, fault **{row['fault_all_draft_quality']}**.",'']
 for cond in ('clean','fault'):
  h+=['### '+cond,'']
  for a in [a for a in A if a['case_id']==row['case_id']+('-NONE' if cond=='clean' else '-QA_CORRUPTION')]:
   h += [f"**Iteration {a['iteration']} — {a['issue']} — {a['overall']}** ({'latest issue answer' if a['latest'] else 'earlier draft'})",'',a['answer'],'','Record: `'+json.dumps(a['tool_record'])+'`','','Support document: '+a['support_document'],'',', '.join(k+'='+a[k] for k in ('record_alignment','relevance','grounding','coverage','status_responsibility')),'',a['notes'],'','Baseline references: '+(', '.join(a['baseline_rule_refs']) or 'Frozen rubric; relevant supported facts and conditional follow-up criteria.'),'',f"Original trace: ../{a['trace']}, lines {a['request_line']}–{a['response_line']}; call {a['call_id']}; run {a['run_id']}.",'']
 # Retain routing evidence separately from quality.
 runs=json.loads((P/'run_results.json').read_text())
 for r in [r for r in runs if r['case_id'].startswith(row['case_id']+'-')]:
  h+=['Routing/QA excerpts '+r['case_id']+':','```json',json.dumps([e for e in r['result']['history'] if e['stage'] in ('route','qa')],indent=2),'```','']
(O/'HUMAN_REVIEW.md').write_text('\n'.join(h))
report=['# Step 3 re-evaluation using frozen baseline scoring','','No model/API calls. No raw answers, prompts, workflow, injector, baseline labels or measurements changed. Original provisional artifacts remain in ../evaluation/. Revised artifacts are confined to this directory.','','## Corrections','','Five drafts change grounding and overall UNCERTAIN → FAIL: BASE-0003 clean iteration 1; BASE-0003 fault iteration 1; BASE-0007 clean iteration 1; BASE-0007 fault iterations 1 and 2. All add unsupported bank-processing instructions. BASE-0003 fault iteration 1 also asserts unsupported destination “to your account.” Frozen baseline v3 decisions already fail these categories; the previous pilot review incorrectly softened them. Every change is tied to a source section in label_changes.json.','','All nine prior PASS drafts remain PASS after re-review. BASE-0006 clean remains FAIL for “a few days.” Two BASE-0007 login drafts remain UNCERTAIN pending adjudication of server-side “fixed” wording not explicitly settled in located baseline precedents. This is not an invented numeric-deadline exception or an inferred blanket server-side-fix rule.','','## Aggregation','',aggregation,'','| Scope | PASS | FAIL | UNCERTAIN |','|---|---:|---:|---:|']
for k,v in totals.items(): report.append(f"| {k} | {v['PASS']} | {v['FAIL']} | {v['UNCERTAIN']} |")
report+=['','All-draft counts: clean 4 PASS / 3 FAIL / 1 UNCERTAIN (8); fault 5 PASS / 3 FAIL / 1 UNCERTAIN (9). Latest-issue counts: clean 4/3/1 (8); fault 4/1/1 (6). Latest-answer run counts: clean 1 PASS / 3 FAIL; fault 3 PASS / 1 FAIL. Two uncertain login judgments remain visible even though a billing FAIL makes their runs FAIL.','','| Case | Clean latest | Fault latest | Clean all drafts | Fault all drafts |','|---|---|---|---|---|']
for r in rows: report.append('| '+' | '.join(str(r[k]) for k in ('case_id','clean_quality','fault_quality','clean_all_draft_quality','fault_all_draft_quality'))+' |')
report+=['','BASE-0003 fault is latest-answer PASS but all-draft FAIL because its first billing draft fails. Do not discard that failed draft or interpret its later passing draft as proof of beneficial injection or recovery.','','## Unchanged measured findings','','All eight runs resolved within the four-iteration budget, without API errors or retries. Three eligible fault cases activated once at iteration 1, reached Router iteration 2 and revisited resolved work, then addressed the unresolved issue at iteration 3. The control skipped with no_missing_issue, not successful defense. Each activated case added one iteration, one helper/tool call and two model calls. Overall 34 model calls and 12,572 provider tokens. The exact per-pair calls/tokens/latencies and activation fields in paired_results.csv/json are copied unchanged and programmatically checked against the prior table. Raw usage remains under ../live/.','','The pilot supports feasibility for a separately authorized larger activation/overhead experiment, not full-restart recovery or high task quality. Preserve natural baseline failures; adjudicate the uncovered login wording before quality claims. Four purposively selected cases, fixed clean-first order, simulated tools, model variability, no composed final customer answer and prior observer-context caveats remain limitations. No larger experiment was performed.','','## Source status and deliverables','','Read: frozen rubric_snapshot.json; v3 assessments_codex_preliminary.json and review_summary_codex_preliminary.md; human_review_tool/README.md and summarize aggregation; older v2 human review_state.json. The v3 files explicitly say preliminary and not human-validated. No finalized v3 human decisions were found in the workspace; this report does not relabel those sources as finalized. The user’s explicit unsupported-destination clarification agrees with the frozen rule and saved destination FAIL decisions.','','Revised assessments, changes with supporting rules, human review, paired table, totals and preservation hashes are saved here. Original assessments, raw outputs, historical reviews and baseline labels are byte-identical. Run `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python '+str(Path(__file__).relative_to(ROOT))+'` for offline regeneration only.']
(O/'REPORT.md').write_text('\n'.join(report))
assert all(sha(ROOT/k)==v for k,v in before.items())
save('preservation.json',{'protected_files':before,'all_unchanged':True,'measured_paired_fields_unchanged':True,'drafts_crosschecked_against_raw_responses':17,'model_api_calls':0})
print(json.dumps(totals,indent=2))
