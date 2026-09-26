# M1 upstream capture

The capture harness is [`tools/capture_upstream.py`](../tools/capture_upstream.py).
It checks out `vivek-v-rao/moving-average-systems` at
`91e9e35a9eca36d314138302fb86075f05cb71c0` into ignored `.work/upstream/`,
checks that the documented reference command is present in the pinned source,
and runs imported `xma` modules with a separate Python 3.12 environment. The
environment is installed from [`tools/upstream-capture.lock`](../tools/upstream-capture.lock),
which resolves upstream's unpinned NumPy and pandas requirements plus PyArrow
for fixture serialization. The lock includes package hashes. The capture uses
NumPy 2.5.3, pandas 3.0.6, and PyArrow 25.0.1.

## Synthetic oracle committed to Git

Run `uv run python tools/capture_upstream.py --mode synthetic` to regenerate
[`tests/fixtures/upstream/`](../tests/fixtures/upstream/manifest.json). This
creates an independent synthetic price CSV, row dictionaries and deflation
diagnostics as canonical JSON, and per-row daily returns as Parquet. The
manifest records the upstream commit, dependency-lock hash, input hash, dates,
environment versions, candidate counts, and every output hash. The synthetic
input SHA-256 is
`7b83c64f5b7da222fbbb3bfa656d840e0062bfa248e73c7923e92aa536872595`.

The 17 cases cover single and multiple signal/trade assets, three thresholds,
lags 0/1/2, zero and positive cost, down positions 0/0.5/−1, a down asset,
average exposure, annual output, deflation, and a 597-candidate grid. The
asynchronous-calendar case has synthetic SPY prices in 2001 while IEF starts
in 2002; its common-window returns begin only after both series are available.
Two consecutive captures produced identical SHA-256 hashes for all 36 files.
CI verifies fixture hashes, counts, key cases, and Parquet shape without
downloading upstream or installing the side environment.

## Published 597-candidate example

The exact command printed by pinned upstream
`INTERPRETING_DEFLATION.md` is:

```text
python xma_signal.py [SPY IEF TLT] 1 2:200 --trade SPY --read-prices-file prices.csv --terse --time --best --deflate
```

The three assets supply signals; **SPY is the only traded asset**. This is
3 × 1 × 199 × 1 = 597 signal rules. The pinned upstream `prices.csv` has
SHA-256 `4739a0b4a630cddd69215db1ed5ede7480488ace3ade889e6b203973c316a63b`.
Its rows span 1993-01-29 through 2026-09-24; SPY begins on the first date,
and IEF and TLT first appear on 2002-07-30. The common backtest window is
2003-05-15 through 2026-09-24, with 5,878 observations.

The locked local capture matched the published figures to printed precision:

| Measure | Local capture | Published precision |
|---|---:|---:|
| MeanCorr | 0.665142545 | 0.665 |
| EffN-B | 200.575043 | 200.58 |
| EffN-G | 20.985285 | 20.99 |
| EffN-max | 6.946624 | 6.95 |
| Best rule | IEF 1/7, trade SPY | IEF 1/7, trade SPY |
| Best Sharpe | 0.714354 | 0.714 |
| DSR | 0.981671 | 0.982 |
| Max-p | 0.006850 | 0.0068 |

Run `uv run python tools/capture_upstream.py --mode vendor` for the vendor-derived
capture. Its input and all outputs stay in ignored `.work/` and are excluded
from Git and CI pending a source-terms review and permission to redistribute.
The published historical data are already inspected and support retrospective
parity only; they are not a fresh confirmatory assessment window.
