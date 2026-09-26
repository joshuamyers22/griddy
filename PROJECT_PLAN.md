# Project Plan: `griddy`

- Status: M0–M1 complete; M2 is next
- Date: 2026-09-25
- Owner: Josh Myers
- Template: `joshuamyers22/production-project-template` @
  `efd1e9cb0defeb3442d3a2d10ea874524664173d`, archetype `python-data-quant`
- Upstream: `vivek-v-rao/moving-average-systems` @ `91e9e35a9eca36d314138302fb86075f05cb71c0` (MIT)
- Companion records: [`PROJECT_BRIEF.md`](PROJECT_BRIEF.md),
  [`STATISTICAL_ANALYSIS_PLAN.md`](STATISTICAL_ANALYSIS_PLAN.md), and
  [`ADVERSARIAL_PLAN_REVIEW.md`](ADVERSARIAL_PLAN_REVIEW.md)

## 1. Objective

1. **Recreate** the upstream `xma` tool with demonstrated numerical parity.
   `xma` does a fast exact grid search of SMA-crossover systems with
   multiple-testing-aware Sharpe diagnostics. Parity is checked against golden
   outputs captured from the pinned upstream commit.
2. **Generalize** it into a family-agnostic grid-search engine. The engine runs
   over any causal feature, set of features, signal construction, and position
   rule, on any contract-checked time-series dataset. The multiple-testing
   evidence is honest about everything that was searched.

The MA crossover becomes a single configuration of the general engine. It is
not a special code path. The acceptance test for the generalization is that
this configuration reproduces the Milestone 3 results bit-for-bit.

## 2. What upstream does (inventory summary)

About 1,890 lines of Python in package `xma`, entry point `xma_signal.py`. There
are no tests, no CI, no packaging, and no pinned dependencies, and it needs
Python ≥ 3.12.

| Area | Upstream behavior to recreate |
|---|---|
| Features | SMA only, via `rolling(L, min_periods=L).mean()`, computed once per unique length. |
| Signal | `dev = fast/slow − 1`. The state is up when `dev > threshold` (strict inequality). It is NaN until both MAs exist. The fast × slow × threshold grid is a full Cartesian product with no `fast < slow` constraint. |
| Rule | Up → weight 1, down → `down_pos` (may be negative or above 1). An optional down-state asset gets `1 − down_pos`. Cash absorbs the residual at a constant `cash_rate`. |
| Timing | The state at close *t* is shifted `1 + lag` sessions within the common dates and earns P(t+1)/P(t) − 1. With lag 0 this is market-on-close at the signal's own close. |
| Costs | `cost × |Δw|` on the traded weight and the down-asset weight. Cash is free. Entry from flat is charged on the first valid day. |
| Search | Blocks of `B` candidates (default 512). Fancy-index gathers `ma_matrix[idx]` into shape (B, T). Thresholds are broadcast, lag is an array shift, and metrics are axis-1 reductions. A scalar pandas path serves as the de facto oracle. |
| Window | A common evaluation window across every candidate by default. It starts at the latest first-signal date + 1 + lag, intersected across signal, trade, and down series. |
| Metrics | 252-day annualization. CAGR from n/252 years, volatility (ddof = 1), Sharpe versus the constant cash rate, beta and Jensen alpha versus buy-and-hold of the traded asset, changes/year, average position, cash weight. Max drawdown only on the scalar path. Annual table. |
| Multiple testing | Pearson correlation of candidate returns. Effective N three ways: EffN-B (average correlation), EffN-G (Galwey), and EffN-max (simulated correlated Gaussian maxima inverted through Gauss–Hermite E[max]). PSR, DSR with SR0 = sd(SR) · E[max Z](EffN-B), "haircut" = SR − SR0, a parametric max-T familywise p-value, empirical-Bayes shrunk Sharpe, and a Galwey redundancy decomposition by grid axis. |
| Other | Average (ensemble) system, `--best`, crossover listing, yfinance loader, CSV I/O, matplotlib `show()` plots. |
| Reference result | The pinned upstream worked example has 597 candidates and 5,878 observations, with MeanCorr .665, EffN-B 200.58, EffN-G 20.99, EffN-max 6.95, best IEF 1/7 signal trading SPY with SR .714, DSR .982, and Max-p .0068. M1 captured the exact command, input hash, environment, and matching local figures in `docs/UPSTREAM_CAPTURE.md`. |

**Design ideas we keep:**
- Compute each feature once per unique parameter tuple, then build candidates by
  gather and broadcast in blocks.
