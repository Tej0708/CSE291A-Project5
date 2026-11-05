"""Reproduce offline preparation only; no provider dispatch is permitted."""
import argparse, csv, hashlib, json, os, shutil, socket, subprocess, sys
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

p = argparse.ArgumentParser()
p.add_argument('--source', required=True)
p.add_argument('--output', required=True)
a = p.parse_args()
src = Path(a.source).resolve()
out = Path(a.output).resolve()
out.mkdir(parents=True, exist_ok=False)
os.chdir(src)
sys.path.insert(0, str(src))
sys.dont_write_bytecode = True
from csa_workflow.dataset import load_cases
from csa_workflow.services import scenario_for, call_tool
from csa_workflow.taxonomy import ISSUE_ROUTE
from csa_workflow.recovery import run_recovery_case, RunBudget
from csa_workflow.cost_metrics import summarize
from run_fault_audit import ScriptedLLM

def save(name, obj):
    path = out/name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=True)+'\n')

def git(*args):
    return subprocess.check_output(['git', *args], cwd=src, text=True).strip()

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

assert git('branch', '--show-current') == 'codex/workflow2-cost-accounting'
paths = sorted(set(git('ls-files').splitlines()+git('ls-files','--others','--exclude-standard').splitlines()))
source_hashes = {n:digest(src/n) for n in paths if (src/n).is_file() and not n.endswith(('.pyc','.DS_Store')) and n != '.env'}
status_before = git('status','--short')
for name in ['csa_workflow/recovery.py','csa_workflow/provider_accounting.py','csa_workflow/cost_metrics.py','csa_workflow/llm.py','COST_ACCOUNTING.md','accounting_validation/REPORT.md','BASELINE_EVALUATION_RULES.md']:
    dest = out/'source_snapshot'/name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src/name, dest)
(out/'source_snapshot'/'uncommitted.patch').write_text(git('diff','--','csa_workflow/recovery.py')+'\n')
rows = {c.case_id:c for c in load_cases(src/'support_cases_unique40.jsonl')}
suffixes = ['NONE','QA_CORRUPTION','HELPER_CORRUPTION','TIMEOUT']
cases = [rows['BASE-0004-'+s] for s in suffixes]
cases[1] = replace(cases[1], fault_config={'profile':'qa_first_missing_once_v1','target_stage':'qa_to_router'})
clean=cases[0]
scenario=scenario_for(clean.case_id,clean.user_query)
assert len(clean.expected_issues)==2
assert {ISSUE_ROUTE[i] for i in clean.expected_issues}=={'technical','billing'}
for case in cases:
    assert case.user_query==clean.user_query and case.max_iterations==clean.max_iterations
    assert scenario_for(case.case_id,case.user_query)==scenario
    for issue in clean.expected_issues:
        result=call_tool(issue,case_id=case.case_id,user_query=case.user_query)
        assert result.status=='ok' and result.record
