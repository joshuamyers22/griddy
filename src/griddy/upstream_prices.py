"""Strict Polars-first ingest of upstream adjusted-close price tables."""

from __future__ import annotations

import csv
import hashlib
import importlib
import io
import re
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl

from .dataset import (
    DatasetContractError,
    publish_dataset,
    upstream_adjusted_close_contract,
    validate_dataset_frame,
)

SYMBOL = re.compile(r"^[A-Z^][A-Z0-9.^_-]*$")
DATE_TEXT = re.compile(r"^\d{4}-\d{2}-\d{2}$")
POSITIVE_NUMBER = re.compile(r"^\+?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?$")


@dataclass(frozen=True, slots=True)
class UpstreamPrices:
    frame: pl.DataFrame
    source_sha256: str
    source_kind: str
    input_dates: int
    missing_by_symbol: dict[str, int]


def _nonblank_label(label: str, name: str) -> str:
    if not label or label != label.strip():
        raise DatasetContractError(f"{name} must be nonblank and trimmed")
    return label


def ingest_upstream_prices(
    source: pl.DataFrame | pl.LazyFrame,
    *,
    quote_unit: str,
    calendar: str,
    legacy_symbol: str | None = None,
) -> UpstreamPrices:
    """Validate a wide upstream table, preserving blanks as absent observations.

    A Polars frame is the primary API. The source hash identifies its canonical
    CSV serialization, not a prior file from which the frame may have originated.
    """
    quote_unit = _nonblank_label(quote_unit, "quote_unit")
    calendar = _nonblank_label(calendar, "calendar")
    frame = source.collect() if isinstance(source, pl.LazyFrame) else source
    if frame.width < 2 or frame.columns[0] != "Date" or frame.height == 0:
        raise DatasetContractError(
            "input needs Date first, prices, and at least one row"
        )
    if len(frame.columns) != len(set(frame.columns)):
        raise DatasetContractError("duplicate input columns are not allowed")

    price_columns = frame.columns[1:]
    if price_columns == ["Adj Close"]:
        if legacy_symbol is None or not SYMBOL.fullmatch(legacy_symbol):
            raise DatasetContractError("Adj Close requires an uppercase legacy_symbol")
        symbols = [legacy_symbol]
    else:
        if legacy_symbol is not None or "Adj Close" in price_columns:
            raise DatasetContractError("legacy_symbol is only valid for Date,Adj Close")
        symbols = price_columns
        if not all(SYMBOL.fullmatch(symbol) for symbol in symbols):
            raise DatasetContractError("price columns must be uppercase ticker symbols")

    digest = hashlib.sha256(frame.write_csv().encode("utf-8")).hexdigest()
    text = frame.select(pl.all().cast(pl.String))
    dates = text.get_column("Date").to_list()
    parsed_dates: list[date] = []
    for date_text in dates:
        if not isinstance(date_text, str) or not DATE_TEXT.fullmatch(date_text):
            raise DatasetContractError("Date must use exact YYYY-MM-DD text")
        try:
            parsed_dates.append(date.fromisoformat(date_text))
        except ValueError as error:
            raise DatasetContractError(
                "Date contains an invalid calendar day"
            ) from error
    if any(
        right <= left
        for left, right in zip(parsed_dates, parsed_dates[1:], strict=False)
    ):
        raise DatasetContractError("Date must be strictly increasing and unique")

    if price_columns == ["Adj Close"]:
        text = text.rename({"Adj Close": symbols[0]})
    missing_by_symbol: dict[str, int] = {}
    for symbol in symbols:
        values = text.get_column(symbol)
        missing_by_symbol[symbol] = values.null_count()
        present = values.drop_nulls().to_list()
        if not present:
            raise DatasetContractError(f"{symbol} has no adjusted closes")
        if any(not POSITIVE_NUMBER.fullmatch(value) for value in present):
            raise DatasetContractError(f"{symbol} contains an invalid adjusted close")

    long = (
        text.unpivot(
            on=symbols,
            index="Date",
            variable_name="instrument",
            value_name="price_text",
        )
        .filter(pl.col("price_text").is_not_null())
        .with_columns(
            pl.col("Date")
            .str.strptime(pl.Date, "%Y-%m-%d", strict=True)
            .alias("event_date"),
            pl.col("price_text").cast(pl.Float64, strict=True).alias("adjusted_close"),
            pl.lit(quote_unit).alias("quote_unit"),
            pl.lit(calendar).alias("calendar"),
        )
        .with_columns(pl.col("event_date").dt.year().cast(pl.Int32).alias("year"))
        .select(upstream_adjusted_close_contract().schema.names())
        .sort("year", "event_date", "instrument")
    )
    validate_dataset_frame(long, upstream_adjusted_close_contract())
    return UpstreamPrices(
        frame=long,
        source_sha256=digest,
        source_kind="polars-canonical-csv",
        input_dates=len(parsed_dates),
        missing_by_symbol=missing_by_symbol,
    )


