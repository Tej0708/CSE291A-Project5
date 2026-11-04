"""Offline only. Validate a separately edited complete CSV, then create NEW analysis.
Usage: /usr/bin/python3 import_human_reviews.py REVIEW_COPY.csv NEW_OUTPUT_DIR
"""
import csv,json,sys,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
meta=json.loads((HERE/'integrity.json').read_text());sys.path.insert(0,meta['source_root'])
from workflow2_phase1 import analyze,CRITERIA
if len(sys.argv)!=3:raise SystemExit(__doc__)
source=Path(sys.argv[1]);target=Path(sys.argv[2]);assert not target.exists(),'Choose a new output directory'
base={r['event_id']:r for r in csv.DictReader((HERE/'human_review_complete.csv').open(encoding='utf-8-sig'))}
rows=list(csv.DictReader(source.open(encoding='utf-8-sig')));seen=set();accepted=[]
immutable=['slot_id','run_id','event_id','answer_sha256','case_id','scenario','policy','issue','retained','answer','original_record','observed_record','trace','user_question','expected_issues','base_case_id','repetition','retained_discarded']
for row in rows:
 eid=row['event_id'];assert eid in base and eid not in seen,'Unknown/duplicate event';seen.add(eid)
 assert all(row[k]==base[eid][k] for k in immutable),'Changed review identity/evidence: '+eid
 assert hashlib.sha256(row['answer'].encode()).hexdigest()==row['answer_sha256']
 assert all(row[k] in ('PASS','FAIL','UNCERTAIN','UNREVIEWED','') for k in CRITERIA),'Invalid criteria'
 if all(row[k] in ('','UNREVIEWED') for k in CRITERIA):continue
 assert all(row.get(k,'').strip() for k in ('reviewer','review_timestamp','rationale')),'Missing human provenance: '+eid
 assert all(row[k] for k in CRITERIA),'Use explicit UNREVIEWED for incomplete criteria'
 accepted.append(row)
assert seen==set(base),'Complete review table required; keep unreviewed rows'
# Adapter input is a new sibling file, never overwrites the original or review copy.
normalized=target.with_name(target.name+'_validated_reviews.csv')
with normalized.open('x',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(accepted)
analyze(meta['raw_results'],target,normalized)
(target/'human_import_provenance.json').write_text(json.dumps({'input':str(source.resolve()),'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'assessed_rows':len(accepted),'unreviewed_rows':len(rows)-len(accepted)},indent=2))
print('Created offline analysis:',target,'assessed rows:',len(accepted))
