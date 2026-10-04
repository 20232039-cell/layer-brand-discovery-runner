"""Offline synthetic-only E2E canary; private sentinel values are never printed."""
import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import sys
from .collector import run, validate_private_root

class SyntheticFetcher:
    def __init__(self, names):
        self.names=names
    def get(self,url):
        if url=='https://canary.invalid/error':
            raise RuntimeError('Private synthetic failure: '+self.names['error'])
        if url!='https://canary.invalid/success':
            raise ValueError('Not an approved synthetic fixture')
        return url,'<html><body>상의 셔츠 장바구니 '+self.names['success']+'</body></html>'

def exercise(root):
    with (root/'candidates.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    if len(rows)!=2 or any(not r.get('name','').startswith('CANARY_') for r in rows):
        raise ValueError('Synthetic inputs required')
    names={}
    for row in rows:
        url=row.get('official_url','')
        if url not in ('https://canary.invalid/success','https://canary.invalid/error'):
            raise ValueError('Synthetic inputs required')
        names[url.rsplit('/',1)[1]]=row['name']
    if set(names)!= {'success','error'}:
        raise ValueError('Synthetic fixture pair required')
    # Retry-safe: previous synthetic completed records are accepted for repeat runs.
    run(root,limit=2,fetcher=SyntheticFetcher(names))
    saved=json.loads((root/'checkpoint.json').read_text())
    assert len(saved)==2
    by_url={r['submitted_url']:r for r in saved.values()}
    assert by_url['https://canary.invalid/success']['status']=='needs_review'
    assert by_url['https://canary.invalid/error']['status']=='fetch_failed'
    assert by_url['https://canary.invalid/success']['identity_status']=='unverified'
    assert run(root,limit=2,fetcher=SyntheticFetcher(names))==0
    empty=root/'empty-canary'
    empty.mkdir()
    try:
        (empty/'candidates.csv').write_text('name,official_url\n')
        assert run(empty,fetcher=SyntheticFetcher(names))==0
        assert json.loads((empty/'checkpoint.json').read_text())=={}
    finally:
        shutil.rmtree(empty)

def main():
    p=argparse.ArgumentParser();p.add_argument('--private-root',required=True);args=p.parse_args()
    os.umask(0o077)
    try:
        root=validate_private_root(args.private_root,Path(__file__).resolve().parents[1]);exercise(root)
    except Exception:
        sys.exit('Synthetic privacy canary failed; no diagnostic data emitted.')

if __name__=='__main__': main()
