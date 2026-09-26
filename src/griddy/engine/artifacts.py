"""Immutable Parquet results and a content-addressed M2 run manifest."""

from __future__ import annotations

import hashlib
import json
import platform
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from typing import Any, cast

import polars as pl

from griddy.dataset import (
    DatasetContractError,
    scan_verified_dataset,
    upstream_adjusted_close_contract,
    verify_dataset,
)
from griddy.evidence import validate_sha256

from .metrics import CandidateMetrics, ReturnMetrics, calculate_core_metrics
from .reference import (
    RESULT_SCHEMA,
    ReferenceExecution,
    SmaCrossoverCandidate,
    SmaCrossoverResult,
    run_sma_crossover,
)

RUN_SCHEMA_VERSION = "run-manifest/v1"
SPACE_VERSION = "sma-ratio-crossover/v1"
CONFIG_VERSION = "single-sma-config/v1"
SUMMARY_SCHEMA_VERSION = "single-sma-summary/v1"
RETURNS_SCHEMA_VERSION = "single-sma-returns/v1"
SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SUMMARY_SCHEMA = pl.Schema(
    {
        "candidate_id": pl.String,
        "split_id": pl.String,
        "signal_instrument": pl.String,
        "trade_instrument": pl.String,
        "fast": pl.Int64,
        "slow": pl.Int64,
        "threshold": pl.Float64,
        "lag": pl.Int64,
        "cost_bps": pl.Float64,
        "cash_rate": pl.Float64,
        "periods_per_year": pl.Int64,
        "start": pl.Date,
        "end": pl.Date,
        "observations": pl.Int64,
        "years": pl.Float64,
        "strategy_total_return": pl.Float64,
        "strategy_cagr": pl.Float64,
        "strategy_annualized_volatility": pl.Float64,
        "strategy_sharpe": pl.Float64,
        "strategy_beta": pl.Float64,
        "strategy_jensen_alpha": pl.Float64,
        "strategy_max_drawdown": pl.Float64,
        "benchmark_total_return": pl.Float64,
        "benchmark_cagr": pl.Float64,
        "benchmark_annualized_volatility": pl.Float64,
        "benchmark_sharpe": pl.Float64,
        "benchmark_beta": pl.Float64,
        "benchmark_jensen_alpha": pl.Float64,
        "benchmark_max_drawdown": pl.Float64,
        "position_changes": pl.Int64,
        "changes_per_year": pl.Float64,
        "average_trade_weight": pl.Float64,
        "average_cash_weight": pl.Float64,
        "total_turnover": pl.Float64,
        "total_transaction_cost": pl.Float64,
    }
)
RETURNS_SCHEMA = pl.Schema({"candidate_id": pl.String, **dict(RESULT_SCHEMA)})


class RunIntegrityError(ValueError):
    """A run artifact or its declared provenance failed verification."""


@dataclass(frozen=True, slots=True)
class RunVerification:
    manifest_sha256: str
    reproducibility_sha256: str
    result_rows: int
    return_rows: int


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _digest_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _digest(value: object) -> str:
    return _digest_bytes(_canonical_bytes(value))


def _sha256_file(path: Path) -> str:
    return _digest_bytes(path.read_bytes())


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _software_versions() -> dict[str, str]:
    return {
        "griddy": version("griddy"),
        "numpy": version("numpy"),
        "polars": version("polars"),
        "python": platform.python_version(),
        "statsmodels": version("statsmodels"),
    }


def _metric_fields(prefix: str, metrics: ReturnMetrics) -> dict[str, float | None]:
    return {
        f"{prefix}_total_return": metrics.total_return,
        f"{prefix}_cagr": metrics.cagr,
        f"{prefix}_annualized_volatility": metrics.annualized_volatility,
        f"{prefix}_sharpe": metrics.sharpe,
        f"{prefix}_beta": metrics.beta,
        f"{prefix}_jensen_alpha": metrics.jensen_alpha,
        f"{prefix}_max_drawdown": metrics.max_drawdown,
    }


