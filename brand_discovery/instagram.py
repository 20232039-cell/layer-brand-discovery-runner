"""Bounded, logged-out public HTML observation. No cookies or private APIs."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import ssl
import sys
import time
from urllib.parse import urlsplit, urljoin
from urllib.robotparser import RobotFileParser
from .collector import PinnedTLS, atomic_json, validate_private_root, write_csv
from .xlsx import write_xlsx

AGENT = 'LayerPublicProfileEvidence/0.1'
HOST = 'www.instagram.com'
STOP_STATUSES = {'robots_disallow','robots_unavailable','login_required','challenge',
                 'http_5xx','http_401','http_403','http_429','http_500','http_502','http_503','redirect_refused','identity_mismatch',
                 'response_too_large','network_error','unsupported_response'}
RESERVED = {'accounts','explore','p','reel','reels','stories','direct','about','developer','legal','challenge','web','api'}

def profile_identity(url):
    p=urlsplit(url)
    if p.scheme!='https' or p.hostname not in (HOST,'instagram.com') or p.username or p.password or p.port not in (None,443) or p.query or p.fragment:
        raise ValueError('invalid_profile_url')
    parts=p.path.strip('/').split('/')
    if len(parts)!=1 or not re.fullmatch(r'[A-Za-z0-9._]{1,30}',parts[0]) or not re.search(r'[A-Za-z0-9_]',parts[0]) or parts[0].lower() in RESERVED:
        raise ValueError('invalid_profile_url')
    return parts[0].lower()

class MetaPage(HTMLParser):
    def __init__(self):
        super().__init__();self.meta={};self.canonicals=[];self.titles=[];self.in_title=False;self.stop_hint=None;self.surface=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ('script','style'):self.skip+=1
        if tag=='form' and '/accounts/login' in a.get('action',''):self.stop_hint='login_required'
        if tag=='input' and a.get('type','').lower()=='password':self.stop_hint='login_required'
        if tag in ('form','iframe') and any(x in a.get('action','')+a.get('src','') for x in ('/challenge','/checkpoint','captcha')):self.stop_hint='challenge'
        if tag=='meta':
            name=a.get('property') or a.get('name','')
            if name.lower() in ('og:title','og:url','og:description','description'):
                self.meta.setdefault(name.lower(),[]).append(a.get('content',''))
        if tag=='link' and 'canonical' in a.get('rel','').lower().split():
            self.canonicals.append(a.get('href',''))
        if tag=='title':self.in_title=True
    def handle_endtag(self,tag):
        if tag=='title':self.in_title=False
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
    def handle_data(self,data):
        if self.in_title:self.titles.append(data)
        if not self.skip:self.surface.append(data)

def parse_number(raw):
    text=raw.strip()
    if re.fullmatch(r'(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)',text):
        return int(text.replace(',','')),'exact'
    if re.fullmatch(r'\d+(?:[.,]\d+)?\s*(?:[KMB]|만|천|억)',text,re.I):
        # Display rounding cannot establish an exact count. Never fabricate zero.
        return None,'abbreviated'
    return None,'ambiguous'

def parse_profile(html,url):
    expected=profile_identity(url);page=MetaPage();page.feed(html)
    if page.stop_hint:return {'status':page.stop_hint}
    surface=' '.join(page.surface).lower()
    if any(x in surface for x in ('please log in to continue','log in to continue','login to continue','sign in to continue','log in to see photos and videos','로그인하여 계속')):return {'status':'login_required'}
    if any(x in surface for x in ('confirm you are human','verify you are human','please wait a few minutes before you try again')):return {'status':'challenge'}
    title=' '.join(page.titles+page.meta.get('og:title',[]))
    if re.search(r'challenge|checkpoint|confirm (?:your|you)|verify (?:your|you)|security check|로봇|본인 확인',title,re.I):
        return {'status':'challenge'}
    if re.search(r'(?:log\s*in|login|로그인)\s*(?:[•|\-–]|to (?:continue|instagram))',title,re.I):
        return {'status':'login_required'}
    identities=[]
    for value in page.canonicals+page.meta.get('og:url',[]):
        try:identities.append(profile_identity(value))
        except ValueError:
            if '/accounts/login' in value:return {'status':'login_required'}
            if '/challenge' in value or '/checkpoint' in value:return {'status':'challenge'}
            return {'status':'identity_mismatch'}
    for value in page.meta.get('og:title',[]):
        identities.extend(x.lower() for x in re.findall(r'\(@([A-Za-z0-9._]{1,30})\)',value))
    if identities and any(x!=expected for x in identities):
        return {'status':'identity_mismatch'}
    if not identities:
        # No profile-bound identity evidence: don't mine script or API payloads.
        return {'status':'profile_identity_unverified'}
    observations=[]
    number_token=r'[+\-\u2212]?\d(?:[\d., \t\u00a0\u202f]*\d)?(?:[ \t]*[KMB만천억])?'
    for source in ('og:description','description'):
        for description in page.meta.get(source,[]):
            matches=list(re.finditer(r'(?<![\w.,+\-\u2212])('+number_token+r')\s+followers?\b',description,re.I))
            matches+=list(re.finditer(r'팔로워\s*('+number_token+r')(?=\s*(?:명|,?\s*팔로잉|$))',description,re.I))
            for match in matches:
                raw=match.group(1).strip();count,precision=parse_number(raw)
                observations.append({'raw_display':raw,'nullable_count':count,'precision':precision,
                                     'source':'public_html_meta_'+source,'metadata_excerpt':description[:1000]})
    unique={(x['raw_display'],x['nullable_count'],x['precision']) for x in observations}
    if len(unique)>1:
        return {'status':'conflicting_displays','precision':'ambiguous','observations':observations}
    if not observations:return {'status':'count_not_present'}
    result=dict(observations[0]);result['status']='observed_'+result['precision']
    result['profile_identity_verified']=True
    return result

class PublicFetcher:
    def __init__(self):self.last=0;self.robots=None;self.delay=5
    def raw(self,path):
        wait=self.delay-(time.monotonic()-self.last)
        if wait>60:return 'robots_unavailable',{},b''
        if wait>0:time.sleep(wait)
        self.last=time.monotonic()
        conn=PinnedTLS(HOST,timeout=15,context=ssl.create_default_context())
        try:
            conn.request('GET',path,headers={'User-Agent':AGENT,'Accept':'text/html,text/plain','Accept-Language':'en-US,en;q=0.8','Accept-Encoding':'identity'})
            response=conn.getresponse();body=response.read(2_000_001)
            if len(body)>2_000_000:return 'response_too_large',{},b''
            return response.status,{k.lower():v for k,v in response.getheaders()},body
        except Exception:return 'network_error',{},b''
        finally:conn.close()
    def get(self,url):
        handle=profile_identity(url);url='https://'+HOST+'/'+handle+'/'
        if self.robots is None:
            status,headers,body=self.raw('/robots.txt')
            if status in (403,429):return {'status':'http_'+str(status)}
            if status!=200:return {'status':'robots_unavailable'}
            robots_text=body.decode('utf-8','replace')
            # HTML login/challenge/error pages are never interpreted as allow-all robots.
            if 'html' in headers.get('content-type','').lower() or robots_text.lstrip().startswith('<'):
                guard=parse_profile(robots_text,url)
                return {'status':guard['status'] if guard['status'] in ('login_required','challenge') else 'robots_unavailable'}
            if not re.search(r'^\s*User-agent\s*:',robots_text,re.I|re.M):
                return {'status':'robots_unavailable'}
            rp=RobotFileParser();rp.parse(robots_text.splitlines())
            self.robots=rp
            rate=rp.request_rate(AGENT) or rp.request_rate('*')
            self.delay=max(self.delay,rp.crawl_delay(AGENT) or rp.crawl_delay('*') or 0,rate.seconds/rate.requests if rate else 0)
        if not self.robots.can_fetch(AGENT,url):return {'status':'robots_disallow'}
        status,headers,body=self.raw('/'+handle+'/')
        if status in (403,429):return {'status':'http_'+str(status)}
        if isinstance(status,str):return {'status':status}
        if status in (301,302,303,307,308):
            # No redirect is followed. In particular, never follow a login flow.
            target=urljoin(url,headers.get('location',''))
            if '/accounts/login' in target:return {'status':'login_required'}
            if '/challenge' in target or '/checkpoint' in target:return {'status':'challenge'}
            return {'status':'redirect_refused'}
        if status>=500:return {'status':'http_5xx'}
        if status!=200:return {'status':'http_'+str(status)}
        if 'text/html' not in headers.get('content-type',''):return {'status':'unsupported_response'}
        result=parse_profile(body.decode('utf-8','replace'),url)
        result['response_sha256']=hashlib.sha256(body).hexdigest()
        return result

def run(root,fetcher=None):
    with (root/'instagram_profiles.csv').open(encoding='utf-8-sig',newline='') as f:inputs=list(csv.DictReader(f))
    if not 1<=len(inputs)<=3:raise ValueError('one_to_three_profiles_required')
    identities=[profile_identity(r.get('profile_url','')) for r in inputs]
    if len(set(identities))!=len(identities) or any(r.get('profile_link_verified')!='true' or not r.get('official_source_url') for r in inputs):
        raise ValueError('verified_unique_profile_inputs_required')
    fetcher=fetcher or PublicFetcher();results=[];halted=False
    for row in inputs:
        result={'brand_id':row.get('brand_id',''),'profile_url':row['profile_url'],
                'raw_display':None,'nullable_count':None,'precision':'unknown',
                'observed_at':None,'attempted_at':None,
                'status':'skipped_after_stop','source_record':dict(row)}
        if not halted:
            result['attempted_at']=datetime.now(timezone.utc).isoformat()
            try:observed=fetcher.get(row['profile_url'])
            except Exception:observed={'status':'network_error'}
            result.update(observed)
            if result['status'].startswith('observed_'):
                result['observed_at']=datetime.now(timezone.utc).isoformat()
            if result['status'] in STOP_STATUSES:halted=True
        results.append(result)
    report={'schema_version':1,'run_completed_at':datetime.now(timezone.utc).isoformat(),
            'stopped_early':halted,'logged_out_public_html_only':True,'results':results}
    # A new run never replaces a previous exact success with a fake zero.
    history_path=root/'instagram_history.json'
    history=json.loads(history_path.read_text()) if history_path.exists() else []
    history.append(report)
    atomic_json(history_path,history)
    atomic_json(root/'instagram_results.json',report)
    fields=['brand_id','profile_url','raw_display','nullable_count','precision','observed_at','attempted_at','status']
    rows=[{k:('' if r.get(k) is None else r.get(k)) for k in fields} for r in results]
    write_csv(root/'instagram_results.csv',rows,fields)
    write_xlsx(root/'instagram_results.xlsx',rows,fields)
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--private-root',required=True);args=p.parse_args();os.umask(0o077)
    try:
        if os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('LAYER_APPROVED_INSTAGRAM_CHECK')!='true':raise ValueError()
        root=validate_private_root(args.private_root,Path(__file__).resolve().parents[1]);run(root)
    except Exception:sys.exit('Private public-profile observation stopped; no diagnostic data emitted.')

if __name__=='__main__':main()
