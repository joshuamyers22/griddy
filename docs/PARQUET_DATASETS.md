# Parquet Dataset Contract

`griddy-dataset` publishes the reference market-observation CSV as an
immutable, date-partitioned Parquet dataset. The implementation uses Polars'
native stable single-file writer inside deterministic partition directories. It
does not use `PartitionBy` or inferred Hive schemas because those APIs are marked
unstable by Polars.

## M2 adjusted-close input

`publish-upstream` accepts the pinned `xma` wide CSV shape: `Date` followed by
uppercase ticker columns such as `SPY,IEF,TLT`. `Date,Adj Close` is accepted
only when `--legacy-symbol` identifies its ticker. Polars is the primary
in-memory interface through `ingest_upstream_prices(DataFrame | LazyFrame)`;
`load_upstream_prices_csv` reads file bytes with Polars. An optional
`ingest_upstream_prices_pandas` adapter accepts a pandas DataFrame after
installing `griddy[pandas]`. It converts once into Polars and uses the same
validation and publisher; pandas is absent from the default installation.

Dates must be real, unique, strictly increasing `YYYY-MM-DD` session dates.
Ticker names must be uppercase. Present adjusted closes must be positive,
finite numbers. Blank price cells remain absent observations: no price is
filled, and the ingest result reports missing cells by ticker. Quote unit and
calendar are explicit caller declarations, not inferred from ticker names or
checked against an exchange schedule. The publisher does not invent an
intraday timestamp or claim point-in-time availability for adjusted prices.

The `upstream-adjusted-closes/v1` contract is a long table with `year` (Int32),
`event_date` (Date), `instrument` (String), `adjusted_close` (Float64),
`quote_unit` (String), and `calendar` (String). `(event_date, instrument)` is
unique, and `year` must equal the event date's year. Calendar and quote unit
must be constant within one version. The dataset is partitioned by year to
avoid a file per session. Publication, manifest hashing, and verified reads
use the same immutable writer described below.

```sh
uv run griddy-dataset publish-upstream \
  tests/fixtures/upstream/synthetic_prices.csv .work/processed \
  --dataset-version synthetic-m2-v1 \
  --source-id synthetic/m1-prices \
  --revision "$(git rev-parse HEAD)" \
  --created-at-utc "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --quote-unit synthetic --calendar synthetic-weekdays
uv run griddy-dataset verify .work/processed/synthetic-m2-v1 \
  --kind upstream-prices
```

CSV publications hash the exact input bytes. In-memory Polars and adapted
pandas publications hash their canonical Polars CSV serialization; callers
should set a `source_id` that identifies this in-memory source. The pinned
upstream vendor CSV and any derived Parquet dataset remain local under ignored
`.work/` until source terms permit redistribution and CI access.

## Published layout

```text
<root>/<dataset-version>/
├── event_date=YYYY-MM-DD/part-00000.parquet
├── manifest.json
└── manifest.sha256
```

The contract requires exact ordered columns and dtypes: UTC microsecond
timestamps, an explicit event date, string instrument and unit, and
`Decimal(20, 8)` values. Partition, primary-key, sort, nullability, and
market-observation invariants are code, not prose. Publication sorts canonically,
writes Zstandard-compressed files with statistics, writes the manifest last, and
renames a same-filesystem staging directory into place. Existing versions are
never overwritten.

The manifest records its schema version, dataset and contract versions, portable
source identifier and hash, code revision, UTC creation time, writer versions,
storage settings, row count, and every file's relative path, partition, size,
row count, and SHA-256 hash. `manifest.sha256` protects the manifest itself.

## Verification and reads

Verification fails closed on malformed manifests, checksum or file-set drift,
unsafe or symbolic-link paths, unknown files, schema changes, duplicate primary
keys, null violations, partition/data disagreement, date/timestamp disagreement,
or noncanonical row order. Only after verification does
`scan_verified_dataset` return a lazy Polars scan. Hive inference is explicitly
disabled because partition columns remain inside every file.

```sh
uv run griddy-dataset publish data/example.csv data/processed \
  --dataset-version 2026-01-02.1 \
  --source-id fixture/example.csv \
  --revision "$(git rev-parse HEAD)" \
  --created-at-utc "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

uv run griddy-dataset verify data/processed/2026-01-02.1
```

## Compatibility and trust boundaries

`assert_backward_compatible` permits only a higher schema version with existing
columns, order, dtypes, nullability, partitions, keys, sorting, and invariants
unchanged. New fields must be nullable and appended. This is a conservative
release check; consumers still need an explicit mixed-version read/migration
policy before schemas coexist.

SHA-256 detects accidental or uncoordinated change but does not authenticate a
publisher: an attacker able to replace the dataset can replace its checksums.
Use access controls, object retention/versioning, and signed provenance where the
threat model requires them. Directory rename gives atomic visibility on one local
filesystem, not crash durability, distributed object-store transactions, or
automatic cleanup after process termination. The verifier confirms declared
writer settings, but it does not inspect every Parquet page's physical encoding.

Dataset manifests may expose sensitive identifiers, values, and lineage. Apply
the project's classification, authorization, encryption, retention, deletion,
and backup policy. Never commit client, account, credential, or restricted market
data.

## Polars references

- [Parquet writer](https://docs.pola.rs/api/python/stable/reference/api/polars.DataFrame.write_parquet.html)
- [Lazy Parquet scan](https://docs.pola.rs/api/python/stable/reference/api/polars.scan_parquet.html)
- [Parquet schema reader](https://docs.pola.rs/api/python/stable/reference/api/polars.read_parquet_schema.html)
- [Hive partitioning](https://docs.pola.rs/user-guide/io/hive/)
