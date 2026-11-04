"""Offline tests use a disposable copy of saved evidence; never modify originals."""
import contextlib
import io
import json
import shutil
import socket
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from infrastructure_continuation import prepare_continuation,tree_hashes,infrastructure_accounting
from workflow2_phase1 import ROOT, execute, analyze, read, sha, resume_state
from run_recovery_smoke_pilot import execute_one, sanitized_provider_error
from test_recovery_smoke_pilot import FakeSDK,client
from run_fault_audit import ScriptedLLM

SAVED=ROOT/'results/workflow2_phase1_20261103_210112'
SLOT='BASE-0011__NONE__full_restart__r1'
class ContinuationTests(unittest.TestCase):
 def test_saved_counts_retry_archive_accounting_and_resume(self):
  before=tree_hashes(SAVED)
  with tempfile.TemporaryDirectory() as tmp,patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden')):
   out=Path(tmp)/'runs';shutil.copytree(SAVED,out)
   planpath=Path(tmp)/'plan.json';plan=prepare_continuation(out,SLOT,planpath)
   self.assertEqual((plan['completed_slots'],plan['unstarted_slots']),(37,202))
   self.assertEqual(tree_hashes(out),before)
   with self.assertRaisesRegex(ValueError,'explicit new protocol'):resume_state(out,read(out/'manifest.json'))
   manifest_hash=sha(out/'manifest.json');sdk=FakeSDK();seen=[]
   def run(case,mode,model,gate,path):
    seen.append(path.name);sdk.fixture=ScriptedLLM(case.expected_issues)
    return execute_one(case,mode,model,gate,path)
   with patch('workflow2_phase1.OpenAIClient',return_value=client(sdk)),patch('workflow2_phase1.execute_one',side_effect=run),contextlib.redirect_stdout(io.StringIO()):
    execute(out/'manifest.json',out,True,planpath)
   self.assertEqual(len(seen),203);self.assertEqual(seen[0],SLOT)
   archive=out/plan['archive_relative_path'];self.assertEqual(tree_hashes(archive),plan['original_evidence'])
   for sid,hashes in plan['completed_evidence'].items():self.assertEqual(tree_hashes(out/sid),hashes)
   self.assertEqual(sha(out/'manifest.json'),manifest_hash)
   self.assertEqual(len(resume_state(out,read(out/'manifest.json'))),240)
   usage=read(out/SLOT/'provider_usage.json');self.assertEqual(usage[0]['provider_request_number'],185)
   self.assertNotEqual(read(out/SLOT/'result.json')['run_id'],read(archive/'result.json')['run_id'])
   self.assertEqual(read(out/SLOT/'result.json')['restart_count'],0)
   accounting=infrastructure_accounting(out);self.assertEqual(len(accounting),1)
   self.assertEqual(len(accounting[0]['provider_usage']),3)
   self.assertEqual(sum(x.get('usage',{}).get('total_tokens',0) for x in accounting[0]['provider_usage'] if x.get('usage')),706)
   analysis=Path(tmp)/'analysis';self.assertEqual(len(analyze(out,analysis)),240)
   self.assertEqual(len(read(analysis/'infrastructure_attempts.json')),1)
   with patch('workflow2_phase1.OpenAIClient',side_effect=AssertionError('No repeat execution')):execute(out/'manifest.json',out,True,planpath)
   # A new provider error cannot be re-archived/retried using the old authorization.
   receipt=read(out/SLOT/'complete.json');receipt['execution']='error';(out/SLOT/'complete.json').write_text(json.dumps(receipt))
   with patch('workflow2_phase1.OpenAIClient',side_effect=AssertionError('No automatic retry')),self.assertRaisesRegex(ValueError,'explicit new protocol'):
    execute(out/'manifest.json',out,True,planpath)
  self.assertEqual(tree_hashes(SAVED),before)

 def test_sanitized_error_allowlist(self):
  secret='private-provider-credential'
  exc=SimpleNamespace(body={'error':{'code':'insufficient_quota','type':'quota_error','message':'Quota exhausted; key='+secret+' Bearer abc123 https://host/?token=hidden'}},response=SimpleNamespace(headers={'retry-after':'60','authorization':'DO_NOT_RECORD'}))
  fields=sanitized_provider_error(exc,SimpleNamespace(api_key=secret))
  self.assertEqual(fields['provider_error_code'],'insufficient_quota');self.assertEqual(fields['retry_after'],'60')
  serialized=json.dumps(fields)
  for value in (secret,'abc123','hidden','DO_NOT_RECORD'):self.assertNotIn(value,serialized)
  self.assertIsNone(sanitized_provider_error(RuntimeError('SECRET BODY'),SimpleNamespace())['provider_error_message'])

 def test_source_drift_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   with patch('infrastructure_continuation.sources',return_value={}):
    with self.assertRaisesRegex(ValueError,'source/data drift'):prepare_continuation(SAVED,SLOT,Path(tmp)/'plan.json')
if __name__=='__main__':unittest.main()
