# ADR-009: Polars-first inputs with optional pandas conversion

- Status: accepted
- Date: 2026-09-26
- Owner: Josh Myers
- Supersedes / superseded by: none

## Context

M2 needs strict upstream price ingest. The owner specified Polars inputs as the
default and pandas as a secondary input. The project uses Polars for core
tabular work and has no default pandas dependency.

## Decision

`ingest_upstream_prices` accepts Polars DataFrame and LazyFrame inputs.
`load_upstream_prices_csv` reads CSV bytes with Polars. A separate
`ingest_upstream_prices_pandas` function is available through the optional
`griddy[pandas]` extra. It converts a pandas DataFrame once into Polars, then
uses the same strict validation and versioned Parquet publisher. Core modules
do not import pandas on the default path.

Dates, symbols, prices, missing values, quote units, and calendar declarations
have one shared contract. The pandas adapter does not supply a second numeric
or backtesting implementation. A future yfinance adapter may reuse this
boundary, but is not part of this decision's implementation.

## Consequences and verification

Default installations remain Polars-only. The secondary adapter adds an
optional dependency and must be tested with that extra installed. Tests compare
native Polars and adapted pandas rows, while the default suite exercises CSV,
Polars, strict validation, publication, and verified reads. See
`tests/test_upstream_prices.py` and `docs/PARQUET_DATASETS.md`.
