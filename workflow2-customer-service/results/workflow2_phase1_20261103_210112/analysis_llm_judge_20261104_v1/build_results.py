"""Offline final report; no API calls, no changes to experiment or human judgments."""
from pathlib import Path
import csv,json,hashlib,statistics,re
from collections import Counter,defaultdict
P=Path(__file__).resolve().parent
AUDIT=P.parent/'analysis_offline_20261104_3d072433_en'
def read(p):return json.loads(p.read_text())
def csvread(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def writecsv(p,rows,fields=None):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)
def dump(x):return json.dumps(x,ensure_ascii=False,sort_keys=True)
def mean(xs):return statistics.mean(xs) if xs else 'unavailable'
rows=csvread(P/'review_sheet.csv');jobs={j['job_id']:j for j in map(json.loads,(P/'jobs.jsonl').read_text().splitlines())};quality=csvread(P/'run_quality.csv');measurements={r['run_id']:r for r in read(AUDIT/'existing_analysis/measurements.json')};summary=read(P/'summary.json')
enriched=[];priority=[]
for r in rows:
 c=jobs[r['job_id']]['context'];r=dict(r,user_question=c['user_request'],original_records=dump(c['original_authoritative_records']),observed_records=dump(c['observed_records']),answers=dump(c['answers']),support_document=dump([a.get('support_documents_untrusted') for a in c['answers']]),workflow_context=dump(c.get('workflow_context')),context_path='jobs.jsonl#'+r['job_id'],disposition='retained' if r['retained']=='True' else 'discarded')
 enriched.append(r)
 text=' '.join(str(a) for a in c['answers']).lower();categories=[]
 if re.search(r'\b(days?|weeks?|business days?|original payment|credit card|bank account)\b',text):categories.append('Refund timing/destination: check whether asserted or only generic confirmation')
 if r['llm_grounding']=='FAIL':categories.append('Unsupported amount/fact or residual fault pollution')
 if r['llm_coverage']=='FAIL':categories.append('Missing necessary issue conclusion or next step')
 if re.search(r'(new|another|separate) (support )?ticket',text):categories.append('New-ticket request for an included issue')
 if re.search(r'(case|ticket).{0,25}(closed|resolved)|everything.{0,20}(fixed|resolved)',text):categories.append('Possible premature whole-case closure')
 if r['llm_status_responsibility'] in ['FAIL','UNCERTAIN']:categories.append('Status/responsibility boundary')
 if r['evaluation_status']!='EVALUATED':categories.append('No validated LLM assessment; review directly')
 if r['llm_overall'] in ['FAIL','UNCERTAIN','DATA_ISSUE'] or r['human_followup_needed']=='True':categories.append('May affect delivered quality/recovery conclusion' if r['retained']=='True' else 'Discarded diagnostic answer')
 if categories:priority.append(dict(r,priority_reasons='; '.join(categories),priority_basis='LLM labels and text triage only; not human findings'))
writecsv(P/'complete_review_with_context.csv',enriched)
writecsv(P/'priority_review_with_context.csv',priority,list(enriched[0])+['priority_reasons','priority_basis'])
qmap={q['run_id']:q for q in quality};joined=[]
for rid,m in measurements.items():
 q=qmap[rid];v=q['llm_assessed_run_quality'];activated=m['activation']=='ACTIVATED';recovery=bool(m['policy_recovery']);met=m['metrics']
 joined.append(dict(slot_id=m['slot_id'],run_id=rid,case=m['base_case_id'],scenario=q['scenario'],policy=q['policy'],execution=m['execution'],activation=m['activation'],policy_recovery_triggered=recovery,continuation=m['continuation'],llm_run_quality=v,human_quality='UNREVIEWED',llm_success_after_activation=(v=='PASS') if activated and v!='UNREVIEWED' else 'unavailable',llm_policy_recovery_success=(v=='PASS') if activated and recovery and v!='UNREVIEWED' else 'not applicable' if not recovery else 'unavailable',**{k:met[k] for k in ['model_calls','business_tool_calls','verification_calls','e2e_latency_ms','repair_latency_ms','discarded_calls']},input_tokens=met['provider_usage']['input_tokens'],output_tokens=met['provider_usage']['output_tokens'],total_tokens=met['provider_usage']['total_tokens']))