- Keep a readable scalar oracle alongside the vectorized path, both producing
  one row schema.
- Default to a common evaluation window.
- Treat candidate return streams as the family-agnostic input to inference.
- Report several effective-N views side by side.
- Use seeded antithetic max simulation.
- Keep the EB shrinkage and the per-axis redundancy decomposition.
- Document the diagnostics honestly, in the style of `INTERPRETING_DEFLATION.md`.

**Blockers to generalization:**
- 252 periods per year is hard-coded in 5 files.
- The CLI and row schema are fixed to exactly two length groups plus a threshold.
- The ratio signal assumes positive levels.
- The rule is binary.
- Inputs are price-only, with a `Date` column.
- Each candidate has one traded asset.
- Sharpe is the only selection metric.
- Business logic is triplicated (scalar, vectorized, plotting).
- Output is stdout only.
- Deflation is O(M²) memory and O(M³) time.

## 3. Scope

**In scope (v1)**
- Parity recreation.
- A declarative search space over feature transforms, signal constructors,
  position rules, feature subsets, and multi-feature combinations.
- Single-asset and per-entity panel evaluation.
- Configurable frequency and risk-free rate.
- Holdout and walk-forward selection with a locked final assessment.
- A family-agnostic inference suite, including bootstrap-based familywise tests
  and PBO.
- A cross-run trial ledger.
- Machine-readable evidence artifacts.
- CLI and Python API.
- An upstream-compatible `xma` subcommand.

**Explicit non-goals (v1)**
- Order-level or event-driven simulation, fills, and intraday microstructure.
  `gambit` owns that. A selected candidate may later be exported to it for
  confirmatory replay.
- Live trading or signal serving.
- Cross-sectional ranking portfolios and optimizers (deferred to v2).
- ML model fitting inside the search (e.g., fitted regressions as features).
- Genetic, Bayesian, or other adaptive search. Only exhaustive grid and seeded
  random subsampling are in scope, so the trial count stays exact.
- Committing vendor data.

## 4. Divergence register (upstream behaviors we will not copy)

Each item gets a test that pins the upstream value, our value, and the
explained delta. Legacy behavior is not reachable through production flags.
Parity fixtures either avoid the affected configuration or assert the
documented delta.

| ID | Upstream behavior | Our behavior | Evidence |
|---|---|---|---|
| D1 | A single-symbol run silently uses any CSV `Adj Close` column, even for the wrong ticker (`cli.py:271`, `data.py:36`). | Entity columns must match exactly. A legacy column is accepted only through explicit `--legacy-column-entity`. | Regression test using the `QQQ`-on-SPY-file reproduction. |
| D2 | The current-direction display uses `< 0` rather than `< threshold` (`backtest.py:59-61`). | Display uses the same predicate as the backtest. | Unit test. |
| D3 | Drawdown starts from `equity[0] = 1 + r0`, so a first-day loss is missed. | Equity starts at 1.0 before the first return. | Unit test. |
| D4 | Entry cost is charged in-window only for candidates whose first valid day is the window start. `changes` counts the entry for all. | One `initial_position` policy (`flat` default: every candidate pays entry at window start, or `carried`) applied to all candidates. | Delta test: Δ = sum of first-day per-leg entry costs for exactly the affected rows, including any down asset. |
| D5 | Any non-finite value makes the whole search re-run silently on the scalar path. | No silent fallback. Non-finite values are classified as data errors or undefined metrics and reported per candidate. | Fault-injection test. |
| D6 | The average system nets costs across components. | Explicit `cost_basis = aggregated \| per_component`. `aggregated` reproduces upstream. | Parity test + delta test. |
| D7 | `exposure.iloc[0] > 0` (wrong for a negative `down_pos`). | `abs(w) > eps` everywhere. | Unit test with `down_pos = −1`. |
| D8 | SR0 uses the Euler–Mascheroni E[max]; EffN-max uses 80-node Gauss–Hermite, which errs 1.3% at n = 1e6. | One accurate E[max] (adaptive quadrature on the order-statistic integral). The legacy approximation is retained only as a named reported column. | Tested against high-precision reference values at n = 2…1e7. |
| D9 | PSR SE is evaluated at SR̂. Max-p reuses that non-null statistic. | Both are available and labeled as diagnostics. The null-SE variant is preferred for its own zero-Sharpe null diagnostic; confirmatory family tests use the separately calibrated paired-return procedure. | Simulation calibration test (§7 M6). |
| D10 | `tested_count` is the nominal grid size. | Report nominal, valid, unique-stream, and ledger-cumulative counts. | Unit test. |
| D11 | `--best` selects by Sharpe but displays buy-and-hold when the winner's CAGR ≤ B&H. | Selection criterion and display are separate. The benchmark is always shown beside the winner. | CLI test. |
| D12 | The warmup check requires `max(fast, slow)`, not `+1+lag`, and is O(grid). | Warmup is derived from each primitive's declared `warmup(params) + 1 + lag`, computed once. | Unit test. |
| D13 | `--common-window` is a no-op. | Single `window = common \| individual`. Deflation is refused under `individual`. | CLI test. |
| D14 | One stderr line per missing date. | Aggregated data-quality report (counts, first/last gaps per entity). | Snapshot test. |
| D15 | Per-pair common dates differ from the all-signal dates used by `--average` and plots. | One window policy computed once per run and recorded in the manifest. | Test on asynchronous calendars. |
| D16 | `--individual-windows` mixes windows inside deflation. | Refused (see D13). | CLI test. |
| D17 | "Haircut Sharpe" is SR − SR0, not Harvey–Liu. | Renamed `sr_minus_sr0`. Harvey–Liu is optional and added later if wanted. | Naming test in the report schema. |

