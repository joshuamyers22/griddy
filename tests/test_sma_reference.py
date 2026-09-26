"""Golden and hand-calculated checks for one SMA crossover candidate."""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl

from griddy.dataset import (
    DatasetContractError,
    scan_verified_dataset,
    upstream_adjusted_close_contract,
)
from griddy.engine.reference import (
    ReferenceExecution,
    SmaCrossoverCandidate,
    run_sma_crossover,
)
from griddy.upstream_prices import (
    ingest_upstream_prices,
    load_upstream_prices_csv,
    publish_upstream_prices,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "upstream"


class SmaReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prices = load_upstream_prices_csv(
            FIXTURES / "synthetic_prices.csv",
            quote_unit="synthetic",
            calendar="synthetic-weekdays",
        ).frame

    def test_golden_daily_returns_lags_and_costs(self) -> None:
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
                    self.prices.lazy(),
                    candidate,
                    ReferenceExecution(
                        periods_per_year=252,
                        cash_rate=0.03,
                        lag=lag,
                        cost_bps=cost_bps,
                    ),
                ).frame
                golden = pl.read_parquet(FIXTURES / "golden" / f"{name}.parquet")
                golden = golden.filter(pl.col("row_id") == "r0000")
                self.assertEqual(
                    result["event_date"].to_list(), golden["date"].to_list()
                )
                joined = result.join(golden, left_on="event_date", right_on="date")
                error = joined.select(
                    (pl.col("net_return") - pl.col("daily_return")).abs().max()
                ).item()
                self.assertLessEqual(error, 1e-12)
                if name == "cost_positive":
                    self.assertEqual(result["transaction_cost"][0], 0.001)

    def test_verified_parquet_scan_matches_in_memory_result(self) -> None:
        prices = load_upstream_prices_csv(
            FIXTURES / "synthetic_prices.csv",
            quote_unit="synthetic",
            calendar="synthetic-weekdays",
        )
        candidate = SmaCrossoverCandidate("SPY", "SPY", fast=2, slow=8)
        execution = ReferenceExecution(periods_per_year=252, cash_rate=0.03, lag=0)
        with tempfile.TemporaryDirectory() as temporary:
            dataset = publish_upstream_prices(
                prices,
                Path(temporary),
                dataset_version="reference-v1",
                source_id="synthetic/m1-prices",
                code_revision="test",
                created_at_utc=datetime(2026, 9, 26, tzinfo=UTC),
            )
            scanned = scan_verified_dataset(
                dataset, contract=upstream_adjusted_close_contract()
            )
            from_parquet = run_sma_crossover(scanned, candidate, execution)
        from_memory = run_sma_crossover(prices.frame, candidate, execution)
        self.assertTrue(from_parquet.frame.equals(from_memory.frame))

    def test_cross_instrument_calendar_matches_golden(self) -> None:
        result = run_sma_crossover(
            self.prices,
            SmaCrossoverCandidate("SPY", "IEF", fast=2, slow=8),
            ReferenceExecution(periods_per_year=252, cash_rate=0.03, lag=0),
        ).frame.filter(pl.col("event_date") <= date(2002, 9, 1))
        golden = pl.read_parquet(FIXTURES / "golden" / "async_calendar.parquet").filter(
            pl.col("row_id") == "r0000"
        )
        self.assertEqual(result["event_date"].to_list(), golden["date"].to_list())
        joined = result.join(golden, left_on="event_date", right_on="date")
        error = joined.select(
            (pl.col("net_return") - pl.col("daily_return")).abs().max()
        ).item()
        self.assertLessEqual(error, 1e-12)

    def test_strict_tie_cash_lag_and_turnover(self) -> None:
        wide = pl.DataFrame(
            {
                "Date": [
                    "2026-01-01",
                    "2026-01-02",
                    "2026-01-03",
                    "2026-01-04",
                    "2026-01-05",
                ],
                "SPY": [100.0, 100.0, 110.0, 100.0, 100.0],
            }
        )
        prices = ingest_upstream_prices(
            wide, quote_unit="synthetic", calendar="synthetic-sessions"
        ).frame
        candidate = SmaCrossoverCandidate("SPY", "SPY", fast=1, slow=2)
        cash_return = 1.252 ** (1 / 252) - 1
        execution = ReferenceExecution(
            periods_per_year=252, cash_rate=0.252, lag=0, cost_bps=10
        )
        result = run_sma_crossover(prices, candidate, execution).frame
        self.assertEqual(result["up_state"].to_list(), [False, True, False])
        self.assertEqual(result["trade_weight"].to_list(), [0.0, 1.0, 0.0])
        self.assertEqual(result["turnover"].to_list(), [0.0, 1.0, 1.0])
        self.assertEqual(result["transaction_cost"].to_list(), [0.0, 0.001, 0.001])
        expected = [cash_return, 100 / 110 - 1 - 0.001, cash_return - 0.001]
        for actual, wanted in zip(
            result["net_return"].to_list(), expected, strict=True
        ):
            self.assertAlmostEqual(actual, wanted, places=15)
        delayed = run_sma_crossover(
            prices,
            candidate,
            ReferenceExecution(periods_per_year=252, cash_rate=0.0, lag=1),
        ).frame
        self.assertEqual(delayed["up_state"].to_list(), [False, True])

    def test_invalid_configuration_and_short_history(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive integers"):
            SmaCrossoverCandidate("SPY", "SPY", fast=0, slow=8)
        with self.assertRaisesRegex(ValueError, "finite"):
            SmaCrossoverCandidate("SPY", "SPY", fast=2, slow=8, threshold=float("nan"))
        with self.assertRaisesRegex(ValueError, "nonnegative integer"):
            ReferenceExecution(periods_per_year=252, cash_rate=0.03, lag=-1)
        with self.assertRaisesRegex(ValueError, "finite and nonnegative"):
            ReferenceExecution(periods_per_year=252, cash_rate=0.03, cost_bps=-1)
        candidate = SmaCrossoverCandidate("SPY", "SPY", fast=2, slow=8)
        execution = ReferenceExecution(periods_per_year=252, cash_rate=0.03)
        with self.assertRaisesRegex(DatasetContractError, "not enough overlapping"):
            run_sma_crossover(self.prices.head(8), candidate, execution)
        with self.assertRaisesRegex(DatasetContractError, "must exist"):
            run_sma_crossover(
                self.prices,
                SmaCrossoverCandidate("NOPE", "SPY", fast=2, slow=8),
                execution,
            )
        extreme = ingest_upstream_prices(
            pl.DataFrame(
                {"Date": ["2026-01-01", "2026-01-02"], "SPY": ["1e-308", "1e308"]}
            ),
            quote_unit="synthetic",
            calendar="synthetic-sessions",
        ).frame
        with self.assertRaisesRegex(DatasetContractError, "trade return is not finite"):
            run_sma_crossover(
                extreme,
                SmaCrossoverCandidate("SPY", "SPY", fast=1, slow=1),
                ReferenceExecution(periods_per_year=252, cash_rate=0.03, lag=0),
            )


if __name__ == "__main__":
    unittest.main()
