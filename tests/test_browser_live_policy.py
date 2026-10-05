import csv,json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from brand_discovery.browser_policy import admit_profile,BrowserPolicy
from brand_discovery.instagram_browser import run

URL='https://www.instagram.com/synthetic_new_01/'
class BrowserLivePolicyTests(unittest.TestCase):
    def input(self,root):
        with (root/'instagram_browser_profile.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['brand_id','profile_url','profile_link_verified','official_source_url','allow_first_rendered_trial']);w.writeheader();w.writerow({'brand_id':'synthetic','profile_url':URL,'profile_link_verified':'true','official_source_url':'https://example.invalid/','allow_first_rendered_trial':'true'})
    def test_only_never_requested_identity_admitted(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.input(root)
            with self.assertRaises(ValueError):admit_profile(root,[])
            with self.assertRaises(ValueError):admit_profile(root,[{'results':[]}])
            self.assertEqual(admit_profile(root,[{'results':[{'profile_url':URL,'status':'skipped_after_stop','attempted_at':None}]}])['profile_url'],URL)
            for state in ['login_required','http_403','network_error','observed_exact']:
                history=[{'results':[{'profile_url':'https://instagram.com/SYNTHETIC_NEW_01','status':state,'attempted_at':'synthetic-time'}]}]
                with self.assertRaises(ValueError):admit_profile(root,history)
    def policy(self):return BrowserPolicy(URL,resolver=Mock(return_value='8.8.8.8'))
    def test_exact_single_navigation(self):
        p=self.policy();self.assertTrue(p.permit(URL,'GET','document',True,{}))
        self.assertFalse(p.permit(URL,'GET','document',True,{}));self.assertEqual(p.navigation_count,1)
    def test_login_redirect_refused_before_request(self):
        p=self.policy();p.permit(URL,'GET','document',True,{})
        self.assertFalse(p.permit('https://www.instagram.com/accounts/login/?next=synthetic','GET','document',True,{}))
        self.assertEqual(p.stop['status'],'login_required');self.assertEqual(p.navigation_count,1)
    def test_query_cannot_impersonate_login_path(self):
        p=self.policy();p.permit(URL,'GET','document',True,{})
        self.assertFalse(p.permit(URL+'?next=/accounts/login/','GET','document',True,{}))
        self.assertEqual(p.stop['status'],'redirect_refused')
    def test_static_allowlist_and_private_apis(self):
        p=self.policy()
        self.assertTrue(p.permit('https://static.cdninstagram.com/rsrc.php/v4/synthetic.js','GET','script',False,{}))
        for url,kind in [('https://www.instagram.com/api/v1/public','fetch'),('https://www.instagram.com/graphql/query','xhr'),('https://static.cdninstagram.com/rsrc.php/v4/x.js','fetch'),('https://example.invalid/x.js','script'),('https://127.0.0.1/static/x.js','script'),('https://static.cdninstagram.com/static/%2e%2e/api/x','script')]:
            self.assertFalse(p.permit(url,'GET',kind,False,{}))
    def test_credentials_and_non_public_dns_stop(self):
        for headers in [{'Proxy-Authorization':'SYNTHETIC_ONLY'},{'Authorization':'SYNTHETIC_ONLY'}]:
            p=self.policy();self.assertFalse(p.permit(URL,'GET','document',True,headers));self.assertEqual(p.stop['status'],'credential_boundary_violation')
        p=BrowserPolicy(URL,resolver=Mock(side_effect=ValueError('synthetic private address')))
        self.assertFalse(p.permit(URL,'GET','document',True,{}));self.assertEqual(p.stop['status'],'address_policy_refused')
    def test_anonymous_cookie_is_not_treated_as_imported_authentication(self):
        p=self.policy();self.assertTrue(p.permit(URL,'GET','document',True,{'Cookie':'SYNTHETIC_FIXTURE_ONLY'}))

    def test_http_restrictions_stop_and_no_later_requests(self):
        for code in [401,403,429,451,503]:
            p=self.policy();p.navigation_response(code)
            self.assertIsNotNone(p.stop);self.assertFalse(p.permit(URL,'GET','document',True,{}))
    def test_live_workflow_is_manual_gated_and_credential_isolated(self):
        root=Path(__file__).resolve().parents[1]
        text=(root/'.github/workflows/instagram-browser-one-shot.yml').read_text()
        self.assertIn('ENABLE_INSTAGRAM_BROWSER_CHECK',text)
        self.assertNotIn('${{ runner.temp }}',text)
        self.assertIn('workflow_dispatch:',text);self.assertIn('env -i',text)
        for forbidden in ['schedule:','inputs.','upload-artifact','download-artifact','actions/cache','GITHUB_OUTPUT','GITHUB_STEP_SUMMARY']:
            self.assertNotIn(forbidden,text)
        execution=text.split('name: Observe one never-requested public profile')[1].split('name: Save private result')[0]
        self.assertNotIn('secrets.',execution)
    def test_runtime_never_imports_or_reads_cookie_values(self):
        root=Path(__file__).resolve().parents[1]
        runtime=(root/'brand_discovery/browser_runtime.py').read_text()
        collector=(root/'brand_discovery/instagram_browser.py').read_text()
        for forbidden in ['launch_persistent_context','storage_state','add_cookies','context.cookies(','.all_headers()', 'user_agent=', 'proxy=', 'http_credentials=']:
            self.assertNotIn(forbidden,runtime+collector)
        self.assertIn('browser.new_context(',runtime)

    def test_output_keeps_previous_failure_history_and_nulls(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);self.input(root);old={'results':[{'profile_url':'https://www.instagram.com/synthetic_old_01/','status':'login_required','attempted_at':'synthetic-time'},{'profile_url':URL,'status':'skipped_after_stop','attempted_at':None}]}
            (root/'instagram_history.json').write_text(json.dumps([old]))
            result={'brand_id':'synthetic','profile_url':URL,'status':'login_required','raw_display':None,'nullable_count':None,'precision':'unknown','observed_at':None,'attempted_at':'synthetic-now'}
            with patch('brand_discovery.instagram_browser.observe_one',return_value=result) as observe:
                report=run(root);observe.assert_called_once()
            self.assertEqual(json.loads((root/'instagram_history.json').read_text())[0],old)
            self.assertIsNone(report['results'][0]['nullable_count'])
            self.assertNotIn(',None,',(root/'instagram_results.csv').read_text())

if __name__=='__main__':unittest.main()
