# Statistical Analysis Plan

This plan follows `templates/STATISTICAL_ANALYSIS_PLAN.md`. It has two layers:

- **(A) The protocol the tool enforces for any study.** Each study links its own
  filled copy of this plan.
- **(B) The first study:** a retrospective re-analysis of the upstream
  SPY/IEF/TLT MA-crossover family. Its published full-sample results mean the
  historical period is already inspected and cannot serve as an untouched
  confirmatory final assessment. A separate prospective protocol must freeze
  before fresh data are observed.

Status: draft, 2026-09-25. M6 results are method-validation and exploratory
evidence until the protocol, benchmark, family, and fresh final window are frozen
and independently reviewed.

## Decision and estimand

- **Decision this analysis informs:** Whether a rule family, and which of its
  members, deserves confirmatory testing. Confirmatory testing means an
  event-driven replay in `gambit`, paper trading, or fresh data.
- **Population and estimand:**
  - (A) The net return and Sharpe difference between the complete, frozen
    selection procedure and one predeclared passive benchmark over subsequent
    observations. The procedure includes its feature, candidate, tuning, cost,
    and refit rules. This is not the Sharpe of the in-sample winner.
  - Secondary estimand: the maximum expected per-period paired net-return
    differential across a declared family F on one aligned window.
  - (B) The retrospective parity family is SMA ratio crossover, fast = 1,
    slow ∈ 2:200, threshold 0, signal asset ∈ {SPY, IEF, TLT}, and trade asset
    = SPY (597 candidate rules). The exact upstream worked-example command is
    an M1 verification gate. The family average is a separate, declared
    candidate only if it was actually evaluated in that study.
- **Primary hypothesis:**
  - Prospective primary decision: the lower 90% stationary-bootstrap bound for
    the selection procedure's OOS net Sharpe advantage over the predeclared
    passive benchmark must exceed zero, and the point estimate must exceed 0.2.
  - Secondary family null: for every member j, E[r_j,t − r_b,t] ≤ 0, using
    paired, cost-adjusted per-period differentials on identical dates.
    Romano–Wolf stepdown and Hansen SPA are calibrated for their specific nulls
    in M6; their p-values are not described as tests of a Sharpe-difference null.
  - Upstream's parametric Max-p is diagnostic, not confirmatory by default.
- **Prediction time, action, horizon, availability, decision owner:**
  - The signal is formed at the close of *t*.
  - The position is held over (t + lag, t + lag + 1].
  - Horizon: one period, rebalanced every period.
  - Features must have `available_at ≤ close(t)`.
  - Decision owner: Josh Myers.
- **Model objective, decision utility, guardrails, proxy gaps:**
  - Objective: net Sharpe advantage over the benchmark, with the paired mean
    differential used for the secondary familywise hypothesis.
  - Guardrails: max drawdown, turnover, average exposure, OOS/IS Sharpe ratio.
  - Proxy gaps: close-to-close execution; linear costs; no capacity or impact
    modeling. Negative or leveraged weights are exploratory until borrow,
    financing, and margin assumptions are specified. Legacy `xma` parity
    calculations with such weights are labeled retrospective and non-actionable.
- **Economic/practical significance threshold:** OOS net Sharpe improvement of
  at least 0.2 over passive SPY buy-and-hold for the one-trade-asset study, with
  a lower 90% bound above zero. The same date-aligned, net-of-cost benchmark is
  used in every fold; a different universe requires a newly declared benchmark.
- **Pre-specified versus exploratory analyses:**
  - Proposed prospective settings: `lag = 1`, cost 5 bps per leg, walk-forward
    selection, familywise tests on the development window. These are not yet
    pre-registered or confirmatory.
  - Upstream settings (`lag = 0`, cost 0, full-sample, in-sample DSR) and all
    current historical analyses are exploratory parity reproduction.
- **Statistical-learning point-of-view preferences followed or departed from:**
  - Followed:
    - selection is separated from assessment;
    - the whole search is treated as the fitted procedure;
    - disappointing and superseded candidates are retained.
  - Departed from: no fold-local fitted preprocessing exists in v1 primitives,
    so there is nothing to refit per fold except the selection step.

## Data and sample

- **Dataset owners, versions, licenses, hashes, as-of time:**
  - (B) upstream `prices.csv` at repository SHA `91e9e35`: Yahoo-derived adjusted
    closes. Source terms, final observation date, and exact file SHA-256 are M1
    capture fields, not assumed facts. The file remains local and ignored until
    use and redistribution terms are reviewed.
- **Manifest, schema contract, partitions, compatibility:** Archetype Parquet
  publisher. Contract `(ts: date, entity: str, price: f64, role = price)`.
  Business-day frequency, NYSE calendar, `periods_per_year = 252`.
