# Adversarial Project Plan Review

- Review date: 2026-09-25
- Scope: `PROJECT_PLAN.md`, `PROJECT_BRIEF.md`, and
  `STATISTICAL_ANALYSIS_PLAN.md`; planning documents only, no implementation.
- Review basis: current GitHub `joshuamyers22/production-project-template`
  HEAD `efd1e9cb0defeb3442d3a2d10ea874524664173d`, checked via a temporary
  checkout, especially its project brief, statistical analysis plan,
  adversarial review, verification-loop template, and quant point of view.
  These relevant files match the local clone at
  `c5b331b82355a6dca150f0b1730e9f0cd6133361`. The local template
  worktree had unrelated uncommitted changes; no template files were edited.
- External cross-check: the public upstream
  [README](https://github.com/vivek-v-rao/moving-average-systems) describes
  inclusive length ranges and the 597-strategy worked example. The exact
  pinned worked-example input and command remain an M1 capture gate.
- Reviewer: Codex self-review. It is not independent statistical, legal, or
  release approval.

## Verdict

**Revise before implementation.** The original plan was strong on parity,
causality, and evidence retention, but several claims could have produced a
misleading confirmatory result or an infeasible scale target. The corrections
below are incorporated in the three planning documents. Release and
confirmatory-use approval remain subject to the stated evidence gates.

## Findings and dispositions

| ID | Severity | Evidence in original plan | Failure mode | Correction and acceptance check | Status |
|---|---|---|---|---|---|
| P-01 | High | `PROJECT_PLAN.md` called its TOML example a 597-candidate reference while configuring 10 fast lengths × 19 slow lengths × 3 signal assets × 3 trade assets = 1,710 candidate/trade rows. | A passing parity claim could use the wrong family and oracle. | Example now enumerates 1 × 199 × 3 × 1 = 597; M1 must capture the exact upstream command, input hash, trade asset, and counts. | Plan corrected; source capture open. |
| P-02 | Critical | The SAP called 2020 onward a locked final window after citing an upstream full-sample result through the dataset end. | An already inspected period would be described as untouched confirmatory evidence. | Historical study is labeled retrospective; a new final window requires a dated freeze before fresh observations, plus one-time consumption and independent review. | Plan corrected; fresh data and approval open. |
| P-03 | High | The SAP alternated among Sharpe above cash, Sharpe advantage over buy-and-hold, and bootstrap familywise p-values without one test statistic or paired benchmark. | P-values could be interpreted as evidence for a hypothesis they did not test. | Primary procedure comparison and secondary paired-mean family null are separate; passive SPY is the predeclared benchmark for the one-trade-asset study. M6 calibration must use paired, cost-adjusted returns. | Plan corrected; calibration open. |
| P-04 | High | A cumulative ledger was presented as a joint inference family for any runs sharing dataset and estimand. | Differing windows, benchmarks, costs, or prior manual searches invalidate a naive joint bootstrap and can understate selection. | Ledger records all inspected work; joint tests require aligned hypotheses and dates. Unknown earlier exploration remains a limitation. | Plan corrected; ledger design open. |
| P-05 | High | The architecture allowed a dense `T × M` return matrix while promising ≤ 4 GB at 100k × 8.5k. | The float64 matrix alone is 6.8 GB, before features, draws, Gram matrix, or process copies. | Chunked return storage, bounded inference, explicit feasibility gate, measured peak RSS, and a search-only 100k target. | Plan corrected; benchmark open. |
| P-06 | Medium | A deterministic manifest also included `evaluated-at UTC`. | Repeated runs could never have identical manifest hashes as required. | Canonical content payload and variable provenance metadata are separated; compare canonical/result hashes across runs. | Plan corrected; implementation open. |
| P-07 | High | Negative `down_pos` and weights above 1 were allowed without borrow, financing, or margin assumptions. | Net returns could overstate feasible short or leveraged strategies. | V1 rejects weights outside [0, 1] and negative residual cash absent an explicit model. | Plan corrected; test open. |
| P-08 | Medium | Deduplication used position hashes and treated duplicates as trials, without checking assets or execution. | Equal positions can have different returns; a hash collision or differing cost model could merge distinct evidence. | Verify equality and all return-defining inputs; retain search history, while testing distinct hypotheses. | Plan corrected; test open. |
| P-09 | Medium | Vendor-derived `prices.csv` was considered for a cached CI fixture before terms were resolved. | CI could redistribute a dataset without permission. | Default CI uses synthetic fixtures; upstream data stays local and ignored pending source-terms review. | Plan corrected; terms review open. |
| P-10 | Medium | The SAP's one-period purge and fold-local note omitted EB hyperparameters and actual label overlap. | Assessment data could leak through tuning or overlapping realized returns. | Purge by label/return interval; fit EB and every learned rule on training data only. | Plan corrected; tests open. |
| P-11 | High | Cross-calendar action was allowed whenever `lag ≥ 1`. | Different closes, holidays, and order cutoffs can still place execution before feature availability. | Map availability and order cutoff on timestamped signal/trade calendars; reject any causal violation. | Plan corrected; calendar tests open. |
| P-12 | Medium | D4's expected entry-cost delta counted only the traded weight. | A down asset can add a second first-day turnover cost, causing an incorrect parity test. | Compare the sum of all first-day per-leg costs. | Plan corrected; delta test open. |
| P-13 | Medium | PSR null-SE and CSCV/PBO were listed beside confirmatory familywise tests without clear inferential roles. | Diagnostic scores could be presented as chronological or benchmark-adjusted proof. | Label PSR and PBO diagnostic; use calibrated paired-return tests for the declared hypotheses. | Plan corrected; report checks open. |

## Verification performed

| Check | Result |
|---|---|
| Verify template GitHub HEAD and relevant-file parity | Current remote HEAD is `efd1e9c`; the five relevant guidance files match the local checkout. |
| Read template guidance and all three plan documents | Completed. |
| Cross-check upstream README and candidate-count arithmetic | README confirms inclusive ranges; original example count was 1,710, revised one-trade example is 597. Exact worked-example capture remains open. |
| Parse proposed TOML and check resource arithmetic | Both TOML examples parse with Python 3.12; 100,000 × 8,500 × 8 = 6,800,000,000 bytes before overhead. |
| Implementation tests and benchmark | Not applicable: this directory contains planning documents only. |
| Independent statistical or legal review | Not performed. Required before a consequential confirmatory claim or vendor-data redistribution. |

## Next gates

1. M1: capture pinned upstream command, data hash, environment, license terms,
   and numerical outputs without making vendor data a default CI artifact.
2. Before M6: freeze the study protocol, paired benchmark, hypothesis family,
   simulation design, and computational ceiling; use fresh data for any final
   confirmatory assessment.
3. M6/M7: demonstrate null calibration and measured memory/runtime on the
   declared supported family sizes. Suppress confirmatory outputs for failed or
   infeasible methods.