assert cases[2].fault_config['target_agent'] in {ISSUE_ROUTE[i] for i in clean.expected_issues}
policies=['unprotected','full_restart','always_verify']
order=[{'order':n+1,'run_key':case.case_id+'__'+mode,'case_id':case.case_id,'condition':case.fault_type,'policy':mode} for n,(case,mode) in enumerate((c,m) for c in cases for m in policies)]
config_path='results/workflow2_step3_pilot_local_20261102_120737/selected_case_manifest.json'
saved=json.loads((src/config_path).read_text())
blockers=[
 'The saved pilot and unchanged OpenAIClient omit max_tokens/max_completion_tokens. The actual provider-default completion ceiling is unverified; no conservative request reservation can be established from the approved configuration.',
 'No configured USD input/output rates for the exact TritonAI api-glm-5.3-flash route were found. Public model-catalog access did not establish exact-route rates. Rates for api-glm-5.3 or another vendor are not substitutes.'
]
manifest={'status':'FROZEN_OFFLINE_PREPARATION_LIVE_BLOCKED','source_branch':git('branch','--show-current'),'source_sha':git('rev-parse','HEAD'),'source_directory':str(src),'uncommitted_changes':status_before,'source_hashes':source_hashes,'dataset_sha256':digest(src/'support_cases_unique40.jsonl'),'scenario_sha256':digest(src/'csa_workflow/scenario_records.json'),'base_case_id':'BASE-0004','selection_rationale':'Mixed incorrect-invoice and Settings-crash case; valid records and both routes. Existing strict-rubric review marks historical clean answer PASS, provisionally, not human-finalized. Selected before any provider calls; not selected on new live outcomes.','historical_review':'results/workflow2_step3_pilot_local_20261102_120737/evaluation_frozen_rubric_revision/paired_results.json','variants':[{'case_id':c.case_id,'original_fault_config':rows[c.case_id].fault_config,'effective_fault_config':c.fault_config,'max_iterations':c.max_iterations} for c in cases],'qa_profile':'qa_first_missing_once_v1','qa_profile_note':'Existing named profile requested by user; no custom trigger override. Clean has no injector fault.','model_settings':{'model':saved['model'],'temperature':saved['temperature'],'max_completion_tokens':None,'token_cap_status':'omitted/provider default unverified','timeout_seconds':saved['transport']['timeout_seconds'],'sdk_max_retries':saved['transport']['max_retries'],'pacing':'serial; no explicit sleep in saved live runner','configuration_source':config_path,'provider_host':'tritonai-api.ucsd.edu'},'budget':{'provider_requests_including_observable_retries':150,'estimated_usd':0.50,'per_run':asdict(RunBudget()),'lower_project_spend_limit':'not found in project configuration','reservation_status':'BLOCKED: missing verified rates and completion ceiling; dispatch prohibited'},'pricing':{'input_usd_per_million':None,'output_usd_per_million':None,'verified':False,'sources_checked':['https://docs.tritonai.ucsd.edu/models','https://docs.tritonai.ucsd.edu/llm-api/updates'],'note':'Official update page names the route but does not establish its rates or completion ceiling.'},'run_order':order,'planned_runs':12,'live_runs_executed':0,'blockers':blockers,'reproduction_command':f'PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/bin/python3 {Path(__file__).resolve()} --source {src} --output {out}_reproduction','reproduction_scope':'Offline preparation only. No paid execution command is provided while mandatory cost gate is unresolved.'}
save('manifest.json',manifest)
save('supporting_records.json',scenario)
checks=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden in offline preflight')):
    for spec in order:
        case=next(c for c in cases if c.case_id==spec['case_id'])
        r=run_recovery_case(case,mode=spec['policy'],llm=ScriptedLLM(clean.expected_issues),budget=RunBudget())
        save('offline/'+spec['run_key']+'/result.json',r)
        (out/'offline'/spec['run_key']/'trace.jsonl').write_text(''.join(json.dumps(e,ensure_ascii=True)+'\n' for e in r['events']))
        assert r['status']=='completed'
        assert r['actual_mutation_count']==(0 if case.fault_type=='none' else 1)
        assert summarize(r['calls'],r['recoveries'],r['events'][-1]['elapsed_ms'])==r['metrics']
        assert len({c['call_id'] for c in r['calls']})==len(r['calls'])
        for kind,metric in [('model','model_calls'),('tool','business_tool_calls'),('verification','verification_calls')]:
            terminal=[c for c in r['calls'] if c['kind']==kind and c['status']!='incomplete']
            assert len(terminal)==r['metrics'][metric]
        assert r['metrics']['tool_calls']==r['metrics']['business_tool_calls']+r['metrics']['verification_calls']
        mutations=[e for e in r['events'] if e.get('mutated')]
        if case.fault_type=='qa_corruption':
            e=mutations[0]
            assert e['before']['missing_issue'] is not None and e['before']['missing_issue']!=e['after']['missing_issue']
            assert e['iteration'] < case.max_iterations
            hist=r['attempts'][0]['history']
            validation=next(h for h in hist if h['stage']=='qa_label_validation' and h['iteration']==e['iteration'])
            assert e['before']['missing_issue'] in validation['unresolved_issues']
            assert e['after']['missing_issue'] in validation['resolved_issues']
            if spec['policy']=='always_verify': assert r['stage_retry_count']==1 and r['repeated_resolved_routes']==0
            else: assert r['repeated_resolved_routes']==1 and r['restart_count']==0
        checks.append({**spec,'backend':'SCRIPTED_OFFLINE_ONLY','structural_status':r['status'],'mutations':r['actual_mutation_count'],'restarts':r['restart_count'],'stage_retries':r['stage_retry_count'],'mutation_evidence':mutations,'ledger_reconciliation':'PASS','provider_usage':'unknown: scripted fixture, no provider calls','live_eligibility':None,'live_activation':None})