**Timing is a convention, not a bug.** Upstream lag 0 means trading at the
same close that produced the signal. We keep it as `execution = "signal_close"`
with `lag`, record it in every artifact, and make `lag = 1` the pre-specified
primary setting for conclusions (see SAP). For every signal/trade calendar
pair, the implementation maps `available_at` and the intended order cutoff to
actual timestamped sessions and rejects any action that precedes availability;
a numeric lag alone does not prove causality.
The zero-lag setting is an upstream parity mode, not an executable strategy
assumption without evidence that the signal is available before the order cutoff.

## 5. Target architecture

This is a modular monolith in the archetype's `src/` layout. Polars is used at
every tabular boundary. NumPy is used inside the numeric kernel behind one
explicit Polars→NumPy conversion. There is no pandas dependency. yfinance is an
optional extra whose output is converted and published as a versioned dataset
before any run.

```text
src/griddy/
├── data/          contract.py, ingest.py (strict CSV), dataset.py (archetype Parquet publisher/verifier),
│                  calendar.py (frequency → periods_per_year, session alignment), adapters/yfinance.py [extra]
├── space.py       search-space parsing, lazy enumeration, exact counting, canonical candidate IDs
├── features/      registry.py + primitives (sma, ema, momentum, zscore, rolling_vol, level, diff, rank_pct)
├── signals.py     constructors: ratio_minus_one, difference, level, spread_zscore, …
├── rules.py       position rules: binary, ternary, linear_clip (hysteresis in v1.1, needs a sequential scan)
├── combine.py     multi-feature combiners: all, any, vote, mean_position, fixed_weight_score
├── engine/        reference.py (scalar oracle), block.py (vectorized kernel), execution.py (lag, costs,
│                  cash/rf, down asset, initial position), metrics.py
├── selection/     splits.py (full, holdout, walk-forward), cscv.py
├── inference/     sharpe.py (PSR, MinTRL, Lo/HAC SE), expected_max.py, effective_n.py, maxstat.py,
│                  bootstrap.py (stationary bootstrap, SPA, Romano–Wolf), shrinkage.py (EB), pbo.py,
│                  multitest.py (Holm/BHY via statsmodels)
├── evidence/      manifest.py, ledger.py, writers.py
├── report/        text.py, markdown.py, plots.py [extra; writes files, never show()]
├── compat/xma.py  upstream CLI grammar → run config
└── cli.py         plan | run | report | ledger | xma | fetch | verify
```

### 5.1 Core contracts

**Dataset**
- A long panel with columns `ts`, `entity`, and value columns. Each value
  column has a declared role: `price`, `return`, `feature`, or `rf`. Optional
  `available_at` columns can be declared per value column.
- Declared `frequency`, `calendar`, timezone, units, and `periods_per_year`.
  Annualization is derived from these and never hard-coded. Irregular gaps are
  reported; elapsed-time metrics use actual dates rather than pretending every
  observed row is one regular period.
- Ingest is strict: no schema inference, duplicate `(ts, entity)` is rejected,
  and ordering is enforced.
- Published datasets are immutable, manifest-hashed Parquet versions from the
  archetype's `dataset` module.
- A historical adjusted-close file is a frozen research vintage, not proof that
  every historical value was available as recorded on its date. Point-in-time
  claims require source vintage and availability evidence; otherwise the result
  is labeled retrospective.

