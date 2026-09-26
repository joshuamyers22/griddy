# griddy

`griddy` is a planned batch research tool for screening causal,
rule-based trading signals across declared feature sets and time-series
datasets. It will first reproduce the pinned `xma` moving-average search, then
generalize the search and its evidence. It does not place trades or serve live
signals.

**Status:** M0–M1 complete; M2 is in progress. Its upstream price ingest,
versioned Parquet publication, and single-candidate SMA reference engine are
implemented; core metrics, result files, and run CLI remain. The commands below
exercise the generated data/quant example; the `griddy` search engine and
`xma` compatibility command are M2–M6 work. Start with the
[project plan](PROJECT_PLAN.md), [brief](PROJECT_BRIEF.md),
[statistical analysis plan](STATISTICAL_ANALYSIS_PLAN.md),
and [adversarial plan review](ADVERSARIAL_PLAN_REVIEW.md). Consequential design
choices are recorded in the [ADR index](docs/adr/README.md).
The [upstream capture record](docs/UPSTREAM_CAPTURE.md) pins the M1 oracle.
The [Parquet dataset contract](docs/PARQUET_DATASETS.md) covers the M2 price input.
The [reference engine](docs/REFERENCE_ENGINE.md) covers single-candidate timing,
cost, and cash behavior.

```sh
make setup
make check
make build
uv run griddy data/example.csv
```

Publish and verify an immutable, contract-checked Parquet dataset:

```sh
uv run griddy-dataset publish data/example.csv data/processed \
  --dataset-version 2026-01-02.1 \
  --source-id fixture/example.csv \
  --revision "$(git rev-parse HEAD)" \
  --created-at-utc "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
uv run griddy-dataset verify data/processed/2026-01-02.1
```

The separate evidence command turns a pre-specified simple OLS run into a stable,
reviewable JSON artifact:

```sh
uv run griddy-regression data/regression-example.csv \
  --response return --predictor factor \
  --analysis-id factor-return-example \
  --analysis-plan templates/STATISTICAL_ANALYSIS_PLAN.md \
  --revision "$(git rev-parse HEAD)" \
  --evaluated-at-utc "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --sample-filters "none; complete synthetic fixture" \
  --validation-design "illustrative in-sample inference only" \
  --leakage-controls "synthetic fixture; no future-derived features" \
  --output build/regression-evidence.json
```

For temporal prediction, run executable expanding-window validation with explicit
feature and target availability timestamps:

```sh
uv run griddy-validate data/walk-forward-example.csv \
  --response return --predictor factor \
  --prediction-time prediction_time \
  --feature-available-at feature_available_at \
  --target-available-at target_available_at \
  --initial-test-index 5 --test-size 2 --step-size 2 \
  --analysis-id factor-walk-forward-example \
  --analysis-plan templates/STATISTICAL_ANALYSIS_PLAN.md \
  --revision "$(git rev-parse HEAD)" \
  --evaluated-at-utc "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --sample-filters "complete synthetic fixture" \
  --validation-design "non-overlapping expanding windows" \
  --leakage-controls "availability timestamps and strict label purging" \
  --output build/time-validation-evidence.json
```

Complete `PROJECT_BRIEF.md` before selecting architecture or adding dependencies.
Raw or restricted data is never committed. The included model uses explicit UTC
timestamps, units, decimal arithmetic, strict Polars CSV ingestion, and source
hashes. Schema inference is disabled at the trust boundary so numeric source text
cannot silently become binary floating point. Use Polars expressions and lazy
queries for tabular transformations; convert to domain values where precision or
business invariants require it.

Polars is the default dataframe library. Existing pandas price frames are
accepted through the optional input adapter in [ADR-009](docs/adr/ADR-009-polars-first-inputs.md).
Do not maintain parallel Polars and pandas implementations of the same
calculation.

Statsmodels is the default library for statistical inference, econometrics, time
series, and regression. `fit_simple_ols` demonstrates an explicit
Polars-to-NumPy-to-Statsmodels boundary, adds the intercept deliberately, rejects
missing/non-finite or degenerate samples, and defaults to HC3 robust covariance.
Choose the model, covariance estimator, diagnostics, multiple-testing policy,
and validation design from the research question—not from this example.
Complete `templates/STATISTICAL_ANALYSIS_PLAN.md` before consequential analysis.
Use `docs/STATISTICAL_LEARNING_POINT_OF_VIEW.md` to challenge the decision,
baseline, selection, leakage, stability, and serving design. It expresses
preferences, not deterministic rules; record sensible departures in the analysis
plan or an ADR.
For Bayesian regression implementation, use
`docs/BAYESIAN_REGRESSION_IMPLEMENTATION.md` and the applicable analysis-plan
fields. This guidance covers specification, priors, computation, and diagnostics;
the executable starter remains an OLS example and supplies no Bayesian estimator.
The evidence artifact binds the ordered design matrix and results to input and
analysis-plan hashes, code revision, evaluation time, and software versions. It
includes coefficient uncertainty, robust covariance choice, residual scale,
Durbin-Watson, condition number, and maximum Cook's distance. These diagnostics
surface review questions; they do not certify assumptions or replace time-aware
out-of-sample validation. See `docs/REGRESSION_EVIDENCE.md`.
The time-validation command rejects unordered timestamps, future features,
targets available at prediction time, overlapping test windows, and folds with
too few known labels. It purges labels unavailable before each test window,
refits both the model and training-mean baseline per fold, and retains every
out-of-sample prediction and aggregate comparison.

The Parquet publisher enforces exact Decimal/UTC schema, nullability, primary-key,
partition, sort, and domain invariants. Each immutable version has a deterministic
file layout and manifest covering source/revision/writer identity plus file hashes
and row counts. Verification precedes lazy scans. See
`docs/PARQUET_DATASETS.md` for compatibility and trust boundaries.

If this project develops a live or latency-sensitive path, complete
`templates/LATENCY_BUDGET.md`; keep offline research and production-path
correctness/replay evidence distinct.
