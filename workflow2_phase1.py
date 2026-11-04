"""Offline preparation/analysis and explicit local execution with immutable manifests."""
import argparse, csv, hashlib, json, os, random, sys
from dataclasses import replace, asdict
from pathlib import Path
from decimal import Decimal
from csa_workflow.dataset import load_cases
from csa_workflow.services import scenario_for
from csa_workflow.taxonomy import ISSUE_ROUTE
from csa_workflow.recovery import RunBudget
from run_recovery_smoke_pilot import ROOT, SAVED, POLICIES, SpendGate, execute_one, OpenAIClient, load_dotenv
from phase1_metrics import measure, rates

SCENARIOS=['NONE','QA_CORRUPTION','HELPER_CORRUPTION','TIMEOUT','PROMPT_INJECTION']
CRITERIA=['record_alignment','relevance','grounding','coverage','status_responsibility']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'))
def read(p):return json.loads(Path(p).read_text())
def write(p,x):
    with Path(p).open('x') as f:json.dump(x,f,indent=2);f.write('\n')
def effective(c):return replace(c,fault_config={'profile':'qa_first_missing_once_v1','target_stage':'qa_to_router'}) if c.fault_type=='qa_corruption' else c

def applicability():
    cases=load_cases(ROOT/'support_cases_unique40.jsonl');out=[]
    assert len({c.case_id for c in cases})==len(cases)
    for raw in cases:
        c=effective(raw);sc=scenario_for(c.case_id,c.user_query);issues=c.expected_issues
        good=all(i in ISSUE_ROUTE and i in sc['records'] and sc['records'][i]['status']=='ok' and sc['records'][i]['record'].get('issue_type')==i for i in issues)
        reason='Valid scenario records and reachable stages under expected classification'
        eligible=good
        if c.fault_type=='qa_corruption' and (len(issues)<2 or c.max_iterations<2):eligible=False;reason='No OPEN issue plus resolved replacement with a subsequent Router iteration'
        if c.fault_type=='helper_corruption' and c.fault_config.get('target_agent') not in {ISSUE_ROUTE[i] for i in issues}:eligible=False;reason='Configured helper not reachable'
        targets={'timeout':'simulated_tool','prompt_injection':'retrieved_support_text','qa_corruption':'qa_to_router'}
        if c.fault_type in targets and (c.fault_config or {}).get('target_stage')!=targets[c.fault_type]:eligible=False;reason='Injection target stage mismatch'
        if c.fault_type=='prompt_injection' and not c.fault_config.get('payload'):eligible=False;reason='Empty adversarial payload'
        if c.max_iterations<1:eligible=False;reason='No helper iteration available'
        if not good:reason='Missing/misaligned record or route'
        out.append({'base_case_id':raw.raw['base_case_id'],'case_id':c.case_id,'fault_type':c.fault_type,'static_applicable':eligible,'reason':reason,'max_iterations':c.max_iterations,'effective_fault_config':c.fault_config,'record_contract_alignment':good,'semantic_alignment':'UNREVIEWED: contract match does not replace human scenario review','runtime_activation':'UNKNOWN','category':'control' if c.fault_type=='none' else 'adversarial' if c.fault_type=='prompt_injection' else 'accidental_modelled'})
    return out

def sources():
    paths=[*sorted((ROOT/'csa_workflow').glob('*.py')),ROOT/'workflow2_phase1.py',ROOT/'phase1_metrics.py',ROOT/'run_recovery_smoke_pilot.py',ROOT/'support_cases_unique40.jsonl',ROOT/'csa_workflow/scenario_records.json',ROOT/'BASELINE_EVALUATION_RULES.md',SAVED]
    return {str(p.relative_to(ROOT)):sha(p) for p in paths}

