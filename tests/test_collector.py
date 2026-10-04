import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
from brand_discovery.collector import canonical, public_ip, Refused, extract, run, validate_private_root, safe_cell, Fetcher

class FakeFetcher:
    def get(self, url):
        return url, '<html><script>secret script</script><body>상의 셔츠 장바구니<a href="mailto:shop@example.invalid">Contact</a><a href="https://www.instagram.com/synthetic_only/">IG</a></body></html>'

class Tests(unittest.TestCase):
    def test_reject_unsafe_urls(self):
        for url in ['http://example.com','https://a:b@example.com','https://example.com:8443','https://example.com/?token=SECRET','https://instagram.com/a']:
            with self.assertRaises(Refused): canonical(url)
    def test_public_ip(self):
        with patch('socket.getaddrinfo', return_value=[(None,None,None,None,('127.0.0.1',443))]):
            with self.assertRaises(Refused): public_ip('example.invalid')
    def test_extraction_never_confirms(self):
        r = extract(*FakeFetcher().get('https://example.invalid'))
        self.assertEqual(r['current_sale_status'], 'unverified')
        self.assertEqual(r['cart_function_status'], 'not_tested')
        self.assertTrue(r['cart_text_observed'])
        self.assertNotIn('secret script', r['visible_text_excerpt'])
    def test_private_guard(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            with self.assertRaises(Refused): validate_private_root(root, root)
            with self.assertRaises(Refused): validate_private_root(root/'child', root)
            with self.assertRaises(Refused): validate_private_root(root, Path('/unrelated'))
    def test_checkpoint_dedup_exclusions_and_xlsx(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            rows=[{'name':'Synthetic A','official_url':'https://example.invalid/'},{'name':'Synthetic B','official_url':'https://example.invalid/'},{'name':'Known','official_url':'https://known.invalid/'}]
            with (root/'candidates.csv').open('w') as f:
                w=csv.DictWriter(f,fieldnames=['name','official_url']);w.writeheader();w.writerows(rows)
            (root/'exclusions.json').write_text(json.dumps({'names':['Known'],'urls':[]}))
            self.assertEqual(run(root,fetcher=FakeFetcher()),3)
            self.assertEqual(run(root,fetcher=FakeFetcher()),0)
            results=list(json.loads((root/'checkpoint.json').read_text()).values())
            self.assertEqual([r['status'] for r in results],['needs_review','possible_duplicate_review','excluded_known_brand'])
            with ZipFile(root/'review_queue.xlsx') as z:
                self.assertNotIn('<f>', z.read('xl/worksheets/sheet1.xml').decode())
    def test_exception_secrets_not_persisted(self):
        class Fail:
            def get(self,url): raise RuntimeError('SECRET https://example.invalid?token=SECRET')
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'candidates.csv').write_text('name,official_url\nFake,https://example.invalid/\n')
            run(root,fetcher=Fail())
            self.assertNotIn('SECRET',(root/'checkpoint.json').read_text())
    def test_empty_input_writes_checkpoint(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root/'candidates.csv').write_text('name,official_url\n')
            self.assertEqual(run(root, fetcher=FakeFetcher()), 0)
            self.assertEqual(json.loads((root/'checkpoint.json').read_text()), {})
            self.assertTrue((root/'review_queue.xlsx').exists())

    def test_review_export_does_not_mix_historical_canary(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root/'candidates.csv').write_text('name,official_url\nCANARY_FAKE,https://example.invalid/\n')
            run(root, fetcher=FakeFetcher())
            (root/'candidates.csv').write_text('name,official_url\nCURRENT_FAKE,https://other.invalid/\n')
            run(root, fetcher=FakeFetcher())
            self.assertEqual(len(json.loads((root/'checkpoint.json').read_text())), 2)
            exported = (root/'review_queue.csv').read_text()
            self.assertNotIn('CANARY_FAKE', exported)
            self.assertIn('CURRENT_FAKE', exported)

    def test_formula_injection(self):
        for s in ['=1+1',' +cmd','-2','@SUM(A1)']:
            self.assertTrue(safe_cell(s).startswith("'"))
    def test_robots_fail_closed(self):
        f=Fetcher()
        with patch.object(f,'raw',return_value=(503,{},b'')):
            with self.assertRaises(Refused): f.allowed('https://example.invalid/')
    def test_cross_origin_redirect_stops(self):
        f=Fetcher()
        with patch.object(f,'allowed'),patch.object(f,'raw',return_value=(302,{'location':'https://other.invalid/'},b'')):
            with self.assertRaisesRegex(Refused,'cross_origin_redirect'): f.get('https://example.invalid/')
    def test_workflow_has_no_data_transfers(self):
        root=Path(__file__).resolve().parents[1]
        for p in (root/'.github/workflows').glob('*.yml'):
            s=p.read_text()
            for forbidden in ['upload-artifact','download-artifact','actions/cache','GITHUB_STEP_SUMMARY','pull_request_target','schedule:']:
                self.assertNotIn(forbidden,s)
            for line in s.splitlines():
                if 'uses:' in line:
                    self.assertRegex(line,r'@[0-9a-f]{40}')

if __name__=='__main__': unittest.main()
