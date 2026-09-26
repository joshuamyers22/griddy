# Project Brief

This brief follows the `python-data-quant` archetype `PROJECT_BRIEF.md` fields.
[`PROJECT_PLAN.md`](PROJECT_PLAN.md) holds the milestone plan, and
[`STATISTICAL_ANALYSIS_PLAN.md`](STATISTICAL_ANALYSIS_PLAN.md) holds the inference protocol.

## Outcome

- **Problem and affected users:** Researchers (initially the owner) want to screen
  families of rule-based trading signals built from arbitrary features on arbitrary
  time-series datasets. Two tools exist, and neither does this:
  - `vivek-v-rao/moving-average-systems` (`xma`) does it well for one family (SMA
    crossovers on adjusted closes). It is untested and hard-coded to that family.
  - `gambit` is event-driven and too heavy for exhaustive screening.

  Without an honest trial count, large searches produce winners that are selection
  artifacts.
- **Measurable success criteria:**
  1. The source-verified upstream reference run (597 signal rules, with exact
     trade asset and input pinned at M1) and synthetic fixture matrix are
     reproduced. Figures match to printed precision, and rows match to 1e-12
     except for register-documented divergences. Vendor data stays out of
     default CI pending source-terms review.
  2. The MA family, expressed as pure configuration, is bit-identical to the
     recreation.
  3. A non-price, multi-feature study runs through the same engine with
     known-answer tests.
  4. Under declared null scenarios, the familywise tests meet predeclared
     calibration thresholds or are withheld from confirmatory output.
  5. A 10k-candidate × 8.5k-observation search, plus core metrics, finishes in
     ≤ 30 s within a measured 4 GB RAM budget. This is an initial M7 target;
     100k-candidate inference has a separate feasibility gate.
