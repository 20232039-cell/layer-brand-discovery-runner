"""Real Chromium, synthetic documents only, offline network plus deny-all routing."""
import json
from pathlib import Path
import tempfile
import unittest
from playwright.sync_api import sync_playwright
from brand_discovery.browser_snapshot import snapshot_from_loaded_page
from brand_discovery.rendered_profile import assess_visible_snapshot

PROFILE='https://www.instagram.com/synthetic_rendered_01/'
STAMP='2026-10-05T00:00:00+00:00'
BASE='<h1>synthetic_rendered_01</h1><a href="/synthetic_rendered_01/followers/">1.2만 followers</a>'

class OfflineBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();root=Path(cls.temp.name)/'Default';root.mkdir()
        # Native browser content setting; not imported cookies or credentials.
        (root/'Preferences').write_text(json.dumps({'profile':{'default_content_setting_values':{'cookies':2},'block_third_party_cookies':True}}))
        cls.pw=sync_playwright().start()
        cls.context=cls.pw.chromium.launch_persistent_context(cls.temp.name,channel='chromium',headless=True,offline=True,service_workers='block',ignore_https_errors=False)
        cls.aborted=[]
        def deny(route):
            cls.aborted.append(route.request.url);route.abort()
        cls.context.route('**/*',deny)
    @classmethod
    def tearDownClass(cls):
        cls.context.close();cls.pw.stop();cls.temp.cleanup()
    def setUp(self):self.page=self.context.new_page()
    def tearDown(self):self.page.close()
    def observe(self,html,document_url=PROFILE,http_status=200):
        self.page.set_content(html,wait_until='domcontentloaded')
        snap=snapshot_from_loaded_page(self.page,PROFILE,document_url,STAMP,http_status)
        return assess_visible_snapshot(snap)
    def test_login_cta_does_not_hide_visible_followers(self):
        r=self.observe(BASE+'<button>Log in</button>')
        self.assertEqual(r['status'],'observed_abbreviated');self.assertEqual(r['raw_display'],'1.2만')
        self.assertIsNone(r['nullable_count']);self.assertEqual(r['observed_at'],STAMP)
    def test_hidden_count_not_observed(self):
        r=self.observe('<h1>synthetic_rendered_01</h1><a hidden href="/synthetic_rendered_01/followers/">1,234 followers</a><button>Log in</button>')
        self.assertEqual(r['status'],'count_not_visible')
    def test_login_overlay_blocks_underlying_count(self):
        r=self.observe(BASE+'<div role="dialog" aria-modal="true" style="position:fixed;inset:0;background:white;z-index:99"><input type="password"><button>Log in</button></div>')
        self.assertEqual(r['status'],'login_required');self.assertTrue(r['stop_batch']);self.assertIsNone(r['raw_display'])
    def test_opacity_zero_ancestor_not_observed(self):
        r=self.observe('<h1>synthetic_rendered_01</h1><div style="opacity:0"><a href="/synthetic_rendered_01/followers/">1,234 followers</a></div>')
        self.assertEqual(r['status'],'count_not_visible')
    def test_passwordless_login_overlay_is_a_stop(self):
        r=self.observe(BASE+'<div role="dialog" aria-modal="true" style="position:fixed;inset:0;background:white;z-index:99"><h2>Log in to continue</h2><button>Log in</button></div>')
        self.assertEqual(r['status'],'login_required');self.assertTrue(r['stop_batch'])
    def test_login_destination_classification_without_navigation(self):
        r=self.observe(BASE,document_url='https://www.instagram.com/accounts/login/?next=synthetic')
        self.assertEqual(r['status'],'login_required')
        self.assertEqual(self.page.url,'about:blank')
    def test_challenge_and_country_are_stops(self):
        for html,status in [('<h1>Verify you are human</h1>','challenge'),('<h1>Not available in your country</h1>','country_restricted')]:
            self.assertEqual(self.observe(html)['status'],status)
    def test_external_subresource_is_aborted(self):
        before=len(self.aborted)
        self.observe(BASE+'<img src="https://synthetic-external.invalid/image.png">')
        self.page.wait_for_timeout(100)
        self.assertGreater(len(self.aborted),before)
        self.assertEqual(self.page.url,'about:blank')
    def test_no_recorded_cookies_or_browser_artifacts(self):
        self.observe(BASE)
        self.assertEqual(self.context.cookies(),[])
        # This checks the about:blank fixture only; full cookie-policy canary is separate.
        self.assertFalse(any(Path(self.temp.name).rglob('*.har')))

if __name__=='__main__':unittest.main()