**Feature primitive**
- Signature: `(values[T], params) → values[T]`.
- Declares: `warmup(params)`; a `positive_input_required` flag; a **causality
  guarantee** (output at *t* depends only on inputs ≤ *t*); and a `bank`
  implementation that computes every unique parameter tuple once.
- Full-sample normalization is forbidden inside primitives. Anything fitted is
  a fold-local step (see SAP).

**Signal constructor and rule**
- Signal constructor: `features → signal[T]`. `ratio_minus_one` requires
  positive inputs; `difference` and `level` are sign-agnostic. Arbitrary
  non-price features (spreads, yields, returns, z-scores) therefore work.
- Position rule: `signal → target weight[T]`, with parameters such as
  thresholds and up/down weights.

**Search space**
- The Cartesian product of every parameter axis, plus two structural axes:
  - `feature_sets`: explicit lists, or all subsets of size ≤ k drawn from a
    candidate pool.
  - `combine`: the combiner applied to multi-feature sets.
- Constraints (e.g., `fast < slow`) are expressed as predicates. This keeps the
  count exact: nominal, then constrained, then valid.
- Candidate ID = hash of the canonical parameter tuple and the space-version
  hash. It is stable across runs.
- `plan` (dry run) prints counts, the memory estimate, the runtime estimate,
  and warmup. It refuses to run above the configured `max_candidates` ceiling.
- Seeded random subsampling is allowed for oversized spaces. The ledger records
  the full space size *and* the evaluated subset. Unevaluated candidates are not
  counted as tested trials. Researcher changes to the space or subset rule are
  separate, logged trials and cannot be erased by stream deduplication.

**Execution model**
- `execution = signal_close`; `lag` is mapped from signal availability to a
  timestamped tradable session on the trade asset's calendar.
- `cost` in bps of |Δw| per leg.
- `initial_position = flat | carried`.
- Cash rate: a constant, or an `rf` series.
- Optional down asset.
- Leveraged or short weights require an explicit financing, borrow, and margin
  model; otherwise general v1 and confirmatory studies reject weights outside
  [0, 1] and negative residual cash. The `xma` parity path may calculate and
  label legacy short/leveraged cases as retrospective, non-actionable fixtures.
- Per-entity mode: evaluate each candidate on each entity, plus an
  equal-weight portfolio across entities.

**Result schema**
- A Parquet table with one row per (candidate, signal entity, trade entity,
  split).
- Parameter columns are generated from the space with typed columns. They are
  not fixed `fast`/`slow` names.
- Metrics include drawdown on every path.
- Candidate returns are written in bounded, columnar chunks keyed by candidate
  ID. A dense in-memory matrix is permitted only after a measured budget check.

### 5.2 Vectorized kernel

The kernel generalizes upstream's gather-and-broadcast into a feature bank per
(source column, primitive), with shape `(n_param_tuples, T)`:
- Candidates in a block gather their feature rows by index.
- The signal constructor and rule broadcast across the block.
- Lag is an array shift.
- Positions, turnover, costs, and returns are computed as (B, T) arrays.
- Metrics use axis-1 reductions; beta uses a single mat-vec.

**Block size and deduplication**
- Block size is auto-derived from a memory budget:
  ≈ `k_arrays × B × T × 8 bytes ≤ budget`.
- Identical position streams (common for coarse grids and thresholds) are
  detected by hashing each block's position rows and verifying equality on a
  hash match. Deduplication is valid only when the asset returns, execution,
  costs, and evaluation window also match. Duplicates remain in the search
  history; inference uses the documented unique test-statistic family.

**Exactness**
- Rolling sums from cumulative sums lose precision. Rolling statistics
  therefore use a numerically stable method, e.g., blocked re-anchored prefix
  sums.
- Equivalence to the reference must hold to ≤ 1e-12 relative on returns.
- Positions must match *exactly*. Any threshold tie within 1e-10 is reported
  with its margin, never silently resolved.

**Parallelism**
- Blocks are processed in parallel by a process pool with deterministic
  ordered reassembly.
- Numba is not a default dependency (ADR-005). It is adopted only if a
  retained benchmark shows NumPy is the bottleneck. The hysteresis rule is the
  expected first justification, since it is inherently sequential.

### 5.3 Scalable inference

- The inference suite consumes aligned candidate returns and benchmark returns,
  plus metadata. It declares the statistic, null, family, and feasible size for
  each test. Return correlation and effective-N are diagnostics, not substitutes
  for a calibrated familywise test.