def load_upstream_prices_csv(
    path: Path,
    *,
    quote_unit: str,
    calendar: str,
    legacy_symbol: str | None = None,
) -> UpstreamPrices:
    """Read raw CSV bytes with Polars and retain their exact SHA-256 identity."""
    content = path.read_bytes()
    try:
        header = next(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
        if len(header) != len(set(header)):
            raise DatasetContractError("duplicate CSV header columns are not allowed")
        frame = pl.read_csv(
            io.BytesIO(content),
            infer_schema=False,
            try_parse_dates=False,
            ignore_errors=False,
        )
    except (UnicodeError, StopIteration, csv.Error, pl.exceptions.PolarsError) as error:
        raise DatasetContractError("invalid upstream price CSV") from error
    ingested = ingest_upstream_prices(
        frame, quote_unit=quote_unit, calendar=calendar, legacy_symbol=legacy_symbol
    )
    return UpstreamPrices(
        frame=ingested.frame,
        source_sha256=hashlib.sha256(content).hexdigest(),
        source_kind="raw-csv",
        input_dates=ingested.input_dates,
        missing_by_symbol=ingested.missing_by_symbol,
    )


def ingest_upstream_prices_pandas(
    source: object,
    *,
    quote_unit: str,
    calendar: str,
    legacy_symbol: str | None = None,
) -> UpstreamPrices:
    """Optional narrow pandas adapter; pandas is never imported by the core path."""
    try:
        pd: Any = importlib.import_module("pandas")
    except ModuleNotFoundError as error:
        raise RuntimeError("install griddy[pandas] for pandas inputs") from error
    if not isinstance(source, pd.DataFrame):
        raise TypeError("source must be a pandas DataFrame")
    pandas_frame: Any = source
    frame: Any = (
        pandas_frame.reset_index()
        if pandas_frame.index.name == "Date" and "Date" not in pandas_frame
        else pandas_frame
    )
    if len(frame.columns) != len(set(frame.columns)):
        raise DatasetContractError("duplicate input columns are not allowed")
    columns: dict[str, list[Any]] = {}
    for name in frame.columns:
        values: list[Any] = []
        for value in frame[name].tolist():
            if bool(pd.isna(value)):
                values.append(None)
            elif name == "Date" and isinstance(value, (date, pd.Timestamp)):
                values.append(
                    value.date().isoformat()
                    if isinstance(value, pd.Timestamp)
                    else value.isoformat()
                )
            else:
                values.append(value)
        columns[str(name)] = values
    adapted = ingest_upstream_prices(
        pl.DataFrame(columns),
        quote_unit=quote_unit,
        calendar=calendar,
        legacy_symbol=legacy_symbol,
    )
    return replace(adapted, source_kind="pandas-adapted-canonical-csv")


def publish_upstream_prices(
    prices: UpstreamPrices,
    root: Path,
    *,
    dataset_version: str,
    source_id: str,
    code_revision: str,
    created_at_utc: datetime,
) -> Path:
    """Publish validated adjusted closes through the versioned Parquet writer."""
    return publish_dataset(
        prices.frame,
        root,
        contract=upstream_adjusted_close_contract(),
        dataset_version=dataset_version,
        source_id=source_id,
        source_sha256=prices.source_sha256,
        code_revision=code_revision,
        created_at_utc=created_at_utc,
    )
