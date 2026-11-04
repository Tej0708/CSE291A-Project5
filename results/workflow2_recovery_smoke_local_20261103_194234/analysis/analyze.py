"""Read-only experiment analysis; manual Codex judgments are bound to exact answer hashes."""
import csv, json, hashlib, sys, math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
HERE=Path(__file__).resolve().parent
RUN=HERE.parent
ROOT=RUN.parents[1]
sys.path.insert(0,str(ROOT))
from csa_workflow.cost_metrics import summarize
S=['NONE','QA_CORRUPTION','HELPER_CORRUPTION','TIMEOUT']
P=['unprotected','full_restart','always_verify']
COL=['#3977b5','#df8431','#329178']
LABEL=['Unprotected','Full restart','Always verify']
def read(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,x):(HERE/n).write_text(json.dumps(x,indent=2)+'\n')
before={str(p.relative_to(RUN)):digest(p) for p in RUN.rglob('*') if p.is_file() and 'analysis' not in p.relative_to(RUN).parts}
manifest=read(RUN/'manifest.json')
assert all(digest(ROOT/n)==h for n,h in manifest['source_hashes'].items())
records=read(RUN/'supporting_records.json')['records']
summary=list(csv.DictReader((RUN/'summary.csv').open()))
assert len(summary)==12 and all(r['status']=='COMPLETED' for r in summary)
def equivalent(a,b):
 if isinstance(a,dict):return a.keys()==b.keys() and all(equivalent(a[k],b[k]) for k in a)
 if isinstance(a,float):return math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-9)
 return a==b
