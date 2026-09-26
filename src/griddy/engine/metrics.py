"""Core descriptive metrics for one aligned, net-of-cost candidate return path."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import cast

import polars as pl

from griddy.dataset import DatasetContractError

from .reference import RESULT_SCHEMA, SmaCrossoverResult


@dataclass(frozen=True, slots=True)
class ReturnMetrics:
    """Performance of a return stream on the candidate's evaluation dates."""

    total_return: float | None
    cagr: float | None
    annualized_volatility: float | None
    sharpe: float | None
    beta: float | None
    jensen_alpha: float | None
    max_drawdown: float | None


@dataclass(frozen=True, slots=True)
class CandidateMetrics:
    start: date
    end: date
    observations: int
    years: float
    strategy: ReturnMetrics
    buy_and_hold: ReturnMetrics
    position_changes: int
    changes_per_year: float
    average_trade_weight: float
    average_cash_weight: float
    total_turnover: float
    total_transaction_cost: float


def _finite_sum(values: list[float], name: str) -> float:
    try:
        total = math.fsum(values)
    except (OverflowError, ValueError) as error:
        raise DatasetContractError(
            f"{name} cannot be represented as float64"
        ) from error
    if not math.isfinite(total):
        raise DatasetContractError(f"{name} cannot be represented as float64")
    return total


def _mean(values: list[float]) -> float:
    try:
        total = math.fsum(values)
        if math.isfinite(total):
            return total / len(values)
    except (OverflowError, ValueError):
        pass
    # A finite mean can survive when the unscaled sum exceeds float64.
    return _finite_sum([value / len(values) for value in values], "metric mean")


def _wealth_metrics(
    returns: list[float], years: float
) -> tuple[float | None, float | None, float | None]:
    equity = 1.0
    peak = 1.0  # A first-period loss is a drawdown from the initial capital.
    worst_drawdown = 0.0
    for value in returns:
        if value < -1.0:
            return None, None, None
        equity *= 1.0 + value
        if not math.isfinite(equity):
            return None, None, None
        peak = max(peak, equity)
        worst_drawdown = min(worst_drawdown, equity / peak - 1.0)
    total_return = equity - 1.0
    if equity == 0.0:
        cagr = -1.0
    else:
        try:
            cagr = equity ** (1.0 / years) - 1.0
        except OverflowError:
            cagr = None
        if cagr is not None and not math.isfinite(cagr):
            cagr = None
    return total_return, cagr, worst_drawdown


def _sample_variance(values: list[float], mean: float) -> float | None:
    if len(values) < 2:
        return None
    try:
        squared = [(value - mean) ** 2 for value in values]
    except OverflowError:
        return None
    if not all(math.isfinite(value) for value in squared):
        return None
    try:
        variance = math.fsum(squared) / (len(values) - 1)
    except (OverflowError, ValueError):
        return None
    return variance if math.isfinite(variance) else None


def _return_metrics(
    returns: list[float],
    *,
    periods_per_year: int,
    cash_return: float,
    beta: float | None,
    jensen_alpha: float | None,
) -> ReturnMetrics:
    observations = len(returns)
    years = observations / periods_per_year
    total_return, cagr, max_drawdown = _wealth_metrics(returns, years)
    mean = _mean(returns)
    variance = _sample_variance(returns, mean)
    annualized_volatility = (
        math.sqrt(variance) * math.sqrt(periods_per_year)
        if variance is not None
        else None
    )
    if annualized_volatility is not None and not math.isfinite(annualized_volatility):
        annualized_volatility = None
    sharpe = (
        (mean - cash_return) * periods_per_year / annualized_volatility
        if annualized_volatility is not None and annualized_volatility > 0
        else None
    )
    if sharpe is not None and not math.isfinite(sharpe):
        sharpe = None
    return ReturnMetrics(
        total_return=total_return,
        cagr=cagr,
        annualized_volatility=annualized_volatility,
        sharpe=sharpe,
        beta=beta,
        jensen_alpha=jensen_alpha,
        max_drawdown=max_drawdown,
    )


