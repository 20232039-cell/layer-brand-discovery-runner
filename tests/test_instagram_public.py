import csv
import io
import json
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from brand_discovery.instagram import parse_number, parse_profile, profile_identity, PublicFetcher, run
from brand_discovery.private_sync import output_files, SyncError

URL='https://www.instagram.com/synthetic_test_01/'
def fixture(description='1,234 Followers, 5 Following, 6 Posts',handle='synthetic_test_01'):
    return '<html><meta property="og:url" content="https://www.instagram.com/'+handle+'/"><meta property="og:title" content="Synthetic (@'+handle+') • Instagram"><meta property="og:description" content="'+description+'"></html>'

class InstagramTests(unittest.TestCase):
    def test_exact_zero_is_only_observed_zero(self):
        self.assertEqual(parse_number('0'),(0,'exact'))
        self.assertEqual(parse_number('1,234'),(1234,'exact'))
        self.assertEqual(parse_number('1234'),(1234,'exact'))
    def test_abbreviated_never_exact_integer(self):
        for raw in ['1.2K','1.2만','3M','1,2K','2억','12천']:
            self.assertEqual(parse_number(raw),(None,'abbreviated'))
        for raw in ['1.234','1,23','','unknown','-1']:
            self.assertEqual(parse_number(raw),(None,'ambiguous'))
    def test_public_meta_only_and_exact(self):
        r=parse_profile(fixture(),URL)
        self.assertEqual((r['status'],r['nullable_count'],r['raw_display']),('observed_exact',1234,'1,234'))
    def test_korean_and_short_displays(self):
        r=parse_profile(fixture('팔로워 1.2만명, 팔로잉 5명'),URL)
        self.assertEqual((r['status'],r['nullable_count'],r['raw_display']),('observed_abbreviated',None,'1.2만'))
    def test_ambiguous_and_conflicting_displays(self):
        self.assertEqual(parse_profile(fixture('1.234 Followers'),URL)['status'],'observed_ambiguous')
        html=fixture()+'<meta name="description" content="9,999 Followers">'
        self.assertEqual(parse_profile(html,URL)['status'],'conflicting_displays')
    def test_identity_must_match(self):
        self.assertEqual(parse_profile(fixture(handle='wrong_synthetic'),URL)['status'],'identity_mismatch')
        self.assertEqual(parse_profile('<meta name="description" content="1,234 Followers">',URL)['status'],'profile_identity_unverified')
    def test_no_private_script_extraction(self):
        html=fixture('No public count')+'<script>{"edge_followed_by":{"count":1234}}</script>'
        self.assertEqual(parse_profile(html,URL)['status'],'count_not_present')
    def test_negative_not_misparsed_as_positive(self):
        r=parse_profile(fixture('-123 Followers'),URL)
        self.assertEqual(r['status'],'observed_ambiguous');self.assertIsNone(r['nullable_count'])
    def test_login_and_challenge_stop_even_with_profile_metadata(self):
        for html in [fixture()+'<form action="/accounts/login/">',fixture()+'<input type="password">',fixture()+'<p>Log in to continue</p>','<title>Login • Instagram</title>']:
            self.assertEqual(parse_profile(html,URL)['status'],'login_required')
        for html in ['<title>Security Check</title>',fixture()+'<iframe src="/challenge/test">',fixture()+'<p>Verify you are human</p>']:
            self.assertEqual(parse_profile(html,URL)['status'],'challenge')
    def test_only_normal_profile_urls(self):
        for url in ['http://www.instagram.com/test/','https://www.instagram.com/accounts/login/','https://www.instagram.com/test/?__a=1','https://user:password@www.instagram.com/test/','https://www.instagram.com:444/test/','https://example.invalid/test/','https://www.instagram.com/p/123/','https://www.instagram.com/../','https://www.instagram.com/./']:
            with self.assertRaises(ValueError):profile_identity(url)
    def test_single_normal_profile_get_without_robots_precheck(self):
        f=PublicFetcher()
        with patch.object(f,'raw',return_value=(200,{'content-type':'text/html'},fixture().encode())) as raw:
            self.assertEqual(f.get(URL)['status'],'observed_exact')
            raw.assert_called_once_with('/synthetic_test_01/')
    def test_http_and_redirect_stops_no_follow(self):
        for status,headers,expected in [(403,{},'http_403'),(429,{},'http_429'),(451,{},'http_451'),(501,{},'http_5xx'),(504,{},'http_5xx'),(302,{'location':'/accounts/login/'},'login_required'),(302,{'location':'/challenge/'},'challenge'),(302,{'location':'https://example.invalid/'},'redirect_refused')]:
            f=PublicFetcher()
            with patch.object(f,'raw',return_value=(status,headers,b'')) as raw:
                self.assertEqual(f.get(URL)['status'],expected);self.assertEqual(raw.call_count,1)
    def test_spaced_numbers_not_truncated_into_exact_counts(self):
        for display in ['1 234 Followers','1\u202f234 Followers','팔로워 1 234명','팔로워 1\u00a0234명']:
            r=parse_profile(fixture(display),URL)
            self.assertEqual(r['status'],'observed_ambiguous')
            self.assertIsNone(r['nullable_count'])
        self.assertEqual(parse_profile(fixture('팔로워 1,234, 팔로잉 5명'),URL)['nullable_count'],1234)

    def test_public_login_challenge_country_pages_stop(self):
        for html,expected in [('<form action="/accounts/login/"><input type="password"></form>','login_required'),
                              ('<title>CAPTCHA</title>','challenge'),
                              ('<html>This content is not available in your country</html>','country_restricted')]:
            f=PublicFetcher()
            with patch.object(f,'raw',return_value=(200,{'content-type':'text/html'},html.encode())) as raw:
                self.assertEqual(f.get(URL)['status'],expected)
                raw.assert_called_once_with('/synthetic_test_01/')

    def write_input(self,root,count=3):
        with (root/'instagram_profiles.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['brand_id','profile_url','official_source_url','profile_link_verified']);w.writeheader()
            w.writerows({'brand_id':'SYNTHETIC_'+str(i),'profile_url':URL.replace('01',str(i+1).zfill(2)),'official_source_url':'https://example.invalid/','profile_link_verified':'true'} for i in range(count))
    def test_stop_skips_remaining_and_preserves_history(self):
        class Fake:
            def __init__(self):self.calls=0
            def get(self,url):self.calls+=1;return {'status':'http_429'}
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);self.write_input(root);old={'previous_exact_count':1234};(root/'instagram_history.json').write_text(json.dumps([old]))
            f=Fake();out=io.StringIO()
            with redirect_stdout(out),redirect_stderr(out):report=run(root,f)
            self.assertEqual(out.getvalue(),'');self.assertEqual(f.calls,1)
            self.assertEqual([x['status'] for x in report['results']],['http_429','skipped_after_stop','skipped_after_stop'])
            self.assertTrue(all(x['nullable_count'] is None for x in report['results']))
            self.assertIsNone(report['results'][1]['attempted_at'])
            self.assertEqual(json.loads((root/'instagram_history.json').read_text())[0],old)
            self.assertEqual(len(output_files(root,profile=True)),4)
    def test_all_access_restrictions_stop_whole_batch(self):
        for status in ['http_401','http_403','http_429','http_451','http_5xx','country_restricted','login_required','challenge','redirect_refused']:
            class Blocked:
                calls=0
                def get(self,url):self.calls+=1;return {'status':status}
            with tempfile.TemporaryDirectory() as t:
                root=Path(t);self.write_input(root);fetcher=Blocked();report=run(root,fetcher)
                self.assertEqual(fetcher.calls,1)
                self.assertTrue(report['stopped_early'])
                self.assertTrue(all(r['nullable_count'] is None for r in report['results']))
                self.assertEqual(report['results'][1]['status'],'skipped_after_stop')

    def test_limit_and_verified_input(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);self.write_input(root,count=4)
            with self.assertRaises(ValueError):run(root,object())
    def test_workflow_is_private_manual_clean_environment(self):
        s=(Path(__file__).resolve().parents[1]/'.github/workflows/instagram-public.yml').read_text()
        for forbidden in ['schedule:','inputs.','upload-artifact','download-artifact','actions/cache','GITHUB_STEP_SUMMARY','GITHUB_OUTPUT']:
            self.assertNotIn(forbidden,s)
        self.assertIn('ENABLE_INSTAGRAM_PUBLIC_CHECK',s);self.assertIn('env -i',s);self.assertIn('--profile',s)

if __name__=='__main__':unittest.main()
