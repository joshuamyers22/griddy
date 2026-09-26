"""Check the committed synthetic oracle's provenance and coverage."""

import hashlib
import json
import unittest
from pathlib import Path

import polars as pl

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "upstream"
LOCK = Path(__file__).resolve().parents[1] / "tools" / "upstream-capture.lock"
EXPECTED_CASES = {
    "single",
    "multi_signal_trade",
    "thresholds",
    "lag_0",
    "lag_1",
    "lag_2",
    "cost_0",
    "cost_positive",
    "down_pos_0",
    "down_pos_half",
    "down_pos_short",
    "down_symbol",
    "average",
    "annual",
    "deflate",
    "async_calendar",
    "reference_597",
}


class UpstreamFixtureTests(unittest.TestCase):
    def test_synthetic_oracle_is_complete_and_integral(self) -> None:
        manifest = json.loads((FIXTURES / "manifest.json").read_text())
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(
            manifest["upstream_commit"],
            "91e9e35a9eca36d314138302fb86075f05cb71c0",
        )
        self.assertEqual(
            hashlib.sha256(LOCK.read_bytes()).hexdigest(),
            manifest["upstream_dependency_lock_sha256"],
        )
        source = FIXTURES / manifest["input_file"]
        self.assertEqual(
            hashlib.sha256(source.read_bytes()).hexdigest(), manifest["input_sha256"]
        )
        self.assertEqual(
            {case["name"] for case in manifest["fixtures"]}, EXPECTED_CASES
        )
        for case in manifest["fixtures"]:
            with self.subTest(case=case["name"]):
                self.assertEqual(case["source"], "synthetic")
                for filename_key, hash_key in (
                    ("rows_file", "rows_sha256"),
                    ("returns_file", "returns_sha256"),
                ):
                    path = FIXTURES / "golden" / case[filename_key]
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                    self.assertEqual(digest, case[hash_key])
                payload = json.loads(
                    (FIXTURES / "golden" / case["rows_file"]).read_text()
                )
                self.assertEqual(len(payload["rows"]), case["row_count"])
                self.assertEqual(
                    sum(row["type"] == "Strategy" for row in payload["rows"]),
                    case["candidate_count"],
                )

    def test_critical_cases_are_present(self) -> None:
        manifest = json.loads((FIXTURES / "manifest.json").read_text())
        by_name = {case["name"]: case for case in manifest["fixtures"]}
        self.assertEqual(by_name["reference_597"]["candidate_count"], 597)
        reference = json.loads((FIXTURES / "golden" / "reference_597.json").read_text())
        self.assertEqual(reference["deflation"]["SPY"]["raw_count"], 597)
        self.assertEqual(reference["deflation"]["SPY"]["best"]["trade"], "SPY")
        self.assertTrue(reference["case"]["vectorized"])
        self.assertTrue(reference["case"]["deflate"])
        self.assertIn("_dsr", reference["rows"][0])
        self.assertTrue(reference["annual_report"] == [])
        annual = json.loads((FIXTURES / "golden" / "annual.json").read_text())
        self.assertTrue(annual["annual_report"])
        average = json.loads((FIXTURES / "golden" / "average.json").read_text())
        self.assertTrue(any(row["type"] == "*Average*" for row in average["rows"]))
        asynchronous = json.loads(
            (FIXTURES / "golden" / "async_calendar.json").read_text()
        )
        self.assertEqual(asynchronous["case"]["trades"], ["IEF"])
        self.assertGreater(asynchronous["rows"][0]["start"], "2001-12-31")
        returns = pl.read_parquet(FIXTURES / "golden" / "reference_597.parquet")
        self.assertEqual(returns.height, by_name["reference_597"]["return_count"])
        self.assertEqual(returns.columns, ["row_id", "date", "daily_return"])
        self.assertEqual(returns["row_id"].n_unique(), 597)


if __name__ == "__main__":
    unittest.main()