def _summary_frame(
    candidate_id: str,
    result: SmaCrossoverResult,
    metrics: CandidateMetrics,
) -> pl.DataFrame:
    candidate = result.candidate
    execution = result.execution
    row: dict[str, object] = {
        "candidate_id": candidate_id,
        "split_id": None,
        "signal_instrument": candidate.signal_instrument,
        "trade_instrument": candidate.trade_instrument,
        "fast": candidate.fast,
        "slow": candidate.slow,
        "threshold": candidate.threshold,
        "lag": execution.lag,
        "cost_bps": execution.cost_bps,
        "cash_rate": execution.cash_rate,
        "periods_per_year": execution.periods_per_year,
        "start": metrics.start,
        "end": metrics.end,
        "observations": metrics.observations,
        "years": metrics.years,
        "position_changes": metrics.position_changes,
        "changes_per_year": metrics.changes_per_year,
        "average_trade_weight": metrics.average_trade_weight,
        "average_cash_weight": metrics.average_cash_weight,
        "total_turnover": metrics.total_turnover,
        "total_transaction_cost": metrics.total_transaction_cost,
        **_metric_fields("strategy", metrics.strategy),
        **_metric_fields("benchmark", metrics.buy_and_hold),
    }
    return pl.DataFrame([row], schema=SUMMARY_SCHEMA)


def _returns_frame(candidate_id: str, result: SmaCrossoverResult) -> pl.DataFrame:
    return result.frame.with_columns(pl.lit(candidate_id).alias("candidate_id")).select(
        RETURNS_SCHEMA.names()
    )


def _output_record(path: Path, schema_version: str, rows: int) -> dict[str, object]:
    return {
        "path": path.name,
        "schema_version": schema_version,
        "sha256": _sha256_file(path),
        "bytes": path.stat().st_size,
        "rows": rows,
    }


