"""Readable single-candidate SMA crossover reference engine.

The input is the validated, session-dated adjusted-close dataset. A row dated
``t`` reports the return from the preceding common close to close ``t``.
Signals observed at a close affect that return after ``1 + lag`` common dates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import cast

import polars as pl

from griddy.dataset import (
    DatasetContractError,
    upstream_adjusted_close_contract,
    validate_dataset_frame,
)


@dataclass(frozen=True, slots=True)
class SmaCrossoverCandidate:
    signal_instrument: str
    trade_instrument: str
    fast: int
    slow: int
    threshold: float = 0.0

    def __post_init__(self) -> None:
        if not self.signal_instrument or not self.trade_instrument:
            raise ValueError("signal and trade instruments are required")
        if type(self.fast) is not int or type(self.slow) is not int:
            raise ValueError("SMA lengths must be positive integers")
        if self.fast < 1 or self.slow < 1:
            raise ValueError("SMA lengths must be positive integers")
        if not math.isfinite(self.threshold):
            raise ValueError("threshold must be finite")


@dataclass(frozen=True, slots=True)
class ReferenceExecution:
    """Lag and cost convention for a fully invested or cash position."""

    periods_per_year: int
    cash_rate: float
    lag: int = 1
    cost_bps: float = 0.0

    def __post_init__(self) -> None:
        if type(self.periods_per_year) is not int or self.periods_per_year < 1:
            raise ValueError("periods_per_year must be a positive integer")
        if type(self.lag) is not int or self.lag < 0:
            raise ValueError("lag must be a nonnegative integer")
        if not math.isfinite(self.cash_rate) or self.cash_rate <= -1:
            raise ValueError("cash_rate must be finite and greater than -1")
        if not math.isfinite(self.cost_bps) or self.cost_bps < 0:
            raise ValueError("cost_bps must be finite and nonnegative")


@dataclass(frozen=True, slots=True)
class SmaCrossoverResult:
    candidate: SmaCrossoverCandidate
    execution: ReferenceExecution
    frame: pl.DataFrame


RESULT_SCHEMA = pl.Schema(
    {
        "event_date": pl.Date,
        "signal_date": pl.Date,
        "signal_deviation": pl.Float64,
        "up_state": pl.Boolean,
        "trade_weight": pl.Float64,
        "cash_weight": pl.Float64,
        "trade_return": pl.Float64,
        "cash_return": pl.Float64,
        "turnover": pl.Float64,
        "transaction_cost": pl.Float64,
        "net_return": pl.Float64,
    }
)


def run_sma_crossover(
    prices: pl.DataFrame | pl.LazyFrame,
    candidate: SmaCrossoverCandidate,
    execution: ReferenceExecution,
) -> SmaCrossoverResult:
    """Evaluate one long-or-cash candidate on intersected session dates.

    Moving averages use the signal instrument's own full history. Trade returns
    use consecutive dates common to both instruments; no price is filled. The
    initial position is flat, so first-day entry turnover is charged in-window.
    This historical adjusted-close path makes no point-in-time availability claim.
    """
    frame = prices.collect() if isinstance(prices, pl.LazyFrame) else prices
    validate_dataset_frame(frame, upstream_adjusted_close_contract())
    signal = frame.filter(pl.col("instrument") == candidate.signal_instrument).sort(
        "event_date"
    )
    trade = frame.filter(pl.col("instrument") == candidate.trade_instrument).sort(
        "event_date"
    )
    if signal.is_empty() or trade.is_empty():
        raise DatasetContractError("signal and trade instruments must exist in prices")

    signal_dates = cast(list[date], signal["event_date"].to_list())
    signal_values = signal["adjusted_close"]
    ma_by_length = {
        length: signal_values.rolling_mean(window_size=length, min_samples=length)
        for length in {candidate.fast, candidate.slow}
    }
    fast_values = cast(list[float | None], ma_by_length[candidate.fast].to_list())
    slow_values = cast(list[float | None], ma_by_length[candidate.slow].to_list())
    states: dict[date, tuple[bool, float]] = {}
    for signal_date, fast, slow in zip(
        signal_dates, fast_values, slow_values, strict=True
    ):
        if fast is not None and slow is not None:
            if not math.isfinite(fast) or not math.isfinite(slow) or slow <= 0:
                raise DatasetContractError("SMA produced an invalid value")
            deviation = fast / slow - 1.0
            if not math.isfinite(deviation):
                raise DatasetContractError("SMA deviation is not finite")
            states[signal_date] = (deviation > candidate.threshold, deviation)

    trade_prices = dict(
        zip(
            cast(list[date], trade["event_date"].to_list()),
            cast(list[float], trade["adjusted_close"].to_list()),
            strict=True,
        )
    )
    common_dates = sorted(set(signal_dates) & trade_prices.keys())
    cash_return = (1.0 + execution.cash_rate) ** (
        1.0 / execution.periods_per_year
    ) - 1.0
    rows: list[dict[str, object]] = []
    previous_weight = 0.0
    for index in range(1 + execution.lag, len(common_dates)):
        signal_date = common_dates[index - 1 - execution.lag]
        state = states.get(signal_date)
        if state is None:
            continue
        up_state, deviation = state
        weight = 1.0 if up_state else 0.0
        event_date = common_dates[index]
        asset_return = (
            trade_prices[event_date] / trade_prices[common_dates[index - 1]] - 1.0
        )
        if not math.isfinite(asset_return):
            raise DatasetContractError("trade return is not finite")
        turnover = abs(weight - previous_weight)
        transaction_cost = execution.cost_bps * turnover / 10_000.0
        net_return = (
            weight * asset_return + (1.0 - weight) * cash_return - transaction_cost
        )
        if not math.isfinite(net_return):
            raise DatasetContractError("net return is not finite")
        rows.append(
            {
                "event_date": event_date,
                "signal_date": signal_date,
                "signal_deviation": deviation,
                "up_state": up_state,
                "trade_weight": weight,
                "cash_weight": 1.0 - weight,
                "trade_return": asset_return,
                "cash_return": cash_return,
                "turnover": turnover,
                "transaction_cost": transaction_cost,
                "net_return": net_return,
            }
        )
        previous_weight = weight
    if not rows:
        raise DatasetContractError(
            "not enough overlapping prices after SMA warmup and lag"
        )
    return SmaCrossoverResult(
        candidate=candidate,
        execution=execution,
        frame=pl.DataFrame(rows, schema=RESULT_SCHEMA),
    )