writecsv(P/'run_results_joined.csv',joined)
groups=defaultdict(list)
for r in joined:groups[r['scenario'],r['policy']].append(r)
agg=[]
for (s,p),g in sorted(groups.items()):
 n=len(g);cnt=Counter(r['llm_run_quality'] for r in g);act=[r for r in g if r['activation']=='ACTIVATED'];rec=[r for r in act if r['policy_recovery_triggered']]
 agg.append(dict(scenario=s,policy=p,expected_n=n,completed_n=sum(r['execution']=='completed' for r in g),assessed_n=n-cnt['UNREVIEWED'],llm_PASS=cnt['PASS'],llm_FAIL=cnt['FAIL'],llm_UNCERTAIN=cnt['UNCERTAIN'],llm_DATA_ISSUE=cnt['DATA_ISSUE'],unassessed_n=cnt['UNREVIEWED'],activated_n=len(act),pass_after_activation_n=sum(r['llm_run_quality']=='PASS' for r in act),policy_recovery_n=len(rec),pass_after_policy_recovery_n=sum(r['llm_run_quality']=='PASS' for r in rec),human_reviewed_n=0,**{k+'_mean':mean([r[k] for r in g if isinstance(r[k],(int,float))]) for k in ['model_calls','business_tool_calls','verification_calls','e2e_latency_ms','discarded_calls']},recovery_latency_ms_mean_triggered=mean([r['repair_latency_ms'] for r in rec]),**{k+'_sum':sum(r[k] for r in g) if all(isinstance(r[k],(int,float)) for r in g) else 'unavailable' for k in ['input_tokens','output_tokens','total_tokens']}))
writecsv(P/'scenario_policy_results.csv',agg)
lookup={(r['case'],r['scenario'],r['policy']):r for r in joined};pairs=[]
for r in joined:
 targets=[('own_clean',lookup[(r['case'],'NONE',r['policy'])])] if r['scenario']!='NONE' else []
 if r['policy']=='always_verify':targets.append(('same_case_full_restart',lookup[(r['case'],r['scenario'],'full_restart')]))
 if r['policy']!='unprotected':targets.append(('same_case_unprotected',lookup[(r['case'],r['scenario'],'unprotected')]))
 for kind,b in targets:
  assessed=r['llm_run_quality']!='UNREVIEWED' and b['llm_run_quality']!='UNREVIEWED'
  pairs.append(dict(case=r['case'],scenario=r['scenario'],policy=r['policy'],comparison=kind,slot_id=r['slot_id'],control_slot_id=b['slot_id'],llm_quality=r['llm_run_quality'],control_llm_quality=b['llm_run_quality'],both_assessed=assessed,pass_indicator_delta=(int(r['llm_run_quality']=='PASS')-int(b['llm_run_quality']=='PASS')) if assessed else 'unavailable',latency_delta_ms=r['e2e_latency_ms']-b['e2e_latency_ms'],model_calls_delta=r['model_calls']-b['model_calls'],business_tool_calls_delta=r['business_tool_calls']-b['business_tool_calls']))
writecsv(P/'paired_results.csv',pairs)
pg=defaultdict(list)
for r in pairs:pg[r['scenario'],r['policy'],r['comparison']].append(r)
ps=[]
for (s,p,c),g in sorted(pg.items()):
 valid=[r for r in g if r['both_assessed']];ps.append(dict(scenario=s,policy=p,comparison=c,pairs_n=len(g),assessed_pairs_n=len(valid),pass_gain_n=sum(r['pass_indicator_delta']==1 for r in valid),pass_loss_n=sum(r['pass_indicator_delta']==-1 for r in valid),unchanged_pass_indicator_n=sum(r['pass_indicator_delta']==0 for r in valid),mean_latency_delta_ms=mean([r['latency_delta_ms'] for r in g]),median_latency_delta_ms=statistics.median(r['latency_delta_ms'] for r in g),mean_model_calls_delta=mean([r['model_calls_delta'] for r in g])))