def publish_reference_run(
    input_dataset: Path,
    root: Path,
    *,
    run_id: str,
    candidate: SmaCrossoverCandidate,
    execution: ReferenceExecution,
    code_revision: str,
    lockfile: Path,
    evaluated_at_utc: datetime,
) -> Path:
    """Replay one candidate from a verified dataset and publish immutable output."""
    if not SAFE_RUN_ID.fullmatch(run_id):
        raise DatasetContractError("run_id contains unsafe characters")
    if not code_revision.strip():
        raise DatasetContractError("code_revision is required")
    if evaluated_at_utc.utcoffset() != timedelta(0):
        raise DatasetContractError("evaluated_at_utc must use UTC")
    lock_sha256 = _sha256_file(lockfile)
    input_verification = verify_dataset(
        input_dataset, contract=upstream_adjusted_close_contract()
    )
    input_manifest = json.loads((input_dataset / "manifest.json").read_text())
    source_record = input_manifest["dataset"]
    result = run_sma_crossover(
        scan_verified_dataset(
            input_dataset, contract=upstream_adjusted_close_contract()
        ),
        candidate,
        execution,
    )
    metrics = calculate_core_metrics(result)
    space = {"version": SPACE_VERSION, "candidates": [asdict(candidate)]}
    config = {
        "version": CONFIG_VERSION,
        "dataset_manifest_sha256": input_verification.manifest_sha256,
        "candidate": asdict(candidate),
        "execution": asdict(execution),
    }
    candidate_id = _digest(
        {"space_version": SPACE_VERSION, "candidate": asdict(candidate)}
    )
    summary = _summary_frame(candidate_id, result, metrics)
    daily = _returns_frame(candidate_id, result)

    root.mkdir(parents=True, exist_ok=True)
    destination = root / run_id
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"run already exists: {destination}")
    stage = Path(tempfile.mkdtemp(dir=root, prefix=".staging-"))
    try:
        summary.write_parquet(
            stage / "results.parquet", compression="zstd", statistics=True
        )
        daily.write_parquet(
            stage / "returns.parquet", compression="zstd", statistics=True
        )
        outputs = [
            _output_record(stage / "results.parquet", SUMMARY_SCHEMA_VERSION, 1),
            _output_record(
                stage / "returns.parquet", RETURNS_SCHEMA_VERSION, daily.height
            ),
        ]
        reproducibility = {
            "candidate_id": candidate_id,
            "code_revision": code_revision,
            "config": config,
            "config_sha256": _digest(config),
            "counts": {"nominal": 1, "constrained": 1, "valid": 1, "unique": 1},
            "dataset": {
                "name": source_record["name"],
                "version": source_record["version"],
                "manifest_sha256": input_verification.manifest_sha256,
                "source_id": source_record["source_id"],
                "source_sha256": source_record["source_sha256"],
            },
            "execution": {
                **asdict(execution),
                "timing": "signal_close",
                "initial_position": "flat",
            },
            "outputs": outputs,
            "search_space": space,
            "search_space_sha256": _digest(space),
            "seeds": {},
            "software": _software_versions(),
            "splits": [],
            "uv_lock_sha256": lock_sha256,
            "window": {
                "policy": "single_candidate_common_sessions",
                "start": metrics.start.isoformat(),
                "end": metrics.end.isoformat(),
                "observations": metrics.observations,
            },
        }
        manifest = {
            "schema_version": RUN_SCHEMA_VERSION,
            "reproducibility": reproducibility,
            "reproducibility_sha256": _digest(reproducibility),
            "provenance": {
                "run_id": run_id,
                "evaluated_at_utc": _utc_text(evaluated_at_utc),
            },
        }
        manifest_bytes = (
            json.dumps(manifest, allow_nan=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        (stage / "manifest.json").write_bytes(manifest_bytes)
        (stage / "manifest.sha256").write_text(
            f"{_digest_bytes(manifest_bytes)}  manifest.json\n", encoding="ascii"
        )
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"run already exists: {destination}")
        stage.replace(destination)
        return destination
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def _load_run_manifest(run: Path) -> tuple[dict[str, Any], str]:
    if any(
        path.is_symlink()
        for path in (run, run / "manifest.json", run / "manifest.sha256")
    ):
        raise RunIntegrityError("run manifest paths cannot be symbolic links")
    try:
        manifest_bytes = (run / "manifest.json").read_bytes()
        expected_line = (run / "manifest.sha256").read_text(encoding="ascii")
        expected_digest, filename = expected_line.rstrip("\n").split("  ", 1)
        validate_sha256("manifest SHA-256", expected_digest)
        digest = _digest_bytes(manifest_bytes)
        if filename != "manifest.json" or expected_digest != digest:
            raise RunIntegrityError("run manifest checksum mismatch")
        parsed: object = json.loads(manifest_bytes)
        if not isinstance(parsed, dict):
            raise RunIntegrityError("run manifest must be an object")
        return cast(dict[str, Any], parsed), digest
    except RunIntegrityError:
        raise
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        raise RunIntegrityError("run manifest is missing or malformed") from error


def verify_reference_run(
    run: Path,
    *,
    input_dataset: Path | None = None,
    lockfile: Path | None = None,
    replay: bool = False,
) -> RunVerification:
    """Verify run hashes, schemas, summary consistency, and optional source replay."""
    if replay and input_dataset is None:
        raise ValueError("replay requires input_dataset")
    manifest, manifest_sha256 = _load_run_manifest(run)
    try:
        if (
            set(manifest)
            != {
                "schema_version",
                "reproducibility",
                "reproducibility_sha256",
                "provenance",
            }
            or manifest["schema_version"] != RUN_SCHEMA_VERSION
        ):
            raise RunIntegrityError("unsupported run manifest schema")
        provenance = manifest["provenance"]
        if provenance["run_id"] != run.name or not SAFE_RUN_ID.fullmatch(
            provenance["run_id"]
        ):
            raise RunIntegrityError("run id does not match directory")
        evaluated_at = datetime.fromisoformat(
            provenance["evaluated_at_utc"].replace("Z", "+00:00")
        )
        if evaluated_at.utcoffset() != timedelta(0):
            raise RunIntegrityError("evaluation time must use UTC")
        reproducibility = manifest["reproducibility"]
        if _digest(reproducibility) != manifest["reproducibility_sha256"]:
            raise RunIntegrityError("reproducibility hash mismatch")
        validate_sha256("reproducibility SHA-256", manifest["reproducibility_sha256"])
        config = reproducibility["config"]
        space = reproducibility["search_space"]
        if _digest(config) != reproducibility["config_sha256"]:
            raise RunIntegrityError("config hash mismatch")
        if _digest(space) != reproducibility["search_space_sha256"]:
            raise RunIntegrityError("search-space hash mismatch")
        if space != {"version": SPACE_VERSION, "candidates": [config["candidate"]]}:
            raise RunIntegrityError("search space does not match config")
        if config["version"] != CONFIG_VERSION:
            raise RunIntegrityError("unsupported config schema")
        candidate = SmaCrossoverCandidate(**config["candidate"])
        execution = ReferenceExecution(**config["execution"])
        candidate_id = _digest(
            {"space_version": SPACE_VERSION, "candidate": asdict(candidate)}
        )
        if candidate_id != reproducibility["candidate_id"]:
            raise RunIntegrityError("candidate id does not match config")
        if reproducibility["execution"] != {
            **asdict(execution),
            "timing": "signal_close",
            "initial_position": "flat",
        }:
            raise RunIntegrityError("execution record does not match config")
        if (
            reproducibility["counts"]
            != {
                "nominal": 1,
                "constrained": 1,
                "valid": 1,
                "unique": 1,
            }
            or reproducibility["seeds"] != {}
        ):
            raise RunIntegrityError("single-candidate counts or seeds are invalid")
        if not isinstance(reproducibility["code_revision"], str) or not (
            reproducibility["code_revision"].strip()
        ):
            raise RunIntegrityError("code revision is missing")
        validate_sha256("uv.lock SHA-256", reproducibility["uv_lock_sha256"])
        if (
            lockfile is not None
            and _sha256_file(lockfile) != reproducibility["uv_lock_sha256"]
        ):
            raise RunIntegrityError("lockfile hash mismatch")
        dataset_record = reproducibility["dataset"]
        if (
            dataset_record["name"] != upstream_adjusted_close_contract().name
            or not isinstance(dataset_record["version"], str)
            or not SAFE_RUN_ID.fullmatch(dataset_record["version"])
            or not isinstance(dataset_record["source_id"], str)
            or not dataset_record["source_id"].strip()
        ):
            raise RunIntegrityError("input dataset identity is invalid")
        if config["dataset_manifest_sha256"] != dataset_record["manifest_sha256"]:
            raise RunIntegrityError("config dataset hash mismatch")
        validate_sha256("dataset manifest SHA-256", dataset_record["manifest_sha256"])
        validate_sha256("dataset source SHA-256", dataset_record["source_sha256"])
        software: object = reproducibility["software"]
        expected_software = {"griddy", "numpy", "polars", "python", "statsmodels"}
        if not isinstance(software, dict):
            raise RunIntegrityError("software identity is invalid")
        versions = cast(dict[str, object], software)
        if set(versions) != expected_software or any(
            not isinstance(value, str) or not value.strip()
            for value in versions.values()
        ):
            raise RunIntegrityError("software identity is invalid")
        if input_dataset is not None:
            input_verification = verify_dataset(
                input_dataset, contract=upstream_adjusted_close_contract()
            )
            if input_verification.manifest_sha256 != dataset_record["manifest_sha256"]:
                raise RunIntegrityError("input dataset manifest hash mismatch")
        raw_files: object = reproducibility["outputs"]
        if not isinstance(raw_files, list):
            raise RunIntegrityError("run output records are invalid")
        raw_records = cast(list[object], raw_files)
        if any(not isinstance(record, dict) for record in raw_records):
            raise RunIntegrityError("run output records are invalid")
        files = cast(list[dict[str, Any]], raw_files)
        if [record.get("path") for record in files] != [
            "results.parquet",
            "returns.parquet",
        ]:
            raise RunIntegrityError("run output records are invalid")
        expected_files = {
            run / "manifest.json",
            run / "manifest.sha256",
            run / "results.parquet",
            run / "returns.parquet",
        }
        actual_entries = set(run.rglob("*"))
        if actual_entries != expected_files or any(
            path.is_symlink() for path in actual_entries
        ):
            raise RunIntegrityError("run file set contains missing or extra files")
        for record, schema_version in zip(
            files, (SUMMARY_SCHEMA_VERSION, RETURNS_SCHEMA_VERSION), strict=True
        ):
            path = run / record["path"]
            validate_sha256("output SHA-256", record["sha256"])
            if record["schema_version"] != schema_version:
                raise RunIntegrityError("output schema version mismatch")
            if (
                path.stat().st_size != record["bytes"]
                or _sha256_file(path) != record["sha256"]
            ):
                raise RunIntegrityError("output file hash or size mismatch")
        if pl.read_parquet_schema(run / "results.parquet") != SUMMARY_SCHEMA:
            raise RunIntegrityError("result Parquet schema mismatch")
        if pl.read_parquet_schema(run / "returns.parquet") != RETURNS_SCHEMA:
            raise RunIntegrityError("return Parquet schema mismatch")
        summary = pl.read_parquet(run / "results.parquet")
        daily = pl.read_parquet(run / "returns.parquet")
        if summary.height != 1 or daily.is_empty():
            raise RunIntegrityError("result or return row count is invalid")
        if summary.height != files[0]["rows"] or daily.height != files[1]["rows"]:
            raise RunIntegrityError("output row counts do not match")
        if (
            daily["candidate_id"].n_unique() != 1
            or daily["candidate_id"][0] != candidate_id
        ):
            raise RunIntegrityError("daily returns have the wrong candidate id")
        reconstructed = SmaCrossoverResult(
            candidate=candidate,
            execution=execution,
            frame=daily.select(RESULT_SCHEMA.names()),
        )
        metrics = calculate_core_metrics(reconstructed)
        expected_summary = _summary_frame(candidate_id, reconstructed, metrics)
        if not summary.equals(expected_summary):
            raise RunIntegrityError("summary does not match daily returns")
        window = {
            "policy": "single_candidate_common_sessions",
            "start": metrics.start.isoformat(),
            "end": metrics.end.isoformat(),
            "observations": metrics.observations,
        }
        if reproducibility["window"] != window or reproducibility["splits"] != []:
            raise RunIntegrityError("run window or split does not match returns")
        if replay:
            assert input_dataset is not None
            rerun = run_sma_crossover(
                scan_verified_dataset(
                    input_dataset, contract=upstream_adjusted_close_contract()
                ),
                candidate,
                execution,
            )
            if not rerun.frame.equals(reconstructed.frame):
                raise RunIntegrityError("source replay does not match daily returns")
    except RunIntegrityError:
        raise
    except (
        AttributeError,
        IndexError,
        KeyError,
        TypeError,
        ValueError,
        OSError,
        pl.exceptions.PolarsError,
    ) as error:
        raise RunIntegrityError("run manifest or output is malformed") from error
    return RunVerification(
        manifest_sha256=manifest_sha256,
        reproducibility_sha256=manifest["reproducibility_sha256"],
        result_rows=summary.height,
        return_rows=daily.height,
    )