def prepare(config,output):
    cfg=read(config);ap=applicability();known={r['base_case_id'] for r in ap}
    unresolved=[k for k in ('base_case_ids','scenarios','repetitions','order') if cfg.get(k) is None]
    if unresolved:raise ValueError('Unresolved full-design values: '+', '.join(unresolved))
    if not cfg['base_case_ids'] or len(set(cfg['base_case_ids']))!=len(cfg['base_case_ids']) or not set(cfg['base_case_ids'])<=known:raise ValueError('Invalid base-case population')
    if not cfg['scenarios'] or len(set(cfg['scenarios']))!=len(cfg['scenarios']) or not set(cfg['scenarios'])<=set(SCENARIOS) or 'NONE' not in cfg['scenarios']:raise ValueError('Include clean exactly once and select known scenarios')
    if type(cfg['repetitions']) is not int or cfg['repetitions']<1:raise ValueError('Explicit positive repetitions required')
    if cfg['order'] not in ('case_scenario_policy','clean_first','seeded_shuffle','case_clean_rotating'):raise ValueError('Unknown order')
    if cfg['order'] in ('seeded_shuffle','case_clean_rotating') and type(cfg.get('seed')) is not int:raise ValueError('Explicit shuffle seed required')
    if cfg.get('request_limit') is not None and (type(cfg['request_limit']) is not int or cfg['request_limit']<=0):raise ValueError('Request limit must be null or positive')
    if cfg.get('policies',list(POLICIES))!=list(POLICIES):raise ValueError('Preserve the three agreed policies')
    if cfg['order']=='case_clean_rotating':
        selected=[r for r in ap if r['base_case_id'] in cfg['base_case_ids'] and r['case_id'].rsplit('-',1)[-1] in cfg['scenarios']]
        if any(not r['static_applicable'] for r in selected):raise ValueError('Selected fault is structurally inapplicable')
    cases={c.case_id:effective(c) for c in load_cases(ROOT/'support_cases_unique40.jsonl')}
    rows=[]
    for rep in range(1,cfg['repetitions']+1):
        bases=list(cfg['base_case_ids'])
        if cfg['order']=='case_clean_rotating':random.Random(cfg['seed']).shuffle(bases)
        for index,base in enumerate(bases):
            scenarios=sorted(cfg['scenarios'],key=lambda s:s!='NONE') if cfg['order']=='case_clean_rotating' else cfg['scenarios']
            policies=POLICIES[index%3:]+POLICIES[:index%3] if cfg['order']=='case_clean_rotating' else POLICIES
            for scenario in scenarios:
                for policy in policies:
                    c=cases[base+'-'+scenario]
                    rows.append(dict(slot_id=f'{base}__{scenario}__{policy}__r{rep}',case_id=c.case_id,base_case_id=base,scenario=scenario,policy=policy,repetition=rep,max_iterations=c.max_iterations,fault_config=c.fault_config))
    if cfg['order']=='clean_first':rows.sort(key=lambda r:r['scenario']!='NONE')
    if cfg['order']=='seeded_shuffle':random.Random(cfg['seed']).shuffle(rows)
    saved=read(SAVED)
    import subprocess
    manifest=dict(schema='workflow2-full-phase1-v1',config=cfg,run_order=rows,expected_run_count=len(rows),source_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),source_hashes=sources(),model=saved['model'],temperature=saved['temperature'],transport=saved['transport'],generation='Other parameters omitted; provider defaults',per_run_budget=asdict(RunBudget()),applicability=ap,pricing=None,pricing_note='Optional metadata; costs unknown; no USD enforcement')
    manifest['manifest_id']=hashlib.sha256(canonical(manifest).encode()).hexdigest();write(output,manifest)
    return manifest

def validate_manifest(m):
    body={k:v for k,v in m.items() if k!='manifest_id'}
    if hashlib.sha256(canonical(body).encode()).hexdigest()!=m['manifest_id']:raise ValueError('Manifest identity mismatch')
    if any(sha(ROOT/n)!=h for n,h in m['source_hashes'].items()):raise ValueError('Source/data/configuration drift; prepare a new manifest')
    if len(m['run_order'])!=m['expected_run_count'] or len({r['slot_id'] for r in m['run_order']})!=len(m['run_order']):raise ValueError('Invalid run identity')

def resume_state(out,m):
    complete=[]
    for slot in m['run_order']:
        d=out/slot['slot_id']
        if not d.exists():continue
        if not (d/'complete.json').exists():raise ValueError('Partial run preserved; automatic replay forbidden: '+slot['slot_id'])
        receipt=read(d/'complete.json')
        if receipt['manifest_id']!=m['manifest_id'] or receipt['slot_id']!=slot['slot_id'] or receipt['result_sha256']!=sha(d/'result.json'):raise ValueError('Completion receipt mismatch')
        if receipt['execution']=='budget_exhausted' or not receipt['sanity_passed']:raise ValueError('Recorded infrastructure/budget/sanity stop requires an explicit new protocol; no automatic replay')
        complete.append(slot['slot_id'])
    return complete

