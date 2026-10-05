"""Manual one-shot observation of one never-requested, verified public profile."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sys
import time
from .browser_policy import admit_profile,BrowserPolicy
from .browser_runtime import create_context
from .browser_redirect_guard import install_response_guard
from .browser_snapshot import snapshot_from_loaded_page
from .rendered_profile import assess_visible_snapshot
from .instagram import profile_identity,classify_error
from .collector import atomic_json,validate_private_root,write_csv
from .xlsx import write_xlsx

def now():return datetime.now(timezone.utc).isoformat()

def observe_one(row,root):
    from playwright.sync_api import sync_playwright,TimeoutError as BrowserTimeout
    identity=profile_identity(row['profile_url']);target='https://www.instagram.com/'+identity+'/'
    result={'brand_id':row.get('brand_id',''),'profile_url':row['profile_url'],'source_record':dict(row),
            'raw_display':None,'nullable_count':None,'precision':'unknown','observed_at':None,
            'attempted_at':None,'status':'browser_not_started','error_category':None,
            'evidence_kind':'no_profile_observation','evidence_url':target,
            'profile_navigation_attempted':False,'restriction_evidence':None}
    policy=BrowserPolicy(target)
    with sync_playwright() as pw:
        browser,context=create_context(pw)
        try:
            page=context.new_page();page.set_default_timeout(1000)
            def route_request(route):
                try:
                    request=route.request
                    main=request.is_navigation_request() and request.frame==page.main_frame
                    if request.is_navigation_request() and request.frame!=page.main_frame:
                        policy.blocked_resources+=1;route.abort();return
                    if policy.permit(request.url,request.method,request.resource_type,main,{name:'present' for name in ('authorization','proxy-authorization') if request.header_value(name) is not None}):route.continue_()
                    else:route.abort()
                except Exception:
                    policy.block('request_policy_error','request_context_not_verified');route.abort()
            def response(response):
                try:
                    if response.status in (401,403,429,451):
                        policy.block('http_'+str(response.status),'response_access_restriction')
                    if response.request.is_navigation_request() and response.request.frame==page.main_frame:
                        policy.navigation_response(response.status)
                except Exception:policy.block('request_policy_error','response_context_not_verified')
            context.route('**/*',route_request)
            context.route_web_socket('**/*',lambda socket:socket.close())
            page.on('response',response)
            install_response_guard(context,page,policy)
            context.set_offline(False)
            result['attempted_at']=now();result['profile_navigation_attempted']=True
            try:
                page.goto(target,wait_until='domcontentloaded',timeout=20000)
                deadline=time.monotonic()+8
                while time.monotonic()<deadline and not policy.stop:
                    snapshot=snapshot_from_loaded_page(page,target,page.url,now(),policy.http_status)
                    decision=assess_visible_snapshot(snapshot)
                    if decision['stop_batch'] or decision['status'].startswith('observed_'):
                        result.update(decision);break
                    result.update(decision)
                    page.wait_for_timeout(400)
            except BrowserTimeout:
                result.update(status='render_timeout',error_category='timeout')
            except Exception as exc:
                result.update(status='render_error',error_category=classify_error(exc))
            if policy.stop:
                result.update(policy.stop);result['error_category']=None
                result['evidence_kind']='navigation_or_request_restriction'
            if not result['status'].startswith('observed_'):
                result.update(raw_display=None,nullable_count=None,precision='unknown',observed_at=None)
            result['http_status']=policy.http_status
            result['initial_navigation_requests']=policy.navigation_count
            result['blocked_resource_requests']=policy.blocked_resources
            if result['status'] in ('count_not_visible','public_profile_unconfirmed') and policy.blocked_resources:
                result['status']='rendering_incomplete_policy'
            return result
        finally:
            try:context.close()
            except Exception:result['cleanup_error']='context_close_error'
            try:browser.close()
            except Exception:result['cleanup_error']='browser_close_error'

def run(root):
    history_path=root/'instagram_history.json'
    if not history_path.is_file():raise ValueError('reviewed_history_required')
    history=json.loads(history_path.read_text())
    row=admit_profile(root,history)
    try:result=observe_one(row,root)
    except Exception as exc:
        result={'brand_id':row.get('brand_id',''),'profile_url':row['profile_url'],'source_record':dict(row),
                'status':'browser_start_error','error_category':classify_error(exc),'raw_display':None,
                'nullable_count':None,'precision':'unknown','observed_at':None,'attempted_at':None,
                'profile_navigation_attempted':False}
    report={'schema_version':3,'observation_mode':'normal_browser_visible_ui','run_completed_at':now(),
            'robots_precheck_performed':False,'one_profile_only':True,'results':[result]}
    history.append(report);atomic_json(history_path,history);atomic_json(root/'instagram_results.json',report)
    fields=['brand_id','profile_url','raw_display','nullable_count','precision','observed_at','attempted_at','status','error_category','evidence_kind','evidence_url']
    rows=[{k:('' if result.get(k) is None else result.get(k)) for k in fields}]
    write_csv(root/'instagram_results.csv',rows,fields);write_xlsx(root/'instagram_results.xlsx',rows,fields)
    return report

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--private-root',required=True);args=parser.parse_args();os.umask(0o077)
    try:
        if os.environ.get('LAYER_APPROVED_BROWSER_ONE_SHOT')!='true':raise ValueError()
        root=validate_private_root(args.private_root,Path(__file__).resolve().parents[1]);run(root)
    except Exception:sys.exit('Private rendered observation stopped; no diagnostic data emitted.')

if __name__=='__main__':main()