- **Correlation eigenvalues without forming C (M×M).** For standardized returns
  `Z` (T×M), the nonzero eigenvalues of `C = ZᵀZ/(T−1)` equal those of the
  T×T Gram `ZZᵀ/(T−1)`. Take whichever side is smaller. EffN-G and the
  participation ratio stay exact at M ≫ T, with memory O(min(T, M)²).
- **Correlated-max simulation without a factorization.** Draws from N(0, C) are
  `x = Zᵀg/√(T−1)` with `g ~ N(0, I_T)`. Batched as `ZᵀG`, this is exact and
  BLAS-bound, with no M×M matrix. Antithetic pairs are kept.
- **Mean correlation.** Computed from `‖Σ z_i‖²` in O(TM), no matrix needed.
- **Bootstrap tests** (Hansen SPA, Romano–Wolf stepdown) use pre-specified,
  paired candidate-minus-benchmark return differentials, a stationary-bootstrap
  block-length rule, and a seed. Multiplicity is defined by the tested
  hypotheses; identical streams do not create distinct test statistics.
- **PBO via CSCV.** S = 16 blocks by default, with the combination count
  bounded and sampled with a seed when above the limit. It is a retrospective
  selection-risk diagnostic, not a substitute for chronological assessment.
- Exact tests that cannot be completed under the declared memory/time ceiling
  fail closed or run on an explicitly smaller, predeclared family. They are never
  silently replaced by effective-N approximations. Legacy upstream columns stay
  available under their original meaning for continuity.

### 5.4 Evidence and trial ledger

**Run manifest (JSON)**
- Config hash and search-space hash.
- Dataset manifest hash.
- Code revision and `uv.lock` hash.
- Library versions.
- Seeds.
- Window.
- Execution model.
- Counts (nominal, constrained, valid, unique).
- Split definitions.
- Output file hashes.
- A content-addressed deterministic payload containing the fields above. UTC
  evaluation time and machine/run identifiers are separate provenance metadata;
  they are excluded from the reproducibility hash.

**Trial ledger**
- An append-only local record keyed by a predeclared study ID. Every run records
  candidate IDs, search-space changes, dataset vintage, window, costs, benchmark,
  inspected outcomes, and whether any final window was consumed. Atomic append
  requires a lock and a recoverable manifest update.
- A cumulative hypothesis family is valid only when hypotheses share an aligned
  outcome, benchmark, and observation window. Otherwise the ledger discloses
  prior searches, while confirmatory inference uses a newly declared compatible
  family or fresh data. Manual and unlogged prior exploration remains a stated
  limitation; the ledger cannot retroactively restore independence.
- The report states which family it used.

## 6. Configuration example

TOML is parsed with the stdlib `tomllib` into frozen dataclasses with strict
validation (ADR-004). The upstream reference run is:

```toml
[dataset]
version_dir = "data/processed/upstream-prices/91e9e35"   # verified before scan
[execution]
lag = 0                      # exploratory parity only; prospective study uses lag = 1
cost_bps = 0
cash_rate = 0.03
initial_position = "flat"
[universe]
signal = ["SPY", "IEF", "TLT"]
trade  = ["SPY"]
pairing = "cross"
[[features]]
name = "fast"
source = "price"
primitive = "sma"
params = { window = "1" }
[[features]]
name = "slow"
source = "price"
primitive = "sma"
params = { window = "2:200" }
[signal]
constructor = "ratio_minus_one"
inputs = ["fast", "slow"]
[rule]
kind = "binary"
threshold = [0.0]
up_weight = 1.0
down_weight = 0.0
[inference]
suite = ["effective_n", "psr_dsr", "maxstat", "eb"] # upstream parity diagnostics
simulations = 20000
seed = 12345
```

This configuration has `3 × 1 × 199 × 1 = 597` candidate signal rules **for
one trade asset**. M1 verified from the pinned source that SPY is the traded
asset. A three-trade-asset run has
1,791 candidate/trade rows. The previous example (`1:10`, `20:200:10`, three
signal and three trade assets) had 1,710 rows and could not verify the stated
597-candidate result.

A multi-feature generalization over a set of candidate features:

```toml
[feature_sets]
pool = ["trend", "carry", "vol_regime"]   # each a named feature+signal+rule block
sizes = [1, 2]
combine = ["all", "vote", "mean_position"]
```

The upstream grammar keeps working through the compat subcommand:
`griddy xma "[SPY IEF TLT]" 1 2:200 --trade SPY --terse --deflate`.
The exact worked-example command and source vintage are recorded in
`docs/UPSTREAM_CAPTURE.md`.

## 7. Milestones