def calculate_core_metrics(result: SmaCrossoverResult) -> CandidateMetrics:
    """Summarize the strategy and aligned traded-asset buy-and-hold baseline.

    Undefined quantities are ``None``: sample variance needs two returns,
    Sharpe needs positive volatility, and beta needs benchmark variance. A
    return below -100% makes equity-based metrics undefined. No trial selection,
    inference, or annual table is performed here.
    """
    frame = result.frame
    if frame.schema != RESULT_SCHEMA or frame.is_empty():
        raise DatasetContractError("invalid or empty reference result frame")
    if any(value != 0 for value in frame.null_count().row(0)):
        raise DatasetContractError("reference result contains nulls")
    dates = cast(list[date], frame["event_date"].to_list())
    if any(right <= left for left, right in zip(dates, dates[1:], strict=False)):
        raise DatasetContractError("reference result dates must increase")
    numeric_columns = (
        "signal_deviation",
        "trade_weight",
        "cash_weight",
        "trade_return",
        "cash_return",
        "turnover",
        "transaction_cost",
        "net_return",
    )
    if (
        frame.select(
            pl.any_horizontal(~pl.col(column).is_finite() for column in numeric_columns)
        )
        .to_series()
        .any()
    ):
        raise DatasetContractError("reference result contains non-finite numbers")

    returns = cast(list[float], frame["net_return"].to_list())
    benchmark = cast(list[float], frame["trade_return"].to_list())
    weights = cast(list[float], frame["trade_weight"].to_list())
    cash_weights = cast(list[float], frame["cash_weight"].to_list())
    turnover = cast(list[float], frame["turnover"].to_list())
    costs = cast(list[float], frame["transaction_cost"].to_list())
    observations = len(returns)
    periods_per_year = result.execution.periods_per_year
    years = observations / periods_per_year
    cash_return = (1.0 + result.execution.cash_rate) ** (1.0 / periods_per_year) - 1.0
    strategy_mean = _mean(returns)
    benchmark_mean = _mean(benchmark)
    benchmark_variance = _sample_variance(benchmark, benchmark_mean)
    if benchmark_variance is not None and benchmark_variance > 0:
        cross_products = [
            (strategy - strategy_mean) * (asset - benchmark_mean)
            for strategy, asset in zip(returns, benchmark, strict=True)
        ]
        if all(math.isfinite(value) for value in cross_products):
            try:
                covariance = math.fsum(cross_products) / (observations - 1)
                beta = covariance / benchmark_variance
                alpha = (
                    strategy_mean - cash_return - beta * (benchmark_mean - cash_return)
                ) * periods_per_year
                if not math.isfinite(beta) or not math.isfinite(alpha):
                    beta = alpha = None
            except (OverflowError, ValueError):
                beta = alpha = None
        else:
            beta = alpha = None
        benchmark_beta: float | None = 1.0
        benchmark_alpha: float | None = 0.0
    else:
        beta = alpha = benchmark_beta = benchmark_alpha = None

    position_changes = sum(value > 1e-12 for value in turnover)
    return CandidateMetrics(
        start=dates[0],
        end=dates[-1],
        observations=observations,
        years=years,
        strategy=_return_metrics(
            returns,
            periods_per_year=periods_per_year,
            cash_return=cash_return,
            beta=beta,
            jensen_alpha=alpha,
        ),
        buy_and_hold=_return_metrics(
            benchmark,
            periods_per_year=periods_per_year,
            cash_return=cash_return,
            beta=benchmark_beta,
            jensen_alpha=benchmark_alpha,
        ),
        position_changes=position_changes,
        changes_per_year=position_changes / years,
        average_trade_weight=_mean(weights),
        average_cash_weight=_mean(cash_weights),
        total_turnover=_finite_sum(turnover, "total turnover"),
        total_transaction_cost=_finite_sum(costs, "total transaction cost"),
    )
