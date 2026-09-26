# ADR-002: Pinned parity oracle and explicit divergences

- Status: accepted
- Date: 2026-09-25
- Owner: Josh Myers
- Supersedes / superseded by: none

## Context and forces

The upstream `xma` tool is the behavioral reference for the initial SMA family,
but it has no pinned dependency set or automated tests in the source reviewed
for the project plan. The plan also identifies behaviors that should be corrected
instead of copied. Its 597-candidate worked example has an exact
command, input hash, and environment capture in `docs/UPSTREAM_CAPTURE.md`.

## Options considered

- Port directly and compare printed tables by eye.
- Preserve upstream code and bugs behind runtime flags.
- Capture pinned upstream outputs, use an independent scalar reference and
  vectorized implementation, and test each intentional divergence.

## Decision

Use the pinned upstream commit and locked capture environment to produce
content-hashed golden outputs. Synthetic fixtures are the mandatory CI oracle;
vendor-derived data stays local and ignored pending source-terms review. For
each divergence in `PROJECT_PLAN.md`, record the upstream result, chosen result,
and exact expected delta. The `xma` compatibility command preserves the input
grammar and labeled retrospective calculations, but documented defects do not
become production behavior flags.

## Consequences

- Benefit: parity and corrections can be reviewed separately.
- Cost: a capture harness, fixture maintenance, and explicit tolerance policy.
- Failure mode: dependency or data-vintage drift can change goldens; the
  capture manifest must reject unpinned inputs.
- Reversibility: a divergence can be reconsidered through a new ADR and delta
  test without discarding the upstream capture.

## Verification

M1 pinned the 597-candidate command, trade asset, input hash, environment,
and counts. At M3, run synthetic parity and D1–D17 delta tests plus scalar versus
block equivalence; never mark unavailable vendor-data checks as passed CI.
