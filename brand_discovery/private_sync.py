"""Credential-isolated GitHub private data transport; never prints server responses."""
import argparse
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import sys
from .collector import atomic_json

class SyncError(Exception):
    pass

class GitHub:
    def __init__(self):
        self.repo = os.environ['DATA_REPOSITORY']
        self.token = os.environ['DATA_TOKEN']
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', self.repo):
            raise SyncError()
    def request(self, method, path, data=None):
        conn=http.client.HTTPSConnection('api.github.com',timeout=30)
        payload=json.dumps(data).encode() if data is not None else None
        try:
            conn.request(method,'/repos/'+self.repo+path,body=payload,headers={'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'LayerPrivateDataBuild/0.1','Content-Type':'application/json'})
            response=conn.getresponse()
            body=response.read(16_000_001)
            if not 200 <= response.status < 300 or len(body)>16_000_000:
                raise SyncError()
            return json.loads(body)
        finally:
            conn.close()
    def verify_private(self):
        repo=self.request('GET','')
        if repo.get('private') is not True or repo.get('full_name','').lower()!=self.repo.lower() or repo.get('default_branch')!='main':
            raise SyncError()
    def head(self):
        return self.request('GET','/git/ref/heads/main')['object']['sha']

INPUTS=('candidates.csv','exclusions.json','checkpoint.json')
PROFILE_INPUTS=('instagram_profiles.csv','instagram_history.json')
RENDERED_INPUTS=('instagram_browser_profile.csv','instagram_history.json')
PROFILE_OUTPUTS=('instagram_history.json','instagram_results.json','instagram_results.csv','instagram_results.xlsx')

def download(api, root, profile=False, rendered=False):
    if rendered and not profile:raise SyncError()
    api.verify_private()
    head=api.head()
    commit=api.request('GET','/git/commits/'+head)
    tree=api.request('GET','/git/trees/'+commit['tree']['sha'])
    entries={x['path']:x for x in tree['tree']}
    required = 'instagram_browser_profile.csv' if rendered else ('instagram_profiles.csv' if profile else 'candidates.csv')
    if required not in entries or tree.get('truncated') or (rendered and 'instagram_history.json' not in entries):
        raise SyncError()
    root.mkdir(mode=0o700,parents=True,exist_ok=False)
    (root/'.private-data-root').touch(mode=0o600)
    hashes={}
    for name in (RENDERED_INPUTS if rendered else (PROFILE_INPUTS if profile else INPUTS)):
        if name not in entries:
            continue
        entry=entries[name]
        if entry['type']!='blob' or entry['mode']!='100644' or entry.get('size',0)>10_000_000:
            raise SyncError()
        blob=api.request('GET','/git/blobs/'+entry['sha'])
        if blob.get('encoding')!='base64':
            raise SyncError()
        value=base64.b64decode(blob['content'])
        if len(value)>10_000_000:
            raise SyncError()
        (root/name).write_bytes(value)
        hashes[name]=hashlib.sha256(value).hexdigest()
    atomic_json(root/'.sync-state.json',{'head':head,'tree':commit['tree']['sha'],'inputs':hashes,'profile_mode':profile,'rendered_mode':rendered})

def output_files(root, profile=False):
    # Never glob input directories or recursively upload a private checkout.
    files=[root/x for x in (PROFILE_OUTPUTS if profile else ('checkpoint.json','review_queue.csv','review_queue.xlsx'))]
    if not profile:
        files+=sorted((root/'evidence').glob('*.json'))
    for file in files:
        rel=file.relative_to(root).as_posix()
        allowed = rel in PROFILE_OUTPUTS if profile else (rel in ('checkpoint.json','review_queue.csv','review_queue.xlsx') or re.fullmatch(r'evidence/[0-9a-f]{64}\.json',rel))
        if not allowed:
            raise SyncError()
        if file.is_symlink() or root.resolve() not in file.resolve().parents or not file.is_file() or file.stat().st_size>10_000_000:
            raise SyncError()
    return files

def upload(api, root, profile=False, rendered=False):
    if rendered and not profile:raise SyncError()
    api.verify_private()
    state=json.loads((root/'.sync-state.json').read_text())
    if state.get('profile_mode', False) != profile or state.get('rendered_mode', False) != rendered:
        raise SyncError()
    # Refuse overwrite of any concurrently updated private dataset.
    if api.head()!=state['head']:
        raise SyncError()
    for name,digest in state['inputs'].items():
        if name not in (('instagram_history.json',) if profile else ('checkpoint.json',)) and hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
            raise SyncError()
    tree=[]
    for file in output_files(root, profile=profile):
        api.verify_private()
        data=file.read_bytes()
        blob=api.request('POST','/git/blobs',{'content':base64.b64encode(data).decode(),'encoding':'base64'})
        # Verify Git's returned SHA against local bytes before constructing commit.
        expected=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        if blob.get('sha')!=expected:
            raise SyncError()
        tree.append({'path':file.relative_to(root).as_posix(),'mode':'100644','type':'blob','sha':expected})
    newtree=api.request('POST','/git/trees',{'base_tree':state['tree'],'tree':tree})
    commit=api.request('POST','/git/commits',{'message':'Update private project evidence and review queue','tree':newtree['sha'],'parents':[state['head']]})
    api.verify_private()
    if api.head()!=state['head']:
        raise SyncError()
    api.request('PATCH','/git/refs/heads/main',{'sha':commit['sha'],'force':False})
    if api.head()!=commit['sha']:
        raise SyncError()
    atomic_json(root/'.upload-receipt.json',{'commit':commit['sha'],'files':len(tree)})

def main():
    p=argparse.ArgumentParser()
    p.add_argument('mode',choices=['download','upload'])
    p.add_argument('--root',required=True)
    p.add_argument('--profile',action='store_true')
    p.add_argument('--rendered',action='store_true')
    args=p.parse_args()
    os.umask(0o077)
    try:
        api=GitHub()
        (download if args.mode=='download' else upload)(api,Path(args.root).resolve(),profile=args.profile,rendered=args.rendered)
    except Exception:
        # No exception text, request URLs, private repository names or server body.
        sys.exit('Private data transfer stopped; no diagnostic data emitted.')

if __name__=='__main__': main()
