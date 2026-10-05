"""Synthetic HTML only; these fixtures are not a real Instagram DOM contract."""
from html.parser import HTMLParser
from dataclasses import replace
import socket
import unittest
from unittest.mock import patch
from brand_discovery.rendered_profile import VisibleSnapshot, assess_visible_snapshot, prior_access_restrictions

URL='https://www.instagram.com/synthetic_rendered_01/'
TIME='2026-10-05T00:00:00+00:00'

class FixtureHTML(HTMLParser):
    def __init__(self):
        super().__init__();self.data={};self.hidden=[];self.target=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        hidden=bool(self.hidden and self.hidden[-1]) or 'hidden' in a or a.get('aria-hidden')=='true' or 'display:none' in a.get('style','').replace(' ','')
        self.hidden.append(hidden)
        role=a.get('data-test-role')
        if role and not hidden:
            self.target=role
            self.data[role]=''
    def handle_endtag(self,tag):
        if self.hidden:self.hidden.pop()
        self.target=None
    def handle_data(self,data):
        if self.target and not any(self.hidden):self.data[self.target]+=data

def snapshot(html,final=URL,status=200):
    p=FixtureHTML();p.feed(html);d=p.data
    return VisibleSnapshot(URL,final,TIME,status,profile_handle=d.get('profile'),
        profile_header_visible='profile' in d,follower_display=d.get('followers'),
        follower_label_visible='followers' in d,login_cta_visible='login-cta' in d,
        login_form_visible='login-form' in d,blocking_login_view='login-wall' in d,
        challenge_visible='challenge' in d,country_restriction_visible='country-block' in d)

class RenderedProfileTests(unittest.TestCase):
    def test_public_count_and_login_cta_can_coexist(self):
        html='<h1 data-test-role="profile">synthetic_rendered_01</h1><span data-test-role="followers">1.2만</span><button data-test-role="login-cta">Log in</button>'
        r=assess_visible_snapshot(snapshot(html))
        self.assertEqual(r['status'],'observed_abbreviated');self.assertEqual(r['raw_display'],'1.2만')
        self.assertIsNone(r['nullable_count']);self.assertFalse(r['stop_batch']);self.assertEqual(r['observed_at'],TIME)
    def test_visible_login_form_is_a_conservative_stop(self):
        html='<h1 data-test-role="profile">synthetic_rendered_01</h1><span data-test-role="followers">1,234</span><form data-test-role="login-form">Log in</form>'
        self.assertEqual(assess_visible_snapshot(snapshot(html))['status'],'login_required')
    def test_login_destination_always_stops(self):
        html='<h1 data-test-role="profile">synthetic_rendered_01</h1><span data-test-role="followers">1,234</span>'
        r=assess_visible_snapshot(snapshot(html,final='https://www.instagram.com/accounts/login/'))
        self.assertEqual(r['status'],'login_required');self.assertTrue(r['stop_batch']);self.assertIsNone(r['raw_display'])
    def test_actual_login_wall_and_challenge_stop(self):
        for role,status in [('login-wall','login_required'),('challenge','challenge'),('country-block','country_restricted')]:
            r=assess_visible_snapshot(snapshot('<div data-test-role="'+role+'">Restricted</div>'))
            self.assertEqual(r['status'],status);self.assertTrue(r['stop_batch']);self.assertIsNone(r['nullable_count'])
    def test_hidden_metadata_or_hidden_count_not_observed(self):
        html='<meta name="description" content="1234 Followers"><h1 data-test-role="profile">synthetic_rendered_01</h1><span hidden data-test-role="followers">1,234</span><a data-test-role="login-cta">Log in</a>'
        self.assertEqual(assess_visible_snapshot(snapshot(html))['status'],'count_not_visible')
    def test_http_restrictions_stop(self):
        for code in [401,403,429,451,503]:
            r=assess_visible_snapshot(snapshot('',status=code));self.assertTrue(r['stop_batch']);self.assertIsNone(r['nullable_count'])
    def test_prior_denial_is_not_a_browser_fallback(self):
        history=[{'results':[{'profile_url':URL,'status':'login_required'},{'profile_url':'https://www.instagram.com/synthetic_other/','status':'network_error'}]}]
        self.assertEqual(prior_access_restrictions(history),{'synthetic_rendered_01'})
    def test_prior_denial_matches_url_variants(self):
        history=[{'results':[{'profile_url':'https://instagram.com/SYNTHETIC_RENDERED_01','status':'login_required'}]}]
        self.assertEqual(prior_access_restrictions(history),{'synthetic_rendered_01'})

    def test_decision_core_performs_no_network(self):
        with patch.object(socket,'create_connection',side_effect=AssertionError('Network forbidden')),patch.object(socket,'getaddrinfo',side_effect=AssertionError('DNS forbidden')):
            r=assess_visible_snapshot(snapshot('<a data-test-role="login-cta">Log in</a>'))
            self.assertEqual(r['status'],'public_profile_unconfirmed')

if __name__=='__main__':unittest.main()
