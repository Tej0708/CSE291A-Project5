"""Frozen formal QA study: prepare and evaluate offline; execute is explicit."""
import argparse
import hashlib
import json
import random
from pathlib import Path

from csa_workflow.dataset import load_cases
from csa_workflow.taxonomy import ISSUE_ROUTE
from formal_observer import PROFILE, ProviderClient, observe

PILOT = Path('results/workflow2_step3_pilot_local_20261102_120737/selected_case_manifest.json')
DATASET = 'support_cases_unique40.jsonl'
SEED = 20261102


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    with Path(path).open('x') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def prepare(output):
    pilot = json.loads(PILOT.read_text())
    cases = load_cases(DATASET)
    clean = sorted((c for c in cases if c.fault_type=='none' and
                    {ISSUE_ROUTE[i] for i in c.expected_issues}=={'technical','billing'}),key=lambda c:c.case_id)
    if len(clean)!=20:
        raise ValueError(f'Dataset-derived mixed-case count is {len(clean)}, expected 20; investigate before freezing')
    rng=random.Random(SEED)
    rng.shuffle(clean)
    orders=['clean']*10+['fault']*10
    rng.shuffle(orders)
    selection=[]; runs=[]
    for c,first in zip(clean,orders):
        base=c.case_id.rsplit('-',1)[0]
        matches=[f for f in cases if f.case_id==base+'-QA_CORRUPTION']
        if len(matches)!=1: raise ValueError(f'Missing or duplicate fault variant: {base}')
        f=matches[0]
        assert (c.user_query,c.expected_issues,c.max_iterations)==(f.user_query,f.expected_issues,f.max_iterations)
        selection.append(dict(base_id=base,clean_id=c.case_id,fault_id=f.case_id,
                              expected_issues=c.expected_issues,max_iterations=c.max_iterations,first=first,
                              clean_original_config=c.fault_config,fault_original_config=f.fault_config))
        for condition in (first,'fault' if first=='clean' else 'clean'):
            case=c if condition=='clean' else f
            runs.append(dict(sequence=len(runs)+1,run_id=f'formal-v1-{base}-{condition}',
                             base_id=base,case_id=case.case_id,condition=condition,max_iterations=case.max_iterations))
    sources=[*Path('csa_workflow').glob('*.py'),Path('csa_workflow/scenario_records.json'),
             Path(DATASET),PILOT,Path('BASELINE_EVALUATION_RULES.md'),
             Path('run_fault_audit.py'),Path('formal_observer.py'),Path(__file__).resolve(),
             Path('test_formal_experiment.py'),Path('human_review_tool/review_app.py'),
             Path('codex_preliminary_reviews/v3_20261102_111235_89734943_support-human-v1/rubric_snapshot.json')]
    sources += sorted(Path('formal_experiment').glob('*.schema.json'))
    sources.append(Path('formal_experiment/PLAN.md'))
    root=Path.cwd()
    hashes={str(p.resolve().relative_to(root)):digest(p) for p in sources}
    # Freeze only if the actual workflow still matches the successful pilot.
    for path,expected in pilot['source_hashes'].items():
        if path.startswith('csa_workflow/') or path==DATASET:
            if digest(path)!=expected: raise ValueError(f'Pilot setup drift: {path}')
    manifest=dict(version='formal-qa-v1',dataset=DATASET,dataset_rows=len(cases),
                  mixed_case_count=len(clean),planned_run_count=len(runs),shuffle_seed=SEED,
                  shuffle_algorithm='Python random.Random(seed): shuffle sorted clean cases, then shuffle 10 clean/10 fault first labels',
                  model=pilot['model'],temperature=pilot['temperature'],
                  generation_settings=pilot['generation_settings'],transport=pilot['transport'],
                  profile=PROFILE,selection=selection,runs=runs,source_hashes=hashes,
                  execution='serial, adjacent pairs, fresh client/workflow/injector/observer per run; no retries; stop on first runtime error',
                  retention='Keep skipped/ineligible/error/not_attempted slots; no replacement or outcome-dependent reruns',
                  results_root='results/workflow2_formal_v1',evaluation_rules='BASELINE_EVALUATION_RULES.md')
    write(output,manifest)
    write(str(output)+'.sha256',dict(sha256=digest(output)))
    return manifest


