"""Round-trip and tamper checks for the M2 result files and run manifest."""

from __future__ import annotations

import hashlib
import json
import math
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from griddy.dataset import DatasetContractError
from griddy.engine.artifacts import (
    RETURNS_SCHEMA,
    SUMMARY_SCHEMA,
    RunIntegrityError,
    publish_reference_run,
    verify_reference_run,
)
from griddy.engine.reference import ReferenceExecution, SmaCrossoverCandidate
from griddy.upstream_prices import (
    ingest_upstream_prices,
    load_upstream_prices_csv,
    publish_upstream_prices,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "upstream"
LOCKFILE = ROOT / "uv.lock"
CREATED = datetime(2026, 9, 26, tzinfo=UTC)
CANDIDATE = SmaCrossoverCandidate("SPY", "SPY", fast=2, slow=8)
EXECUTION = ReferenceExecution(periods_per_year=252, cash_rate=0.03, lag=0)


def _input_dataset(root: Path) -> Path:
    prices = load_upstream_prices_csv(
        FIXTURES / "synthetic_prices.csv",
        quote_unit="synthetic",
        calendar="synthetic-weekdays",
    )
    return publish_upstream_prices(
        prices,
        root,
        dataset_version="synthetic-m2-v1",
        source_id="synthetic/m1-prices",
        code_revision="fixture-revision",
        created_at_utc=CREATED,
    )


def _publish(dataset: Path, root: Path, run_id: str = "run-1") -> Path:
    return publish_reference_run(
        dataset,
        root,
        run_id=run_id,
        candidate=CANDIDATE,
        execution=EXECUTION,
        code_revision="test-revision",
        lockfile=LOCKFILE,
        evaluated_at_utc=CREATED,
    )


class RunArtifactTests(unittest.TestCase):
    def test_publish_verify_replay_and_golden_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = _input_dataset(root / "datasets")
            run = _publish(dataset, root / "runs")
            verification = verify_reference_run(
                run, input_dataset=dataset, lockfile=LOCKFILE, replay=True
            )
            summary = pl.read_parquet(run / "results.parquet")
            daily = pl.read_parquet(run / "returns.parquet")
            golden_row = json.loads((FIXTURES / "golden" / "single.json").read_text())[
                "rows"
            ][0]
            golden_returns = pl.read_parquet(FIXTURES / "golden" / "single.parquet")
            manifest = json.loads((run / "manifest.json").read_text())
            payload = manifest["reproducibility"]

            self.assertEqual(summary.schema, SUMMARY_SCHEMA)
            self.assertEqual(daily.schema, RETURNS_SCHEMA)
            self.assertEqual(
                (verification.result_rows, verification.return_rows), (1, 850)
            )
            self.assertEqual(summary["candidate_id"][0], payload["candidate_id"])
            self.assertEqual(daily["candidate_id"].n_unique(), 1)
            self.assertTrue(
                math.isclose(
                    summary["strategy_cagr"][0], golden_row["return"], abs_tol=1e-12
                )
            )
            self.assertTrue(
                math.isclose(
                    summary["strategy_sharpe"][0], golden_row["sharpe"], abs_tol=1e-12
                )
            )
            self.assertEqual(
                daily["event_date"].to_list(), golden_returns["date"].to_list()
            )
            joined = daily.join(golden_returns, left_on="event_date", right_on="date")
            difference = joined.select(
                (pl.col("net_return") - pl.col("daily_return")).abs().max()
            ).item()
            self.assertLessEqual(difference, 1e-12)
            self.assertEqual(
                payload["counts"],
                {"nominal": 1, "constrained": 1, "valid": 1, "unique": 1},
            )
            self.assertEqual(payload["seeds"], {})
            self.assertEqual(payload["splits"], [])
            self.assertIsNone(summary["split_id"][0])
            self.assertEqual(payload["window"]["observations"], 850)
            self.assertEqual(payload["dataset"]["version"], "synthetic-m2-v1")
            self.assertEqual(
                payload["uv_lock_sha256"],
                hashlib.sha256(LOCKFILE.read_bytes()).hexdigest(),
            )

    def test_content_hash_excludes_run_identity_and_time(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = _input_dataset(root / "datasets")
            first = _publish(dataset, root / "runs", "run-1")
            second = publish_reference_run(
                dataset,
                root / "runs",
                run_id="run-2",
                candidate=CANDIDATE,
                execution=EXECUTION,
                code_revision="test-revision",
                lockfile=LOCKFILE,
                evaluated_at_utc=CREATED + timedelta(days=1),
            )
            first_check = verify_reference_run(first)
            second_check = verify_reference_run(second)
            self.assertEqual(
                first_check.reproducibility_sha256,
                second_check.reproducibility_sha256,
            )
            self.assertNotEqual(
                first_check.manifest_sha256, second_check.manifest_sha256
            )
            with self.assertRaises(FileExistsError):
                _publish(dataset, root / "runs", "run-1")

    def test_detects_tampering_and_wrong_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = _input_dataset(root / "datasets")
            run = _publish(dataset, root / "runs")
            returns_path = run / "returns.parquet"
            original = returns_path.read_bytes()
            returns_path.write_bytes(original + b"tampered")
            with self.assertRaisesRegex(RunIntegrityError, "hash or size"):
                verify_reference_run(run)
            returns_path.write_bytes(original)

            extra = run / "extra.txt"
            extra.write_text("unmanifested")
            with self.assertRaisesRegex(RunIntegrityError, "file set"):
                verify_reference_run(run)
            extra.unlink()

            wrong_lock = root / "other.lock"
            wrong_lock.write_text("different lock")
            with self.assertRaisesRegex(RunIntegrityError, "lockfile hash"):
                verify_reference_run(run, lockfile=wrong_lock)
            other_dataset = publish_upstream_prices(
                load_upstream_prices_csv(
                    FIXTURES / "synthetic_prices.csv",
                    quote_unit="synthetic",
                    calendar="synthetic-weekdays",
                ),
                root / "datasets",
                dataset_version="different-v1",
                source_id="synthetic/m1-prices",
                code_revision="fixture-revision",
                created_at_utc=CREATED,
            )
            with self.assertRaisesRegex(RunIntegrityError, "input dataset manifest"):
                verify_reference_run(run, input_dataset=other_dataset)

            manifest_path = run / "manifest.json"
            manifest_path.write_bytes(manifest_path.read_bytes() + b" ")
            with self.assertRaisesRegex(RunIntegrityError, "checksum"):
                verify_reference_run(run)

    def test_rejects_inconsistent_summary_even_with_rehashed_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = _input_dataset(root / "datasets")
            run = _publish(dataset, root / "runs")
            summary_path = run / "results.parquet"
            summary = pl.read_parquet(summary_path).with_columns(
                pl.lit(123.0).alias("strategy_cagr")
            )
            summary.write_parquet(summary_path, compression="zstd", statistics=True)
            manifest = json.loads((run / "manifest.json").read_text())
            output = manifest["reproducibility"]["outputs"][0]
            output["sha256"] = hashlib.sha256(summary_path.read_bytes()).hexdigest()
            output["bytes"] = summary_path.stat().st_size
            payload = json.dumps(
                manifest["reproducibility"],
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
            manifest["reproducibility_sha256"] = hashlib.sha256(payload).hexdigest()
            manifest_bytes = (
                json.dumps(manifest, sort_keys=True, indent=2, allow_nan=False) + "\n"
            ).encode()
            (run / "manifest.json").write_bytes(manifest_bytes)
            (run / "manifest.sha256").write_text(
                f"{hashlib.sha256(manifest_bytes).hexdigest()}  manifest.json\n"
            )
            with self.assertRaisesRegex(RunIntegrityError, "summary does not match"):
                verify_reference_run(run)

    def test_nullable_metrics_and_invalid_publication_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prices = ingest_upstream_prices(
                pl.DataFrame(
                    {
                        "Date": ["2026-01-01", "2026-01-02", "2026-01-03"],
                        "SPY": [100.0, 100.0, 100.0],
                    }
                ),
                quote_unit="synthetic",
                calendar="synthetic-sessions",
            )
            dataset = publish_upstream_prices(
                prices,
                root / "datasets",
                dataset_version="flat-v1",
                source_id="synthetic/flat",
                code_revision="fixture-revision",
                created_at_utc=CREATED,
            )
            run = publish_reference_run(
                dataset,
                root / "runs",
                run_id="flat-run",
                candidate=SmaCrossoverCandidate("SPY", "SPY", fast=1, slow=1),
                execution=ReferenceExecution(
                    periods_per_year=252, cash_rate=0.0, lag=0
                ),
                code_revision="test-revision",
                lockfile=LOCKFILE,
                evaluated_at_utc=CREATED,
            )
            self.assertEqual(
                verify_reference_run(
                    run, replay=True, input_dataset=dataset
                ).return_rows,
                2,
            )
            row = pl.read_parquet(run / "results.parquet").row(0, named=True)
            self.assertIsNone(row["strategy_sharpe"])
            self.assertIsNone(row["strategy_beta"])
            with self.assertRaisesRegex(DatasetContractError, "unsafe"):
                publish_reference_run(
                    dataset,
                    root / "runs",
                    run_id="../escape",
                    candidate=CANDIDATE,
                    execution=EXECUTION,
                    code_revision="test-revision",
                    lockfile=LOCKFILE,
                    evaluated_at_utc=CREATED,
                )


if __name__ == "__main__":
    unittest.main()