- **Inclusion/exclusion and point-in-time universe:** A fixed three-ETF
  universe, chosen with hindsight. This is disclosed as a limitation, since the
  universe itself is a selection.
- **Observation unit, range, frequency, sample size:**
  - Daily. SPY from 1993-01-29; IEF and TLT from 2002-07-30.
  - The published worked example reports 5,878 common observations at `lag = 0`;
    M1 must verify the exact input and window before using it as an oracle.
- **Outcome, predictors, units, transformations:**
  - Outcome: simple daily net return of the rule.
  - Predictors: SMA levels of adjusted close.
  - Signal: `fast/slow − 1`.
- **Missing-data, outlier, censoring, imputation:** No imputation. Series are
  aligned by intersection. Returns across gaps compound correctly. Outliers
  are reported but not altered.
- **Look-ahead, survivorship, selection, leakage controls:**
  - Causality property tests.
  - Lag in sessions.
  - Cross-calendar actions are rejected unless source availability precedes
    the actual trade order cutoff on the traded asset's calendar.
  - A frozen adjusted-close vintage makes retrospective runs reproducible but
    does not prove historical availability. The study makes no point-in-time
    claim for values lacking source-vintage evidence; sensitivity to revisions
    is assessed when vintages exist.
  - Survivorship: ETFs chosen ex post (see above).
- **Timestamp semantics:** Decision at `close(t)`, execution at `close(t + lag)`,
  return realized at `close(t + lag + 1)`.

## Model specification

- **Engine and locked version:**
  - Custom rule engine; the version is the package version plus the `uv.lock`
    hash.
  - Statsmodels (locked) is used only for `multipletests` and HAC utilities.
- **Polars pipeline and Polars-to-model boundary:** The Polars dataset is
  converted to a NumPy (entities × T) float64 array once per run in
  `engine/block.py`. Parameter columns come back as Polars.
- **Formula / ordered design:**
  - The candidate axis order is the canonical search-space enumeration.
  - Candidate IDs are stable hashes.
- **Intercept, weights, fixed effects, interactions:** Not applicable (no
  regression).
- **Distributional assumptions:**
  - PSR/DSR use a moments-based approximation with finite fourth moments;
    serial dependence can make an i.i.d. SE invalid. They are diagnostics until
    their relevant null calibration passes.
  - Lo (2002) and HAC SEs are a sensitivity analysis for serial correlation.
  - Bootstrap tests use a stationary bootstrap with mean block length chosen by
    the Politis–White rule. This is pre-specified; the length is recorded.
- **Covariance / SE estimator:**
  - PSR moments-based SE. The null-evaluated variant is preferred for its own
    zero-Sharpe diagnostic; the SR̂-evaluated variant is reported for parity.
    Neither supplies the primary paired benchmark or familywise inference.
- **Multiple-testing and model-selection correction:**
  - Primary confirmatory inference is the prospective OOS procedure comparison
    after protocol freeze and independent review. The secondary paired-mean
    family uses calibrated Romano–Wolf stepdown; Hansen SPA is a separate
    benchmark-comparison sensitivity analysis.
  - Reported alongside:
    - DSR, with SR0 from accurate E[max] at EffN-B, EffN-G, and EffN-max;
    - parametric Max-p;
    - Holm and BHY on PSR p-values;
    - PBO via CSCV (S = 16), labeled retrospective and non-chronological;
    - EB-shrunk Sharpe.
  - The ledger records every trial and inspected outcome. Tests combine runs
    only when their candidate hypotheses, benchmark, return definition, and
    dates are compatible. Other prior work is disclosed as selection history,
    not inserted into a mathematically invalid joint bootstrap.
- **Baselines:**
  - Passive SPY buy-and-hold is the declared paired benchmark for this
    one-trade-asset study. Cash and the equal-weight family average are
    descriptive comparators; the average counts as a trial if evaluated.
  - A "random rule" baseline: identical turnover with randomized timing, 1,000
    seeded draws, labeled diagnostic because random timing may violate market
    dependence or execution constraints.
- **Search space:** As stated in the estimand, fixed before M6. Any expansion
  is a new ledger entry, and the cumulative count grows.
- **Fold-local learned steps:** Only candidate selection (argmax of the
  selection criterion on training data). The selection criterion is
  EB-shrunk Sharpe (Q5), with raw Sharpe and DSR as sensitivity analyses.
- **Random seeds and numerical tolerances:**
  - Base seed 12345, with per-component substreams via `numpy.random.SeedSequence`.
    Freeze and record the generator, library versions, and Monte Carlo draws
    before confirmatory use.
  - Engine equivalence: positions exact, returns ≤ 1e-12 relative.
  - E[max] ≤ 1e-8 absolute versus the high-precision reference.

## Bayesian regression implementation, when applicable

