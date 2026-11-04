"""Explicit infrastructure retry authorization; no provider calls during preparation."""
import argparse
from pathlib import Path
from workflow2_phase1 import ROOT, read, write, sha, sources, validate_manifest

ALLOWED_CHANGES = {'workflow2_phase1.py', 'run_recovery_smoke_pilot.py'}

def tree_hashes(folder):
    return {str(p.relative_to(folder)): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}

def prepare_continuation(run_dir, slot_id, output):
    out = Path(run_dir)
    if (out/'.execution.lock').exists():
        raise ValueError('Execution lock exists; do not prepare while running')
    m = read(out/'manifest.json')
    current = sources()
    changed = {n for n,h in m['source_hashes'].items() if current.get(n) != h}
    if not changed <= ALLOWED_CHANGES:
        raise ValueError('Experimental source/data drift: '+str(sorted(changed)))
    validate_manifest(m, source_hashes=current)
    if slot_id not in {s['slot_id'] for s in m['run_order']}:
        raise ValueError('Unknown slot')
    # All other existing slots must be valid terminal experimental outcomes.
    completed = []
    for slot in m['run_order']:
        sid = slot['slot_id']; d = out/sid
        if not d.exists():
            continue
        r = read(d/'complete.json')
        if r['manifest_id'] != m['manifest_id'] or r['slot_id'] != sid or r['result_sha256'] != sha(d/'result.json'):
            raise ValueError('Receipt mismatch')
        if not r['sanity_passed']:
            raise ValueError('Sanity failure requires separate investigation')
        if sid == slot_id:
            usage = read(d/'provider_usage.json')
            if r['execution'] != 'error' or not any(x.get('error_type') == 'RateLimitError' and x.get('status_code') == 429 for x in usage):
                raise ValueError('This protocol only authorizes a recorded RateLimitError/429')
        elif r['execution'] not in ('completed','failed'):
            raise ValueError('Additional unresolved infrastructure slot: '+sid)
        else:
            completed.append(sid)
    d = out/slot_id
    if not d.exists():
        raise ValueError('Missing interrupted slot')
    plan = dict(schema='workflow2-infrastructure-continuation-v1',manifest_id=m['manifest_id'],
        manifest_sha256=sha(out/'manifest.json'),slot_id=slot_id,
        original_evidence=tree_hashes(d),completed_evidence={sid:tree_hashes(out/sid) for sid in completed},
        completed_slots=len(completed),unstarted_slots=len(m['run_order'])-len(completed)-1,
        archive_relative_path='_infrastructure_attempts/'+slot_id+'/attempt_001',
        source_hashes=current,continuation_code_sha256=sha(ROOT/'infrastructure_continuation.py'),
        source_changes={n:dict(before=m['source_hashes'][n],after=current[n]) for n in sorted(changed)},
        semantics='One explicitly authorized infrastructure re-execution, distinct from experimental full_restart. Original attempt remains separately accounted. No automatic provider retries; a new error stops execution and requires a new decision.',
        cause='HTTP 429 / RateLimitError; original provider code/message/Retry-After absent; temporary limiting versus exhausted quota undetermined')
    write(output,plan)
    return plan

def validate_plan(path, out, m):
    plan = read(path)
    if plan['manifest_id'] != m['manifest_id'] or plan['manifest_sha256'] != sha(out/'manifest.json'):
        raise ValueError('Continuation manifest mismatch')
    if plan['source_hashes'] != sources() or plan['continuation_code_sha256'] != sha(ROOT/'infrastructure_continuation.py'):
        raise ValueError('Continuation source drift')
    changed={n for n,h in m['source_hashes'].items() if plan['source_hashes'].get(n)!=h}
    if not changed <= ALLOWED_CHANGES:
        raise ValueError('Unauthorized experimental source drift')
    sid=plan['slot_id']
    if sid not in {s['slot_id'] for s in m['run_order']} or plan['archive_relative_path'] != '_infrastructure_attempts/'+sid+'/attempt_001':
        raise ValueError('Invalid archive identity')
    for name, hashes in plan['completed_evidence'].items():
        if tree_hashes(out/name) != hashes:
            raise ValueError('Completed evidence changed: '+name)
    return plan

def archive_interruption(out, plan):
    """Called under the execution lock; atomic rename preserves every original byte."""
    original=out/plan['slot_id']; archive=out/plan['archive_relative_path']
    if archive.exists():
        if tree_hashes(archive) != plan['original_evidence']:
            raise ValueError('Archived evidence changed')
        # Never archive a second failed retry under the same authorization.
        return
    if tree_hashes(original) != plan['original_evidence']:
        raise ValueError('Interrupted evidence changed')
    archive.parent.mkdir(parents=True,exist_ok=True)
    original.rename(archive)

def infrastructure_accounting(out):
    rows=[]
    for p in sorted(out.glob('_infrastructure_attempts/*/*/result.json')):
        r=read(p); usage=read(p.parent/'provider_usage.json')
        rows.append(dict(slot_id=p.parent.parent.name,archive=str(p.parent.relative_to(out)),
            run_id=r['run_id'],execution=r['status'],experimental_policy=r['mode'],
            infrastructure_attempt=True,metrics=r['metrics'],provider_usage=usage,
            note='Excluded from primary experimental outcomes; include separately in total operational usage. Missing failed-request usage is unknown, not zero.'))
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-dir',required=True);p.add_argument('--slot',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();plan=prepare_continuation(a.run_dir,a.slot,a.output)
    print('Prepared offline:',plan['completed_slots'],'terminal slots, 1 infrastructure retry,',plan['unstarted_slots'],'unstarted slots')