The sizes are rough, for a solo developer working with an agent. Each milestone
ends with `make check` green, an updated `PROJECT_MEMORY.md` if durable facts
changed, and the adversarial review from
`templates/ADVERSARIAL_CODE_ARCHITECTURE_REVIEW.md` at M3, M6, and M8.

### M0 — Repository bootstrap (S)

**Tasks**
- Generate the repository from a clean checkout of the pinned template's
  `python-data-quant` starter and use the approved project name `griddy`.
- Complete `checklists/REPOSITORY_SETUP.md`: local git identity, `joshuamyers22`
  auth, origin, branch protection, signed commits, and Actions permissions.
- Commit this plan, the brief, and the SAP.
- Write ADR-001 through ADR-004.

**Exit criteria**
- The generated skeleton passes `make check` in CI.

### M1 — Upstream capture harness (S)

Completed 2026-09-25. See `docs/UPSTREAM_CAPTURE.md` for the pinned command,
sample vintage, local vendor reference, synthetic fixture matrix, hashes, and
double-capture result.

**Tasks**
- Write `tools/capture_upstream.py`. It checks out upstream at the pinned SHA
  into ignored `.work/`, installs its unpinned deps into a *locked* side
  environment, imports `xma` modules directly, and serializes row dicts,
  deflation outputs, and per-candidate returns to JSON/Parquet golden fixtures
  with a manifest of hashes.
- Verify the published 597-candidate example's exact command, trade asset,
  sample vintage, and count against the pinned source. Keep any mismatch open
  instead of changing the oracle to fit the plan.
- Build a fixture matrix covering:
  - single and multi signal/trade;
  - thresholds;
  - lag 0/1/2;
  - cost 0 and >0;
  - `down_pos` ∈ {0, 0.5, −1};
  - down symbol;
  - `--average`;
  - `--annual`;
  - `--deflate`, including the 597-candidate reference run;
  - an asynchronous-calendar case (SPY vs IEF pre-2002).
- Sample-data handling follows the M1 decision for Q3: synthetic CI fixtures,
  with vendor-derived input and captures kept local and ignored.

**Exit criteria**
- Synthetic fixtures are reproducible: a second capture yields identical content
  hashes. Vendor-derived fixtures require a licensing decision and stay out of
  Git and CI until redistribution and CI access are explicitly permitted.

### M2 — Walking skeleton (S)

**Tasks**
- Strict ingest of the upstream-format CSV and publication as a versioned
  Parquet dataset.
- A reference engine for one SMA-crossover candidate: lag, cost, cash.
- Core metrics.
- Result Parquet and run manifest.
- CLI `run` with a minimal TOML config.

**Exit criteria**
- One golden candidate matches upstream to 1e-12.

### M3 — Faithful recreation (L)

**Tasks**
- Block kernel.
- Common-window policy.
- Down asset and `down_pos`.
- Multi signal/trade.
- Average system (`cost_basis = aggregated`).
- Annual table and best selection.
- Crossover listing.
- Full deflation suite port (EffN-B/G/max, PSR, DSR, sr_minus_sr0, Max-p,
  EB, Galwey decomposition).
- `xma` compat subcommand.
- Text report matching upstream's tables.
- Divergence-register tests D1–D17.

**Exit criteria**
- The whole fixture matrix passes.
- The source-verified 597-candidate reference reproduces every printed figure
  to printed precision when the licensed input is available. Synthetic parity
  and divergence fixtures remain mandatory in CI.
- Reference and block engines are equivalent under Hypothesis property tests
  (random series, gaps, NaNs, parameters).
- Adversarial review #1.

### M4 — Generalized search space (M)

**Tasks**
- Feature registry and primitives, each with a scalar reference, bank
  implementation, and causality test.
- Signal constructors, rules, and constraints.
- Canonical candidate IDs.
- `plan` dry run with ceilings.
- Frequency-derived annualization and `rf` series.
- Result schema with dynamic parameter columns.
- Re-express the MA crossover as pure config and delete any MA-specific code
  path.

**Exit criteria**
- The config-expressed MA family reproduces the M3 results bit-for-bit.
- A non-price feature study (e.g., yield-spread level with a sign-agnostic
  `difference` signal) runs end to end on a synthetic fixture with known
  answers.

### M5 — Feature sets, panels, and arbitrary datasets (M)

**Tasks**
- The `feature_sets` axis and combiners.
- Per-entity panel evaluation and an equal-weight entity portfolio.
- Feature-column datasets (non-price) with `available_at` enforcement.
- Calendar/timezone guard for cross-calendar pairs.
- Data-quality report.
- Optional yfinance `fetch` → versioned dataset.

