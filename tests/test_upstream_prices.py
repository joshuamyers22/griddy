"""Trust-boundary checks for M2 upstream price ingestion and publication."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import polars as pl

from griddy.dataset import (
    DatasetContractError,
    scan_verified_dataset,
    upstream_adjusted_close_contract,
    verify_dataset,
)
from griddy.upstream_prices import (
    ingest_upstream_prices,
    ingest_upstream_prices_pandas,
    load_upstream_prices_csv,
    publish_upstream_prices,
)

SYNTHETIC = (
    Path(__file__).resolve().parent / "fixtures" / "upstream" / "synthetic_prices.csv"
)


def ingest(frame: pl.DataFrame | pl.LazyFrame):
    return ingest_upstream_prices(
        frame, quote_unit="synthetic", calendar="synthetic-weekdays"
    )


class UpstreamPriceTests(unittest.TestCase):
    def test_polars_csv_publish_verify_and_missing_calendar(self) -> None:
        prices = load_upstream_prices_csv(
            SYNTHETIC, quote_unit="synthetic", calendar="synthetic-weekdays"
        )
        self.assertEqual(
            prices.source_sha256, hashlib.sha256(SYNTHETIC.read_bytes()).hexdigest()
        )
        self.assertEqual(prices.source_kind, "raw-csv")
        self.assertEqual(prices.input_dates, 858)
        self.assertEqual(prices.missing_by_symbol, {"SPY": 0, "IEF": 260, "TLT": 300})
        self.assertEqual(prices.frame.height, 2014)
        self.assertEqual(prices.frame.schema, upstream_adjusted_close_contract().schema)
        self.assertEqual(
            prices.frame.filter(pl.col("instrument") == "IEF")["event_date"].min(),
            date(2002, 1, 1),
        )
        self.assertEqual(
            prices.frame.filter(pl.col("event_date") < date(2002, 1, 1))
            .get_column("instrument")
            .unique()
            .to_list(),
            ["SPY"],
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = publish_upstream_prices(
                prices,
                root,
                dataset_version="synthetic-v1",
                source_id="synthetic/m1-prices",
                code_revision="f2232463",
                created_at_utc=datetime(2026, 9, 26, tzinfo=UTC),
            )
            verified = verify_dataset(
                dataset, contract=upstream_adjusted_close_contract()
            )
            manifest = json.loads((dataset / "manifest.json").read_text())
            collected = scan_verified_dataset(
                dataset, contract=upstream_adjusted_close_contract()
            ).collect()
            self.assertEqual((verified.rows, verified.files), (2014, 4))
            self.assertEqual(manifest["dataset"]["source_sha256"], prices.source_sha256)
            self.assertTrue(collected.equals(prices.frame))
            with self.assertRaises(FileExistsError):
                publish_upstream_prices(
                    prices,
                    root,
                    dataset_version="synthetic-v1",
                    source_id="synthetic/m1-prices",
                    code_revision="f2232463",
                    created_at_utc=datetime(2026, 9, 26, tzinfo=UTC),
                )

    def test_polars_lazy_and_legacy_single_symbol(self) -> None:
        wide = pl.DataFrame(
            {"Date": ["2001-01-02", "2001-01-03"], "Adj Close": ["1.5", "1.6"]}
        )
        with self.assertRaisesRegex(DatasetContractError, "legacy_symbol"):
            ingest(wide)
        prices = ingest_upstream_prices(
            wide.lazy(),
            quote_unit="USD",
            calendar="source-sessions",
            legacy_symbol="SPY",
        )
        self.assertEqual(prices.source_kind, "polars-canonical-csv")
        self.assertEqual(
            prices.frame.get_column("instrument").to_list(), ["SPY", "SPY"]
        )
        self.assertEqual(
            prices.frame.get_column("adjusted_close").to_list(), [1.5, 1.6]
        )

    def test_rejects_order_dates_symbols_and_bad_prices(self) -> None:
        cases = (
            ({"Date": ["2001-01-03", "2001-01-02"], "SPY": ["1", "2"]}, "increasing"),
            ({"Date": ["2001-01-02", "2001-01-02"], "SPY": ["1", "2"]}, "increasing"),
            ({"Date": ["2001-1-02"], "SPY": ["1"]}, "YYYY-MM-DD"),
            ({"Date": ["2001-02-30"], "SPY": ["1"]}, "calendar day"),
            ({"Date": ["2001-01-02"], "spy": ["1"]}, "uppercase"),
            ({"Date": ["2001-01-02"], "SPY": ["NaN"]}, "invalid adjusted close"),
            ({"Date": ["2001-01-02"], "SPY": ["1e309"]}, "positive and finite"),
            ({"Date": ["2001-01-02"], "SPY": ["0"]}, "positive and finite"),
            ({"Date": ["2001-01-02"], "SPY": [None]}, "no adjusted closes"),
        )
        for columns, message in cases:
            with (
                self.subTest(columns=columns),
                self.assertRaisesRegex(DatasetContractError, message),
            ):
                ingest(pl.DataFrame(columns))

    def test_rejects_duplicate_csv_header(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "duplicate.csv"
            path.write_text("Date,SPY,SPY\n2001-01-02,1,2\n")
            with self.assertRaisesRegex(DatasetContractError, "duplicate CSV header"):
                load_upstream_prices_csv(
                    path, quote_unit="USD", calendar="source-sessions"
                )

    def test_publisher_revalidates_price_domain(self) -> None:
        prices = ingest(pl.DataFrame({"Date": ["2001-01-02"], "SPY": ["1"]}))
        corrupt = prices.frame.with_columns(
            pl.lit(float("nan")).alias("adjusted_close")
        )
        with (
            tempfile.TemporaryDirectory() as temporary,
            self.assertRaisesRegex(DatasetContractError, "positive and finite"),
        ):
            publish_upstream_prices(
                replace(prices, frame=corrupt),
                Path(temporary),
                dataset_version="bad-v1",
                source_id="synthetic/corrupt",
                code_revision="f2232463",
                created_at_utc=datetime(2026, 9, 26, tzinfo=UTC),
            )

    def test_optional_pandas_adapter_matches_polars(self) -> None:
        if importlib.util.find_spec("pandas") is None:
            self.skipTest("install griddy[pandas] to test the optional adapter")
        pd: Any = importlib.import_module("pandas")
        pandas_frame = pd.DataFrame(
            {"Date": ["2001-01-02", "2001-01-03"], "SPY": [1.5, 1.6]}
        ).set_index("Date")
        adapted = ingest_upstream_prices_pandas(
            pandas_frame, quote_unit="USD", calendar="source-sessions"
        )
        self.assertEqual(adapted.source_kind, "pandas-adapted-canonical-csv")
        native = ingest_upstream_prices(
            pl.DataFrame({"Date": ["2001-01-02", "2001-01-03"], "SPY": [1.5, 1.6]}),
            quote_unit="USD",
            calendar="source-sessions",
        )
        self.assertTrue(adapted.frame.equals(native.frame))


if __name__ == "__main__":
    unittest.main()