def verify(path):
    manifest=json.loads(Path(path).read_text())
    assert digest(path)==json.loads(Path(str(path)+'.sha256').read_text())['sha256'], 'Manifest changed'
    for source,expected in manifest['source_hashes'].items():
        assert digest(source)==expected, f'Frozen source changed: {source}'
    return manifest


def execute(manifest_path, output):
    manifest=verify(manifest_path)
    output=Path(output)
    if output.resolve().parent != Path('results').resolve() or not output.name.startswith('workflow2_formal_'):
        raise ValueError('Use a new results/workflow2_formal_* directory, separate from pilot data')
    output.mkdir(exist_ok=False)
    write(output/'manifest.json',manifest)
    cases={c.case_id:c for c in load_cases(manifest['dataset'])}
    slots=[dict(r,status='not_attempted') for r in manifest['runs']]
    # Each update is an append-only journal, including outstanding planned slots.
    write(output/'schedule.json',slots)
    with (output/'execution.jsonl').open('x') as journal:
        for slot in slots:
            folder=output/slot['run_id'];folder.mkdir()
            try:
                client=ProviderClient(model=manifest['model'],temperature=manifest['temperature'])
                client._client=client._client.with_options(max_retries=0,timeout=120)
                result=observe(cases[slot['case_id']],client,folder,slot['condition'],slot['run_id'])
                slot['status']=result['run_status']
            except Exception as exc:
                slot.update(status='error',error_type=type(exc).__name__)
                write(folder/'initialization_error.json',slot)
            journal.write(json.dumps(slot)+'\n');journal.flush()
            if slot['status']=='error': break
    write(output/'execution_status.json',slots)


