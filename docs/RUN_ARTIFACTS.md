# Single-candidate run artifacts

`publish_reference_run` replays one SMA candidate from a verified
adjusted-close dataset, calculates [core metrics](CORE_METRICS.md), and publishes
an immutable directory at `<root>/<run-id>/`:

```text
<root>/<run-id>/
├── results.parquet
├── returns.parquet
├── manifest.json
└── manifest.sha256
```

`results.parquet` has one typed row for the candidate, signal instrument, trade
instrument, parameters, execution settings, window, strategy metrics, benchmark
metrics, exposure, turnover, and cost. Undefined metrics are null. The
`split_id` is null because this M2 run has no declared train/test split.
`returns.parquet` has one dated row per evaluated return, keyed by the stable
candidate ID, with the signal date, state, weights, returns, turnover, and cost.
The candidate ID hashes the canonical candidate tuple and the SMA space
version; it does not depend on the run ID or input dataset.

```python
from datetime import UTC, datetime
from pathlib import Path

from griddy.engine.artifacts import publish_reference_run, verify_reference_run
from griddy.engine.reference import ReferenceExecution, SmaCrossoverCandidate

dataset = Path(".work/processed/synthetic-m2-v1")
run = publish_reference_run(
    dataset,
    Path(".work/runs"),
    run_id="synthetic-sma-1",
    candidate=SmaCrossoverCandidate("SPY", "SPY", fast=2, slow=8),
    execution=ReferenceExecution(periods_per_year=252, cash_rate=0.03),
    code_revision="replace-with-commit-sha",
    lockfile=Path("uv.lock"),
    evaluated_at_utc=datetime.now(UTC),
)
verify_reference_run(run, input_dataset=dataset, lockfile=Path("uv.lock"), replay=True)
```

The `run-manifest/v1` JSON records the normalized config and search-space
hashes, verified input dataset manifest hash, source identity, code revision,
`uv.lock` hash, library versions, execution model, evaluated window, one
candidate in each count, no random seeds, no declared splits, and the size,
row count, schema version, and SHA-256 of each Parquet file. The
`reproducibility_sha256` hashes those deterministic fields. Run ID and UTC
evaluation time are separate provenance fields, so two equivalent runs have
the same reproducibility hash. `manifest.sha256` covers the complete manifest.

Publication writes into a staging directory and renames it into place; an
existing run ID is refused. Verification checks the manifest and exact file
set, hashes, schemas, candidate ID, return dates, summary consistency, and
optional input dataset and lockfile identity. `replay=True` recomputes the
candidate from the verified input and compares every dated return. Summary
consistency and replay use the installed implementation, so validation of older
runs should use the recorded code revision.

This M2 output is a retrospective, single-candidate artifact. It makes no
point-in-time or out-of-sample claim. The general search result schema,
bounded return chunks, trial ledger, and run CLI remain later work.