# Capture exact ledger eligibility at the existing QA hook, without altering values.
from csa_workflow.faults import FaultInjector
original=FaultInjector.on_qa_feedback
boundaries=[]
def observe(self,iteration,feedback,state=None):
    before=asdict(state) if state else None
    result=original(self,iteration,feedback,state)
    if self.last_profile_event:
        boundaries.append({'state_before':before,'before':asdict(feedback),'after':asdict(result),'profile_event':self.last_profile_event.copy()})
    return result
with patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden')), patch.object(FaultInjector,'on_qa_feedback',observe):
    # Boundary-only unit preflight, not another planned/live workflow execution.
    from csa_workflow.state import WorkflowState, IssueStatus
    from csa_workflow.faults import QAFeedback
    state=WorkflowState(clean.case_id,clean.user_query,clean.max_iterations)
    first,second=clean.expected_issues
    state.ensure_issue(first).status=IssueStatus.RESOLVED
    state.ensure_issue(second).status=IssueStatus.OPEN
    state.iteration=1
    injector=FaultInjector('qa_corruption',cases[1].fault_config)
    observe(injector,1,QAFeedback(False,second,'One issue remains open.'),state)
    assert boundaries[-1]['profile_event']['eligible']
save('offline_preflight.json',{'checks':checks,'qa_boundary_unit_check':boundaries,'note':'Expected labels used only in offline fixtures. Live activation remains unobserved. No fixture output is a live final answer.'})
fields=['order','run_key','case_id','condition','policy','execution_status','structural_status','quality','live_eligibility','actual_mutation_count','model_calls','provider_requests','business_tool_calls','verification_calls','tool_calls','input_tokens','output_tokens','total_tokens','unknown_usage_calls','e2e_latency_ms','verification_latency_ms','repair_latency_ms','discarded_calls','estimated_usd','final_answer','reason']
with (out/'summary.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for row in order:w.writerow({**row,'execution_status':'NOT_RUN_CONFIGURATION','quality':'NOT_ASSESSED','reason':'; '.join(blockers)})
review=['# Human review — pending live execution','', 'No retained or discarded live answers exist. No PASS/FAIL/UNCERTAIN quality judgment is justified. Scripted outputs are excluded. The unchanged support-human-v1 rubric and later strict interpretation are preserved in source_snapshot/BASELINE_EVALUATION_RULES.md.','', '| Planned run | Final answer | Supporting records | Provisional quality |','|---|---|---|---|']
for row in order:review.append(f"| {row['run_key']} | NOT_RUN_CONFIGURATION | supporting_records.json: incorrect_invoice and app_crash | NOT_ASSESSED |")
(out/'HUMAN_REVIEW.md').write_text('\n'.join(review)+'\n')
save('live_trace.json',{'events':[],'provider_requests':0,'estimated_spend_usd':0,'note':'No live sanity-check run was dispatched because the pre-request configuration gate failed.'})
save('preservation_check.json',{'source_files_changed':[n for n,h in source_hashes.items() if not (src/n).exists() or digest(src/n)!=h],'git_status_unchanged':status_before==git('status','--short')})
(out/'REPRODUCE.txt').write_text(manifest['reproduction_command']+'\n')
print(str(out))
print(json.dumps([{k:c[k] for k in ('run_key','mutations','restarts','stage_retries','ledger_reconciliation')} for c in checks],indent=2))
