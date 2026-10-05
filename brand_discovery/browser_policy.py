"""One-profile browser admission and network policy. No browser or HTTP calls."""
from urllib.parse import urlsplit
import csv
from pathlib import Path
from .instagram import profile_identity
from .collector import public_ip

ASSET_HOSTS={'www.instagram.com','static.cdninstagram.com'}
ASSET_TYPES={'script','stylesheet','image','font'}

def admit_profile(root, history):
    with (root/'instagram_browser_profile.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    if len(rows)!=1:raise ValueError('one_profile_required')
    row=rows[0];identity=profile_identity(row.get('profile_url',''))
    if row.get('profile_link_verified')!='true' or row.get('allow_first_rendered_trial')!='true' or not row.get('official_source_url'):
        raise ValueError('verified_first_trial_required')
    if not isinstance(history,list) or not history:raise ValueError('reviewed_history_required')
    seen=False
    for report in history:
        for old in report.get('results',[]):
            try:previous=profile_identity(old.get('profile_url',''))
            except ValueError:continue
            if previous!=identity:continue
            seen=True
            # Only explicit never-attempted records are eligible. Unknown history
            # is not permission to retry through a different client.
            if old.get('attempted_at') is not None or old.get('status')!='skipped_after_stop':
                raise ValueError('prior_request_or_restriction')
    if not seen:raise ValueError('explicit_never_attempted_record_required')
    return row

class BrowserPolicy:
    def __init__(self,profile_url,resolver=public_ip):
        self.identity=profile_identity(profile_url);self.resolver=resolver
        self.navigation_count=0;self.requests=0;self.blocked_resources=0
        self.stop=None;self.checked_hosts=set();self.http_status=None
    def block(self,status,evidence):
        if self.stop is None:self.stop={'status':status,'restriction_evidence':evidence}
        return False
    def permit(self,url,method,resource_type,is_main_navigation,headers):
        self.requests+=1
        if self.stop:return False
        if self.requests>80:return self.block('request_budget_exceeded','bounded_request_limit')
        try:
            p=urlsplit(url)
            safe=p.scheme=='https' and p.hostname in ASSET_HOSTS and p.port in (None,443) and not p.username and not p.password
        except ValueError:safe=False
        if not safe:
            self.blocked_resources+=1
            return self.block('redirect_refused','navigation_outside_scope') if is_main_navigation else False
        if any(k.lower() in ('authorization','proxy-authorization') and v for k,v in headers.items()):
            return self.block('credential_boundary_violation','credential_header_present')
        if method!='GET':self.blocked_resources+=1;return False
        path=p.path
        if is_main_navigation:
            if path=='/accounts/login' or path.startswith('/accounts/login/'):
                return self.block('login_required','login_destination_path')
            if any(path==x or path.startswith(x+'/') for x in ('/challenge','/checkpoint')):
                return self.block('challenge','challenge_destination_path')
            if resource_type!='document' or self.navigation_count or p.hostname!='www.instagram.com' or path.rstrip('/')!='/'+self.identity or p.query or p.fragment:
                return self.block('redirect_refused','only_one_initial_profile_navigation')
        else:
            if '%' in path or '\\' in path or '..' in path.split('/'):
                self.blocked_resources+=1;return False
            if resource_type not in ASSET_TYPES or p.query.find('__a=')>=0 or any(path==x or path.startswith(x+'/') for x in ('/api','/graphql','/ajax','/accounts','/challenge','/checkpoint')):
                self.blocked_resources+=1;return False
            if not (path.startswith('/rsrc.php/') or path.startswith('/static/') or path=='/rsrc.php'):
                self.blocked_resources+=1;return False
        if p.hostname not in self.checked_hosts:
            try:self.resolver(p.hostname)
            except Exception:return self.block('address_policy_refused','public_destination_not_verified')
            self.checked_hosts.add(p.hostname)
        if is_main_navigation:self.navigation_count+=1
        return True
    def navigation_response(self,status):
        self.http_status=status
        if status in (401,403,429,451):self.block('http_'+str(status),'navigation_response_status')
        elif status>=500:self.block('http_5xx','navigation_response_status')