rows=[];reviews=[];evidence=[];timelines=[]
for d in sorted(RUN.glob('[0-9][0-9]_*')):
 r=read(d/'result.json');m=r['metrics'];events=[json.loads(x) for x in (d/'trace.jsonl').read_text().splitlines()];usage=read(d/'provider_usage.json');a=read(d/'answers.json')
 assert events==r['events']
 assert equivalent(summarize(r['calls'],r['recoveries'],events[-1]['elapsed_ms']),m)
 assert read(d/'metrics.json')==m and read(d/'logging_sanity.json')['passed']
 models=[c for c in r['calls'] if c['kind']=='model']
 assert len(models)==len(usage)==m['model_calls']
 assert len({c['call_id'] for c in r['calls']})==len(r['calls'])
 for c,u in zip(models,usage):
  assert c['call_id']==u['call_id'] and c['attempt_id']==u['attempt_id']
  assert c['token_usage']==dict(input_tokens=u['usage']['prompt_tokens'],output_tokens=u['usage']['completion_tokens'],total_tokens=u['usage']['total_tokens'])
 for kind,key in [('model','model_calls'),('tool','business_tool_calls'),('verification','verification_calls')]:assert sum(c['kind']==kind and c['status']!='incomplete' for c in r['calls'])==m[key]
 assert m['tool_calls']==m['business_tool_calls']+m['verification_calls']
 assert m['discarded_calls']==sum(bool(c['discarded_reason']) for c in r['calls'])
 assert r['restart_count']==sum(e['event']=='restart_triggered' for e in events)
 assert r['stage_retry_count']==sum(e['event']=='stage_retry' for e in events)
 s=r['case_id'].split('BASE-0004-')[1];p=r['mode'];faults=[e for e in events if e.get('mutated')]
 assert len(faults)==(0 if s=='NONE' else 1)
 if s=='QA_CORRUPTION':
  f=faults[0];assert f['hook']=='on_qa_feedback'
  h=next(h for h in r['attempts'][0]['history'] if h['stage']=='qa_label_validation' and h['iteration']==f['iteration'])
  assert f['before']['missing_issue'] in h['unresolved_issues'] and f['after']['missing_issue'] in h['resolved_issues']
  assert f['iteration']<r['max_iterations']
  routes=[e for e in events if e['event']=='router_selection' and e['iteration']>f['iteration']]
  assert (routes[0]['target']==f['after']['missing_issue'])==(p!='always_verify')
 if s in ('TIMEOUT','HELPER_CORRUPTION'):
  f=faults[0];assert f['before']['status']=='ok'
  candidate=next(e for e in events if e['event']=='helper_candidate' and e['elapsed_ms']>=f['elapsed_ms'])
  assert candidate['record']==f['after']
  if s=='TIMEOUT':assert f['hook']=='on_tool_call' and f['after']['status']=='timeout' and f['after']['record'] is None
  else:assert f['hook']=='on_helper_output' and candidate['issue']=='incorrect_invoice' and f['after']['record']['amount']==191 and f['before']['record']['amount']==19 and not f['after']['authoritative']
 assert set(r['attempts'][-1]['issue_states'])==set(records)
 assert all(v=='RESOLVED' or v=='resolved' for v in r['attempts'][-1]['issue_states'].values())
 verdict='FAIL' if s=='HELPER_CORRUPTION' and p=='unprotected' else 'PASS'
 for disposition in ['retained','discarded_intermediate']:
  for e in a[disposition]:
   bad=e['issue']=='incorrect_invoice' and '$191' in e['answer']
   reason=('Wrong amount relative to authoritative USD 19 corrected invoice; necessary supported correction is absent. ' + ('Unsupported claim that verification is underway: "We\'re checking it against the authoritative billing ledger".' if "We're checking" in e['answer'] else 'Asks customer to supply information already available in the scenario ledger.')) if bad else ('Supported available build 7.9.3, existing installation channel and Settings retest; no observed user repair claimed.' if e['issue']=='app_crash' else 'Supported corrected/reissued USD 19 invoice; follow-up adds no numeric timing or delivery channel. "When you receive it" is conditional review wording, not a promise of delivery timing.')
   reviews.append(dict(run=d.name,event_id=e['event_id'],disposition=disposition,issue=e['issue'],quote=e['answer'],answer_sha256=hashlib.sha256(e['answer'].encode()).hexdigest(),supporting_record=records[e['issue']],observed_record=e['record'],reviewer='Codex-reviewed; provisional pending human review',original_quality=a['quality'],record_alignment='PASS (underlying scenario)',relevance='PASS',grounding='FAIL' if bad else 'PASS',coverage='FAIL' if bad else 'PASS',status_responsibility='FAIL' if bad and "We're checking" in e['answer'] else 'PASS',overall='FAIL' if bad else 'PASS',rationale=reason))
 rejected=[e for e in events if e['event']=='verification_decision' and not e['accepted']]
 if s=='NONE':outcome='N/A: clean'
 elif verdict=='FAIL':outcome='Not recovered; no policy detection'
 elif r['restart_count']:outcome='Restart recovery (Codex-reviewed)'
 elif r['stage_retry_count']:outcome='Stage retry recovery (Codex-reviewed)'
 else:outcome='Natural continuation; no policy recovery'
 row=dict(run=d.name,scenario=s,policy=p,execution='COMPLETED',structural='PASS: ledger and issue coverage',original_quality=a['quality'],codex_quality=verdict,activation='N/A' if not faults else 'CONFIRMED',recovery=outcome,verification_calls=m['verification_calls'],rejected_verifications=len(rejected),restarts=r['restart_count'],stage_retries=r['stage_retry_count'],model_calls=m['model_calls'],provider_requests=len(usage),business_tool_calls=m['business_tool_calls'],tool_calls=m['tool_calls'],input_tokens=m['provider_usage']['input_tokens'],output_tokens=m['provider_usage']['output_tokens'],total_tokens=m['provider_usage']['total_tokens'],unknown_usage_calls=m['provider_usage']['unknown_usage_calls'],e2e_latency_ms=m['e2e_latency_ms'],verification_latency_ms=m['verification_latency_ms'],repair_latency_ms=m['repair_latency_ms'],discarded_calls=m['discarded_calls'],estimated_usd=None)
 for k in ['model_calls','tool_calls','verification_calls','total_tokens','e2e_latency_ms']:assert float(next(z for z in summary if z['case_id']==r['case_id'] and z['policy']==p)[k])==row[k]
 rows.append(row)
 evidence.append(dict(run=d.name,mutations=faults,rejections=rejected,recoveries=r['recoveries'],source_trace=str(d.relative_to(RUN)/'trace.jsonl')))
 timeline=[e for e in events if e.get('mutated') or e['event'] in ('router_selection','helper_unavailable','restart_triggered','stage_retry','helper_accepted','attempt_finished') or (e['event']=='verification_decision' and not e['accepted'])]
 timelines.append((d.name,timeline))