- **Explicit non-goals:**
  - Event-driven, order-level simulation (that is `gambit`'s job).
  - Live trading or serving.
  - Cross-sectional ranking portfolios in v1.
  - Fitted ML models as features.
  - Adaptive (Bayesian or genetic) search.
  - Committing vendor data.
- **Critical user journeys:**
  1. `xma`-compatible command → same tables as upstream.
  2. TOML search space → `plan` (counts, memory, runtime) → `run` → results
     Parquet + manifest + report.
  3. Walk-forward selection → OOS returns of the selection procedure → paired
     benchmark comparison. Familywise tests use compatible aligned trials;
     the ledger also discloses other inspected work.
  4. Publish a new dataset version → verify → search over its feature columns.

## Constraints and risk

- **Runtime/deployment environment:** Python 3.12 (upstream syntax already requires
  ≥ 3.12). `uv`-locked. Local workstation and CI batch jobs. No deployed service,
  so no container is required beyond the archetype CI.
- **Tabular engine:** Polars at all tabular boundaries. NumPy inside the numeric
  kernel behind one explicit conversion. No pandas dependency. yfinance, which
  returns pandas, is isolated in an optional adapter whose output is published as
  a Polars/Parquet dataset (ADR-008).
- **Statistical engine:** Statsmodels for multiple-testing adjustments
  (`multipletests`: Holm, BHY) and HAC/autocorrelation utilities. Custom, tested
  implementations for PSR/DSR, effective N, max-stat simulation, stationary
  bootstrap SPA / Romano–Wolf, CSCV/PBO, and EB shrinkage. Statsmodels does not
  provide these.
- **Statistical-learning point-of-view departures and supporting evidence:**
  - Exhaustive grid search is itself the fitted procedure. It is accepted only
    with a disclosed trial count, a cumulative ledger, and separation of
    selection from assessment.
  - Full-sample in-sample reports (upstream behavior) are kept for parity but
    labeled exploratory.
- **Decision objective, action, horizon, utility, guardrails, and proxy gaps:**
  - Decision: whether a rule family, and which member, merits confirmatory
    (event-driven or paper) testing.
  - Utility: net-of-cost risk-adjusted return (Sharpe versus the rf rate).
  - Guardrails: turnover, drawdown, exposure, OOS degradation.
  - Proxy gaps: daily close-to-close returns ignore intraday execution, borrow,
    capacity, and slippage beyond linear bps.
  - General v1 rejects short/leveraged weights without financing and borrow
    assumptions; the compatibility path can reproduce them only as labeled
    retrospective fixtures.
- **Heuristic and interpretable baselines:** Buy-and-hold of the traded asset,
  cash, the equal-weight family average (upstream's `--average`), and the
  in-sample-best versus OOS-procedure comparison.
- **Data classification and retention:** Public market data under vendor terms,
  plus user-supplied datasets that may be restricted. Nothing vendor-derived or
  restricted goes in Git. Outputs are local, and retention is at the user's
  discretion. The trial ledger is retained for the life of a study.
- **Dataset contract, versioning, partitioning, migration:**
  - Long panel `(ts, entity, value columns)` with declared roles, units,
    frequency, calendar, and timezone, plus optional `available_at`.
  - Immutable versioned Parquet via the archetype publisher.
  - Schema changes create a new dataset version. Contract version bumps require
    an ADR.
- **Published dataset immutability, access control, integrity, backup, deletion:**
  Manifest SHA-256 verification before every scan, and published versions are
  never mutated. Access control and backup rely on the local filesystem; there is
  no shared store in v1.
- **Availability and recovery objectives:** Not applicable (a local research tool).
  Runs are deterministic, so recovery means rerunning.
- **Research/batch latency, throughput, jitter:** Batch only. Targets are in the
  success criteria. There is no live path, so `LATENCY_BUDGET.md` is not
  required.
- **Queue, capacity, stale-data, overload behavior:** The `plan` dry run refuses
  searches above `max_candidates` or the memory budget. Block size is derived
  from the budget. Seeded subsampling is explicit and recorded, never automatic.
- **Top failure or abuse scenarios:**
  1. Look-ahead through a feature, calendar misalignment, or revised data.
  2. A selection artifact reported as a discovery (in-sample winner, ignored
     prior runs).
  3. Silent wrong data, as in upstream's `Adj Close` bug.
  4. Memory blow-up from a combinatorial space.
  5. Divergence between the vectorized and reference engines, including
     float ties at thresholds.
- **Units, precision, timezone, market calendar:**
  - Prices are in quote currency; returns are simple, per period.
  - Float64 in the kernel (ADR-003).
  - Timestamps are UTC, or date plus a declared exchange calendar.
  - `periods_per_year` is derived from the declared frequency and is never
    hard-coded.
- **Missing-data, outlier, adjustment, survivorship rules:**
  - No price forward-fill. Series are aligned by intersection within the common
    window. Multi-day returns across gaps compound correctly, with gap duration
    and invalid execution dates reported.
  - Adjusted closes are accepted as supplied; adjustment method and source
    vintage are recorded when available. A frozen historical file is not proof
    of point-in-time availability.
  - Outliers are flagged in the data-quality report, never altered.
  - Survivorship is the dataset owner's responsibility, and the dataset manifest
    must declare the universe basis.
- **Point-in-time and look-ahead controls:**
  - Primitive causality contract plus perturb-the-future property tests.
  - `available_at` enforcement.
  - Execution lag in declared sessions.
  - Cross-calendar execution uses timestamped source availability and trade
    order cutoffs; a numeric lag alone does not establish causality.
  - Fitted steps (none in v1 primitives) must be fold-local.
- **Regression sample construction, leakage controls, standard errors,
  multiple-testing policy:** See the SAP. Sharpe SEs use the PSR moments formula
  as a diagnostic, with Lo/HAC as a sensitivity analysis. Confirmatory paired
  return tests use a declared, aligned hypothesis family and benchmark.
- **Development/selection/final-assessment separation:**
  - Development window for iteration.
  - Walk-forward or holdout for selection.
  - A final window frozen before fresh data are observed, evaluated once per
    study and recorded in the ledger. The upstream historical window is already
    inspected and supports retrospective analysis only.
- **Research-to-production parity, skew monitoring, fallback, retirement:**
  - Not a production system.
  - Optional v1.1 export of a selected candidate to `gambit` for event-driven
    replay, with a parity check on positions and returns.
- **Reconciliation source and tolerances:**
  - Upstream golden fixtures: positions exact; returns and metrics ≤ 1e-12
    relative; printed figures at printed precision.
  - Reference versus block engine: the same tolerances.
- **Feed sequence, gap, duplicate, reordering, replay policy:**
  - Duplicate `(ts, entity)` and unordered input are rejected at ingest.
  - Gaps are reported.
  - No streaming feeds.
- **Legal/compliance:** Upstream code is MIT. Ported portions keep the copyright
  and permission notice (ADR-001). Yahoo data terms mean no redistribution.
- **Budget and delivery deadline:** Solo, agent-assisted. Milestones M0–M8 are
  sized S/M/L in the plan, with no fixed deadline.
- **Owner:** Josh Myers (`joshuamyers22`).

## System outline

- **Sources of truth:**
  - Versioned dataset manifests.
  - TOML run configs.
  - Upstream fixtures at SHA `91e9e35`.
  - The trial ledger.
- **External dependencies:** polars, numpy, statsmodels (scipy transitively).
  Optional: yfinance, matplotlib.
- **Trust boundaries:** CSV/Parquet ingest, vendor adapter, and user-authored
  configs (strict validation; unknown keys rejected).
- **Core domain invariants:**
  - Causality at every stage.
  - Identical evaluation window across a family used for joint inference.
  - Evaluated-trial counts and study history are exact and monotone in the
    ledger; unevaluated grid members are reported separately.
  - Deterministic canonical outputs for fixed inputs, config, and seed,
    independent of worker count; run time and host provenance are separate.
- **Consistency and concurrency:** Process-pool block evaluation with ordered
  reassembly. Ledger appends are atomic (write-new-file plus manifest).
- **Observability signals:** Structured run events per the archetype telemetry
  schema:
  - `run.started`, `run.completed`, `run.failed`;
  - `plan.refused`;
  - `data_quality.gap`;
  - `engine.tie_margin`;
  - `inference.fallback_sampled`.
- **Replay and performance-regression evidence:** Retained benchmark artifacts
  (M7), parity fixtures (M1), and the calibration study (M6).

## Acceptance evidence

| Requirement | Verification | Owner | Status |
|---|---|---|---|
| Upstream parity | M3 fixture suite + divergence-register delta tests | Josh | Planned |
| MA-as-config identity | M4 bit-identical regression test | Josh | Planned |
| Arbitrary feature/set/dataset | M4/M5 known-answer + causality property tests | Josh | Planned |
| Inference calibration | M6 null/power simulation artifact; failed methods withheld | Josh | Planned |
| Prospective validity | SAP freeze and fresh final-window evidence; otherwise exploratory label | Josh | Planned |
| Scale | M7 benchmark artifacts vs thresholds | Josh | Planned |
| Reproducibility | Double-run and worker-count canonical payload/result hash test | Josh | Planned |

## Open decisions

| Question | Decision deadline | Owner | ADR |
|---|---|---|---|
| Project name: `signal-grid` | M0 | Josh | Decided |
| License model: proprietary new code plus MIT upstream notice | M0 | Josh | 001 accepted |
| Handling of upstream `prices.csv` in tests | M1 | Josh | 008 |
| Search ceiling and memory budget defaults | M4 | Josh | 004 |
| Primary selection criterion, PSR SE variant, trial family | M6 | Josh | 006 |
| Numba adoption | M7 | Josh | 005 |
| Cross-sectional rules in v1 | M5 | Josh | — |