writecsv(P/'paired_results_summary.csv',ps)
text='# Workflow 2: GLM-assisted result analysis\n\n'
text+=f"Assessment coverage: {summary['valid_unique_judgments']}/{summary['unique_jobs']} unique contexts. Accounted cost including all pilot versions and retries: ${summary['accounted_usd']}; {summary['attempted_paid_calls']} paid requests. These are LLM assessments, not human approval.\n\n"
text+='The experiment remains 240 completed unique slots, with 180/180 fault scenarios activated. Five archived infrastructure attempts are separate. Original experiment statistics and the [Phase 1 requirements matrix](../analysis_offline_20261104_3d072433_en/PHASE1_REQUIREMENTS.md) remain authoritative for deterministic measures. No experiment was rerun.\n\n'
text+='| Scenario | Policy | Assessed / planned | LLM PASS / planned | FAIL | UNCERTAIN | DATA_ISSUE | Activated | Policy recovery triggered | PASS after policy recovery / triggered | Mean latency ms | Mean model calls |\n|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n'
for a in agg:text+=f"| {a['scenario']} | {a['policy']} | {a['assessed_n']}/{a['expected_n']} | {a['llm_PASS']}/{a['expected_n']} | {a['llm_FAIL']} | {a['llm_UNCERTAIN']} | {a['llm_DATA_ISSUE']} | {a['activated_n']} | {a['policy_recovery_n']} | "+(f"{a['pass_after_policy_recovery_n']}/{a['policy_recovery_n']}" if a['policy_recovery_n'] else 'N/A')+f" | {a['e2e_latency_ms_mean']:.1f} | {a['model_calls_mean']:.2f} |\n"
text+='\nPASS-after-activation includes natural continuation; PASS-after-policy-recovery requires an actual policy recovery event. Neither is human-confirmed semantic recovery. Unassessed and UNCERTAIN results are explicit; neither is treated as FAIL. All clean runs have activation N/A. Recovery latency is averaged only over triggered policy recoveries in scenario_policy_results.csv; no trigger is not a zero-duration recovery.\n\n'
disagreements=[]
for r in rows:
 if r['scope']=='primary' and r['kind']=='bundle':
  combined=qmap[r['run_id']]['llm_assessed_run_quality']
  if r['llm_overall']!=combined:disagreements.append(dict(slot_id=r['slot_id'],run_id=r['run_id'],bundle_llm_verdict=r['llm_overall'],combined_retained_and_bundle_verdict=combined,action='Review retained drafts and bundle together; labels preserved, no automatic human decision'))
writecsv(P/'quality_disagreements.csv',disagreements,['slot_id','run_id','bundle_llm_verdict','combined_retained_and_bundle_verdict','action'])
text+='## Main observations\n\n'
text+='HELPER_CORRUPTION has the largest observed separation: unprotected yields 3/20 combined LLM PASS, full_restart 15/20, and always_verify 16/20 with one unassessed run. Paired against unprotected, full_restart gains PASS on 12/20 cases and loses none; always_verify gains on 13/19 assessed pairs and loses none. These are LLM outcomes pending human review.\n\n'
text+='QA_CORRUPTION yields 13/20 PASS for unprotected and full_restart, versus 14/20 for always_verify. The first two policies do not trigger policy recovery in this scenario. TIMEOUT yields 13/20, 18/20 and 13/20 respectively; full_restart gains PASS on 6/20 pairs versus unprotected and loses on 1/20. Clean controls themselves yield 16/20, 15/20 and 15/20 PASS respectively, with one unassessed always_verify run. Fault-case differences cannot all be attributed to recovery because the clean answer-quality baseline is imperfect.\n\n'
text+='For HELPER_CORRUPTION, always_verify uses 4 model calls/run versus 8 for full_restart, with observed mean end-to-end latency 2752.3 ms versus 4856.2 ms. Against its own clean control, the mean latency increase is 721.3 ms (median paired increase 40.1 ms); full_restart increases by 2667.9 ms (median 2463.8 ms). These single-repetition descriptive results do not establish stable speedups. Full within-case comparisons for all three policy pairs are saved in paired_results*.csv.\n\n'
text+=f"Bundle-only assessment gives 180/240 PASS, while combining retained draft assessments with bundle coverage gives 164/240 PASS, 65/240 FAIL, 9/240 DATA_ISSUE and 2/240 unassessed. There are {len(disagreements)} bundle-versus-combined outcome differences in quality_disagreements.csv. The nine DATA_ISSUE outcomes occur in injected helper-corruption runs: reviewers should check whether the judge has conflated corrupted observations with a genuinely misaligned authoritative environment. Do not treat those classifications as confirmed dataset defects.\n\n"
text+='The two unresolved retained drafts are BASE-0027__NONE__always_verify__r1 (event bf263e2c-fab8-41f6-a310-b62f87f43207:49; non-exact answer quotation) and BASE-0007__HELPER_CORRUPTION__always_verify__r1 (event 4f7ef584-a85a-4845-8d5b-5316332da5a9:62; nonexistent evidence pointer). Both exhausted the configured two explicit retries. Review them directly; original experimental reruns are unnecessary.\n\n'
text+='## Interpretation and limits\n\nThe same case/scenario comparisons and each policy’s own clean control are in paired_results.csv and paired_results_summary.csv. Each group contains 20 distinct cases with one repetition each; latency differences are descriptive observations, not stable speedup or repeatability evidence. QA corruption can lead to natural continuation without a policy recovery event; do not rename it successful full-restart recovery.\n\n'
text+='The judge model is api-glm-5.3-flash, which also generated the original answers. Shared-model bias and LLM inconsistency limit independence. Exact quotes/source pointers are validated, but semantic judgments still require human review. Whole-run aggregation combines retained draft quality and independent bundle coverage; discarded drafts never lower delivered run quality. Archive bundles remain separate. Missing provider attempt usage and original experiment USD costs remain unavailable; the judge ledger does not retroactively estimate experimental charges.\n\n'
text+='## Human review and remaining work\n\nOpen priority_review_with_context.csv first. For each row compare user_question, original_records, observed_records and answers, then inspect the trace and exact criterion evidence. Fill the five human_* criteria and human verdict/reviewer/timestamp/rationale. Judge suggestions do not count as your decision. Then review complete_review_with_context.csv, including rows absent from the priority queue. human_followup_queue.csv also provides a reproducible PASS sample. Keep individual draft and final-bundle identities distinct.\n\n'
for scope in ['primary','infrastructure_archive']:
 for disposition in ['retained','discarded']:
  g=[r for r in enriched if r['scope']==scope and r['kind']=='draft' and r['disposition']==disposition];text+=f"- {scope} {disposition} drafts: {len(g)} total, {sum(r['evaluation_status']=='EVALUATED' for r in g)} LLM-assessed, all human UNREVIEWED.\n"
