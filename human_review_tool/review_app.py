"""Offline browser-based review of saved support-workflow runs. Standard library only."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import webbrowser

RUBRIC_VERSION = 'support-human-v1'
CRITERIA = [
    ('record_alignment', 'Record matches the scenario', 'Does the record address this specific request and provide enough evidence for an appropriate response? FAIL identifies an environment/data problem, not automatically a model error.'),
    ('relevance', 'Answers the assigned question', 'Answer the concrete question for this helper. A billing helper need not answer the technical part handled by another helper.'),
    ('grounding', 'Important claims have evidence', 'No unsupported amounts, currencies, refund timelines, destinations, platforms, or guarantees. Faithful paraphrases and non-factual politeness are allowed.'),
    ('coverage', 'Includes necessary conclusions and steps', 'Include what is needed to address the assigned issue. Do not require every tool field to be repeated.'),
    ('status_responsibility', 'Accurate status and responsibility', 'Do not claim confirmed user-side repair or require a new ticket for a problem already in this workflow. Conditional follow-up after supported steps is allowed.'),
]
VALUES = {'UNREVIEWED', 'PASS', 'FAIL', 'UNCERTAIN'}
ANSWER_KEYS = [x[0] for x in CRITERIA[1:]]


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def read_json(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def aggregate(values):
    values = list(values)
    if not values or 'UNREVIEWED' in values:
        return 'UNREVIEWED'
    if 'FAIL' in values:
        return 'FAIL'
    if 'UNCERTAIN' in values:
        return 'UNCERTAIN'
    return 'PASS'


def load_run(folder):
    path = folder / 'case_results.jsonl'
    if not path.is_file():
        raise ValueError('The run directory must contain case_results.jsonl.')
    reports = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if not reports or len({r['case_id'] for r in reports}) != len(reports):
        raise ValueError('Case results are empty or contain duplicate case IDs.')
    manifest = read_json(folder / 'manifest.json', {})
    source_summary = read_json(folder / 'summary.json', {})
    selected = manifest.get('case_ids', [r['case_id'] for r in reports])
    if len(set(selected)) != len(selected):
        raise ValueError('Duplicate selected case IDs in manifest.')
    cases, items, reference_inputs = [], [], {}
    lookup = {r['case_id']:r for r in reports}
    for case_id in dict.fromkeys(selected + list(lookup)):
        if not re.fullmatch(r'[A-Za-z0-9_-]+',case_id):
            raise ValueError('Unsafe case ID in input.')
        report = lookup.get(case_id, {'case_id':case_id,'run_status':'not_attempted'})
        checks = report.get('checks') or {}
        trace_input = {}
        trace = folder / (case_id + '.trace.jsonl')
        if trace.is_file():
            with trace.open(encoding='utf-8') as stream:
                for line in stream:
                    if line.strip():
                        event=json.loads(line)
                        if event.get('event') == 'case_input':
                            trace_input=event
                            break
        reference_inputs[case_id] = trace_input
        expected = checks.get('expected_issues',trace_input.get('case',{}).get('expected_issues',[]))
        query = report.get('user_query',trace_input.get('case',{}).get('user_query',''))
        ids=[]; latest={}
        for index, helper in enumerate(report.get('helper_runs',[])):
            issue=helper['issue']; key=f'{case_id}::{index}'
            evidence=helper.get('new_evidence',[])
            records=[e['record'] for e in helper.get('workflow_events',[]) if e.get('stage')=='helper_result']
            item={'key':key,'case_id':case_id,'issue':issue,'iteration':helper.get('iteration'),
                  'route':helper.get('route'),'user_query':query,'records':records,
                  'answer':'\n\n'.join(e.get('content','') for e in evidence if e.get('source') in ('billing_service','technical_tool')),
                  'support_documents':[e.get('content','') for e in evidence if e.get('source')=='support_doc'],
                  'evidence_flags':[{k:e.get(k) for k in ('source','authoritative','verified')} for e in evidence],
                  'reference_record':trace_input.get('clean_reference_records',{}).get(issue),
                  'workflow_events':helper.get('workflow_events',[])}
            items.append(item); ids.append(key); latest[issue]=key
        cases.append({'case_id':case_id,'user_query':query,'expected_issues':expected,
                      'expected_issues_known':bool(expected),'item_keys':ids,'latest':latest,
                      'run_status':report.get('run_status'), 'checks':checks,
                      'result':report.get('result',{}),'metrics':report.get('metrics',{}),
                      'qa_decisions':[e for e in report.get('result',{}).get('history',[]) if e.get('stage')=='qa_label_validation']})
    fingerprint=digest({'reports':reports,'manifest':manifest,'summary':source_summary,'reference_inputs':reference_inputs})
    return {'cases':cases,'items':items,'manifest':manifest,'source_summary':source_summary,
            'fingerprint':fingerprint,'criteria':CRITERIA,'rubric_version':RUBRIC_VERSION}


def blank_review():
    return {**{key:'UNREVIEWED' for key,_,_ in CRITERIA},'notes':''}


def summarize(data, reviews):
    helper_rows=[]
    for item in data['items']:
        review=reviews.get(item['key'],blank_review())
        helper_rows.append({**item,**review,'answer_verdict':aggregate(review[k] for k in ANSWER_KEYS),
                            'fully_reviewed':all(review[k]!='UNREVIEWED' for k,_,_ in CRITERIA)})
    case_rows=[]
    for c in data['cases']:
        missing=sorted(set(c['expected_issues'])-set(c['latest']))
        # Assess all latest issue outputs, including extra user-facing answers.
        effective=list(c['latest'].values())
        rr=[reviews.get(k,blank_review()) for k in effective]
        complete=bool(rr) and all(all(r[k]!='UNREVIEWED' for k,_,_ in CRITERIA) for r in rr)
        align=aggregate(r['record_alignment'] for r in rr)
        if any(r['record_alignment']=='FAIL' for r in rr):
            outcome='DATA_ISSUE'
        elif c['run_status']!='completed':
            outcome='FAIL'
        elif not c['expected_issues_known']:
            outcome='UNCERTAIN'
        elif missing:
            outcome='FAIL'
        elif not complete:
            outcome='UNREVIEWED'
        elif align=='UNCERTAIN':
            outcome='UNCERTAIN'
        else:
            outcome=aggregate(aggregate(r[k] for k in ANSWER_KEYS) for r in rr)
        case_rows.append({'case_id':c['case_id'],'semantic_verdict':outcome,'run_status':c['run_status'],
                          'structural_pass':c['checks'].get('structural_pass'),
                          'missing_helper_issues':missing,'all_latest_outputs_reviewed':complete,
                          'expected_issues':c['expected_issues'],'latest_item_keys':effective,
                          'notes':' | '.join(r['notes'] for r in rr if r['notes'])})
    counts={v:sum(c['semantic_verdict']==v for c in case_rows) for v in ['PASS','FAIL','UNCERTAIN','UNREVIEWED','DATA_ISSUE']}
    helper_counts={v:sum(h['answer_verdict']==v for h in helper_rows) for v in ['PASS','FAIL','UNCERTAIN','UNREVIEWED']}
    eligible=not any(counts[v] for v in ['UNCERTAIN','UNREVIEWED','DATA_ISSUE'])
    n=len(case_rows)
    stats={'rubric_version':RUBRIC_VERSION,'case_count':n,'helper_count':len(helper_rows),
           'fully_reviewed_helpers':sum(h['fully_reviewed'] for h in helper_rows),
           'case_verdicts':counts,'helper_answer_verdicts':helper_counts,
           'confirmed_case_pass_fraction':counts['PASS']/n if n else None,
           'task_success_rate':counts['PASS']/n if n and eligible else None,
           'helper_answer_pass_rate':helper_counts['PASS']/len(helper_rows) if helper_rows and not helper_counts['UNCERTAIN'] and not helper_counts['UNREVIEWED'] else None,
           'structural_passes':sum(c['checks'].get('structural_pass') is True for c in data['cases']),
           'definition':'All expected issues covered and all latest helper outputs pass human answer review with aligned records. Structural checks are separate diagnostics. Earlier failed attempts remain in helper statistics.',
           'limitations':'This tool reviews saved helper outputs, not a separately bundled final response. It does not prove fault activation, recovery, or real-world repair. DATA_ISSUE requires dataset/environment adjudication.'}
    return stats,helper_rows,case_rows


class ReviewStore:
    def __init__(self, folder, reviewer):
        self.folder=folder;self.reviewer=reviewer;self.lock=threading.Lock()
        self.data=load_run(folder)
        slug=re.sub(r'[^A-Za-z0-9_-]+','_',reviewer).strip('_')[:40] or 'reviewer'
        self.output=folder/'human_reviews'/(slug+'_'+hashlib.sha256(reviewer.encode()).hexdigest()[:8])
        self.output.mkdir(parents=True,exist_ok=True)
        self.path=self.output/'review_state.json'
        self.state=read_json(self.path,{'revision':0,'reviewer':reviewer,'run_fingerprint':self.data['fingerprint'],
                                      'rubric_version':RUBRIC_VERSION,'reviews':{},'history':[]})
        self.check_identity(self.state)

    def check_identity(self,state):
        if state.get('run_fingerprint')!=self.data['fingerprint'] or state.get('rubric_version')!=RUBRIC_VERSION or state.get('reviewer')!=self.reviewer:
            raise ValueError('Saved review belongs to different inputs, rubric, or reviewer. Use a new reviewer/version directory; do not overwrite it.')

    def refresh(self):
        if load_run(self.folder)['fingerprint']!=self.data['fingerprint']:
            raise ValueError('Input files changed during review. Restart and reconcile versions before continuing.')
        if self.path.exists():
            self.state=read_json(self.path);self.check_identity(self.state)

    def snapshot(self):
        with self.lock:
            self.refresh()
            stats,_,case_rows=summarize(self.data,self.state['reviews'])
            return {**self.data,'reviewer':self.reviewer,'revision':self.state['revision'],
                    'reviews':self.state['reviews'],'stats':stats,'case_verdicts':case_rows,'output_path':str(self.output)}

    def save(self,payload):
        with self.lock:
            self.refresh()
            if payload.get('revision')!=self.state['revision']:
                raise ValueError('Review changed in another tab/session. Reload before saving.')
            key=payload.get('key');review=payload.get('review',{})
            if key not in {i['key'] for i in self.data['items']}:
                raise ValueError('Unknown helper review ID.')
            if set(review)!={k for k,_,_ in CRITERIA}|{'notes'}:
                raise ValueError('Review fields do not match the rubric.')
            if any(review[k] not in VALUES for k,_,_ in CRITERIA):
                raise ValueError('Invalid score.')
            if not isinstance(review['notes'],str) or len(review['notes'])>20000:
                raise ValueError('Notes must be text up to 20,000 characters.')
            if any(review[k] in ('FAIL','UNCERTAIN') for k,_,_ in CRITERIA) and not review['notes'].strip():
                raise ValueError('Add evidence or a reason for FAIL / UNCERTAIN ratings.')
            item=next(i for i in self.data['items'] if i['key']==key)
            if not item['answer'].strip() and all(review[k]=='PASS' for k in ANSWER_KEYS):
                raise ValueError('An empty captured answer cannot pass all answer criteria.')
            updated=json.loads(json.dumps(self.state));updated['revision']+=1
            updated['reviews'][key]=review;updated['updated_utc']=now()
            updated['history'].append({'revision':updated['revision'],'timestamp_utc':now(),'key':key,
                                       'before':self.state['reviews'].get(key),'after':review})
            fd,temp=tempfile.mkstemp(prefix='.review_',suffix='.tmp',dir=self.output)
            try:
                with os.fdopen(fd,'w',encoding='utf-8') as f:
                    json.dump(updated,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
                os.replace(temp,self.path)
            finally:
                if os.path.exists(temp):os.unlink(temp)
            self.state=updated
            return {'revision':updated['revision'],'saved_utc':updated['updated_utc']}

    def export(self):
        with self.lock:
            self.refresh()
            stats,helpers,cases=summarize(self.data,self.state['reviews'])
            dest=self.output/('export_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+secrets.token_hex(3))
            dest.mkdir()
            metadata={'reviewer':self.reviewer,'run_fingerprint':self.data['fingerprint'],
                      'source_manifest':self.data['manifest'],'revision':self.state['revision'],'exported_utc':now()}
            (dest/'rubric.json').write_text(json.dumps({'version':RUBRIC_VERSION,'criteria':CRITERIA},indent=2),encoding='utf-8')
            (dest/'human_summary.json').write_text(json.dumps({**metadata,**stats},indent=2),encoding='utf-8')
            (dest/'review_state.json').write_text(json.dumps(self.state,ensure_ascii=False,indent=2),encoding='utf-8')
            helper_fields=['case_id','issue','iteration','route','user_query','records','reference_record','answer']+[k for k,_,_ in CRITERIA]+['answer_verdict','notes']
            write_csv(dest/'helper_reviews.csv',helpers,helper_fields)
            write_csv(dest/'case_reviews.csv',cases,list(cases[0]) if cases else ['case_id'])
            report=['# Human review summary','',f'Reviewer: {self.reviewer}',f'Rubric: {RUBRIC_VERSION}',f'Run fingerprint: {self.data["fingerprint"]}','',
                    f'Fully reviewed helpers: {stats["fully_reviewed_helpers"]}/{stats["helper_count"]}',
                    f'Case outcomes: {json.dumps(stats["case_verdicts"])}',
                    f'Task success rate: {stats["task_success_rate"] if stats["task_success_rate"] is not None else "Pending adjudication or incomplete review"}','',stats['definition'],'',stats['limitations'],'',
                    'Original experiment files were not modified. A partial export is not a completed assessment.']
            (dest/'review_summary.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
            return {'export_path':str(dest),'stats':stats}


def write_csv(path,rows,fields):
    def safe(value):
        if isinstance(value,(dict,list)):value=json.dumps(value,ensure_ascii=False)
        if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):return "'"+value
        return value
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader()
        for row in rows:writer.writerow({k:safe(row.get(k)) for k in fields})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',required=True,type=Path)
    parser.add_argument('--reviewer',required=True)
    parser.add_argument('--port',type=int,default=0)
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    if not args.reviewer.strip():parser.error('Reviewer must not be empty.')
    store=ReviewStore(args.run_dir.resolve(),args.reviewer.strip())
    token=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def respond(self,status,payload,kind='application/json'):
            body=json.dumps(payload,ensure_ascii=False).encode() if kind=='application/json' else payload.encode()
            self.send_response(status);self.send_header('Content-Type',kind+'; charset=utf-8')
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def valid_host(self):
            return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'
        def do_GET(self):
            if not self.valid_host():return self.respond(403,{'error':'Invalid host.'})
            try:
                if self.path=='/':
                    html=Path(__file__).with_name('review.html').read_text(encoding='utf-8').replace('__CSRF_TOKEN__',token)
                    return self.respond(200,html,'text/html')
                if self.path=='/api/state':return self.respond(200,store.snapshot())
                self.respond(404,{'error':'Not found.'})
            except Exception as exc:self.respond(400,{'error':str(exc)})
        def do_POST(self):
            if not self.valid_host() or self.headers.get('X-Review-Token')!=token:
                return self.respond(403,{'error':'Invalid request token.'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<=length<=100000:raise ValueError('Request too large.')
                payload=json.loads(self.rfile.read(length) or b'{}')
                if self.path=='/api/save':return self.respond(200,store.save(payload))
                if self.path=='/api/export':return self.respond(200,store.export())
                self.respond(404,{'error':'Not found.'})
            except Exception as exc:self.respond(400,{'error':str(exc)})
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    url=f'http://127.0.0.1:{server.server_port}/'
    print(f'Review UI: {url}',flush=True)
    print(f'Reviews saved to: {store.output}',flush=True)
    print('No model calls. Original run files remain unchanged. Press Ctrl+C to stop.',flush=True)
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
