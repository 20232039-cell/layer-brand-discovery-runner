import base64
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from brand_discovery.private_sync import download, upload, output_files, SyncError, GitHub

class FakeAPI:
    def __init__(self):
        self.current='a'*40
        self.calls=[]
    def verify_private(self): self.calls.append('verify_private')
    def head(self): return self.current
    def request(self,method,path,data=None):
        self.calls.append((method,path,data))
        if path.startswith('/git/commits/'):
            return {'tree':{'sha':'b'*40}}
        if path.startswith('/git/trees/'):
            return {'tree':[{'path':'candidates.csv','type':'blob','mode':'100644','sha':'c'*40,'size':100}]}
        if method=='GET' and path.startswith('/git/blobs/'):
            return {'encoding':'base64','content':base64.b64encode(b'name,official_url\nFake,https://example.invalid/\n').decode()}
        if path=='/git/blobs':
            raw=base64.b64decode(data['content'])
            return {'sha':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()}
        if path=='/git/trees': return {'sha':'d'*40}
        if path=='/git/commits': return {'sha':'e'*40}
        if path=='/git/refs/heads/main':
            self.current=data['sha'];return {'object':{'sha':self.current}}
        raise AssertionError(path)

class SyncTests(unittest.TestCase):
    def setup_output(self,root):
        for name in ('checkpoint.json','review_queue.csv','review_queue.xlsx'):
            (root/name).write_bytes(b'synthetic-private-marker')
        (root/'evidence').mkdir()
        (root/'evidence'/('f'*64+'.json')).write_text('{}')
    def test_transport_roundtrip_only_allowlist(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'data';api=FakeAPI()
            download(api,root);self.setup_output(root)
            (root/'never-upload-secret.txt').write_text('DO_NOT_UPLOAD')
            upload(api,root)
            tree=[c[2]['tree'] for c in api.calls if isinstance(c,tuple) and c[:2]==('POST','/git/trees')][0]
            self.assertEqual(len(tree),4)
            self.assertNotIn('DO_NOT_UPLOAD',str(api.calls))
            self.assertEqual(api.current,'e'*40)
    def test_reject_public_repo(self):
        with patch.dict('os.environ',{'DATA_REPOSITORY':'owner/repo','DATA_TOKEN':'SYNTHETIC'}):
            api=GitHub()
            with patch.object(api,'request',return_value={'private':False,'full_name':'owner/repo','default_branch':'main'}):
                with self.assertRaises(SyncError):api.verify_private()
    def test_conflict_refuses_write(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'data';api=FakeAPI();download(api,root);self.setup_output(root)
            api.current='changed';before=len(api.calls)
            with self.assertRaises(SyncError):upload(api,root)
            self.assertEqual(api.calls[before:],['verify_private'])
    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);self.setup_output(root)
            (root/'review_queue.csv').unlink();(root/'review_queue.csv').symlink_to(root/'checkpoint.json')
            with self.assertRaises(SyncError):output_files(root)
    def test_bad_evidence_name_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);self.setup_output(root);(root/'evidence'/'secret.json').write_text('{}')
            with self.assertRaises(SyncError):output_files(root)
    def test_workflow_credentials_isolated(self):
        text=(Path(__file__).resolve().parents[1]/'.github/workflows/project-data-build.yml').read_text()
        collect=text.split('- name: Build bounded private review dataset')[1].split('- name: Save checkpoint')[0]
        self.assertNotIn('secrets.',collect)
        self.assertIn('env -i',collect)
        self.assertIn("ENABLE_PRIVATE_DATA_BUILD == 'true'",text)
        for banned in ['upload-artifact','download-artifact','actions/cache','GITHUB_OUTPUT','GITHUB_STEP_SUMMARY','inputs.','schedule:']:
            self.assertNotIn(banned,text)

if __name__=='__main__':unittest.main()