text+='\nThe formal course rubric/submission format still requires confirmation because it was not found in the repository. Clean baseline and semantic recovery claims still await human review. Original run completeness requires no reruns. Any remaining judge errors are listed exactly in unfinished_items.csv; these are evaluation gaps, not failed experiments.\n'
(P/'RESULTS.md').write_text(text)
(P/'review_counts.json').write_text(json.dumps({'complete_rows':len(enriched),'priority_rows':len(priority),'priority_note':'Triage only; non-priority answers remain unreviewed'},indent=2)+'\n')
print('Generated contextual reviews, 240 joined runs, paired comparisons, grouped results and RESULTS.md')
(P/'PHASE1_LLM_ADDENDUM.md').write_text('''# Phase 1 requirement update after LLM assessment

The full requirement/evidence matrix remains [PHASE1_REQUIREMENTS.md](../analysis_offline_20261104_3d072433_en/PHASE1_REQUIREMENTS.md). This addendum records only the effect of the new assessment.

| Requirement | Current evidence | Status | Remaining action |
|---|---|---|---|
| Frozen experiment and all 240 unique slots | Original verifier passes; raw evidence hashes preserved | Completed | No experimental reruns indicated by completeness checks |
| Clean baseline answer quality | GLM assessments in complete_review_with_context.csv; NONE rows in scenario_policy_results.csv | Awaiting human review | Independently check authoritative records and answers; LLM PASS is not human approval |
| Fault activation and execution recovery | Prior deterministic measurements joined by run_id | Completed | Keep natural continuation distinct from policy-triggered recovery |
| Semantic recovery success | Retained draft plus independent bundle assessment; run_results_joined.csv | LLM-assessed; awaiting human review | Verify boundary answers and recorded recovery events before formal semantic-success claims |
| Complete saved-answer assessment | SUMMARY.md and unfinished_items.csv | '''+('LLM assessment complete' if summary['complete'] else 'Needs evaluation follow-up')+''' | Any unfinished judge item is listed exactly; do not rerun original experiments to fix a judge error |
| Human review materials | Complete and prioritized contextual CSVs, separate UNREVIEWED human fields | Materials completed; review pending | Record reviewer, time, rationale and five criterion decisions; retain discarded drafts for diagnosis |
| Metrics, pairing and limitations | scenario_policy_results.csv; paired_results*.csv; RESULTS.md | Completed descriptive analysis | One repetition per case; do not claim stable latency improvements; disclose same-model judge bias |
| Official course Phase 1 rubric and submission format | No official course document found in original repository audit | Requirements unclear | Confirm with course materials; this internal matrix does not invent grading requirements |
''')