def evaluate(manifest_path, run_dir, output, assessments=None):
    """Offline structural extraction and frozen review aggregation; never judges prose."""
    from human_review_tool.review_app import summarize, blank_review
    manifest=verify(manifest_path)
    run_dir=Path(run_dir);out=Path(output);out.mkdir(parents=True,exist_ok=False)
    reviews=json.loads(Path(assessments).read_text()) if assessments else {}
    items=[];cases=[];metrics=[];template={}
    for slot in manifest['runs']:
        path=run_dir/slot['run_id']/'result.json'
        if not path.exists():
            metrics.append(dict(**slot,run_status='not_attempted_or_initialization_error',result_path=str(path)))
            cases.append(dict(case_id=slot['run_id'],expected_issues=next(s['expected_issues'] for s in manifest['selection'] if s['base_id']==slot['base_id']),
                              expected_issues_known=True,latest={},run_status='not_attempted',checks={}))
            continue
        r=json.loads(path.read_text())
        if (r['run_id'],r['case_id'],r['condition']) != (slot['run_id'],slot['case_id'],slot['condition']):
            raise ValueError(f'Result does not match frozen slot: {path}')
        trace=[json.loads(l) for l in path.with_name('trace.jsonl').read_text().splitlines()]
        result=r.get('result') or {};latest={}
        for draft in r['drafts']:
            key=draft['draft_id'];latest[draft['issue']]=key
            items.append(dict(key=key,case_id=slot['run_id'],**draft))
            template[key]={**blank_review(),'reviewer':None,'provenance':'UNREVIEWED','rule_references':[],'evidence_quote':None}
        expected=next(s['expected_issues'] for s in manifest['selection'] if s['base_id']==slot['base_id'])
        cases.append(dict(case_id=slot['run_id'],expected_issues=expected,expected_issues_known=bool(expected),
                          latest=latest,run_status=r['run_status'] if result.get('final_status')=='resolved' else 'unsuccessful',checks={}))
        routes=[e for e in trace if e['event']=='router_selection']
        repeated=[e for e in routes if e['selected_was_resolved']]
        mutations=[e for e in r.get('events',[]) if e['effective_mutation']]
        after=min((e['iteration'] for e in mutations),default=None)
        subsequent=[e for e in routes if after is not None and e['iteration']>after and e['selected_issue'] in e['unresolved_at_input']]
        repeated_ids={e['event_id'] for e in repeated}
        helpers=[e for e in trace if e['event']=='helper_start' and any(d in repeated_ids for d in e['depends_on'])]
        helper_ids={e['event_id'] for e in helpers}
        metrics.append(dict(**slot,run_status=r['run_status'],eligibility=r.get('eligible') if slot['condition']=='fault' else None,
            skip_reasons=r.get('skip_reasons'),mutation_count=r.get('actual_mutation_count'),router_receipt=r.get('effective_consumed'),
            repeated_helper_calls=len(helpers),repeated_tool_calls=sum(e['event']=='tool_request' and any(d in helper_ids for d in e['depends_on']) for e in trace),
            affected_stages=sorted({e['stage'] for e in trace if after is not None and e['iteration']>after}),
            subsequent_unresolved_work=subsequent,ledger_completion=result.get('final_status'),iterations=result.get('iterations'),
            model_calls=r['model_calls'],tool_calls=r['tool_calls'],provider_tokens=r['provider_tokens'],elapsed_seconds=r['elapsed_seconds'],
            error_type=r.get('error_type'),injection_events=r.get('events',[]),
            affected_stage_note='Observed post-mutation stages, not proof of causal difference from clean'))
    unknown=set(reviews)-set(template)
    if unknown: raise ValueError(f'Unknown draft assessment IDs: {sorted(unknown)}')
    for key,review in reviews.items():
        for criterion in ('record_alignment','relevance','grounding','coverage','status_responsibility'):
            if review.get(criterion) not in ('PASS','FAIL','UNCERTAIN','UNREVIEWED'): raise ValueError(f'Invalid criterion for {key}')
        if any(review[k] in ('FAIL','UNCERTAIN') for k in ('record_alignment','relevance','grounding','coverage','status_responsibility')) and not review.get('notes'):
            raise ValueError(f'FAIL/UNCERTAIN needs notes: {key}')
        if not review.get('reviewer') or not review.get('provenance'): raise ValueError(f'Review provenance required: {key}')
    stats,drafts,latest=summarize(dict(items=items,cases=cases),reviews)
    pairs=[]
    for selection in manifest['selection']:
        pair=[m for m in metrics if m['base_id']==selection['base_id']]
        clean=next(m for m in pair if m['condition']=='clean')
        fault=next(m for m in pair if m['condition']=='fault')
        complete=all(m['run_status']=='completed' for m in pair)
        deltas={k:fault[k]-clean[k] if complete and clean.get(k) is not None and fault.get(k) is not None else None
                for k in ('iterations','model_calls','tool_calls','elapsed_seconds')}
        for k in ('prompt_tokens','completion_tokens','total_tokens'):
            a=clean.get('provider_tokens',{}).get(k,{}).get('total')
            b=fault.get('provider_tokens',{}).get(k,{}).get('total')
            deltas[k]=b-a if complete and a is not None and b is not None else None
        pairs.append(dict(base_id=selection['base_id'],clean_run_id=clean['run_id'],fault_run_id=fault['run_id'],
                          pair_complete=complete,deltas=deltas))
    write(out/'paired_results.json',pairs)
    write(out/'metrics.json',metrics);write(out/'assessment_template.json',template)
    write(out/'all_draft_quality.json',drafts);write(out/'latest_answer_quality.json',latest)
    write(out/'quality_summary.json',stats)
    write(out/'evaluation_provenance.json',dict(rules_sha256=digest('BASELINE_EVALUATION_RULES.md'),
        assessments_sha256=digest(assessments) if assessments else None,
        note='Ledger diagnostics separate; all-draft helper statistics separate from latest-per-issue case scoring. No automated semantic labels.'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare');a.add_argument('--output',default='formal_experiment/manifest.json')
    a=sub.add_parser('verify');a.add_argument('--manifest',default='formal_experiment/manifest.json')
    a=sub.add_parser('execute');a.add_argument('--manifest',default='formal_experiment/manifest.json');a.add_argument('--output',required=True)
    a=sub.add_parser('evaluate');a.add_argument('--manifest',default='formal_experiment/manifest.json');a.add_argument('--run-dir',required=True);a.add_argument('--output',required=True);a.add_argument('--assessments')
    args=p.parse_args()
    if args.command=='prepare': print(json.dumps({k:v for k,v in prepare(args.output).items() if k in ('mixed_case_count','planned_run_count')}))
    elif args.command=='verify': verify(args.manifest);print('Frozen hashes verified; no execution.')
    elif args.command=='execute': execute(args.manifest,args.output)
    else: evaluate(args.manifest,args.run_dir,args.output,args.assessments)

if __name__=='__main__': main()
