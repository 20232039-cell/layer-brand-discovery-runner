# LAYER brand evidence runner

A conservative, dependency-free candidate-to-review pipeline. Public code and synthetic tests are separated from private candidates, exclusions, evidence and outputs. Public code and synthetic CI are deployed; actual collection is **disabled pending secure setup and live privacy validation**. It does not discover unlimited new brands automatically or confirm an eligible brand without review.

## Status and deployment boundary

- Ready locally: bounded serial HTTPS collection, robots.txt, rate limiting, identity review flags, exclusion/dedup review, resume checkpoints, CSV and XLSX review exports.
- Public Actions CI: offline synthetic tests only. A separate bounded manual project data-build workflow is owner-gated off by default, with no public artifacts or caches.
- Actual hosted collection: pending credential setup and end-to-end privacy testing. The implemented private transfer adapter verifies visibility, uploads allowlisted files only, and commits with conflict checks. CLI requires an explicit approved data-build mode in Actions.
- No scheduling, paid LLM calls, external model provider, imported browser sessions, passwords, Instagram login or automatic decisions.
- GitHub-hosted Actions use must satisfy its current [additional-product terms](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features#actions); free public minutes are not a permission for unrestricted general-purpose collection. A genuine bounded LAYER software data-build/publication workflow may be reviewed, not disguised as CI. No compliance claim is made here.

## Local use

Python 3.11+; standard library only. Keep a private checkout outside this public source directory. Verify its GitHub visibility is private before seeding or uploading data. `.private-data-root` is an intentional local acknowledgement, not proof of remote privacy.

Create `.private-data-root` in that separate private directory. Add `candidates.csv` with `name,official_url` or the Korean columns `브랜드(한글),브랜드(영문),공식몰 링크`. Optional additional columns are preserved in input, not rewritten. URLs must be observed public HTTPS links, not guessed domains. Add `exclusions.json` with `names` and `urls` arrays for known brands. Both files stay private.

Run `python3 -m brand_discovery --private-root /absolute/private/directory --limit 30 --seconds 1800`.

Run tests with `python3 -m unittest discover -s tests -v`.

Outputs within the same private directory: `evidence/<candidate hash>.json`, `checkpoint.json`, `review_queue.csv`, `review_queue.xlsx`. Files use restrictive permissions under CLI. Original candidates and canonical CSV/workbook are never changed. Source row changes get a new checkpoint ID; unchanged terminal results are skipped. To retry a failed candidate, deliberately remove only its checkpoint entry in the private directory after reviewing the failure. Review exports include only the current candidate input rows; historical checkpoint/evidence records remain privately preserved. Exports are not an approved master catalog.

## What the evidence means

Email links are observed mailto links only; no guessed addresses. Instagram links are observed links and explicitly unvisited. Visible text and platform/apparel/cart-text signals are hints. Korean identity, official ownership, clothing-primary status, recency, product availability and working cart all remain unverified. No products are added to carts. Review queue is never silently merged into the master dataset. Structured product extraction, product-page visits, source discovery, storefront rendering and human approval import are future extensions, not implemented claims.

A single origin's homepage is fetched at a time; 2s minimum interval honors longer robots crawl delay/request rate. Failed robots fetch, disallowed paths, HTTP errors, excessive size and cross-origin redirects stop collection for the candidate. HTTPS only, public resolved addresses only, pinned destination IP with hostname certificate validation, no proxies, credentials, cookies, query strings or cross-origin redirects. Social sites are outside this homepage collector and require their separately approved bounded workflow. Robots permission is necessary but not sufficient: only seed sources whose terms permit this use.

## Privacy release gate

Read `docs/PRIVACY.md`. Do not enable the gated build before the privacy release gate or upload real inputs into this repository. No credential acquisition/configuration is included. Proposed repositories: `layer-brand-discovery-runner` (public code) and `layer-brand-discovery-data` (private data). Both repositories are initialized. Remote end-to-end testing is still pending.

## Input provenance and private canary

The adapter accepts the 17-column Korean master schema and reconciliation queue columns (including `공식몰`, `판정`, `verification_excel_row`). It preserves every input value in private evidence as `source_record`; pre-existing decisions stay separately labeled `source_verdict`. New heuristic signals always remain unverified. The master is not written or promoted automatically.

The manual `privacy-canary.yml` workflow is separately gated by `ENABLE_PRIVATE_CANARY=true`; leave the production `ENABLE_PRIVATE_DATA_BUILD` gate off. It accepts two synthetic CANARY records at `canary.invalid/success` and `/error`, makes no website requests, verifies empty-input behavior and checkpoint resume, and saves only to the private repo. After a run, audit all public logs, annotations, artifacts, caches, summaries and commit contents for the private canary markers before actual data is seeded. Passing offline tests alone is insufficient.

## Evidence schema v2

New evidence calls the extracted text `html_text_excerpt`, explicitly unrendered: CSS-hidden template text, footer dates and JavaScript placeholders may be included. It does not establish visibility, recent launches, stock or working cart behavior. Existing v1 evidence is retained unchanged; its legacy `visible_text_excerpt` name did not prove rendered visibility either.

Mailto targets, static anchor labels and literal addresses observed elsewhere in page text are kept separately. Disagreement creates review flags, not a confirmed parser error or a verified official contact. `email_links_observed` remains a raw target list for compatibility and must not be imported directly as official email. Multiple legitimate contact roles can also explain differing addresses. No email is sent.

Platform hints now include literal Sixshop evidence when present. Hints are separate from canonical master platform values and remain unverified; absent evidence remains unknown. No brand status is promoted, and old checkpoints are not automatically refetched or reclassified.

## Logged-out public profile pilot

`instagram-public.yml` is manual-only, separately gated by `ENABLE_INSTAGRAM_PUBLIC_CHECK=true`, and limited to three verified profile links per run. Inputs live only in private `instagram_profiles.csv` with columns `brand_id,profile_url,official_source_url,profile_link_verified`; verification must be the literal `true` and must come from an already verified official-site link. Public code contains no real accounts.

The Instagram pilot uses a declared bot user agent and makes ordinary HTTPS GET requests to the public profile page only. At the owner’s explicit direction it does not perform a robots.txt precheck. This does not establish site permission or relax actual access restrictions. It does not log in, send cookies, impersonate a browser, use proxies/private APIs, follow redirects, retry blocked requests, or circumvent access restrictions. Login, CAPTCHA/challenge, country restrictions, 403/429 and other safety stops end the entire batch; remaining profiles get `skipped_after_stop`. A successful Actions run may therefore mean only that a blocked status was saved privately. Public-page availability does not establish permission under Meta's terms; the owner must separately assess the permitted use.

Only profile-bound public HTML metadata is parsed. `raw_display`, `nullable_count`, `precision`, `observed_at`, `attempted_at` and `status` are distinct. An explicit observed `0` is exact zero; missing/error values are null. Rounded displays such as `1.2K` or `1.2만` stay raw with `precision=abbreviated` and no fabricated exact integer. Conflicting metadata stays unresolved. No legacy master field is changed automatically.

Private outputs are `instagram_results.json`, `instagram_results.csv`, `instagram_results.xlsx` and append-only `instagram_history.json`. They use the already approved isolated private transfer steps and the existing concurrency group. No scheduled runs, new credentials, public logs containing accounts/counts, artifacts or caches are created. This pilot adds no Instagram permission or guarantee of successful collection.

The first Instagram pilot stopped at robots precheck before any profile GET. That private history remains intact; later manually authorized observations record `robots_precheck_performed=false` without overwriting earlier outcomes. No automatic retry follows any access restriction.

Network diagnostics are coarse private categories (DNS, timeout, TLS, connection/routing, or internal error), never raw exception text, URLs or headers. A generic legacy `network_error` cannot retrospectively establish whether a request reached Instagram. When DNS offers both address families, the connection selects one validated public IPv4 address first; IPv6-only answers remain IPv6. There are no connection retries, alternative hosts, proxies, TLS-verification changes or user-agent changes. Every resolved address is still checked for SSRF safety before selecting one.

## Offline rendered-UI prototype

A separate synthetic Chromium CI tests visible profile identity/counts, login CTA versus an authentication form or overlay, hidden/occluded content and exact login-path classification. It has no private inputs or secrets. UI documents use `set_content` while offline; session and redirect fixtures use only an in-process loopback server, with every external page request aborted. Official browser installation downloads are separate from the offline tests. This does not enable Instagram browser collection or prove access to any real profile. See `docs/RENDERED_PROFILE_DESIGN.md` for the remaining admission, cookie-policy and live-rendering checks.

Legacy HTTP login results without preserved Location cannot prove a rendered login wall. Future HTTP redirect classification uses the parsed destination host and pathname, so a login path appearing only inside a query no longer becomes a login verdict. New private evidence includes response type, exact HTTP status and a coarse restriction class, without storing raw Location or its query.

## One-shot visible-UI entrypoint (disabled until reviewed and enabled)

`instagram-browser-one-shot.yml` is a separate manual-only workflow gated by `ENABLE_INSTAGRAM_BROWSER_CHECK=true`. It accepts exactly one private `instagram_browser_profile.csv` row with `allow_first_rendered_trial=true`. The downloaded existing history is mandatory, must contain explicit never-attempted records for that normalized identity, and must contain no prior request/restriction for it. A previously attempted or restricted profile is not eligible for a browser fallback.

The official Chromium runtime starts a fresh non-persistent browser context without importing an existing profile, authentication state or cookies. Ordinary anonymous session cookies set by a public page may remain inside that disposable context; the program does not read their values, export storage state or save them. The context and browser are closed at the end. The browser uses its default user agent and TLS verification, no proxy, no credentials, no imported cookies and no private APIs. Only a single initial profile document GET is permitted. Static GET assets are limited to `www.instagram.com` and `static.cdninstagram.com`, conventional static paths and script/style/image/font types. Fetch/XHR, private API paths, other origins, authentication headers and further navigations are blocked. Public DNS checks are an additional guard, not a claim of IP pinning inside Chromium.

Response-stage CDP interception fails redirects before Chromium can follow them; request routing alone is not assumed to cover redirect hops. An actual login/challenge/country restriction or denied response stops the trial. A login CTA alone does not suppress a simultaneously visible, unobscured follower count. The latest visible display, observation time, source and precision stay private, and every unavailable count remains null. Blocked resources can cause `rendering_incomplete_policy`; the collector does not relax its boundaries or try a different route.

Fresh-context session isolation and redirect guards require their synthetic Chromium CI tests to pass before enabling this entrypoint. Tests use only fulfilled offline documents or an in-process loopback server with all non-loopback requests denied. No real Instagram request is part of CI. Installing official runtime dependencies requires ordinary vendor downloads; page tests and private collector output are separate. No trace, screenshot, video, HAR, public artifact or cache upload is configured.

For rendered observations, `precision` describes the displayed numeric format, not a guarantee of Instagram’s internal counter update time. `observed_at` is the fresh browser-view capture time; no source-side update timestamp is invented.
