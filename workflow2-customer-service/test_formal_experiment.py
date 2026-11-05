import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from csa_workflow.dataset import load_cases
from csa_workflow.llm import OpenAIClient
from csa_workflow import agents, services
from formal_observer import observe, ProviderClient
from run_fault_audit import audit, ScriptedLLM


class CapturingScript(ScriptedLLM):
    def __init__(self, issues):
        super().__init__(issues)
        self.requests = []
    def complete(self, system, user):
        self.requests.append((system,user))
        return super().complete(system,user)


class FormalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {c.case_id:c for c in load_cases('support_cases_unique40.jsonl')}

    def run_observed(self, case, client, condition):
        with tempfile.TemporaryDirectory() as tmp:
            report = observe(case, client, Path(tmp), condition)
            events = [json.loads(l) for l in (Path(tmp)/'trace.jsonl').read_text().splitlines()]
        return report, events

    def test_equivalence_all_cases_both_orders_and_conditions(self):
        # No SDK instantiation or network path is reachable in these fixtures.
        for case in self.cases.values():
            if case.fault_type not in ('none','qa_corruption'): continue
            for issues in (case.expected_issues,list(reversed(case.expected_issues))):
                condition = 'clean' if case.fault_type=='none' else 'fault'
                with self.subTest(case=case.case_id, issues=issues):
                    a,b = CapturingScript(issues),CapturingScript(issues)
                    plain = audit(case,a,profile='qa_first_missing_once_v1' if condition=='fault' else None)
                    report,events = self.run_observed(case,b,condition)
                    self.assertEqual(plain['result'],report['result'])
                    for key in ('eligible','actual_mutation_count','effective_consumed','behavioral_effect','skip_reasons'):
                        self.assertEqual(plain[key],report[key])
                    self.assertEqual(a.requests,b.requests)
                    ids={e['event_id'] for e in events}
                    self.assertEqual(len(ids),len(events))
                    self.assertTrue(all(d in ids for e in events for d in e['depends_on']))
                    for e in events:
                        if e['event']=='model_request':
                            expected = ('classification' if 'classifier' in e['system_prompt'] else
                                        'qa' if 'QA routing reviewer' in e['system_prompt'] else 'helper_')
                            self.assertTrue(e['stage'].startswith(expected))
                            self.assertEqual(e['iteration']==0,expected=='classification')
                        if e['event']=='tool_request':
                            self.assertTrue(e['stage'].startswith('helper_'))
                            self.assertGreater(e['iteration'],0)
                    for e in events:
                        if e['event']=='router_input' and e['iteration']>1:
                            qa=next(x for x in events if x['event']=='qa_feedback' and x['iteration']==e['iteration']-1)
                            self.assertEqual(e['feedback'],qa['feedback'])
                            self.assertEqual(e['depends_on'],[qa['event_id']])
                    requests=[e for e in events if e['event'] in ('model_request','tool_request')]
                    self.assertEqual(len({e['call_id'] for e in requests}),len(requests))
                    routes=[e for e in events if e['event']=='router_selection']
                    self.assertEqual(len(routes),report['result']['iterations'])
                    actions=[e for e in events if e['event']=='workflow_action' and e['action']=='route']
                    self.assertEqual([r['selected_issue'] for r in routes],[a['details']['issue'] for a in actions])
                    self.assertTrue(all(a['depends_on']==[r['event_id']] for a,r in zip(actions,routes)))
                    self.assertEqual(report['provider_tokens']['total_tokens']['total'],None)

    def test_isolation_skip_and_restoration(self):
        originals=(agents.RouterAgent.decide,agents.QAAgent.review,services.call_tool)
        case=self.cases['BASE-0003-QA_CORRUPTION']
        one,e1=self.run_observed(case,ScriptedLLM(case.expected_issues),'fault')
        two,e2=self.run_observed(case,ScriptedLLM(case.expected_issues),'fault')
        self.assertEqual(one['actual_mutation_count'],1)
        self.assertEqual(two['actual_mutation_count'],1)
        self.assertEqual(one['result']['iterations'],3)
        self.assertNotEqual(one['run_id'],two['run_id'])
        self.assertTrue({e['event_id'] for e in e1}.isdisjoint(e['event_id'] for e in e2))
        skip=self.cases['BASE-0006-QA_CORRUPTION']
        result,_=self.run_observed(skip,ScriptedLLM(skip.expected_issues),'fault')
        self.assertFalse(result['eligible'])
        self.assertEqual(result['actual_mutation_count'],0)
        self.assertIn('no_missing_issue',result['skip_reasons'])
        self.assertEqual(originals,(agents.RouterAgent.decide,agents.QAAgent.review,services.call_tool))

    def test_error_and_missing_zero_usage(self):
        case=self.cases['BASE-0003-NONE']
        class Zero(ScriptedLLM):
            last_metadata={'usage':{'total_tokens':0,'prompt_tokens':0,'completion_tokens':0,'details':{'cached':0}}}
        result,_=self.run_observed(case,Zero(case.expected_issues),'clean')
        self.assertEqual(result['provider_tokens']['total_tokens']['total'],0)
        self.assertEqual(result['usage_records'][0]['usage']['details'],{'cached':0})
        class Broken:
            def complete(self,*args): raise RuntimeError('fixture')
        result,events=self.run_observed(case,Broken(),'clean')
        self.assertEqual(result['run_status'],'error')
        self.assertEqual(result['model_calls'],1)
        self.assertIsNone(result['provider_tokens']['total_tokens']['total'])
        self.assertEqual(events[1]['stage'],'classification')
        result,_=self.run_observed(case,ScriptedLLM(case.expected_issues),'clean')
        self.assertEqual(result['run_status'],'completed')
        class FailHelper(ScriptedLLM):
            def complete(self,system,user):
                if 'helper agent' in system: raise RuntimeError('helper fixture')
                return super().complete(system,user)
        failed,events=self.run_observed(case,FailHelper(case.expected_issues),'clean')
        self.assertEqual(failed['tool_calls'],1)
        call=next(e for e in events if e['event']=='model_result' and e['status']=='error')
        self.assertEqual(call['iteration'],1)
        self.assertTrue(call['stage'].startswith('helper_'))
        class MissingField(ScriptedLLM):
            last_metadata={'usage':{'prompt_tokens':0,'completion_tokens':0}}
        partial,_=self.run_observed(case,MissingField(case.expected_issues),'clean')
        self.assertIsNone(partial['provider_tokens']['total_tokens']['total'])
        self.assertEqual(partial['provider_tokens']['prompt_tokens']['total'],0)


    def test_manifest_and_offline_evaluation(self):
        from run_formal_experiment import prepare, verify, evaluate
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);manifest=root/'manifest.json'
            m=prepare(manifest)
            self.assertEqual(m['mixed_case_count'],20)
            self.assertEqual(len(m['runs']),40)
            self.assertEqual(sum(c['first']=='clean' for c in m['selection']),10)
            self.assertEqual(verify(manifest),m)
            output=root/'fixtures';output.mkdir()
            for slot in m['runs']:
                case=self.cases[slot['case_id']]
                folder=output/slot['run_id'];folder.mkdir()
                observe(case,ScriptedLLM(case.expected_issues),folder,slot['condition'],slot['run_id'])
            evaluate(manifest,output,root/'evaluation')
            stats=json.loads((root/'evaluation/quality_summary.json').read_text())
            self.assertEqual(stats['case_verdicts']['UNREVIEWED'],40)
            self.assertIsNone(stats['task_success_rate'])
            metrics=json.loads((root/'evaluation/metrics.json').read_text())
            self.assertEqual(sum(m['mutation_count'] for m in metrics),20)
            self.assertEqual(sum(m['repeated_tool_calls'] for m in metrics),20)
            reviews=json.loads((root/'evaluation/assessment_template.json').read_text())
            for r in reviews.values():
                for k in ('record_alignment','relevance','grounding','coverage','status_responsibility'): r[k]='PASS'
                r.update(reviewer='fixture',provenance='synthetic test, not a quality judgment')
            slot=next(s for s in m['runs'] if s['condition']=='fault')
            result=json.loads((output/slot['run_id']/'result.json').read_text())
            reviews[result['drafts'][0]['draft_id']].update(grounding='FAIL',notes='Synthetic superseded failure')
            review_path=root/'reviews.json';review_path.write_text(json.dumps(reviews))
            evaluate(manifest,output,root/'reviewed',review_path)
            stats=json.loads((root/'reviewed/quality_summary.json').read_text())
            self.assertEqual(stats['case_verdicts']['PASS'],40)
            self.assertEqual(stats['helper_answer_verdicts']['FAIL'],1)
            for slot in m['runs']:
                result=json.loads((output/slot['run_id']/'result.json').read_text())
                schema=json.loads(Path('formal_experiment/result.schema.json').read_text())
                self.assertFalse(set(schema['required'])-set(result))

    def test_provider_request_identical_without_sdk(self):
        requests=[]
        usage={'total_tokens':0,'extra_provider_detail':{'cached_tokens':0}}
        response=SimpleNamespace(usage=SimpleNamespace(model_dump=lambda:usage),id='fixture',model='fixture',
                                 choices=[SimpleNamespace(message=SimpleNamespace(content='answer'),finish_reason='stop')])
        def create(**kw): requests.append(kw); return response
        for cls in (OpenAIClient,ProviderClient):
            client=object.__new__(cls)
            client.model='api-glm-5.3-flash';client.temperature=0.0
            client._client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
            self.assertEqual(client.complete('system','user'),'answer')
        self.assertEqual(requests[0],requests[1])
        self.assertEqual(client.last_metadata['usage'],usage)

if __name__=='__main__': unittest.main()
