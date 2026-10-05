"""Loopback-only response fixtures prove Chromium cannot follow redirects."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
import unittest
from playwright.sync_api import sync_playwright,Error as BrowserError
from brand_discovery.browser_policy import BrowserPolicy
from brand_discovery.browser_redirect_guard import install_response_guard

class RedirectGuardTests(unittest.TestCase):
    def test_redirect_is_failed_before_second_server_request(self):
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                if self.path=='/initial':
                    self.send_response(302);self.send_header('Location','/accounts/login/');self.end_headers()
                else:
                    self.send_response(200);self.end_headers();self.wfile.write(b'Synthetic unexpected follow')
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        origin='http://127.0.0.1:'+str(server.server_port)
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='chromium',headless=True)
                context=browser.new_context(service_workers='block',ignore_https_errors=False)
                page=context.new_page();policy=BrowserPolicy('https://www.instagram.com/synthetic_unrequested/',resolver=lambda _: '8.8.8.8')
                browser_requests=[];page.on('request',lambda r:browser_requests.append(r.url))
                # Only loopback requests can leave this page. Both initial and redirect
                # paths are permitted by this test route, so only the response
                # guard can prevent the synthetic follow request.
                context.route('**/*',lambda r:r.continue_() if r.request.url.startswith(origin+'/') else r.abort())
                install_response_guard(context,page,policy)
                try:page.goto(origin+'/initial',timeout=5000)
                except BrowserError:pass
                page.wait_for_timeout(200)
                self.assertEqual(requests,['/initial'])
                self.assertEqual(browser_requests,[origin+'/initial'])
                self.assertIsNotNone(policy.stop)
                self.assertEqual(policy.http_status,302)
                self.assertEqual(policy.stop['status'],'redirect_refused')
                context.close();browser.close()
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)
    def test_control_without_guard_follows_two_loopback_requests(self):
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path in ('/initial','/accounts/login/'):requests.append(self.path)
                if self.path=='/initial':
                    self.send_response(302);self.send_header('Location','/accounts/login/');self.end_headers()
                else:
                    self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(b'<h1>Synthetic login fixture</h1>')
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        origin='http://127.0.0.1:'+str(server.server_port)
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='chromium',headless=True);context=browser.new_context(service_workers='block',ignore_https_errors=False)
                context.route('**/*',lambda r:r.continue_() if r.request.url.startswith(origin+'/') else r.abort())
                page=context.new_page();page.goto(origin+'/initial',timeout=5000)
                self.assertEqual(requests,['/initial','/accounts/login/'])
                context.close();browser.close()
        finally:server.shutdown();server.server_close();thread.join(timeout=2)
    def test_normal_loopback_response_can_be_rendered(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(b'<h1>Synthetic local content</h1>')
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        url='http://127.0.0.1:'+str(server.server_port)+'/initial'
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='chromium',headless=True);context=browser.new_context(service_workers='block',ignore_https_errors=False)
                page=context.new_page();policy=BrowserPolicy('https://www.instagram.com/synthetic_unrequested/',resolver=lambda _: '8.8.8.8')
                context.route('**/*',lambda r:r.continue_() if r.request.url==url else r.abort())
                install_response_guard(context,page,policy);page.goto(url,timeout=5000)
                self.assertEqual(page.locator('h1').inner_text(),'Synthetic local content')
                self.assertIsNone(policy.stop);context.close();browser.close()
        finally:server.shutdown();server.server_close();thread.join(timeout=2)

if __name__=='__main__':unittest.main()
