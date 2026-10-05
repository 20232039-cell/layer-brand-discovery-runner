"""Cookie writes on a fulfilled synthetic HTTPS origin; context remains offline."""
from pathlib import Path
import tempfile
import unittest
from playwright.sync_api import sync_playwright
from brand_discovery.browser_runtime import create_context,verify_cookie_policy,COOKIE_FIXTURE

class CookiePolicyTests(unittest.TestCase):
    def test_native_cookie_blocking_on_synthetic_origin(self):
        with tempfile.TemporaryDirectory() as td,sync_playwright() as pw:
            context=create_context(pw,td)
            try:self.assertTrue(verify_cookie_policy(context));self.assertEqual(context.cookies(),[])
            finally:context.close()
    def test_canary_detects_cookie_storage_without_block_policy(self):
        # Control proves that the fixture can set cookies; no private/user cookie is used.
        with tempfile.TemporaryDirectory() as td,sync_playwright() as pw:
            context=pw.chromium.launch_persistent_context(td,channel='chromium',headless=True,offline=True,service_workers='block',ignore_https_errors=False)
            try:self.assertFalse(verify_cookie_policy(context))
            finally:context.close()

if __name__=='__main__':unittest.main()