Not applicable. The EB Sharpe shrinkage is a method-of-moments empirical-Bayes
estimator, not a posterior computation. Its assumptions (normal–normal, noise
covariance proxied by return correlation) are stated in the inference guide.

## Diagnostics and validation

- **Identification and rank/collinearity checks:**
  - Effective-N suite.
  - Unique-stream deduplication count.
  - Rank of the candidate correlation (Gram side).
- **Residual, influence, dependence, stability:**
  - Per-candidate skew, kurtosis, lag-1 to lag-5 autocorrelation.
  - Per-year Sharpe table.
  - Rolling 3-year Sharpe dispersion.
- **Time-aware evaluation design:**
  - Expanding walk-forward.
  - Initial training window of 10 years.
  - Test blocks of 1 year, stepped by 1 year.
  - Purge every training label whose realized return interval overlaps the
    test block; the minimum is the one-period label horizon. A feature's
    warmup is not itself an embargo. Any lag or multi-period holding rule
    lengthens the purge according to its actual information/return interval.
  - Every fitted quantity, including EB cross-sectional shrinkage parameters,
    selection thresholds, and any estimated bootstrap settings, uses only the
    fold's training data. OOS blocks cannot tune later reports presented as
    locked assessment.
- **Development, selection, and locked final assessment:**
  - The 1993–2019 development and 2020–2026 assessment split is retrospective:
    upstream's full-sample worked example already inspected the later period.
    It can exercise the software but cannot supply a clean final claim.
  - A prospective final window begins only after a dated, immutable SAP and
    candidate/benchmark freeze. Its start, end/observation rule, data source,
    access controls, and one-time consumption are recorded before observations
    are available. If fresh data are unavailable, the study remains exploratory.
- **Initial test boundary, window/step, embargo:** As above. All values are
  recorded in the manifest.
- **Baselines and ablations:**
  - Threshold ∈ {0, 0.01}.
  - Lag ∈ {0, 1, 2}.
  - Cost ∈ {0, 5, 20} bps.
  - `down_pos` ∈ {0, −1}.
  - Signal asset = trade asset versus cross.
- **Selection uncertainty and history retention:**
  - All candidate results and OOS returns are retained.
  - The selected-member frequency across folds is reported.
  - All inspected variants of universe, period, costs, benchmark, and selection
    criterion are logged. A ledger started now cannot recover unknown earlier
    trials, and no independence claim is made for them.
- **Sensitivity and alternative specifications:** EMA instead of SMA, the
  `difference` signal instead of `ratio`, and weekly rebalancing (M5
  capability).
- **Stability slices:** By decade, by rate regime (rising/falling 10-year
  yield), by volatility tercile, and by traded asset.
- **Calibration, coverage, failure thresholds:**
  - M6 simulation study: declare null-generating processes, serial/cross
    dependence, replication count, target family sizes, nominal 5% level, and
    a confidence interval for empirical rejection before running. A method
    that fails its predeclared threshold is marked uncalibrated and is withheld
    from confirmatory output; a single favorable simulation is insufficient.
- **Costs, capacity, latency, operational constraints:** Linear bps costs.
  Capacity is not modeled (a stated limitation). No latency path.
- **Research/replay/live parity:** Optional `gambit` replay of the selected
  member (v1.1). Positions must match exactly; returns within cost-model
  differences that are documented.

## Evidence and approval

- **Commands, commit, environment lock, hashes, artifact location:** The run
  manifest (see plan §5.4) under `build/runs/<run-id>/`. The ledger lives
  under `data/ledger/`.
- **Evidence schema version and independent reviewer:** `run-manifest/v1`.
  Reviewer TBD. Agent self-review is not approval.
- **Results with uncertainty:**
  - OOS Sharpe with a stationary-bootstrap 90% interval.
  - Familywise-adjusted p-values.
  - PBO.
  - DSR at three effective-N values.
  - EB-shrunk estimates.
- **Known limitations and invalidating conditions:**
  - Hindsight universe.
  - All historical data through the upstream worked-example end have been
    exposed to a full-sample search; a 2020 start does not restore a holdout.
  - Close-to-close execution.
  - Vendor-adjusted data.
  - Return correlation used as a proxy for estimator correlation (EffN-max, EB).
  - Invalid if the dataset version, window, or cost model changes without a new
    ledger entry.
- **Monitoring, refit, rollback, retirement:** Not applicable to research. A
  study is superseded by a newer ledger entry, never edited.
- **Falsification criteria:** A prospective performance claim fails if the
  point Sharpe advantage is below 0.2, its lower 90% bound is at or below zero,
  the cost/availability assumptions fail, or the final window was inspected
  before freeze. Familywise results, PBO, and stability slices are reported
  with their own denominators and assumptions; no favorable secondary metric
  rescues a failed primary criterion.
- **Author, reviewer, approver, date:** Josh Myers / TBD / TBD / —.
