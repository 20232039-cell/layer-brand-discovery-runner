"""Read an already-loaded Playwright page; this module never navigates or logs in.

The browser CI supplies synthetic HTML with set_content while offline. Production
browser collection is not wired into any workflow and requires separate review.
"""
import re
from urllib.parse import urlsplit
from .instagram import profile_identity
from .rendered_profile import VisibleSnapshot


def unobstructed(locator):
    if not locator.is_visible():return False
    return locator.evaluate(r'''el => {
      for (let node=el; node; node=node.parentElement) {
        const style=getComputedStyle(node);
        if (Number(style.opacity)<=0.01 || style.visibility!=='visible' || style.display==='none') return false;
      }
      const color=getComputedStyle(el).color;
      if (color==='transparent' || /rgba\([^)]*,\s*0(?:\.0+)?\)$/.test(color)) return false;
      const r = el.getBoundingClientRect();
      if (r.width <= 0 || r.height <= 0) return false;
      const x=r.left+r.width/2, y=r.top+r.height/2;
      if (x<0 || y<0 || x>=innerWidth || y>=innerHeight) return false;
      const top=document.elementFromPoint(x,y);
      return !!top && (el===top || el.contains(top));
    }''')


def snapshot_from_loaded_page(page, requested_url, document_url, captured_at, http_status=200):
    """No GET, goto, request API, cookies, screenshot, tracing or output calls.

    document_url must come from an admitted renderer's actual final navigation;
    the offline tests explicitly supply a synthetic URL to test the contract.
    """
    expected=profile_identity(requested_url)
    visible_handle=None
    headings=page.locator('h1,h2,[role="heading"]')
    for i in range(min(headings.count(),20)):
        h=headings.nth(i)
        if unobstructed(h) and h.inner_text().strip().lower().lstrip('@')==expected:
            visible_handle=expected;break
    displays=[]
    links=page.locator('a[href]')
    for i in range(min(links.count(),100)):
        a=links.nth(i);p=urlsplit(a.get_attribute('href') or '')
        if p.netloc and p.hostname not in ('www.instagram.com','instagram.com'):continue
        if p.path.rstrip('/')!='/'+expected+'/followers' or not unobstructed(a):continue
        text=re.sub(r'\s+',' ',a.inner_text()).strip()
        text=re.sub(r'^팔로워\s*','',text,flags=re.I)
        text=re.sub(r'\s*(?:followers?|팔로워|명)$','',text,flags=re.I).strip()
        if text:displays.append(text)
    body=page.locator('body').inner_text().lower()
    login_cta=False
    controls=page.locator('a,button')
    for i in range(min(controls.count(),100)):
        el=controls.nth(i)
        if unobstructed(el) and el.inner_text().strip().lower() in ('log in','login','로그인'):
            login_cta=True;break
    passwords=page.locator('input[type="password"]')
    login_form=any(unobstructed(passwords.nth(i)) for i in range(min(passwords.count(),10)))
    login_overlay=False
    dialogs=page.locator('[role="dialog"][aria-modal="true"]')
    for i in range(min(dialogs.count(),10)):
        dialog=dialogs.nth(i)
        if unobstructed(dialog) and re.search(r'log\s*in|login|로그인',dialog.inner_text(),re.I):
            if visible_handle is None or not displays:login_overlay=True
    challenge=any(x in body for x in ('verify you are human','confirm you are human','complete the captcha'))
    country=any(x in body for x in ('not available in your country','not available in your region'))
    return VisibleSnapshot(requested_url,document_url,captured_at,http_status,
        profile_handle=visible_handle,profile_header_visible=visible_handle is not None,
        follower_display=displays[0] if len(set(displays))==1 else None,
        follower_label_visible=bool(displays),login_cta_visible=login_cta,
        login_form_visible=login_form,blocking_login_view=login_form or login_overlay,
        challenge_visible=challenge,country_restriction_visible=country)
