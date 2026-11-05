"""Read-only verification of the frozen handoff; never constructs a provider client."""
import argparse
import json
from collections import Counter
from pathlib import Path
from infrastructure_continuation import validate_plan, tree_hashes, infrastructure_accounting
from run_recovery_smoke_pilot import sanity
from workflow2_phase1 import read, sha, validate_manifest


def verify(run_dir, require_complete=False):
    out=Path(run_dir);m=read(out/'manifest.json')
    plan=validate_plan(out/'continuation_plan.json',out,m)
    validate_manifest(m,source_hashes=plan['source_hashes'])
    slots=m['run_order']
    assert len(slots)==240 and len({(s['base_case_id'],s['scenario'],s['policy'],s['repetition']) for s in slots})==240, 'Schedule must contain 240 unique slots'
    counts=Counter()
    for slot in slots:
        d=out/slot['slot_id']
        if not d.exists():counts['unstarted']+=1;continue
        if not (d/'complete.json').exists():counts['partial']+=1;continue
        receipt=read(d/'complete.json');result=read(d/'result.json')
        assert receipt['manifest_id']==m['manifest_id'] and receipt['slot_id']==slot['slot_id'], 'Receipt identity mismatch'
        assert receipt['result_sha256']==sha(d/'result.json'), 'Result hash mismatch'
        assert result['case_id']==slot['case_id'] and result['mode']==slot['policy'], 'Result identity mismatch'
        assert receipt['execution']==result['status'], 'Execution status mismatch'
        assert receipt['sanity_passed'] and read(d/'logging_sanity.json')['passed'], 'Recorded sanity failure'
        assert sanity(result,read(d/'provider_usage.json'))['passed'], 'Provider accounting mismatch'
        counts[result['status']]+=1
    archive=out/plan['archive_relative_path']
    original=archive if archive.exists() else out/plan['slot_id']
    assert tree_hashes(original)==plan['original_evidence'], 'Original interrupted evidence changed'
    summary=dict(planned=240,counts=dict(counts),valid_execution_outcomes=counts['completed']+counts['failed'],
        archived_infrastructure_attempts=len(infrastructure_accounting(out)),
        answer_quality='Execution completion is not an answer-quality PASS; human review remains required.')
    print(json.dumps(summary,indent=2))
    if require_complete and summary['valid_execution_outcomes']!=240:
        raise SystemExit('INCOMPLETE: errors, partial or unstarted slots are not valid completed experimental outcomes')
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run-dir',required=True);p.add_argument('--require-complete',action='store_true')
    a=p.parse_args();verify(a.run_dir,a.require_complete)
