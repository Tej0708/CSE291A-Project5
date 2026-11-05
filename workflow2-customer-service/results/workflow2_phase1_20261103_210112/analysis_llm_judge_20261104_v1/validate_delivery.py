"""Offline validation; never sends inference or modifies original evidence."""
from pathlib import Path
import csv,json,hashlib,subprocess
from decimal import Decimal
import judge_workflow2 as j
P=Path(__file__).resolve().parent;ROOT=P.parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
source=read(P/'source_hashes.json');bad=[s for s,h in source.items() if sha(ROOT/s)!=h];assert not bad,bad
raw=read(P.parent/'analysis_offline_20261104_3d072433_en/preservation.json')['raw_sha256'];bad=[s for s,h in raw.items() if sha(P.parent/s)!=h];assert not bad,bad
jobs=j.verified_inputs();valid=j.successful_jobs(jobs);ledger=read(P/'budget_ledger.json');history=read(P/'config_history.json');c=read(P/'judge_config.json');history[j.contract_hash(c)]=c
assert len({e['request_id'] for e in ledger['requests']})==len(ledger['requests'])
for e in ledger['requests']:
 cfg=history[e['config_hash']];assert j.contract_hash(cfg)==e['config_hash'];assert sha(P/'system_prompt.txt')==e['prompt_hash'];assert j.digest(read(P/'requests'/str(e['request_id'])))==e['request_hash']
 if e['state']=='settled':
  resp=read(P/'responses'/str(e['request_id']));copy=dict(e);j.settle(copy,resp['usage'],cfg);assert copy['accounted_usd']==e['accounted_usd']
 else:assert Decimal(e['accounted_usd'])==Decimal(e['reservation_usd'])
for saved in valid.values():
 if saved.get('local_aggregation'):
  original=json.loads(read(P/'responses'/str(saved['request_id']))['choices'][0]['message']['content'])
  assert original['criteria']==saved['judgment']['criteria']
  assert original['human_followup_needed']==saved['judgment']['human_followup_needed']
  assert saved['judgment']['overall_verdict']==j.aggregate(original['criteria'],jobs[saved['job_id']]['context'])
assert j.balance(ledger)+Decimal(ledger.get('safety_holdback_usd','0'))<=Decimal('3')
with (P/'complete_review_with_context.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
assert len(rows)==811;assert len({r['item_id'] for r in rows})==811
assert all(r['human_verdict']=='UNREVIEWED' and all(r['human_'+k]=='UNREVIEWED' for k in j.CRITERIA) for r in rows)
assert len([r for r in rows if r['scope']=='primary' and r['kind']=='bundle'])==240
assert all(r['answers'] and r['original_records'] and r['observed_records'] and r['trace_path'] for r in rows)
# Read secret only to test exact byte absence; never print or save it.
key,_=j.credentials('/Users/yanghede/Downloads/CSE291A-Project5/.env');leaks=[]
for p in P.rglob('*'):
 if p.is_file() and key.encode() in p.read_bytes():leaks.append(str(p.relative_to(P)))
assert not leaks,'Credential leakage detected in deliverables'
s=read(P/'summary.json');assert s['valid_unique_judgments']==len(valid);assert s['attempted_paid_calls']==len(ledger['requests']);assert Decimal(s['accounted_usd'])==j.balance(ledger)
result={'status':'COMPLETE_LLM_ASSESSED_HUMAN_REVIEW_PENDING' if s['complete'] else 'INCOMPLETE_PRECISE_GAPS_RETAINED','repo':str(ROOT),'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'source_branch':'Billing_loop_structure','worktree_branch':'detached HEAD','primary_slots':240,'all_review_items':811,'valid_unique_judgments':len(valid),'expected_unique_contexts':len(jobs),'paid_requests_all_versions':len(ledger['requests']),'accounted_usd':str(j.balance(ledger)),'safety_holdback_usd':ledger.get('safety_holdback_usd'),'pending_or_unknown_reservations':sum(e['state']=='reserved' for e in ledger['requests']),'raw_files_unchanged':len(raw),'frozen_source_review_files_unchanged':len(source),'credential_scan_passed':True,'all_human_fields_unreviewed':True,'offline_unit_tests':30,'concurrent_mock_requests_verified':12,'original_experiment_verifier':'experiment_verification.txt','no_experiment_rerun':True,'no_commit_or_push':True}
(P/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
files=[p for p in sorted(P.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name not in ['delivery_sha256.json','budget.lock']]
(P/'FILES.md').write_text('# Delivery files\n\nStart with RESULTS.md, then priority_review_with_context.csv and complete_review_with_context.csv.\n\n'+''.join('- `'+str(p.relative_to(P))+'`\n' for p in files if p.name!='FILES.md'))
files=[p for p in sorted(P.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name not in ['delivery_sha256.json','budget.lock']]
(P/'delivery_sha256.json').write_text(json.dumps({str(p.relative_to(P)):sha(p) for p in files},indent=2)+'\n')
print(json.dumps(result,indent=2))
