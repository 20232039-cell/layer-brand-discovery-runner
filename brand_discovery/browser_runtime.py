"""A fresh, non-persistent Chromium context. No session import or export."""

def create_context(playwright):
    browser=playwright.chromium.launch(channel='chromium',headless=True)
    try:
        context=browser.new_context(offline=True,service_workers='block',ignore_https_errors=False)
    except Exception:
        browser.close();raise
    return browser,context