def execute(manifest_path,out,resume=False):
    m=read(manifest_path);validate_manifest(m);out=Path(out)
    if resume:
        if read(out/'manifest.json')!=m:raise ValueError('Resume manifest differs')
    else:out.mkdir(parents=True,exist_ok=False);write(out/'manifest.json',m)
    # Atomic exclusive ownership. Stale lock must be inspected, never auto-deleted.
    lock=out/'.execution.lock';fd=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    try:
        done=resume_state(out,m)
        gate=SpendGate({'verified':False,'project_request_limit':m['config'].get('request_limit')},pilot_ceiling=False)
        starts=[]
        for p in out.glob('*/provider_requests.jsonl'):
            starts.extend(json.loads(line) for line in p.read_text().splitlines() if json.loads(line)['status']=='started')
        gate.requests=len(starts)
        if len(done)==len(m['run_order']):return
        if gate.request_limit is not None and gate.requests>=gate.request_limit:raise ValueError('Cumulative provider request budget exhausted')
        load_dotenv();client=OpenAIClient(model=m['model'],temperature=m['temperature'])
        client._client=client._client.with_options(max_retries=m['transport']['max_retries'],timeout=m['transport']['timeout_seconds'])
        cases={c.case_id:effective(c) for c in load_cases(ROOT/'support_cases_unique40.jsonl')}
        for slot in m['run_order']:
            if slot['slot_id'] in done:continue
            if gate.request_limit is not None and gate.requests>=gate.request_limit:break
            d=out/slot['slot_id'];d.mkdir()
            write(d/'identity.json',dict(manifest_id=m['manifest_id'],slot=slot))
            r,u,check=execute_one(cases[slot['case_id']],slot['policy'],client,gate,d)
            write(d/'phase1.json',measure(r))
            write(d/'complete.json',dict(manifest_id=m['manifest_id'],slot_id=slot['slot_id'],result_sha256=sha(d/'result.json'),execution=r['status'],sanity_passed=check['passed']))
            print(slot['slot_id'],r['status'],flush=True)
            if r['status'] in ('error','budget_exhausted') or not check['passed']:break
    finally:lock.unlink()


def review_quality(items,verdicts,completed,expected):
    if not completed or not set(expected).issubset({e['issue'] for e in items}):return 'FAIL'
    rows=[verdicts.get(e['event_id'],{}) for e in items]
    if any(x.get('record_alignment')=='FAIL' for x in rows):return 'DATA_ISSUE'
    if any(x.get(k)=='FAIL' for x in rows for k in CRITERIA[1:]):return 'FAIL'
    if any(not x.get(k) or x.get(k)=='UNREVIEWED' for x in rows for k in CRITERIA):return 'UNREVIEWED'
    if any(x.get(k)=='UNCERTAIN' for x in rows for k in CRITERIA):return 'UNCERTAIN'
    return 'PASS'

