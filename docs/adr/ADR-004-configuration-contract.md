# ADR-004: Versioned TOML configuration with strict validation

- Status: accepted
- Date: 2026-09-25
- Owner: Josh Myers
- Supersedes / superseded by: none

## Context and forces

The proposed grid has feature, rule, universe, execution, and inference axes.
Silent defaults or ignored keys could change trial counts or timing without
appearing in the evidence. The standard library already parses TOML; there is
no demonstrated need for a second validation framework at M0.

## Options considered

- Free-form dictionaries with permissive defaults.
- TOML plus frozen typed dataclasses and explicit validation.
- A model library such as Pydantic from the start.

## Decision

Use TOML parsed by `tomllib`, then convert to frozen typed configuration objects.
Reject unknown keys, invalid ranges, non-finite numbers, ambiguous units,
incompatible feature/rule combinations, and unsupported schema versions before
evaluation. Canonicalize the validated config for hashing and candidate IDs.
The `plan` command computes exact counts and a bounded resource estimate before
`run`. Limits are enforced, not silently bypassed; seeded subsampling is
explicit. The default candidate and memory ceilings remain an M4 measured
decision, not a value invented at M0.

## Consequences

- Benefit: the same validated contract drives execution and evidence.
- Cost: schema migrations must be explicit as axes are added.
- Failure mode: a rough resource estimate can understate real peak memory; M4
and M7 must compare estimates to measured RSS.
- Reversibility: add a validation dependency only if measured complexity or
missing behavior justifies it, with an ADR and migration tests.

## Verification

M4 exercises rejection of unknown keys, invalid counts/units, unsupported
versions, and over-budget spaces; canonical hashes must be stable across runs.
M7 tests the estimate against measured memory and runtime.
