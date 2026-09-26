# Single-candidate SMA reference engine

`griddy.engine.reference.run_sma_crossover` evaluates one adjusted-close SMA
ratio rule using Polars input. Pass the frame returned by
`load_upstream_prices_csv` or a verified lazy scan of a published dataset. The
runner revalidates the adjusted-close contract; pandas is available only through
the separate optional input adapter before this boundary.

```python
from pathlib import Path

from griddy.dataset import scan_verified_dataset, upstream_adjusted_close_contract
from griddy.engine.metrics import calculate_core_metrics
from griddy.engine.reference import (
    ReferenceExecution,
    SmaCrossoverCandidate,
    run_sma_crossover,
)

prices = scan_verified_dataset(
    Path(".work/processed/synthetic-m2-v1"),
    contract=upstream_adjusted_close_contract(),
)
result = run_sma_crossover(
    prices,
    SmaCrossoverCandidate("SPY", "SPY", fast=2, slow=8),
    ReferenceExecution(periods_per_year=252, cash_rate=0.03, lag=1, cost_bps=5),
)
daily = result.frame
metrics = calculate_core_metrics(result)
```

The fast and slow simple moving averages use the signal instrument's own full
date history. The up state requires `fast / slow - 1 > threshold`; equality is
down. Up holds the traded asset at weight 1, and down holds cash at weight 1.
Signals and trade prices are aligned on their common session dates without
filling prices. A result row dated `t` reports the return from the previous
common close to close `t`. It uses the signal observed `1 + lag` common dates
before `t`. Lag defaults to 1; lag 0 reproduces upstream's same-close timing and
is retrospective parity, not evidence that such an order was executable.

`periods_per_year` is an explicit caller declaration. Cash earns
`(1 + cash_rate) ** (1 / periods_per_year) - 1` per common return period. Trading
cost is `cost_bps / 10_000 * abs(weight - previous_weight)`. The initial weight
is flat, so an entry on the first evaluated row pays its cost. Every row records
the signal date and deviation, weights, asset and cash returns, turnover, cost,
and net return. The result also carries the candidate and execution settings.

This M2 reference supports one long-or-cash candidate. The
[core metric contract](CORE_METRICS.md) summarizes its returns. Result Parquet,
run manifest, and CLI are later M2 tasks. Down-state weights, a down
asset, common-family windows, and the block engine are later M3 work. The
golden tests compare every daily return for the pinned synthetic lag and cost
cases to 1e-12; the asynchronous SPY/IEF case checks calendar alignment.
