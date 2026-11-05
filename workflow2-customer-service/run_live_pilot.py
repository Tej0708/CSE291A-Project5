"""Bounded Step 3 pilot; no workflow/prompt mutations. Execute once per new output."""
import argparse, copy, hashlib, json, time
from pathlib import Path
from dataclasses import asdict
from unittest.mock import patch
from contextlib import ExitStack
from csa_workflow import agents, services
from csa_workflow.dataset import load_cases
from csa_workflow.state import WorkflowState
from run_fault_audit import audit, ScriptedLLM
from run_clean_audit import Recorder, ObservedOpenAI, write_json, utc_now

PROFILE='qa_first_missing_once_v1'
SELECTION={'BASE-0003':'Requested anchor: duplicate charge and settings crash.',
 'BASE-0004':'Incorrect invoice and settings crash; technical issue appears first in text.',
 'BASE-0007':'Charge after cancellation and login failure; distinct technical/billing pair.',
 'BASE-0006':'Single duplicate-charge issue; expected no missing issue after first helper.'}

def hashes():
    paths=[p for p in Path('.').rglob('*') if p.is_file() and not any(x in p.parts for x in ('.git','.venv','__pycache__')) and not p.name=='.env' and not p.name=='.DS_Store']
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

def observe(case, client, folder, condition, manifest):
    rec=Recorder(folder/'trace.jsonl',case.case_id)
    if client is not None: client.recorder=rec
    rec.emit('run_metadata',condition=condition,manifest=manifest,case=case.raw)
    log,tool,review,decompose=WorkflowState.log,services.call_tool,agents.QAAgent.review,agents.RouterAgent.decompose
    snapshots=[]
    def logged(state,stage,**kw):
        log(state,stage,**kw)
        rec.emit('workflow_event',iteration=state.iteration,workflow_stage=stage,**kw)
    def called(issue_type,**kw):
        result=tool(issue_type,**kw)
        rec.emit('tool_action',issue=issue_type,arguments=kw,result=asdict(result))
        return result
    def decomposed(self,state):
        rec.stage='classification'
        decompose(self,state)
        rec.emit('classification_result',issues=list(state.issues))
    def reviewed(self,state):
        rec.iteration=state.iteration; rec.stage='qa'
        result=review(self,state)
        snap=asdict(state); snapshots.append(snap)
        rec.emit('qa_boundary',feedback=asdict(result),state=snap)
        return result
    start=time.perf_counter()
    try:
        with patch.object(WorkflowState,'log',logged), patch.object(services,'call_tool',called), patch.object(agents.QAAgent,'review',reviewed), patch.object(agents.RouterAgent,'decompose',decomposed):
            report=audit(case,client,profile=PROFILE if condition=='fault' else None)
        report['run_status']='completed'
    except Exception as exc:
        report={'run_status':'error','error_type':type(exc).__name__,'status_code':getattr(exc,'status_code',None)}
        rec.emit('runtime_error',**report)
    report.update(condition=condition,case_id=case.case_id,elapsed_seconds=time.perf_counter()-start,usage_records=rec.calls,qa_snapshots=snapshots)
    report['model_calls']=len(rec.calls)
    report['total_tokens']=sum(c['usage']['total_tokens'] for c in rec.calls) if rec.calls and all(c.get('usage') and c['usage'].get('total_tokens') is not None for c in rec.calls) else None
    report['final_answer']=None
    report['final_answer_note']='No final composition stage exists. Latest per-issue helper answers below are an observational view, not newly generated text.'
    report['latest_issue_answers']={k:next((e['content'] for e in reversed(v['evidence']) if e['source']!='support_doc'),None) for k,v in (snapshots[-1]['issues'] if snapshots else {}).items()}
    report['helper_calls']=sum(h['stage'].startswith('helper_') for h in report.get('result',{}).get('history',[]))
    report['tool_calls']=report['helper_calls']
    report['retries']=0
    rec.emit('run_result',report=report); rec.file.close()
    write_json(folder/'result.json',report)
    write_json(folder/'usage.json',rec.calls)
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    before=hashes();write_json(out/'preservation_before.json',before)
    baseline=Path('results/helper_scope_v3_full/clean_audit_20261102_111235_89734943/manifest.json')
    if not baseline.exists():
        baseline=next(Path('results/helper_scope_v3_full').rglob('manifest.json'))
    b=json.loads(baseline.read_text())
    cases=load_cases('support_cases_unique40.jsonl'); selected=[]
    for base,reason in SELECTION.items():
        clean=next(c for c in cases if c.case_id==base+'-NONE')
        fault=next(c for c in cases if c.case_id.startswith(base+'-') and c.fault_type=='qa_corruption')
        assert clean.user_query==fault.user_query and clean.max_iterations==fault.max_iterations
        selected.append((clean,fault,reason))
    manifest={'created_utc':utc_now(),'baseline_manifest':str(baseline),'model':b['requested_model'],'temperature':b['temperature'],
      'generation_settings':{'temperature':b['temperature'],'other_parameters':'omitted, provider defaults; matches baseline request'},
      'transport':{'max_retries':0,'timeout_seconds':120,'note':'No retries; stop entire pilot on first API/runtime error.'},
      'source_hashes':{k:v for k,v in before.items() if k.startswith('csa_workflow/') or k in ('run_clean_audit.py','run_fault_audit.py','run_live_pilot.py','support_cases_unique40.jsonl')},
      'selection':[{'clean_id':c.case_id,'fault_id':f.case_id,'reason':r,'max_iterations':c.max_iterations,'expected_issues':c.expected_issues} for c,f,r in selected],
      'order':'selected order, clean then fault, serial; fresh run_case state each execution',
      'decision_sources':{'model':'classification, helper prose, QA candidate while unresolved','deterministic':'classification filtering/fallback, Router selection, tools, evidence acceptance, QA label validation/reason, injector, termination'},
      'reproduction_command':f'.venv/bin/python run_live_pilot.py --execute --output {out}_reproduction'}
    write_json(out/'selected_case_manifest.json',manifest)
    # Compare observer output with uninstrumented audit using identical deterministic responses.
    checks=[]
    for c,f,_ in selected:
        for case,cond in ((c,'clean'),(f,'fault')):
            folder=out/'offline_validation'/case.case_id;folder.mkdir(parents=True)
            observed=observe(case,ScriptedLLM(case.expected_issues),folder,cond,manifest)
            plain=audit(case,ScriptedLLM(case.expected_issues),profile=PROFILE if cond=='fault' else None)
            assert observed['result']==plain['result']
            assert observed['actual_mutation_count']==plain['actual_mutation_count']
            checks.append({'case':case.case_id,'identical_result_and_mutations':True})
    write_json(out/'observer_validation.json',checks)
    if not a.execute:return
    try:
        client=ObservedOpenAI(model=b['requested_model'],temperature=b['temperature'])
        client._client=client._client.with_options(max_retries=0,timeout=120)
    except Exception as exc:
        write_json(out/'blocker.json',{'error_type':type(exc).__name__});return
    reports=[]
    for clean,fault,_ in selected:
        for case,condition in ((clean,'clean'),(fault,'fault')):
            folder=out/'live'/case.case_id;folder.mkdir(parents=True)
            report=observe(case,client,folder,condition,manifest);reports.append(report)
            print(case.case_id,report['run_status'],report.get('result',{}).get('iterations'),flush=True)
            write_json(out/'run_results.json',reports)
            if report['run_status']=='error':break
        if reports[-1]['run_status']=='error':break
    write_json(out/'preservation_check.json',{'checked_files':len(before),'changed_preexisting_files':[k for k,v in before.items() if not Path(k).exists() or hashlib.sha256(Path(k).read_bytes()).hexdigest()!=v]})
if __name__=='__main__':main()
