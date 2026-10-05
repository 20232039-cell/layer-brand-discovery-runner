# Privacy and deployment review

## Implemented controls

- All fixtures synthetic; no imported real candidate, exclusion or brand records.
- Actual collection workflow is off by default behind an owner-controlled variable and manual trigger. CI has read-only GITHUB_TOKEN, pinned checkout commit, no persisted checkout credentials, no secrets, no cache, no artifacts, no data outputs or step summaries, no workflow inputs, no pull_request_target. The manual data-build workflow scopes secrets to private transfer steps only, and launches the collector with an explicit clean environment.
- Untrusted pull request code runs offline synthetic tests with no private-data credential.
- Private data directory must be outside the public checkout (not its parent or child) and have an explicit local marker. Hidden marker does not verify remote visibility.
- No normal collection console output; generic failure only. Exception bodies/URLs never recorded. HTTP status/refusal codes stored privately. No network fetch credentials.
- Source text, emails, URLs, hashes, checkpoints and exports remain in private root. CSV formula prefixes (=,+,-,@ after whitespace) and leading control characters are apostrophe-neutralized in values and headers; raw JSON evidence is preserved unchanged. XLSX cells use explicit inline strings with no formula or external-link elements. XML-invalid characters are replaced with the replacement glyph only in XLSX display text; raw JSON remains unchanged and literal carriage returns are preserved via XML entities. Offline regressions parse generated CSV/XLSX and check delimiter/newline boundaries; they do not execute formulas or claim validation in every spreadsheet application.
- No packages installed, AI APIs called, secrets copied, or credential grants created.

## Before any production activation

1. Verify target repository identity and private visibility immediately before upload; no fallback public destination. Ensure both repos initialized and code publication reviewed.
2. Verify approved host and terms for the LAYER data-build purpose. Keep bounded execution, no endless loops or hidden schedules.
3. User approves least-privilege credential granting only private target contents read/write and enters it through GitHub secure settings. Do not reuse a broad existing token merely because another workflow references it. Protect main and environment approval as appropriate; changes may require specific user approval.
4. Implement an isolated credential-bearing transfer adapter with no checkout chatter or credential-in-URL. Collector subprocess must have an explicit clean environment without secrets. Adapter verifies visibility every run and writes a single atomic private commit, handles conflicts safely, checks uploaded commit and output checksums. Transfer is implemented and unit-tested; live end-to-end verification is still required.
5. End-to-end sentinel test: synthetic private unique markers must not appear in complete public job logs, artifacts, caches, summaries, annotations, workflow inputs/outputs, files or commit history. Test errors, redirects, cancellation, timeout and upload conflict. Static tests here are not that end-to-end proof.
6. Never print git diff/status, HTTP response or stack traces while private data exists. Capture diagnostics only within private storage; avoid artifact upload even on failure. Scrub workspace on runner exit. Confirm no credentials in checkpoint/evidence.
7. Seed canonical data only after this gate; leave existing source files and repositories untouched until authorized. Review outputs before master import. No public data commits or data in PR comments/issues.

## Known limits

Collection is a conservative homepage evidence pass. It cannot verify brand nationality, ownership, primary category, live inventory/cart behavior, or follower counts. Exclusions match normalized name and exact canonical URL only; alias and related-host identity require manual review. No raw HTML snapshots are stored. HTTP body decoding assumes UTF-8; non-UTF-8 pages can need manual review. Robots redirects fail closed. Each blocked/error candidate requires explicit retry selection. Human review, credential provisioning and live private persistence verification remain deployment work.

## Public-profile pilot isolation

The Instagram pilot uses a separate four-file private output allowlist and downloads only `instagram_profiles.csv` and optional `instagram_history.json`. Transfer mode is recorded and checked before upload. It shares the single private-data concurrency group, scopes the existing token only to transfer steps, and launches collection in a clean environment. Public workflow inputs contain no profile identity. Generic stop outcomes are stored privately, not echoed with account names or counts. No input or existing master dataset is overwritten by the collector.
