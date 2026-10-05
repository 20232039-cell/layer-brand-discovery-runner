# Offline design: Actions-rendered public profile observations

Status: decision core, loaded-page DOM adapter and separate synthetic offline Chromium CI. The browser CI installs official Playwright/Chromium without private inputs or secrets. A separate one-shot browser entrypoint is now implemented behind a manual-only gate that remains off until reviewed and explicitly enabled. Its live target must be a verified identity with explicit never-attempted history. No real browser collection has been run as part of this development. This is not an enabled fallback for the HTTP pilot.

## Existing evidence boundary

The last HTTP pilot reported `login_required` without `response_sha256`. In that deployed code version, every parsed HTTP 200 HTML result receives a response hash, while login-path redirects return without one. This supports the redirect-classification code path rather than mere login-CTA detection. The old classifier searched the entire Location string, so a query containing the login path could also trigger it. That false-positive case is reproducible; exact parsed-path classification is now used for future responses. Original response bytes, exact status and Location were not retained, so a rendered login wall was not observed and cannot be reconstructed. This result concerns that request path; it does not establish that GitHub Actions is categorically incapable of rendering public pages.

No new Instagram contact is authorized by this design. Previously recorded login/challenge/403/429/country restrictions must not be bypassed by switching collectors. `prior_access_restrictions` identifies these private-history records for a future admission guard; it does not perform or authorize navigation.

## Intended renderer, if independently authorized later

Use official Playwright and official Chromium with their ordinary defaults, a fresh ephemeral context, a maximum of three verified profile inputs and one initial navigation per approved profile. No stealth plugins, custom impersonating user agent, proxies, credentials, imported cookies/storage, private API requests, login submission or alternate routes after denial. No interaction to dismiss a blocking login wall.

The one-shot runtime uses the official full Chromium channel in normal headless mode with native cookie blocking. An offline fulfilled HTTPS origin tests Set-Cookie and document.cookie; a control context without the policy must demonstrate that the fixture can store cookies. These synthetic browser tests must pass before live activation. No imported cookie, custom user agent, stealth flag, proxy or TLS exception is used. Dependencies are pinned to official releases; request restrictions are reviewed separately.

The renderer must collect only visible, unobstructed profile-header identity and the associated visible follower count. It must verify the final profile identity and capture time. A login button can coexist with public followers and is not alone a denial. A visible authentication form or blocking login overlay is conservatively treated as a stop. A login destination URL, actual blocking login view, challenge, explicit country restriction or denied response is a stop. DOM CSS visibility alone is insufficient if an overlay obscures the value; occlusion checks and real browser fixtures must be validated.

## Private evidence and interpretation

Record the exact visible display (including K/M/만), nullable exact integer, precision, live observation time, profile URL, visible-UI evidence kind and restriction evidence class. Rounded displays never become fabricated exact integers; unavailable counts remain null. Hidden HTML metadata, script payloads, old master values and fixtures never establish a live observation. Never automatically overwrite verified master values with unavailable results.

All inputs, observed values and evidence stay in the existing private data repository through the reviewed transfer boundary. No public screenshots, traces, videos, HAR files, artifacts, caches, summaries, page console output or exception bodies. Browser recording must remain off. Source snapshots and account identifiers must not appear in public build output. Keep manual-only execution and the shared single-run concurrency group. No new credential, paid API, standing access or schedule is proposed.

## Required future checks before implementation is called live-ready

- Official dependency/Chromium installation and strict cookie policy verification
- Approved navigation/resource scope with no private API or auth traffic
- Real browser tests on local synthetic pages, including overlay occlusion and hidden content
- Prior-access-denial admission guard, not merely post-navigation classification
- Fixed bounded waits and no reload/fallback loops
- Independent security review and public-output canary validation
- Explicit decision on whether a target can be contacted at all, given its prior restriction evidence

Pure tests exercise the classification contract with synthetic HTML. The separate Chromium CI uses set_content with offline=True, service workers blocked and deny-all page routing. Its profile URLs are synthetic labels passed to the classifier, not navigations. It includes visible/hidden/occluded counts, login CTA, login form, redirect classification and denied subresource fixtures. The local environment could not start Chromium because socket creation was denied; no local privilege change or alternate browser was attempted. Remote CI results must be checked before claiming actual rendering passed. No Instagram request is part of these tests.

## Single-trial admission proposal, not enabled

If later authorized, select one verified profile that has never received a profile request in the prior pilot (a skipped input), rather than switching clients on the first profile with ambiguous login evidence. Normalize profile identities before history comparison. Prior confirmed login/challenge/access-denied records block admission; ambiguous legacy records require separate review and are not silently cleared. A trial would be one ordinary visible-page observation, with no reload, retry, alternate client or second target after a restriction. The actual renderer, strict cookie-blocking preflight and request-scope policy still require completed tests and independent review before any such trial.

Official installation references: https://pypi.org/project/playwright/1.62.0/ and https://playwright.dev/python/docs/browsers . Installation downloads occur in a separate CI preparation step; browser test pages remain offline and contain synthetic data only.

## Current one-shot implementation safeguards

`browser_policy.py` requires one private input, mandatory prior history and an explicit skipped record for the normalized target. Every past attempt or access restriction rejects admission. `browser_runtime.py` validates cookie blocking before live navigation. `browser_redirect_guard.py` uses response-stage CDP interception to fail redirects before browser follow-up; loopback control tests verify two unguarded requests versus one guarded request. Those fixtures use only an in-process loopback server, with every non-loopback page request denied. No actual Instagram navigation occurs in tests.

`instagram_browser.py` permits one public document navigation and bounded static GET resources from two exact first-party hosts. Private API paths, fetch/XHR, websockets, cookies/auth headers and additional document navigations are blocked. Public DNS checks are not browser-level IP pinning; fixed trusted hostnames and ordinary TLS validation remain required. A limited resource policy may make the page incomplete; the runtime reports that condition instead of relaxing the policy. Account data, visible values, source URLs and observation times are stored only by the isolated private transfer step.
