# ADR-003: Float64 research kernel with explicit ingest boundary

- Status: accepted
- Date: 2026-09-25
- Owner: Josh Myers
- Supersedes / superseded by: none

## Context and forces

The archetype uses Decimal for monetary values, but `griddy` computes
research price ratios, returns, weights, correlations, and inference over large
arrays. A Decimal array would not fit the planned NumPy block kernel. Silent
CSV inference or non-finite values would still make float results unreliable.

## Options considered

- Decimal throughout.
- Float64 from unvalidated CSV inference.
- Strict text/schema ingest followed by one explicit conversion to float64 for
  the numerical kernel.

## Decision

Use declared string and schema validation at ingest, then float64 for research
series and kernel calculations. Keep ledger-like currency amounts out of this
kernel. Reject non-finite inputs where a metric requires finite values, report
undefined candidate metrics explicitly, and use numerically stable rolling
methods. Position states must agree exactly between reference and block engines;
return and metric tolerances are specified per test, with both absolute and
relative checks near zero. A threshold tie is reported, never resolved by an
unrecorded epsilon.

## Consequences

- Benefit: matches efficient NumPy execution and makes precision boundaries
  auditable.
- Cost: floating-point drift requires reference tests and numerical stress
  cases.
- Failure mode: very small denominators or long cumulative calculations can
  amplify error; primitives must validate their domain and use stable methods.
- Reversibility: a specific metric can adopt higher precision behind an
  explicit boundary if measured error warrants it.

## Verification

M2/M3 compare exact positions and bounded metric errors to pinned fixtures.
M4 adds adversarial magnitudes, non-finite data, small denominators, and tie
cases. The actual tolerance values are attached to those tests and fixtures.
