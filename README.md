# LAYER brand evidence runner

A conservative, dependency-free candidate-to-review pipeline. Public code and synthetic tests are separated from private candidates, exclusions, evidence and outputs. This implementation is **local-tested and not deployed**. It does not discover unlimited new brands automatically or confirm an eligible brand without review.

## Status and deployment boundary

- Ready locally: bounded serial HTTPS collection, robots.txt, rate limiting, identity review flags, exclusion/dedup review, resume checkpoints, CSV and XLSX review exports.
- Public Actions CI: offline synthetic tests only. A separate bounded manual project data-build workflow is owner-gated off by default, with no public artifacts or caches.
- Actual hosted collection: pending architecture/policy review, repository creation, credential setup and end-to-end privacy testing. The implemented private transfer adapter verifies visibility, uploads allowlisted files only, and commits with conflict checks. CLI requires an explicit approved data-build mode in Actions.
- No scheduling, paid LLM calls, external model provider, browser cookies, passwords, Instagram login or automatic decisions.
- GitHub-hosted Actions use must satisfy its current [additional-product terms](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features#actions); free public minutes are not a permission for unrestricted general-purpose collection. A genuine bounded LAYER software data-build/publication workflow may be reviewed, not disguised as CI. No compliance claim is made here.

## Local use

Python 3.11+; standard library only. Keep a private checkout outside this public source directory. Verify its GitHub visibility is private before seeding or uploading data. `.private-data-root` is an intentional local acknowledgement, not proof of remote privacy.

Create `.private-data-root` in that separate private directory. Add `candidates.csv` with `name,official_url` or the Korean columns `브랜드(한글),브랜드(영문),공식몰 링크`. Optional additional columns are preserved in input, not rewritten. URLs must be observed public HTTPS links, not guessed domains. Add `exclusions.json` with `names` and `urls` arrays for known brands. Both files stay private.

Run `python3 -m brand_discovery --private-root /absolute/private/directory --limit 30 --seconds 1800`.

Run tests with `python3 -m unittest discover -s tests -v`.

Outputs within the same private directory: `evidence/<candidate hash>.json`, `checkpoint.json`, `review_queue.csv`, `review_queue.xlsx`. Files use restrictive permissions under CLI. Original candidates and canonical CSV/workbook are never changed. Source row changes get a new checkpoint ID; unchanged terminal results are skipped. To retry a failed candidate, deliberately remove only its checkpoint entry in the private directory after reviewing the failure. Review exports include historical checkpoint rows; they are not a current approved master catalog.

## What the evidence means

Email links are observed mailto links only; no guessed addresses. Instagram links are observed links and explicitly unvisited. Visible text and platform/apparel/cart-text signals are hints. Korean identity, official ownership, clothing-primary status, recency, product availability and working cart all remain unverified. No products are added to carts. Review queue is never silently merged into the master dataset. Structured product extraction, product-page visits, source discovery, storefront rendering and human approval import are future extensions, not implemented claims.

A single origin's homepage is fetched at a time; 2s minimum interval honors longer robots crawl delay/request rate. Failed robots fetch, disallowed paths, HTTP errors, excessive size and cross-origin redirects stop collection for the candidate. HTTPS only, public resolved addresses only, pinned destination IP with hostname certificate validation, no proxies, credentials, cookies, query strings or cross-origin redirects. Social sites require separate manual/authorized API collection. Robots permission is necessary but not sufficient: only seed sources whose terms permit this use.

## Privacy release gate

Read `docs/PRIVACY.md`. Do not enable the gated build before the privacy release gate or upload real inputs into this repository. No credential acquisition/configuration is included. Proposed repositories: `layer-brand-discovery-runner` (public code) and `layer-brand-discovery-data` (private data). Creating them and remote end-to-end testing are still pending.
