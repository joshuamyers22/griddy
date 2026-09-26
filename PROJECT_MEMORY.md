# griddy Project Memory

This is a bounded retrieval index for durable project knowledge. It is not an
activity log, task tracker, transcript, or source of truth. Verify every entry
against the linked implementation, test, issue, or decision record before acting.

Do not record secrets, personal data, client data, hidden reasoning, or other
restricted material. Consult an existing key before editing and update it in
place. Remove stale entries and resolved work instead of preserving a narrative;
Git history provides the audit trail.

## Durable constraints

| Key | Constraint | Evidence | Last verified |
|---|---|---|---|
| `retrospective-boundary` | The upstream full-sample period is already inspected; a confirmatory final window requires a frozen protocol and fresh data. | `STATISTICAL_ANALYSIS_PLAN.md`; `ADVERSARIAL_PLAN_REVIEW.md` | 2026-09-25 |
| `vendor-data-boundary` | Upstream market data remains local and ignored pending source-terms review; synthetic fixtures are the default CI oracle. | `PROJECT_BRIEF.md`; `docs/adr/ADR-001-license-and-attribution.md`; `docs/adr/ADR-002-parity-and-divergences.md` | 2026-09-25 |

## Accepted decisions

| Key | Decision and rationale | Evidence | Last verified |
|---|---|---|---|
| `license-attribution` | New code is proprietary; upstream MIT notice is retained for any later port. | `docs/adr/ADR-001-license-and-attribution.md`; `THIRD_PARTY_NOTICES.md` | 2026-09-25 |
| `parity-boundary` | Pinned upstream captures, synthetic CI fixtures, and explicit divergence tests separate parity from corrections. | `docs/adr/ADR-002-parity-and-divergences.md` | 2026-09-25 |
| `numeric-boundary` | Strict ingest converts to float64 for research calculations; errors and ties are explicit. | `docs/adr/ADR-003-numeric-representation.md` | 2026-09-25 |
| `config-boundary` | TOML is parsed into frozen validated objects; unknown fields and over-budget spaces fail before evaluation. | `docs/adr/ADR-004-configuration-contract.md` | 2026-09-25 |

## Non-obvious current state

| Key | State worth retrieving later | Evidence | Last verified |
|---|---|---|---|
| `generated-scaffold` | This is the pinned template's `python-data-quant` starter, not yet the planned search engine or `xma` implementation. | `README.md`; `PROJECT_PLAN.md`; `src/griddy/` | 2026-09-25 |
| `repository-bootstrap` | Public `joshuamyers22/griddy` has M0 branch, CI, signing, Actions, and security controls; solo ownership has a documented review exception. | `docs/REPOSITORY_BOOTSTRAP.md`; GitHub ruleset `24027427` | 2026-09-25 |
| `upstream-oracle` | M1 captured the pinned `xma` run: 597 signal rules trade SPY, with 5,878 common observations through 2026-09-24. Synthetic fixtures are committed; vendor-derived captures stay ignored under `.work/`. | `docs/UPSTREAM_CAPTURE.md`; `tests/fixtures/upstream/manifest.json`; `tests/test_upstream_capture.py` | 2026-09-25 |
| `upstream-price-dataset` | The M2 input contract uses Polars by default, optional pandas conversion, explicit quote unit/calendar, absent rather than filled prices, and year-partitioned immutable float64 Parquet. The search engine is still open M2 work. | `docs/adr/ADR-009-polars-first-inputs.md`; `src/griddy/upstream_prices.py`; `docs/PARQUET_DATASETS.md`; `tests/test_upstream_prices.py` | 2026-09-26 |

## Verified traps and failed approaches

No project-specific implementation trap is verified yet.

## Open threads

| Key | Unresolved question or next evidence | Owner | Review by |
|---|---|---|---|
| `upstream-parity` | M2–M3 must compare new engine outputs to the captured synthetic oracle and local vendor reference, recording any divergence. | Josh Myers | M2–M3 |
