# Core candidate metrics

`calculate_core_metrics(result)` summarizes the dated return stream from the
single-candidate [reference engine](REFERENCE_ENGINE.md). The strategy is net of
trading cost. Buy-and-hold uses the traded asset's returns on exactly the same
evaluation dates. The result records both summaries, the window, exposure,
position changes, turnover, and total transaction cost.

```python
from griddy.engine.metrics import calculate_core_metrics

metrics = calculate_core_metrics(result)
print(metrics.strategy.sharpe, metrics.buy_and_hold.sharpe)
```

For `n` evaluated returns and the caller's `periods_per_year = P`, years are
`n / P`. Total return compounds `(1 + r_t)`; CAGR is
`final_equity ** (1 / years) - 1`. Annualized volatility uses sample standard
deviation (`ddof = 1`) times `sqrt(P)`. Sharpe is the annualized mean return in
excess of the declared per-period cash return, divided by annualized
volatility. Beta is sample covariance of strategy and buy-and-hold returns
divided by the benchmark's sample variance. Jensen alpha annualizes the mean
strategy excess return minus beta times mean benchmark excess return.

Max drawdown starts from equity 1 before the first return. It therefore counts
a first-period loss, correcting upstream divergence D3. A position change is a
weight change greater than `1e-12`; the initial flat-to-invested entry counts.
Changes per year divide that count by `n / P`. Average trade and cash weights,
total absolute weight turnover, and total paid cost are calculated from the
same evaluated rows.

Undefined statistics are `None`: fewer than two returns have no sample
volatility; zero volatility has no Sharpe; zero benchmark variance has no beta
or Jensen alpha. A net return below -100% makes equity, CAGR, and drawdown
undefined. This descriptive summary does not perform selection or inference.
The pinned synthetic golden tests match upstream CAGR, volatility, Sharpe,
beta, alpha, exposure, and changes per year to 1e-12 for lag and cost cases.
