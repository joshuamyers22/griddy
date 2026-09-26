# ADR-001: Proprietary project license and upstream attribution

- Status: accepted
- Date: 2026-09-25
- Owner: Josh Myers
- Supersedes / superseded by: none

## Context and forces

`griddy` starts from the production template's private, proprietary
license. M1–M3 plan to study and potentially port portions of
`vivek-v-rao/moving-average-systems` at commit
`91e9e35a9eca36d314138302fb86075f05cb71c0`. That upstream project carries
an MIT license. Market data has separate source terms and is outside this code
license decision.

## Options considered

- License all new work under MIT.
- Keep new work proprietary and retain the upstream MIT copyright and permission
  notice for any copied or adapted upstream portions.

## Decision

Keep new `griddy` code proprietary and the repository private by default.
Retain the upstream notice verbatim in `THIRD_PARTY_NOTICES.md`, and identify
ported files when they are introduced. No upstream source code or vendor price
data is included at M0. Redistribution of upstream-derived code or data requires
a separate source-terms review before release.

## Consequences

- Benefit: preserves the template's intended ownership and makes attribution
  visible before any port begins.
- Cost: public distribution needs a deliberate license decision and a check of
  which files incorporate upstream work.
- Operational implication: license and notice checks belong in the release gate.
- Reversibility: the owner may adopt MIT for new code later; upstream notices
  must still be retained where the MIT license requires them.

## Verification

Compare `THIRD_PARTY_NOTICES.md` with the pinned upstream `LICENSE`, verify
that no upstream source or price data is committed at M0, and revisit this ADR
when M3 ports code or when publication is proposed.
