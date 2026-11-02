import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import urllib.request
import urllib.error
import re

from review_app import ReviewStore, blank_review, summarize


def fixture():
    return {'case_id':'BASE-0003-NONE','run_status':'completed','user_query':'Refund my duplicate charge and fix settings crashes.',
            'checks':{'expected_issues':['duplicate_charge','app_crash'],'structural_pass':True},
            'result':{'history':[]},'helper_runs':[
                {'issue':issue,'iteration':i+1,'route':route,
                 'new_evidence':[{'source':source,'content':answer}],
                 'workflow_events':[{'stage':'helper_result','record':{'detail':answer}}]}
                for i,(issue,route,source,answer) in enumerate([
                    ('duplicate_charge','billing','billing_service','The duplicate charge was refunded.'),
                    ('app_crash','technical','technical_tool','Install the available patch.')])]}


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name)
        self.report=fixture();self.write();self.store=ReviewStore(self.folder,'Reviewer A')
    def tearDown(self):self.temp.cleanup()
    def write(self):(self.folder/'case_results.jsonl').write_text(json.dumps(self.report)+'\n')
    def score(self,index,**changes):
        r={k:'PASS' for k in blank_review()};r['notes']='';r.update(changes)
        return self.store.save({'key':self.store.data['items'][index]['key'],'revision':self.store.state['revision'],'review':r})
    def test_partial_and_complete(self):
        self.score(0);self.assertIsNone(self.store.snapshot()['stats']['task_success_rate'])
        self.score(1);self.assertEqual(self.store.snapshot()['stats']['task_success_rate'],1)
    def test_failure_and_uncertainty(self):
        self.score(0);self.score(1,status_responsibility='FAIL',notes='Requires a new ticket.')
        self.assertEqual(self.store.snapshot()['stats']['task_success_rate'],0)
        self.score(1,grounding='UNCERTAIN',notes='Reference not available.')
        self.assertIsNone(self.store.snapshot()['stats']['task_success_rate'])
    def test_data_issue_is_separate(self):
        self.score(0);self.score(1,record_alignment='FAIL',notes='Wrong scenario fixture.')
        self.assertEqual(self.store.snapshot()['case_verdicts'][0]['semantic_verdict'],'DATA_ISSUE')
    def test_missing_helper(self):
        self.report['helper_runs'].pop();self.write();s=ReviewStore(self.folder,'New')
        self.assertEqual(s.snapshot()['case_verdicts'][0]['semantic_verdict'],'FAIL')
    def test_notes_required(self):
        with self.assertRaisesRegex(ValueError,'reason'):self.score(0,grounding='FAIL')
    def test_empty_answer(self):
        self.report['helper_runs'][0]['new_evidence']=[];self.write();self.store=ReviewStore(self.folder,'New')
        with self.assertRaisesRegex(ValueError,'empty'):self.score(0)
    def test_resume_export_and_no_source_mutation(self):
        before=(self.folder/'case_results.jsonl').read_bytes();self.score(0)
        resumed=ReviewStore(self.folder,'Reviewer A');self.assertEqual(resumed.state['revision'],1)
        dest=Path(resumed.export()['export_path']);self.assertTrue((dest/'helper_reviews.csv').exists())
        self.assertTrue((dest/'rubric.json').exists());self.assertEqual(before,(self.folder/'case_results.jsonl').read_bytes())
        self.assertEqual(len(json.loads((dest/'review_state.json').read_text())['history']),1)
    def test_conflict_and_changed_input(self):
        self.score(0)
        with self.assertRaisesRegex(ValueError,'another'):self.store.save({'revision':0})
        self.report['user_query']='Changed';self.write()
        with self.assertRaisesRegex(ValueError,'changed'):self.store.snapshot()
    def test_http(self):
        process=subprocess.Popen([sys.executable,str(Path(__file__).with_name('review_app.py')),'--run-dir',str(self.folder),'--reviewer','HTTP','--no-browser'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            url=process.stdout.readline().strip().split('Review UI: ')[1]
            page=urllib.request.urlopen(url).read().decode();token=re.search("const token='([^']+)'",page).group(1)
            state=json.load(urllib.request.urlopen(url+'api/state'));self.assertEqual(len(state['items']),2)
            req=urllib.request.Request(url+'api/export',data=b'{}',method='POST')
            with self.assertRaises(urllib.error.HTTPError) as cm:urllib.request.urlopen(req)
            self.assertEqual(cm.exception.code,403)
            req.add_header('X-Review-Token',token)
            self.assertTrue(Path(json.load(urllib.request.urlopen(req))['export_path']).exists())
        finally:
            process.terminate();process.communicate(timeout=5)

if __name__=='__main__':unittest.main()
