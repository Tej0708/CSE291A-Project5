"""Full-design regression: real runner and accounting, scripted provider only."""
import contextlib
import csv
import io
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from workflow2_phase1 import ROOT, prepare, execute, analyze, sha, read
from run_recovery_smoke_pilot import execute_one
from test_recovery_smoke_pilot import FakeSDK, client
from run_fault_audit import ScriptedLLM

class FullDesignTests(unittest.TestCase):
 def test_full_schedule_execution_resume_and_review(self):
  with tempfile.TemporaryDirectory() as temp, patch.object(socket.socket,'connect',side_effect=AssertionError('Offline only')):
   t=Path(temp); m=prepare(ROOT/'phase1_v1/full_config.json',t/'manifest.json')
   rows=m['run_order']; self.assertEqual(len(rows),240)
   self.assertEqual(len({(r['base_case_id'],r['scenario'],r['policy']) for r in rows}),240)
   self.assertEqual(sum(r['scenario']=='NONE' for r in rows),60)
   m2=prepare(ROOT/'phase1_v1/full_config.json',t/'second.json');self.assertEqual(m,m2)
   for i in range(20):
    block=rows[i*12:(i+1)*12]
    self.assertEqual(len({r['base_case_id'] for r in block}),1)
    self.assertTrue(all(r['scenario']=='NONE' for r in block[:3]))
    self.assertEqual(block[0]['policy'],('unprotected','full_restart','always_verify')[i%3])
   sdk=FakeSDK()
   def run(case,mode,model,gate,path):
    sdk.fixture=ScriptedLLM(case.expected_issues)
    return execute_one(case,mode,model,gate,path)
   with patch('workflow2_phase1.OpenAIClient',return_value=client(sdk)),patch('workflow2_phase1.execute_one',side_effect=run),contextlib.redirect_stdout(io.StringIO()):
    execute(t/'manifest.json',t/'runs')
   self.assertEqual(len(list((t/'runs').glob('*/complete.json'))),240)
   self.assertGreater(len(sdk.requests),150)
   before={str(p):sha(p) for p in (t/'runs').rglob('*') if p.is_file()}
   with patch('workflow2_phase1.OpenAIClient',side_effect=AssertionError('No repeat dispatch')):
    execute(t/'manifest.json',t/'runs',True)
   self.assertEqual(before,{str(p):sha(p) for p in (t/'runs').rglob('*') if p.is_file()})
   for p in (t/'runs').glob('*/result.json'):
    r=read(p);self.assertEqual(r['actual_mutation_count'],0 if r['fault_type']=='none' else 1)
    self.assertFalse(any(e.get('mutated') and e['attempt_id']>1 for e in r['events']))
   measurements=analyze(t/'runs',t/'analysis');self.assertEqual(len(measurements),240)
   with (t/'analysis/review_template.csv').open() as f: reviews=list(csv.DictReader(f))
   self.assertTrue(reviews);self.assertTrue(all(not r['reviewer'] and not r['human_verdict'] for r in reviews))
   analyze(t/'runs',t/'reviewed',t/'analysis/review_template.csv')
   print('Full offline fixture: 240 runs, %d provider dispatches, immutable resume and review export/import passed.'%len(sdk.requests))

 def test_provider_error_preserved_and_resume_continues(self):
  from workflow2_phase1 import write
  with tempfile.TemporaryDirectory() as temp,patch.object(socket.socket,'connect',side_effect=AssertionError('Offline only')):
   t=Path(temp);cfg=read(ROOT/'phase1_v1/full_config.json');cfg['base_case_ids']=['BASE-0004'];cfg['scenarios']=['NONE'];write(t/'cfg.json',cfg)
   prepare(t/'cfg.json',t/'m.json')
   with patch('workflow2_phase1.OpenAIClient',return_value=client(FakeSDK(fail=True))),contextlib.redirect_stdout(io.StringIO()):execute(t/'m.json',t/'runs')
   first=next((t/'runs').glob('*/result.json'));original=sha(first)
   with patch('workflow2_phase1.OpenAIClient',return_value=client(FakeSDK())),contextlib.redirect_stdout(io.StringIO()):execute(t/'m.json',t/'runs',True)
   self.assertEqual(sha(first),original);self.assertEqual(len(list((t/'runs').glob('*/complete.json'))),3)
if __name__=='__main__':unittest.main()
