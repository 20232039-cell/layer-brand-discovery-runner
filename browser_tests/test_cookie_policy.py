"""Anonymous fixture session state is accepted only within one fresh context."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
import json
import unittest
from playwright.sync_api import sync_playwright
from brand_discovery.browser_runtime import create_context

class SessionIsolationTests(unittest.TestCase):
    def test_fresh_contexts_do_not_share_anonymous_session(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200);self.send_header('Content-Type','text/html')
                if self.path=='/set':self.send_header('Set-Cookie','anonymous_fixture=synthetic; HttpOnly; SameSite=Lax')
                self.end_headers()
                if self.path=='/set':self.wfile.write(b'<script>document.cookie="anonymous_js=synthetic; SameSite=Lax"</script><p>Synthetic session fixture</p>')
                else:
                    # Check presence only. No cookie or authorization value is read/logged.
                    result={'cookie_present':'Cookie' in self.headers,'authorization_present':'Authorization' in self.headers,'proxy_auth_present':'Proxy-Authorization' in self.headers}
                    self.wfile.write(json.dumps(result).encode())
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        origin='http://127.0.0.1:'+str(server.server_port)
        try:
            with sync_playwright() as pw:
                browser,first=create_context(pw)
                def local_only(route):
                    if route.request.url.startswith(origin+'/'):route.continue_()
                    else:route.abort()
                first.route('**/*',local_only);first.set_offline(False);p=first.new_page()
                p.goto(origin+'/check');initial=json.loads(p.locator('body').inner_text())
                self.assertEqual(initial,{'cookie_present':False,'authorization_present':False,'proxy_auth_present':False})
                p.goto(origin+'/set');p.goto(origin+'/check');after=json.loads(p.locator('body').inner_text())
                self.assertTrue(after['cookie_present']);self.assertFalse(after['authorization_present'])
                second=browser.new_context(service_workers='block',ignore_https_errors=False)
                second.route('**/*',local_only);p2=second.new_page();p2.goto(origin+'/check')
                self.assertFalse(json.loads(p2.locator('body').inner_text())['cookie_present'])
                first.close();second.close()
                third=browser.new_context(service_workers='block',ignore_https_errors=False)
                third.route('**/*',local_only);p3=third.new_page();p3.goto(origin+'/check')
                self.assertEqual(json.loads(p3.locator('body').inner_text()),initial)
                third.close();browser.close()
        finally:server.shutdown();server.server_close();thread.join(timeout=2)

if __name__=='__main__':unittest.main()
