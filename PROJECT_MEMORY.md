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

## Verified traps and failed approaches

No project-specific implementation trap is verified yet.

## Open threads

| Key | Unresolved question or next evidence | Owner | Review by |
|---|---|---|---|
| `upstream-capture` | M1 must pin the 597-candidate command, input hash, and environment before treating the worked example as an oracle. | Josh Myers | M1 |