**Exit criteria**
- Known-answer tests for each combiner.
- The causality property test passes for every primitive × combiner (perturb
  data after *t* → no change to position ≤ *t + lag*).
- A two-dataset demo: the upstream prices plus one synthetic multi-feature
  panel.

### M6 — Selection, assessment, and scalable inference (L)

**Tasks**
- Splits: holdout, and expanding/rolling walk-forward with purge/embargo.
- Selection criteria: Sharpe, DSR, EB-shrunk Sharpe.
- Out-of-sample returns of the *selection procedure* are retained.
- CSCV/PBO.
- Stationary bootstrap SPA and Romano–Wolf.
- Holm/BHY on PSR p-values.
- MinTRL.
- Lo/HAC-adjusted Sharpe SE.
- Gram-side eigenvalues and Zᵀg simulation.
- Accurate E[max].
- Trial ledger with cumulative-family inference only for compatible, aligned
  hypotheses; otherwise disclose the cumulative search history without a joint
  p-value.
- A feasibility gate for the bootstrap and stepdown algorithms using bounded
  return storage and a declared maximum hypothesis family. No incomplete or
  approximate output is labeled as exact familywise inference.

**Exit criteria**
- **Calibration study** (seeded, retained):
  - Under a global null (paired candidate/benchmark streams, several serial and
    cross-correlation structures, M up to the measured feasible family size),
    the familywise rejection rates of Max-p, SPA, and Romano–Wolf are checked
    separately against nominal 5%, with predeclared replication count and
    Monte Carlo interval. Any failed method is withheld from confirmatory use.
  - DSR's false-positive rate is reported.
  - Under planted-signal alternatives, power is reported.
- Algebraically comparable dense and chunked computations agree on M ≤ 2,000;
  different test statistics are not presented as equivalent.
- Adversarial review #2.

### M7 — Scale and performance (M)

**Tasks**
- A benchmark suite with retained thresholds (`templates/PERFORMANCE_EXPERIMENT.md`):
  - 597 × 5,878 (reference);
  - 10k × 8.5k single asset;
  - 100k × 8.5k search and core metrics only, with inference gated separately;
  - 1k candidates × 500 entities panel.
- Memory-budget block sizing.
- Process-pool parallelism.
- Unique-stream dedup.
- Numba decision recorded (ADR-005).

**Exit criteria (initial targets, to be confirmed by benchmark and ratified in ADR)**
- 10k × 8.5k search + core metrics: ≤ 30 s.
- Inference at 10k: ≤ 60 s.
- Peak RSS ≤ 4 GB for the declared search and supported inference sizes,
  measured on a documented host; a 100k × 8.5k float64 return matrix alone is
  6.8 GB and cannot be materialized under that ceiling.
- The 100k search completes within its separately declared time and disk budget;
  no 100k exact-inference claim is made without a measured algorithm and gate.

### M8 — Reporting, docs, and release (M)

**Tasks**
- Markdown/text reports, including a per-axis redundancy table for any N-D
  grid.
- File-based plots: equity curves, heatmaps of metric by two chosen axes, and
  the SR distribution vs the null max.
- Docs following `SCIENTIFIC_PYTHON_DOCUMENTATION_GUIDE.md`:
  - a tutorial that reproduces `INTERPRETING_DEFLATION.md` end to end;
  - a "writing a feature primitive" guide;
  - an inference interpretation guide with limitations.
- `checklists/RELEASE_READINESS.md`.
- Tag `v0.1.0` with SBOM.

**Exit criteria**
- Adversarial review #3 is closed.
- The release gate passes.

**Optional v1.1:** hysteresis rule (sequential kernel), Harvey–Liu haircut,
gambit export of the selected candidate for event-driven confirmation
(research-to-production parity), and cross-sectional ranking rules (v2
scoping).

## 8. Verification strategy

| Layer | Evidence |
|---|---|
| Parity | Golden fixtures from pinned upstream. Divergence-register delta tests. |
| Equivalence | Reference engine vs block kernel. Hypothesis property tests with exact position equality and a 1e-12 return tolerance. Tie-margin reporting. |
| Causality | A generic perturb-the-future property test for every primitive, constructor, rule, and combiner. `available_at` violation tests. |
| Numerical | E[max] vs high-precision references. Rolling-stat stability on adversarial magnitudes (1e-8 to 1e8, long series). Gram vs dense eigenvalues. |
| Statistical | Null-calibration and planted-signal power simulations with retained seeds and artifacts. |
| Reproducibility | Identical canonical payload and result hashes across two runs and worker counts; timestamps and host metadata may differ. |
| Performance | Retained benchmarks with thresholds in CI (reduced size) and on a documented host (full size). |
| Quality gate | Ruff, Pyright strict, tests, license check, dependency audit (archetype `make check`). |

