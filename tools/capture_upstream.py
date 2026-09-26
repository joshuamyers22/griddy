"""Capture pinned xma outputs in an isolated, locked environment.

Synthetic outputs may be committed. Vendor-derived outputs always remain under
ignored .work/ and must not be copied into the repository or CI.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import importlib.metadata
import io
import itertools
import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_SHA = "91e9e35a9eca36d314138302fb86075f05cb71c0"
UPSTREAM_URL = "https://github.com/vivek-v-rao/moving-average-systems.git"
UPSTREAM_DIR = ROOT / ".work" / "upstream"
ENV_DIR = ROOT / ".work" / "upstream-env"
LOCK = ROOT / "tools" / "upstream-capture.lock"
FIXTURES = ROOT / "tests" / "fixtures" / "upstream"
VENDOR_DIR = ROOT / ".work" / "captures" / "vendor"
REFERENCE_COMMAND = (
    "python xma_signal.py [SPY IEF TLT] 1 2:200 --trade SPY "
    "--read-prices-file prices.csv --terse --time --best --deflate"
)
VENDOR_INPUT_SHA = "4739a0b4a630cddd69215db1ed5ede7480488ace3ade889e6b203973c316a63b"


@dataclass(frozen=True)
class Case:
    name: str
    signals: tuple[str, ...]
    trades: tuple[str, ...]
    fast: tuple[int, ...]
    slow: tuple[int, ...]
    thresholds: tuple[float, ...] = (0.0,)
    lag: int = 0
    cost: float = 0.0
    down_pos: float = 0.0
    down_symbol: str | None = None
    average: bool = False
    annual: bool = False
    deflate: bool = False
    deflate_sims: int = 128
    trade_date_max: str | None = None
    vectorized: bool = False


SYNTHETIC_CASES = (
    Case("single", ("SPY",), ("SPY",), (2,), (8,)),
    Case("multi_signal_trade", ("SPY", "IEF"), ("SPY", "TLT"), (2,), (8,)),
    Case("thresholds", ("SPY",), ("SPY",), (2,), (8,), (-0.01, 0.0, 0.01)),
    Case("lag_0", ("SPY",), ("SPY",), (2,), (8,)),
    Case("lag_1", ("SPY",), ("SPY",), (2,), (8,), lag=1),
    Case("lag_2", ("SPY",), ("SPY",), (2,), (8,), lag=2),
    Case("cost_0", ("SPY",), ("SPY",), (2,), (8,)),
    Case("cost_positive", ("SPY",), ("SPY",), (2,), (8,), cost=0.001),
    Case("down_pos_0", ("SPY",), ("SPY",), (2,), (8,)),
    Case("down_pos_half", ("SPY",), ("SPY",), (2,), (8,), down_pos=0.5),
    Case("down_pos_short", ("SPY",), ("SPY",), (2,), (8,), down_pos=-1.0),
    Case(
        "down_symbol",
        ("SPY",),
        ("SPY",),
        (2,),
        (8,),
        down_pos=0.5,
        down_symbol="IEF",
    ),
    Case("average", ("SPY", "IEF"), ("SPY",), (2, 4), (8, 12), average=True),
    Case("annual", ("SPY",), ("SPY",), (2,), (8,), annual=True),
    Case(
        "deflate",
        ("SPY", "IEF"),
        ("SPY",),
        (2, 4),
        (8, 12),
        deflate=True,
    ),
    Case(
        "async_calendar",
        ("SPY",),
        ("IEF",),
        (2,),
        (8,),
        trade_date_max="2002-09-01",
    ),
    Case(
        "reference_597",
        ("SPY", "IEF", "TLT"),
        ("SPY",),
        (1,),
        tuple(range(2, 201)),
        deflate=True,
        vectorized=True,
    ),
)

VENDOR_REFERENCE = Case(
    "reference_597_vendor",
    ("SPY", "IEF", "TLT"),
    ("SPY",),
    (1,),
    tuple(range(2, 201)),
    deflate=True,
    deflate_sims=20000,
    vectorized=True,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(
        args, cwd=cwd, check=True, text=True, stdout=subprocess.PIPE
    ).stdout.strip()


def prepare_upstream(source: str) -> None:
    UPSTREAM_DIR.parent.mkdir(parents=True, exist_ok=True)
    if not UPSTREAM_DIR.exists():
        run("git", "clone", "--no-checkout", source, str(UPSTREAM_DIR))
    run("git", "checkout", "--detach", UPSTREAM_SHA, cwd=UPSTREAM_DIR)
    if run("git", "rev-parse", "HEAD", cwd=UPSTREAM_DIR) != UPSTREAM_SHA:
        raise RuntimeError("upstream checkout is not the pinned commit")
    if run("git", "status", "--porcelain", "--untracked-files=no", cwd=UPSTREAM_DIR):
        raise RuntimeError("upstream tracked files are modified")
    if (
        REFERENCE_COMMAND
        not in (UPSTREAM_DIR / "INTERPRETING_DEFLATION.md").read_text()
    ):
        raise RuntimeError("published 597-candidate command differs from pinned source")


def prepare_environment() -> Path:
    if not LOCK.is_file():
        raise RuntimeError("missing tools/upstream-capture.lock")
    python = ENV_DIR / "bin" / "python"
    if not python.exists():
        run("uv", "venv", "--python", "3.12", str(ENV_DIR))
    run("uv", "pip", "sync", "--python", str(python), str(LOCK))
    return python


def synthetic_prices(path: Path) -> None:
    """Construct independent, non-vendor price paths with an early IEF gap."""
    path.parent.mkdir(parents=True, exist_ok=True)
    first = date(2001, 1, 2)
    rows: list[tuple[str, str, str, str]] = []
    session = 0
    for offset in range(1200):
        day = first + timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        spy = 100.0 * math.exp(
            0.00024 * session
            + 0.035 * math.sin(session / 13.0)
            + 0.012 * math.sin(session / 3.7)
        )
        ief = 85.0 * math.exp(
            0.00011 * session
            + 0.025 * math.sin(session / 21.0 + 0.7)
            + 0.008 * math.sin(session / 5.1)
        )
        tlt = 70.0 * math.exp(
            0.00007 * session
            + 0.045 * math.sin(session / 31.0 + 1.3)
            + 0.011 * math.sin(session / 7.3)
        )
        rows.append(
            (
                day.isoformat(),
                format(spy, ".15g"),
                format(ief, ".15g") if session >= 260 else "",
                format(tlt, ".15g") if session >= 300 else "",
            )
        )
        session += 1
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("Date", "SPY", "IEF", "TLT"))
        writer.writerows(rows)


def encode(value: Any) -> Any:
    import numpy as np
    import pandas as pd

    if isinstance(value, (pd.Timestamp, date)):
        return (
            value.date().isoformat()
            if isinstance(value, pd.Timestamp)
            else value.isoformat()
        )
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, dict):
        return {str(key): encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(item) for item in value]
    return value


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(
            encode(payload), sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n",
        encoding="utf-8",
    )


def capture_case(case: Case, price_file: Path, output: Path) -> dict[str, Any]:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    sys.path.insert(0, str(UPSTREAM_DIR))
    from xma.backtest import report_average_system, report_system
    from xma.data import prices_from_file, read_price_file
    from xma.deflation import analyze_deflation_for_trade
    from xma.fast_search import vectorized_summary_rows
    from xma.signals import precompute_moving_averages

    frame = read_price_file(str(price_file))
    requested = set(case.signals + case.trades)
    if case.down_symbol:
        requested.add(case.down_symbol)
    prices = {symbol: prices_from_file(frame, symbol) for symbol in sorted(requested)}
    if any(series is None for series in prices.values()):
        raise ValueError(f"{case.name}: missing symbol in price file")
    signals = {symbol: prices[symbol] for symbol in case.signals}
    trades = {symbol: prices[symbol] for symbol in case.trades}
    down = prices[case.down_symbol] if case.down_symbol else None
    common = next(iter(signals.values())).index
    for series in (
        list(signals.values())[1:]
        + list(trades.values())
        + ([down] if down is not None else [])
    ):
        common = common.intersection(series.index)
    common = common.sort_values()
    longest = max(max(case.fast), max(case.slow))
    first_signal = max(series.index[longest - 1] for series in signals.values())
    dates_with_signal = common[common >= first_signal]
    if len(dates_with_signal) <= 1 + case.lag:
        raise ValueError(f"{case.name}: insufficient common history")
    common_start = dates_with_signal[1 + case.lag]
    maximum = pd.Timestamp(case.trade_date_max) if case.trade_date_max else None
    args = argparse.Namespace(
        down_pos=case.down_pos,
        cost=case.cost,
        cash_rate=0.03,
        lag=case.lag,
        down_symbol=case.down_symbol,
        days=0,
        terse=True,
        common_window=True,
        deflate=case.deflate,
        annual=case.annual,
        trade_date_min=None,
        trade_date_max=maximum,
        effective_trade_date_min=common_start,
        search_block_size=512,
        _ma_length_cache=precompute_moving_averages(
            signals, set(case.fast + case.slow)
        ),
        _signal_event_cache={},
    )
    rows: list[dict[str, Any]] = []
    report_text = io.StringIO()
    with contextlib.redirect_stdout(report_text):
        if case.vectorized:
            fast_rows = vectorized_summary_rows(
                args,
                case.signals,
                case.fast,
                case.slow,
                case.thresholds,
                case.trades,
                signals,
                trades,
                down,
            )
            if fast_rows is None:
                raise ValueError(
                    f"{case.name}: vectorized upstream path declined input"
                )
            rows.extend(fast_rows)
        else:
            for signal, fast, slow, threshold, trade in itertools.product(
                case.signals, case.fast, case.slow, case.thresholds, case.trades
            ):
                report_system(
                    signal,
                    fast,
                    slow,
                    threshold,
                    trade,
                    case.down_symbol,
                    args,
                    signals[signal],
                    trades[trade],
                    down,
                    rows,
                )
        if case.average:
            for trade in case.trades:
                report_average_system(
                    trade,
                    case.down_symbol,
                    args,
                    case.signals,
                    case.fast,
                    case.slow,
                    case.thresholds,
                    signals,
                    trades,
                    down,
                    rows,
                )

    deflation: dict[str, Any] = {}
    if case.deflate:
        for trade in case.trades:
            trade_rows = [row for row in rows if row["trade"] == trade.upper()]
            result = analyze_deflation_for_trade(trade_rows, case.deflate_sims, 12345)
            if result is None:
                raise ValueError(f"{case.name}: no deflation result for {trade}")
            deflation[trade] = {
                key: value
                for key, value in result.items()
                if key not in {"candidates", "frame", "correlation", "best"}
            }
            best = result["best"]
            deflation[trade]["best"] = {
                "signal": best["signal"],
                "fast": best["fast"],
                "slow": best["slow"],
                "trade": best["trade"],
                "sharpe": best["sharpe"],
                "dsr": best.get("_dsr"),
                "max_p": best.get("_max_test_p"),
            }

    candidate_count = sum(row["type"] == "Strategy" for row in rows)
    expected_count = (
        len(case.signals)
        * len(case.trades)
        * len(case.fast)
        * len(case.slow)
        * len(case.thresholds)
    )
    if candidate_count != expected_count:
        raise ValueError(
            f"{case.name}: expected {expected_count} strategies, got {candidate_count}"
        )
    output.mkdir(parents=True, exist_ok=True)
    row_ids: list[str] = []
    return_dates: list[date] = []
    return_values: list[float] = []
    encoded_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        row_id = f"r{index:04d}"
        series = row.get("_returns")
        if series is not None:
            for timestamp, value in series.items():
                row_ids.append(row_id)
                return_dates.append(timestamp.date())
                return_values.append(float(value))
        fields = {key: value for key, value in row.items() if key != "_returns"}
        encoded_rows.append({"id": row_id, **encode(fields)})
    rows_file = output / f"{case.name}.json"
    returns_file = output / f"{case.name}.parquet"
    annual_section = []
    if case.annual:
        for section in report_text.getvalue().split("Calendar-year returns ")[1:]:
            annual_section.append("Calendar-year returns " + section.split("\n\n")[0])
        if not annual_section:
            raise ValueError(f"{case.name}: annual output absent")
    write_json(
        rows_file,
        {
            "case": encode(case.__dict__),
            "rows": encoded_rows,
            "deflation": deflation,
            "annual_report": annual_section,
        },
    )
    table = pa.table(
        {
            "row_id": pa.array(row_ids, type=pa.string()),
            "date": pa.array(return_dates, type=pa.date32()),
            "daily_return": pa.array(return_values, type=pa.float64()),
        }
    )
    pq.write_table(table, returns_file, compression="zstd", version="2.6")
    return {
        "name": case.name,
        "source": "vendor-derived" if case is VENDOR_REFERENCE else "synthetic",
        "candidate_count": candidate_count,
        "row_count": len(rows),
        "return_count": len(return_values),
        "rows_file": rows_file.name,
        "rows_sha256": sha256(rows_file),
        "returns_file": returns_file.name,
        "returns_sha256": sha256(returns_file),
    }


def worker(mode: str) -> None:
    output = VENDOR_DIR if mode == "vendor" else FIXTURES / "golden"
    price_file = (
        UPSTREAM_DIR / "prices.csv"
        if mode == "vendor"
        else FIXTURES / "synthetic_prices.csv"
    )
    if mode == "synthetic":
        synthetic_prices(price_file)
    elif sha256(price_file) != VENDOR_INPUT_SHA:
        raise ValueError("pinned upstream prices.csv hash differs from the M1 source")
    cases = (VENDOR_REFERENCE,) if mode == "vendor" else SYNTHETIC_CASES
    results = [capture_case(case, price_file, output) for case in cases]
    if mode == "vendor":
        reference = json.loads((output / "reference_597_vendor.json").read_text())
        analysis = reference["deflation"]["SPY"]
        first = reference["rows"][0]
        best = analysis["best"]
        if (
            analysis["raw_count"] != 597
            or analysis["common_observations"] != 5878
            or first["start"] != "2003-05-15"
            or first["end"] != "2026-09-24"
            or first["trade"] != "SPY"
            or (best["signal"], best["fast"], best["slow"], best["trade"])
            != ("IEF", 1, 7, "SPY")
        ):
            raise ValueError("vendor reference differs from the pinned published run")
    with price_file.open(newline="", encoding="utf-8") as stream:
        input_dates = [row["Date"] for row in csv.DictReader(stream) if row["SPY"]]
    manifest = {
        "schema_version": 1,
        "upstream_commit": UPSTREAM_SHA,
        "upstream_repository": UPSTREAM_URL,
        "upstream_dependency_lock_sha256": sha256(LOCK),
        "input_file": price_file.name,
        "input_sha256": sha256(price_file),
        "input_first_date": min(input_dates),
        "input_last_date": max(input_dates),
        "environment": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "pandas", "pyarrow")
        },
        "reference_command": REFERENCE_COMMAND,
        "fixtures": results,
    }
    write_json(
        output.parent / "manifest.json"
        if mode == "synthetic"
        else output / "manifest.json",
        manifest,
    )
    print(f"Captured {len(results)} {mode} cases")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("synthetic", "vendor"), default="synthetic")
    parser.add_argument("--upstream-source", default=UPSTREAM_URL)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.mode)
        return
    prepare_upstream(args.upstream_source)
    python = prepare_environment()
    subprocess.run(
        [str(python), str(Path(__file__).resolve()), "--worker", "--mode", args.mode],
        check=True,
        env={**os.environ, "PYTHONHASHSEED": "0"},
    )


if __name__ == "__main__":
    main()