def analyze(run_dir,output,review=None):
    run=Path(run_dir);out=Path(output);out.mkdir(parents=True,exist_ok=False)
    verdicts={}
    if review:
        for x in csv.DictReader(Path(review).read_text().splitlines(keepends=True)):
            if not any(x.get(k) for k in CRITERIA):continue
            if not all(x.get(k) in ('PASS','FAIL','UNCERTAIN','UNREVIEWED') for k in CRITERIA) or not all(x.get(k) for k in ('reviewer','review_timestamp','rationale')):raise ValueError('Incomplete human review metadata/criteria')
            if x['event_id'] in verdicts:raise ValueError('Duplicate human review')
            verdicts[x['event_id']]=x
    cases={c.case_id:c for c in load_cases(ROOT/'support_cases_unique40.jsonl')};rows=[];export=[];seen=set()
    static={x['case_id']:x['static_applicable'] for x in applicability()}
    for p in sorted(run.glob('*/result.json')):
        r=read(p);a=read(p.parent/'answers.json');row=measure(r);row['slot_id']=p.parent.name;row['repetition']=int(p.parent.name.split('__r')[-1]) if '__r' in p.parent.name else 1;row['static_applicable']=static[r['case_id']]
        retained={e['event_id'] for e in a['retained']}
        for e in a['retained']+a['discarded_intermediate']:
            h=hashlib.sha256(e['answer'].encode()).hexdigest();seen.add(e['event_id'])
            if e['event_id'] in verdicts and verdicts[e['event_id']]['answer_sha256']!=h:raise ValueError('Reviewed answer hash mismatch')
            item=dict(slot_id=p.parent.name,run_id=r['run_id'],case_id=r['case_id'],scenario=r['fault_type'],policy=r['mode'],event_id=e['event_id'],issue=e['issue'],retained=e['event_id'] in retained,answer=e['answer'],answer_sha256=h,original_record=json.dumps(scenario_for(r['case_id'],cases[r['case_id']].user_query)['records'].get(e['issue'])),observed_record=json.dumps(e['record']),trace=str(p.parent/'trace.jsonl'),structural=row['structural_validity'],original_machine_quality=r.get('task_quality','UNREVIEWED'),**{k:'' for k in CRITERIA},human_verdict='',rationale='',reviewer='',review_timestamp='')
            export.append(item)
        row['final_answer_quality']=review_quality(a['retained'],verdicts,r['status']=='completed',cases[r['case_id']].expected_issues)
        if row['activation']=='ACTIVATED' and row['final_answer_quality'] in ('PASS','FAIL','DATA_ISSUE'):
            row['recovery_success']=row['final_answer_quality']=='PASS' if row['policy_recovery'] else None
        rows.append(row)
    if set(verdicts)-seen:raise ValueError('Review references unknown events')
    # Preserve planned, unexecuted and partial slots when a full manifest exists.
    manifest=read(run/'manifest.json') if (run/'manifest.json').exists() else {}
    planned=manifest.get('run_order',[])
    known={x['slot_id'] for x in rows}
    for slot in planned:
        sid=slot.get('slot_id')
        if sid and sid not in known:
            c=cases[slot['case_id']];partial=run/sid/'trace.jsonl';events=[]
            if partial.exists():
                for line in partial.read_text().splitlines():
                    try:events.append(json.loads(line))
                    except ValueError:break
            row=measure(dict(case_id=c.case_id,mode=slot['policy'],fault_type=c.fault_type,status='UNKNOWN',events=events));row['slot_id']=sid;row['repetition']=slot['repetition'];row['static_applicable']=static[c.case_id];row['execution']='PARTIAL' if (run/sid).exists() else 'NOT_RUN';rows.append(row)
    for row in rows:
        row['paired_differences']={}
        for name,criterion in [('vs_unprotected',lambda x:x['case_id']==row['case_id'] and x['policy']=='unprotected'),('vs_own_clean',lambda x:x['base_case_id']==row['base_case_id'] and x['policy']==row['policy'] and x['fault_type']=='none')]:
            # Repetition is explicit in full slot IDs; smoke has exactly one per pair.
            candidates=[x for x in rows if criterion(x) and (('__r' not in row['slot_id']) or x['slot_id'].split('__r')[-1]==row['slot_id'].split('__r')[-1])]
            base=candidates[0] if len(candidates)==1 else None
            values={}
            for metric in ('model_calls','business_tool_calls','verification_calls','e2e_latency_ms'):
                a=row['metrics'].get(metric);b=base['metrics'].get(metric) if base else None
                values[metric]={'delta':a-b if a is not None and b is not None else None,'percent':100*(a/b-1) if a is not None and b not in (None,0) else None}
            for metric in ('input_tokens','output_tokens','total_tokens'):
                a=row['metrics'].get('provider_usage',{}).get(metric);b=base['metrics'].get('provider_usage',{}).get(metric) if base else None
                values[metric]={'delta':a-b if a is not None and b is not None else None,'percent':100*(a/b-1) if a is not None and b not in (None,0) else None}
            row['paired_differences'][name]=values
    write(out/'measurements.json',rows)
    from collections import Counter
    draft_counts={part:dict(Counter(review_quality([{'event_id':x['event_id'],'issue':x['issue']}],verdicts,True,[x['issue']]) for x in export if part=='all' or x['retained']==(part=='retained'))) for part in ('all','retained','discarded')}
    write(out/'aggregate.json',{'draft_quality':draft_counts,'all':rates(rows),'by_taxonomy':{cat:rates([r for r in rows if r['taxonomy'] in ('control',cat)]) for cat in ('accidental_modelled','adversarial')},'review_source':str(review) if review else None,'review_sha256':sha(review) if review else None})
    if export:
        with (out/'review_template.csv').open('x',newline='') as f:w=csv.DictWriter(f,fieldnames=list(export[0]));w.writeheader();w.writerows(export)
    write(out/'source_hashes.json',{str(p.relative_to(run)):sha(p) for p in run.rglob('*') if p.is_file() and out not in p.parents and 'analysis' not in p.parts})
    return rows

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='cmd',required=True)
    ap=sub.add_parser('applicability');ap.add_argument('--output',required=True)
    prep=sub.add_parser('prepare');prep.add_argument('--config',required=True);prep.add_argument('--output',required=True)
    ex=sub.add_parser('execute');ex.add_argument('--manifest',required=True);ex.add_argument('--output',required=True);ex.add_argument('--resume',action='store_true')
    an=sub.add_parser('analyze');an.add_argument('--run-dir',required=True);an.add_argument('--output',required=True);an.add_argument('--reviews')
    a=p.parse_args()
    if a.cmd=='applicability':write(a.output,applicability())
    elif a.cmd=='prepare':prepare(a.config,a.output)
    elif a.cmd=='execute':execute(a.manifest,a.output,a.resume)
    else:analyze(a.run_dir,a.output,a.reviews)
if __name__=='__main__':main()