assert {(r['scenario'],r['policy']) for r in rows}=={(s,p) for s in S for p in P}
for r in rows:
 base=next(x for x in rows if x['scenario']==r['scenario'] and x['policy']=='unprotected')
 for k in ['total_tokens','model_calls','e2e_latency_ms','tool_calls']:
  r[k+'_delta']=None if r[k] is None or base[k] is None else r[k]-base[k]
  r[k+'_overhead_pct']=None if base[k] in (None,0) or r[k] is None else 100*(r[k]/base[k]-1)
with (HERE/'run_comparison.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
if (HERE/'reviewed_answer_hashes.json').exists():
 assert read(HERE/'reviewed_answer_hashes.json')=={x['event_id']:x['answer_sha256'] for x in reviews}, 'Answers changed: manual review required'
save('reviewed_answer_hashes.json',{x['event_id']:x['answer_sha256'] for x in reviews})
save('codex_reviews.json',reviews);save('trace_evidence.json',evidence)
F=HERE/'figures';F.mkdir(exist_ok=True)
fontpath='/System/Library/Fonts/Supplemental/Arial.ttf'
def font(n):return ImageFont.truetype(fontpath,n)
def canvas(title,subtitle,h=800):
 im=Image.new('RGB',(1500,h),'white');dr=ImageDraw.Draw(im);dr.text((50,24),title,font=font(32),fill='#182a3b');dr.text((50,70),subtitle,font=font(20),fill='#4c5966');return im,dr
for key,title,unit in [('total_tokens','Total provider tokens','tokens'),('model_calls','Model calls','calls'),('e2e_latency_ms','End-to-end latency','milliseconds')]:
 im,dr=canvas(title,'BASE-0004 | One observation per condition | All attempts included')
 for i,l in enumerate(LABEL):dr.rectangle((60+i*380,114,80+i*380,134),fill=COL[i]);dr.text((90+i*380,109),l,font=font(22),fill='#273747')
 maximum=12 if key=='model_calls' else math.ceil(max(r[key] for r in rows)*1.18/1000)*1000; top=190;bottom=650
 for j in range(5):
  v=maximum*j/4;y=bottom-(bottom-top)*j/4;dr.line((100,y,1450,y),fill='#dde3e8');dr.text((10,y-10),f'{v:.0f}',font=font(18),fill='#4c5966')
 for si,s in enumerate(S):
  center=265+si*350
  for pi,p in enumerate(P):
   v=next(r[key] for r in rows if r['scenario']==s and r['policy']==p);x=center+(pi-1)*88;y=bottom-v/maximum*(bottom-top)
   dr.rectangle((x-32,y,x+32,bottom),fill=COL[pi]);dr.text((x-30,y-29),f'{v:.0f}',font=font(20),fill='#182a3b')
  dr.text((center-132,680),s.replace('_',' ').title(),font=font(21),fill='#182a3b')
 dr.text((50,750),'Unit: '+unit+' | Missing values are not zero; none missing in these series.',font=font(20),fill='#4c5966');im.save(F/(key+'.png'))
im,dr=canvas('Final-answer outcome matrix','Codex-reviewed provisional judgments; original labels remain UNREVIEWED',740)
for pi,l in enumerate(LABEL):dr.text((400+pi*340,140),l,font=font(25),fill=COL[pi])
for si,s in enumerate(S):
 y=195+si*105;dr.text((45,y+28),s.replace('_',' ').title(),font=font(24),fill='#182a3b')
 for pi,p in enumerate(P):
  q=next(r['codex_quality'] for r in rows if r['scenario']==s and r['policy']==p);x=385+pi*340
  dr.rounded_rectangle((x,y,x+310,y+85),radius=8,fill='#d3eee2' if q=='PASS' else '#f4caca');dr.text((x+25,y+25),'Correct / PASS' if q=='PASS' else 'Incorrect / FAIL',font=font(24),fill='#183b30' if q=='PASS' else '#802d2d')
dr.text((50,650),'All 12 completed structurally. Green = correct; red = incorrect; gray = unreviewed (0).',font=font(22),fill='#4c5966');im.save(F/'outcome_matrix.png')
lines=['# Trace timelines','', 'All times are milliseconds from each logical run start. Event IDs identify exact trace records.','']
for name,ev in timelines:
 lines+=['## '+name,'','| ms | Attempt | Iteration | Event | Evidence |','|---:|---:|---:|---|---|']
 for e in ev:
  detail=e.get('reason') or e.get('target') or e.get('issue') or e.get('hook') or e.get('status','')
  lines.append(f"| {e['elapsed_ms']:.1f} | {e['attempt_id']} | {e['iteration']} | {e['event']} | {detail}; `{e['event_id']}` |")
 lines+=['']
(HERE/'timelines.md').write_text('\n'.join(lines))
assert before=={n:digest(RUN/n) for n in before}
save('validation.json',dict(source_files_preserved=True,source_hashes_match_manifest=True,run_count=12,model_calls=sum(r['model_calls'] for r in rows),tokens=sum(r['total_tokens'] for r in rows),all_ledgers_reconciled=True,missing_usage_calls=sum(r['unknown_usage_calls'] for r in rows),estimated_usd=None,source_sha256=before))
print(json.dumps(rows,indent=2))
report='''# Workflow 2 recovery smoke pilot analysis

**Recommendation: READY WITH CONDITIONS** for a larger diagnostic experiment, not a robustness claim.

Selected the newest directory with exactly 12 COMPLETED summary rows and corresponding completed results: `workflow2_recovery_smoke_local_20261103_194234`. The newer complete pilot supersedes earlier incomplete attempts for selection only; none were edited. Coverage is exactly NONE, QA_CORRUPTION, HELPER_CORRUPTION and TIMEOUT × unprotected, full_restart and always_verify, all BASE-0004.

## Outcome interpretation

All 12 executions ended normally and passed ledger/issue-coverage checks. That does not validate answer semantics or source-record integrity: unprotected helper corruption retains a contradictory record despite ledger resolution. Codex review finds 11 final-answer sets PASS and one FAIL, all provisional pending human review. Original UNREVIEWED labels and null recovery-success fields are preserved. Historical human adjudications were used as rubric precedents, not transferred to new answers. This analysis makes no human-finalized claims.

The failed retained billing answer in run 07 quotes a “possible reissue at $191.00 USD” and says “We're checking it against the authoritative billing ledger and will confirm the accurate amount”. The original scenario explicitly records a corrected/reissued USD 19 invoice. The model notices contradiction in prose, but no verification or follow-up action supports its promise. Grounding and coverage fail; unsupported ongoing action also fails status/responsibility. This is fault propagation through an aligned scenario, not a pre-existing DATA_ISSUE. Uncertainty language does not establish successful recovery.

All retained technical answers describe an available build 7.9.3 fix, installation through the existing channel, and Settings retest without claiming observed user-side repair. Other retained billing answers report the supported USD 19 correction. Run 01's “when you receive it” is treated as conditional review wording without a concrete delivery-channel/time guarantee; human review should confirm this interpretation. No unsupported refund timing/destination claims appear. Full quotes, all five criteria, exact event IDs, original labels, observed corrupted records and supporting clean records are in codex_reviews.json. Four discarded drafts are reviewed separately, including the failed billing draft before run 08's successful restart; they do not replace the final-output scoring rule.

## Activation and policy behavior

Every intended fault activated exactly once, confirmed by boundary values and subsequent consumers, not only mutation counts. Detailed before/after evidence is in trace_evidence.json; timelines.md provides all run timelines with exact event IDs.

- QA: iteration 1 changed OPEN `incorrect_invoice` to resolved `app_crash`, leaving an additional Router iteration. Unprotected and full_restart consumed this label and revisited the technical issue. They subsequently handled billing correctly. No QA verifier detected the injected label in these two modes; zero full restarts is expected because final record checks pass. Always_verify rejected `qa_ledger_mismatch` and regenerated QA before routing, avoiding that revisit.
- Helper: the billing record changed from corrected USD 19/authoritative to CONTRADICTORY USD 191/unverified/non-authoritative. Unprotected accepted it without a policy check; model acknowledgment of inconsistency is not detector success. Full_restart found `final_record_mismatch`, discarded attempt 1 and restarted once. Always_verify rejected the record before model prose generation and retried the helper with a fresh record once.
- Timeout: each trace's `on_tool_call` changes an actual successful app_crash tool record into `status=timeout, record=null`. The following helper_candidate contains the same injected value. Unprotected emits helper_unavailable, leaves the issue open and naturally routes back later. Full_restart triggers `helper_timeout` and restarts once. Always_verify rejects record_unavailable_or_mismatch and retries locally once. This is immediate synthetic status injection, not an actual five-second deadline, sleeping tool or provider timeout. A zero failed-business-tool-call count is expected: the successful service call is mutated after it returns.

`csa_workflow/recovery.py` implements terminal-record checks for full_restart and per-candidate helper/QA checks for always_verify. `faults.py` implements transient injection; `state.py` accepts supporting service evidence without requiring authority, explaining unprotected corrupted-record acceptance. Natural continuation is distinct from a measured policy repair interval; neither a successful clean run nor nonactivation counts as recovery. All invoked policy repairs completed in this sample; unprotected helper corruption was not recovered.

## Compact comparison

V = verification calls, R = full restarts, S = stage retries. No SDK retries (saved max_retries=0).

| Scenario | Policy | Activation | Codex final quality | V | R | S | Observed recovery |
|---|---|---|---|---:|---:|---:|---|
'''
for r in rows:report+=f"| {r['scenario']} | {r['policy']} | {r['activation']} | {r['codex_quality']} | {r['verification_calls']} | {r['restarts']} | {r['stage_retries']} | {r['recovery']} |\n"
report+='''
## Accounting and observed overhead

All 59 application model calls match 59 observable provider dispatches, with no failed or incomplete model calls and no missing reported usage. All input/output/total fields reconcile to provider evidence. Calls, verification counts, combined tools, discarded calls, retries/restarts and event streaming reconcile to the ledger and summary. Current implementation hashes match the frozen run manifest. Python runtime floating-point summation differences are tolerated only within 1e-9 ms / 1e-12 relative error; counts and token values are exact. No material accounting inconsistency was found. Gateway-internal upstream attempts remain unobservable despite zero client SDK retries. Pricing, costs and original semantic-recovery judgments remain unknown/null; no USD estimate is made.

End-to-end is the recorded monotonic run endpoint; verification time includes nested fresh record reads, and repair time is an interval union. These categories overlap and must not be added. All attempts, including discarded attempt 1 in full restarts, contribute to the totals. Figure data are taken directly from these reconciled fields; values are rounded only for chart labels.

The table below compares each protected policy to unprotected within the same scenario. Percentage = 100 × (policy / unprotected − 1). Missing inputs or zero denominators yield null, not zero; none of these denominators is missing or zero. A negative latency difference is an observation, not demonstrated speedup. There is one serial run per cell, no counterbalancing, and network/service variation is unmeasured.

| Scenario | Policy | Tokens Δ | Tokens % | Calls Δ | Calls % | Latency Δ ms | Latency % |
|---|---|---:|---:|---:|---:|---:|---:|
'''
for r in rows:
 if r['policy']!='unprotected':report+=f"| {r['scenario']} | {r['policy']} | {r['total_tokens_delta']:+d} | {r['total_tokens_overhead_pct']:+.1f} | {r['model_calls_delta']:+d} | {r['model_calls_overhead_pct']:+.1f} | {r['e2e_latency_ms_delta']:+.1f} | {r['e2e_latency_ms_overhead_pct']:+.1f} |\n"
report+='''
Always_verify avoided a redundant helper generation in QA corruption (1695 versus 2299 tokens) and blocked corrupted helper prose before generation. Full restart repeated both issues in helper corruption (3130 tokens and 8 model calls versus 1587 and 4 unprotected), producing a correct final answer at higher observed work. These effects are specific to this case and deterministic verifier coverage, not evidence of general superiority. Clean controls use four model calls each, while verification adds tool work: combined tool calls 4/8/10 for unprotected/full_restart/always_verify. The unprotected clean latency was 2538 ms versus 1203/1389 ms in protected controls, illustrating why latency cannot be interpreted as deterministic policy cost here.

## Readiness conditions and limitations

The integration, mutation boundaries, logging and expected policy handling support expansion with conditions:

1. Human-review the new Codex judgments, including the conditional invoice wording; keep original labels and discarded drafts intact. Do not equate structural COMPLETED with final-answer PASS or policy recovery.
2. Preflight every added base case for valid records, reachable helpers and remaining iterations; log actual activation separately. Exclude unsuitable paired clean controls from conditional recovery claims.
3. Freeze the larger design, model settings and per-run/request ceilings before launch. Pricing is optional, but unknown costs mean there is no enforced USD spending bound. Do not silently extrapolate this pilot's token use into a dollar budget.
4. Retain the explicit simulated-timeout label. If the full experiment intends to test real deadline/cancellation/late-response behavior, add and separately validate that mechanism before making those claims; this pilot does not test it.
5. Interpret latency descriptively; counterbalance ordering and use repetition in the larger design if comparative latency is an objective. Do not modify baseline policy semantics to hide the observed unprotected failure.

No experiment-logic fix is required for the observed policy behavior. One base case with one run per cell cannot establish failure/recovery rates, statistical significance or general robustness. No significance tests or new experiments were performed.

## Deliverables and reproduction

- figures/outcome_matrix.png: provisional correct/incorrect/unreviewed final outcomes.
- figures/total_tokens.png, figures/model_calls.png, figures/e2e_latency_ms.png: grouped comparisons with consistent policy colors.
- run_comparison.csv: 12 consolidated rows, absolute and percentage overhead; blank CSV cost fields mean unknown.
- codex_reviews.json: separate Codex judgments and quoted evidence for retained and discarded drafts.
- trace_evidence.json and timelines.md: activation, detection and repair event references.
- validation.json: checks and hashes proving source artifacts unchanged.

Reproduce without provider calls from the repository root using the bundled Python with Pillow:

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/yanghede/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 results/workflow2_recovery_smoke_local_20261103_194234/analysis/analyze.py
```

The script only reads experiment data and writes analysis/. Reviews are explicit Codex assessments of this fixed run, not an automatic general-purpose semantic judge. No experiment labels or human adjudications are rewritten.
'''
(HERE/'report.md').write_text(report)
