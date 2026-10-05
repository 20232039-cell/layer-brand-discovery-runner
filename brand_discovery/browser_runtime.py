"""Fresh native-cookie-blocked Chromium context and offline cookie canary."""
import json
from pathlib import Path

COOKIE_FIXTURE='https://cookie-canary.invalid/'

def create_context(playwright,profile_directory):
    path=Path(profile_directory)/'Default';path.mkdir(parents=True,exist_ok=True)
    (path/'Preferences').write_text(json.dumps({'profile':{'default_content_setting_values':{'cookies':2},'block_third_party_cookies':True}}))
    return playwright.chromium.launch_persistent_context(str(profile_directory),channel='chromium',headless=True,
        offline=True,service_workers='block',ignore_https_errors=False)

def verify_cookie_policy(context):
    """Fulfilled synthetic origin while offline: never contacts a website."""
    seen=[]
    def synthetic(route):
        if route.request.url==COOKIE_FIXTURE:
            seen.append(True)
            route.fulfill(status=200,content_type='text/html',
                headers={'Set-Cookie':'synthetic_header=one; Secure; SameSite=None'},
                body='<html><body>Offline cookie policy canary</body></html>')
        else:route.abort()
    context.route('**/*',synthetic)
    page=context.new_page()
    try:
        page.goto(COOKIE_FIXTURE,wait_until='domcontentloaded',timeout=5000)
        page.evaluate("document.cookie='synthetic_script=two; Secure; SameSite=None'")
        return len(seen)==1 and page.evaluate('document.cookie')=='' and context.cookies()==[]
    finally:
        page.close();context.unroute('**/*',synthetic)
