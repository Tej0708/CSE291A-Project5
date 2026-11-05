import unittest,tempfile,subprocess,csv,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
class ReviewAdapterTests(unittest.TestCase):
 def test_blank_stays_unreviewed(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'analysis';r=subprocess.run(['/usr/bin/python3',str(HERE/'import_human_reviews.py'),str(HERE/'human_review_complete.csv'),str(p)],text=True,capture_output=True)
   self.assertEqual(r.returncode,0,r.stderr)
   x=json.loads((p/'aggregate.json').read_text());self.assertEqual(x['draft_quality']['all'],{'UNREVIEWED':560});self.assertEqual(x['all']['clean_success_reviewed']['denominator'],0)
 def test_identity_tampering_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   rows=list(csv.DictReader((HERE/'human_review_complete.csv').read_text(encoding='utf-8-sig').splitlines(keepends=True)));rows[0]['run_id']='wrong-run'
   f=Path(t)/'tampered.csv'
   with f.open('w',newline='') as h:
    w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
   target=Path(t)/'analysis';r=subprocess.run(['/usr/bin/python3',str(HERE/'import_human_reviews.py'),str(f),str(target)],text=True,capture_output=True)
   self.assertNotEqual(r.returncode,0);self.assertIn('Changed review identity',r.stderr);self.assertFalse(target.exists())
if __name__=='__main__':unittest.main()
