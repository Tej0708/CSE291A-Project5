"""Offline only: every SDK response is mocked and socket connects are forbidden."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import run_recovery_smoke_pilot as pilot
from csa_workflow.llm import OpenAIClient
from csa_workflow.recovery import BudgetExceeded
from run_fault_audit import ScriptedLLM


CFG = dict(model='api-glm-5.3-flash', provider_host='tritonai-api.ucsd.edu',
    verified=True, verified_at='OFFLINE_FIXTURE', pricing_source='MOCK_ONLY',
    limits_source='MOCK_ONLY', input_usd_per_million='1', output_usd_per_million='2',
    input_token_ceiling=10000, completion_cap=100, completion_cap_parameter='max_tokens')


class FakeUsage:
    prompt_tokens=12
    completion_tokens=7
    total_tokens=19
    def model_dump(self):
        return dict(prompt_tokens=12,completion_tokens=7,total_tokens=19)


class FakeSDK:
    max_retries=0
    base_url=SimpleNamespace(host='tritonai-api.ucsd.edu')
    def __init__(self, missing=False, fail=False):
        self.chat=SimpleNamespace(completions=SimpleNamespace(create=self.create))
        self.fixture=ScriptedLLM(['incorrect_invoice','app_crash'])
        self.missing,self.fail=missing,fail
        self.requests=[]
    def with_options(self, **kw):
        assert kw == dict(max_retries=0,timeout=120)
        return self
    def create(self, **kw):
        self.requests.append(kw)
        assert kw['model']==CFG['model'] and kw['temperature']==0
        assert kw.get('max_tokens',100)==100
        if self.fail:
            raise RuntimeError('DO_NOT_LOG_SECRET_ERROR_BODY')
        text=self.fixture.complete(kw['messages'][0]['content'],kw['messages'][1]['content'])
        return SimpleNamespace(usage=None if self.missing else FakeUsage(), id='mock-response',
            model=CFG['model'], choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def client(sdk):
    obj=object.__new__(OpenAIClient)
    obj._client=sdk
    obj.model=CFG['model']
    obj.temperature=0.0
    return obj


class SmokeTests(unittest.TestCase):
    def setUp(self):
        self.network=patch('socket.socket.connect',side_effect=AssertionError('Network forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)

    def test_matrix_all_policies_accounted_and_saved(self):
        plan,_=pilot.matrix()
        self.assertEqual(len(plan),12)
        self.assertEqual([c.fault_type for c,m in plan[:3]],['none']*3)
        gate=pilot.SpendGate(CFG)
        with TemporaryDirectory() as tmp:
            for n,(case,mode) in enumerate(plan):
                folder=Path(tmp)/str(n);folder.mkdir()
                sdk=FakeSDK()
                result,usage,check=pilot.execute_one(case,mode,client(sdk),gate,folder)
                self.assertTrue(check['passed'],check)
                self.assertEqual(result['status'],'completed')
                self.assertEqual(result['actual_mutation_count'],0 if n<3 else 1)
                self.assertEqual(len(usage),result['metrics']['model_calls'])
                self.assertEqual(result['metrics']['provider_usage']['total_tokens'],len(usage)*19)
                self.assertEqual(len(pilot.answers(result)['retained']),2)
                self.assertEqual(len((folder/'trace.jsonl').read_text().splitlines()),len(result['events']))
                for req in sdk.requests:
                    self.assertNotIn('expected_issues',json.dumps(req))

    def test_omitted_usage_is_not_instrumentation_failure(self):
        with TemporaryDirectory() as tmp:
            case,mode=pilot.matrix()[0][0]
            result,usage,check=pilot.execute_one(case,mode,client(FakeSDK(missing=True)),pilot.SpendGate(CFG),Path(tmp))
            self.assertTrue(check['passed'])
            self.assertIsNone(result['metrics']['provider_usage']['total_tokens'])
            self.assertEqual(check['unknown_usage_calls'],len(usage))
            usage[0]['call_id']='broken'
            self.assertFalse(pilot.sanity(result,usage)['passed'])

    def test_provider_failure_retains_reservation_and_redacts_message(self):
        with TemporaryDirectory() as tmp:
            gate=pilot.SpendGate(CFG)
            result,usage,check=pilot.execute_one(*pilot.matrix()[0][0],client(FakeSDK(fail=True)),gate,Path(tmp))
            self.assertEqual(result['status'],'error')
            self.assertEqual(gate.requests,1)
            self.assertEqual(gate.reserved,gate.per_request)
            self.assertNotIn('DO_NOT_LOG_SECRET_ERROR_BODY',''.join(p.read_text() for p in Path(tmp).iterdir()))

    def test_request_and_spend_limits_no_dispatch_after_cap(self):
        gate=pilot.SpendGate(dict(CFG,project_request_limit=1))
        gate.reserve()
        with self.assertRaises(BudgetExceeded):gate.reserve()
        self.assertEqual(gate.requests,1)
        gate=pilot.SpendGate(dict(CFG,project_usd_limit='0.000001'))
        with self.assertRaises(BudgetExceeded):gate.reserve()
        self.assertEqual(gate.requests,0)
        gate=pilot.SpendGate(dict(CFG,project_request_limit=1000,project_usd_limit='10'))
        self.assertEqual(gate.request_limit,150)
        self.assertEqual(str(gate.usd_limit),'3')

    def test_dry_run_and_missing_config_never_construct_client(self):
        with TemporaryDirectory() as tmp, patch.object(pilot,'OpenAIClient',side_effect=AssertionError('No client')):
            self.assertEqual(pilot.main(['--output',tmp+'/dry']),0)

            with self.assertRaises(FileExistsError):pilot.main(['--output',tmp+'/dry'])

    def test_cli_mock_full_matrix_and_budget_partial(self):
        with TemporaryDirectory() as tmp:
            cfg=Path(tmp)/'prices.json';cfg.write_text(json.dumps(CFG))
            sdk=FakeSDK()
            with patch.object(pilot,'OpenAIClient',return_value=client(sdk)):
                self.assertEqual(pilot.main(['--execute','--output',tmp+'/full','--pricing-config',str(cfg)]),0)
            import csv
            with (Path(tmp)/'full/summary.csv').open() as f: rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),12)
            self.assertTrue(all(r['status']=='COMPLETED' for r in rows))
            cfg.write_text(json.dumps(dict(CFG,project_request_limit=1)))
            with patch.object(pilot,'OpenAIClient',return_value=client(FakeSDK())):
                self.assertEqual(pilot.main(['--execute','--output',tmp+'/partial','--pricing-config',str(cfg)]),2)
            with (Path(tmp)/'partial/summary.csv').open() as f: rows=list(csv.DictReader(f))
            self.assertEqual(rows[0]['status'],'BUDGET_EXHAUSTED')
            self.assertTrue(all(r['status']=='NOT_RUN_BUDGET' for r in rows[1:]))

    def test_optional_pricing_executes_with_unknown_cost(self):
        for supplied in (None, 'missing', {'verified':False}, dict(CFG, completion_cap=None)):
            with TemporaryDirectory() as tmp:
                args=['--execute','--output',tmp+'/out']
                if supplied is not None:
                    path=Path(tmp)/'prices.json'
                    if isinstance(supplied,dict):path.write_text(json.dumps(supplied))
                    args += ['--pricing-config',str(path)]
                sdk=FakeSDK()
                with patch.object(pilot,'OpenAIClient',return_value=client(sdk)):
                    self.assertEqual(pilot.main(args),0)
                status=json.loads((Path(tmp)/'out/pilot_status.json').read_text())
                self.assertIsNone(status['reserved_usd'])
                self.assertEqual(status['executed_runs'],12)
                self.assertTrue(all('max_tokens' not in r for r in sdk.requests))
                for path in (Path(tmp)/'out').glob('*/provider_usage.json'):
                    self.assertTrue(all(r['estimated_observed_usd'] is None for r in json.loads(path.read_text())))

    def test_bad_first_sanity_stops_remaining_runs(self):
        with TemporaryDirectory() as tmp:
            cfg=Path(tmp)/'prices.json';cfg.write_text(json.dumps(CFG))
            with patch.object(pilot,'OpenAIClient',return_value=client(FakeSDK())), patch.object(pilot,'sanity',return_value=dict(passed=False,errors=['broken trace'])):
                self.assertEqual(pilot.main(['--execute','--output',tmp+'/out','--pricing-config',str(cfg)]),2)
            import csv
            with (Path(tmp)/'out/summary.csv').open() as f: rows=list(csv.DictReader(f))
            self.assertTrue(all(r['status']=='NOT_RUN_SANITY_CHECK' for r in rows[1:]))


if __name__=='__main__':unittest.main()
