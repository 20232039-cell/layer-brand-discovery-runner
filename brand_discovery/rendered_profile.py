"""Offline decision core for a possible visible-browser collector, not a renderer.

This module performs no network or browser actions and has no workflow entrypoint.
It must not be used to bypass a previously observed access restriction.
"""
from dataclasses import dataclass
from urllib.parse import urlsplit
from .instagram import profile_identity, parse_number

@dataclass(frozen=True)
class VisibleSnapshot:
    requested_url: str
    final_url: str
    captured_at: str
    http_status: int | None = None
    profile_handle: str | None = None
    profile_header_visible: bool = False
    follower_display: str | None = None
    follower_label_visible: bool = False
    login_cta_visible: bool = False
    login_form_visible: bool = False
    blocking_login_view: bool = False
    challenge_visible: bool = False
    country_restriction_visible: bool = False


def assess_visible_snapshot(snapshot):
    """Evaluate already-observed, visible UI evidence; never inspect hidden meta.

    The future renderer must establish visibility and obstruction checks. A login
    CTA or an optional visible login form is not by itself a blocking login wall.
    """
    result={'status':'public_profile_unconfirmed','stop_batch':False,
            'raw_display':None,'nullable_count':None,'precision':'unknown',
            'observed_at':None,'evidence_kind':'rendered_page_inspection',
            'evidence_url':snapshot.requested_url,'restriction_evidence':None}
    def stop(status,evidence):
        return {**result,'status':status,'stop_batch':True,'restriction_evidence':evidence}
    expected=profile_identity(snapshot.requested_url)
    final=urlsplit(snapshot.final_url)
    if final.hostname not in ('www.instagram.com','instagram.com'):
        return stop('redirect_refused','unexpected_destination_host')
    if final.path=='/accounts/login' or final.path.startswith('/accounts/login/'):
        return stop('login_required','login_destination_url')
    if any(final.path==x or final.path.startswith(x+'/') for x in ('/challenge','/checkpoint')) or snapshot.challenge_visible:
        return stop('challenge','challenge_destination_or_visible_block')
    if snapshot.http_status in (401,403,429,451):
        return stop('http_'+str(snapshot.http_status),'navigation_response_status')
    if snapshot.http_status is not None and snapshot.http_status>=500:
        return stop('http_5xx','navigation_response_status')
    if snapshot.country_restriction_visible:
        return stop('country_restricted','visible_country_restriction')
    if snapshot.blocking_login_view or snapshot.login_form_visible:
        return stop('login_required','visible_blocking_login_view')
    try:final_identity=profile_identity(snapshot.final_url)
    except ValueError:return stop('redirect_refused','non_profile_destination')
    if final_identity!=expected:
        return stop('identity_mismatch','different_profile_destination')
    if not snapshot.profile_header_visible or not snapshot.profile_handle:
        return result
    if snapshot.profile_handle.lower().lstrip('@')!=expected:
        return stop('identity_mismatch','different_visible_profile_handle')
    if not snapshot.follower_label_visible or not snapshot.follower_display:
        return {**result,'status':'count_not_visible'}
    raw=snapshot.follower_display.strip()
    count,precision=parse_number(raw)
    return {**result,'status':'observed_'+precision,'raw_display':raw,
            'nullable_count':count,'precision':precision,'observed_at':snapshot.captured_at,
            'evidence_kind':'rendered_visible_profile_header',
            'login_cta_visible':snapshot.login_cta_visible,
            'login_form_visible':snapshot.login_form_visible}


def prior_access_restrictions(history):
    """A renderer must not become a fallback around an earlier access denial."""
    denied={'login_required','challenge','http_401','http_403','http_429','http_451',
            'country_restricted','redirect_refused'}
    identities=set()
    for report in history:
        for row in report.get('results',[]):
            if row.get('status') in denied and row.get('profile_url'):
                try:identities.add(profile_identity(row['profile_url']))
                except ValueError:continue
    return identities
