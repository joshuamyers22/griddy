"""Golden and known-answer checks for single-candidate core metrics."""

from __future__ import annotations

import json
import math
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

import polars as pl

from griddy.dataset import DatasetContractError
from griddy.engine.metrics import calculate_core_metrics
from griddy.engine.reference import (
    ReferenceExecution,
    SmaCrossoverCandidate,
    run_sma_crossover,
)
from griddy.upstream_prices import ingest_upstream_prices, load_upstream_prices_csv

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "upstream"


def _candidate_on_prices(
    values: list[float], *, threshold: float, cost_bps: float = 0.0
):
    wide = pl.DataFrame(
        {
            "Date": [f"2026-01-{index:02d}" for index in range(1, len(values) + 1)],
            "SPY": values,
        }
    )
    prices = ingest_upstream_prices(
        wide, quote_unit="synthetic", calendar="synthetic-sessions"
    ).frame
    return run_sma_crossover(
        prices,
        SmaCrossoverCandidate("SPY", "SPY", fast=1, slow=1, threshold=threshold),
        ReferenceExecution(
            periods_per_year=252, cash_rate=0.0, lag=0, cost_bps=cost_bps
        ),
    )


class CoreMetricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prices = load_upstream_prices_csv(
            FIXTURES / "synthetic_prices.csv",
            quote_unit="synthetic",
            calendar="synthetic-weekdays",
        ).frame

    def test_strategy_and_benchmark_match_golden_rows(self) -> None:
        candidate = SmaCrossoverCandidate("SPY", "SPY", fast=2, slow=8)
        cases = (
            ("single", 0, 0.0),
            ("lag_1", 1, 0.0),
            ("lag_2", 2, 0.0),
            ("cost_positive", 0, 10.0),
        )
        for name, lag, cost_bps in cases:
            with self.subTest(name=name):
                result = run_sma_crossover(
                    self.prices,
                    candidate,
                    ReferenceExecution(
                        periods_per_year=252,
                        cash_rate=0.03,
                        lag=lag,
                        cost_bps=cost_bps,
                    ),
                )
                actual = calculate_core_metrics(result)
                golden = json.loads((FIXTURES / "golden" / f"{name}.json").read_text())[
                    "rows"
                ]
                strategy, benchmark = golden
                self.assertEqual(actual.start, date.fromisoformat(strategy["start"]))
                self.assertEqual(actual.end, date.fromisoformat(strategy["end"]))
                self.assertEqual(actual.observations, strategy["trading_days"])
                self.assertTrue(
                    math.isclose(actual.years, strategy["years"], abs_tol=1e-12)
                )
                for summary, expected in (
                    (actual.strategy, strategy),
                    (actual.buy_and_hold, benchmark),
                ):
                    for field, golden_field in (
                        ("cagr", "return"),
                        ("annualized_volatility", "volatility"),
                        ("sharpe", "sharpe"),
                        ("beta", "beta"),
                        ("jensen_alpha", "alpha"),
                    ):
                        observed = getattr(summary, field)
                        self.assertIsNotNone(observed)
                        self.assertTrue(
                            math.isclose(
                                observed,
                                expected[golden_field],
                                rel_tol=1e-12,
                                abs_tol=1e-12,
                            ),
                            f"{name} {field}: {observed} != {expected[golden_field]}",
                        )
                self.assertTrue(
                    math.isclose(
                        actual.changes_per_year,
                        strategy["trades_per_year"],
                        rel_tol=1e-12,
                    )
                )
                self.assertTrue(
                    math.isclose(
                        actual.average_trade_weight,
                        strategy["avg_position"],
                        abs_tol=1e-12,
                    )
                )
                self.assertTrue(
                    math.isclose(
                        actual.average_cash_weight,
                        strategy["cash_weight"],
                        abs_tol=1e-12,
                    )
                )
                self.assertEqual(
                    actual.total_transaction_cost,
                    math.fsum(result.frame["transaction_cost"].to_list()),
                )

    def test_first_loss_counts_in_drawdown_and_entry_counts_as_change(self) -> None:
        result = _candidate_on_prices([100.0, 90.0, 108.0], threshold=-0.5)
        metrics = calculate_core_metrics(result)
        self.assertEqual(metrics.observations, 2)
        drawdown = metrics.strategy.max_drawdown
        total_return = metrics.strategy.total_return
        assert drawdown is not None and total_return is not None
        self.assertAlmostEqual(drawdown, -0.1)
        upstream_style_drawdown = min(0.9 / 0.9 - 1, 1.08 / 1.08 - 1)
        self.assertEqual(upstream_style_drawdown, 0.0)
        self.assertTrue(math.isclose(total_return, 0.08, abs_tol=1e-15))
        self.assertEqual(metrics.strategy.beta, 1.0)
        self.assertEqual(metrics.strategy.jensen_alpha, 0.0)
        self.assertEqual(metrics.position_changes, 1)
        self.assertEqual(metrics.changes_per_year, 126.0)
        self.assertEqual(metrics.total_turnover, 1.0)
        self.assertEqual(metrics.average_trade_weight, 1.0)
        self.assertEqual(metrics.average_cash_weight, 0.0)

    def test_undefined_zero_variance_short_sample_and_bankruptcy(self) -> None:
        flat = calculate_core_metrics(
            _candidate_on_prices([100.0, 100.0, 100.0], threshold=0.0)
        )
        self.assertEqual(flat.strategy.total_return, 0.0)
        self.assertEqual(flat.strategy.max_drawdown, 0.0)
        self.assertEqual(flat.strategy.annualized_volatility, 0.0)
        self.assertIsNone(flat.strategy.sharpe)
        self.assertIsNone(flat.strategy.beta)
        self.assertIsNone(flat.strategy.jensen_alpha)
        self.assertIsNone(flat.buy_and_hold.beta)

        one = calculate_core_metrics(
            _candidate_on_prices([100.0, 90.0], threshold=-0.5)
        )
        self.assertIsNone(one.strategy.annualized_volatility)
        self.assertIsNone(one.strategy.sharpe)
        self.assertIsNone(one.strategy.beta)

        bankrupt = calculate_core_metrics(
            _candidate_on_prices([100.0, 90.0], threshold=-0.5, cost_bps=15_000)
        )
        self.assertIsNone(bankrupt.strategy.total_return)
        self.assertIsNone(bankrupt.strategy.cagr)
        self.assertIsNone(bankrupt.strategy.max_drawdown)

        huge = calculate_core_metrics(
            _candidate_on_prices([1.0, 1e308, 1e308], threshold=-0.5)
        )
        self.assertIsNone(huge.strategy.cagr)
        self.assertIsNone(huge.strategy.annualized_volatility)
        self.assertIsNone(huge.strategy.sharpe)

    def test_rejects_malformed_reference_result(self) -> None:
        result = _candidate_on_prices([100.0, 90.0, 108.0], threshold=-0.5)
        with self.assertRaisesRegex(DatasetContractError, "dates must increase"):
            calculate_core_metrics(replace(result, frame=result.frame.reverse()))
        bad = result.frame.with_columns(pl.lit(float("nan")).alias("net_return"))
        with self.assertRaisesRegex(DatasetContractError, "non-finite"):
            calculate_core_metrics(replace(result, frame=bad))


if __name__ == "__main__":
    unittest.main()