## 9. ADR backlog

| ADR | Decision | Proposed choice |
|---|---|---|
| 001 | License and upstream attribution | Keep the proprietary template license for new code. Add `THIRD_PARTY_NOTICES.md` with upstream's MIT notice for ported portions (M3 deflation and kernel logic). Alternative: license the whole project MIT (Q2). |
| 002 | Parity approach | Golden fixtures + divergence register. No legacy behavior flags in production code. |
| 003 | Numeric representation | Float64 end to end in the kernel. Strict string ingest converted at a declared boundary. Decimal is not used for return series (documented departure from the archetype's decimal-money default, since these are research returns, not ledgers). |
| 004 | Configuration | TOML + frozen dataclasses with strict validation. No pydantic unless validation complexity demands it. |
| 005 | Acceleration | NumPy first. Numba only with benchmark evidence (M7). |
| 006 | Inference defaults | Compatible hypothesis-family rule, PSR SE variant, bootstrap block-length rule, and primary selection criterion. |
| 007 | Timing default | `lag = 1` for pre-specified conclusions. `lag = 0` allowed and labeled. |
| 008 | Dataset contract | Long panel, roles, `available_at`, frequency/calendar declaration, and the yfinance extra boundary. |

## 10. Risks

| Risk | Mitigation |
|---|---|
| Combinatorial explosion from feature sets × parameters | Exact counting, `plan` dry run, hard ceilings, dedup, seeded subsampling recorded in the ledger. |
| Multiple-testing diagnostics become decorative ("DSR says fine") | A frozen SAP for any prospective claim. Selection and assessment separated. Full search history disclosed; joint inference uses only compatible trials. Calibration evidence. Reports label retrospective OOS and familywise diagnostics honestly. |
| Look-ahead through features (full-sample normalization, misaligned calendars, revised data) | The primitive causality contract plus property tests, `available_at`, the calendar guard, and immutable dataset versions. |
| Float ties flip threshold decisions between engines | Stable rolling algorithms, exact position equality tests, tie-margin reporting. |
| Parity drift from unpinned upstream deps (pandas/numpy version effects) | A locked capture environment recorded in the fixture manifest. |
| Vendor data licensing (Yahoo) | No vendor data in Git or default CI. Hash-verified local capture only after source terms are reviewed; synthetic fixtures in CI. |
| Historical final window already inspected | The upstream full-sample result makes the 2020–2026 period exploratory for this study. A new final window begins only after the study protocol is frozen and requires fresh, uninspected data or a different independent source. |
| Invalid cross-run familywise claim | Ledger records all attempts but combines p-values/tests only for compatible aligned hypotheses and a prospectively declared family. |
| Overlap with `gambit` | A clear boundary: vectorized screening here, event-driven confirmation there. The export adapter is optional and later. |

## 11. Acceptance evidence (v1)

| Requirement | Verification | Status |
|---|---|---|
| Reproduces upstream reference run and fixture matrix | M3 parity suite | Planned |
| MA family is pure config, bit-identical to M3 | M4 regression test | Planned |
| Any causal feature/set/dataset runs through the same engine | M4/M5 known-answer and causality tests | Planned |
| Familywise tests calibrated under the null | M6 calibration artifact | Planned |
| Scale targets met within the memory budget | M7 benchmark artifacts | Planned |
| Every result bound to a deterministic canonical evidence payload | Reproducibility test | Planned |

## 12. Open decisions

| # | Question | Needed by | Recommendation |
|---|---|---|---|
| Q1 | Project name | M0 | Decided: `griddy` (package `griddy`). |
| Q2 | License | M0 | Decided: proprietary new code with upstream MIT notice; see ADR-001. |
| Q3 | Upstream `prices.csv` (Yahoo-derived): local restricted parity input, or permissioned CI artifact | M1 | Decided: synthetic CI fixtures; upstream sample and derived captures remain local and ignored pending source-terms review. See `docs/UPSTREAM_CAPTURE.md`. |
| Q4 | Default search ceiling and memory budget | M4 | 250k candidates, 4 GB. |
| Q5 | Primary selection criterion for walk-forward | M6 | EB-shrunk Sharpe, with Sharpe and DSR as sensitivity analyses. |
| Q6 | Include cross-sectional ranking rules in v1? | M5 | No (v2). |
