# ai-sdlc

A local-first, vendor-neutral control plane for cost-optimized AI-assisted software development.

The goal is to maximize implementation quality while minimizing **total cost per durable accepted change**—not just token spend. The design replaces the common `frontier plan → cheap implement → retry` pattern with an evidence-driven workflow where deterministic gates, auditable artifacts, and risk-aware model routing control progress.

## Status

**Phase 1A — Schemas and ledger integrity** is implemented on `master`.

| Capability | Status |
|---|---|
| Execution Contract JSON Schema (v0.1.0) | Done |
| Evidence event envelope schema (v0.1.0) | Done |
| RFC 8785 canonical hashing + SHA-256 digests | Done |
| Content-addressed artifact store | Done |
| SQLite append-only event ledger with per-task hash chains | Done |
| Projections, adapters, runtime enforcement, routing | Planned |

See the [design specification](docs/superpowers/specs/2026-07-11-cost-optimized-ai-agent-sdlc-design.md) for the full architecture. The [Phase 1A implementation plan](docs/superpowers/plans/2026-07-11-schemas-and-ledger-integrity.md) describes what shipped in this release.

## Core concepts

The **Execution Package** splits into three artifacts with different semantics:

1. **Execution Contract** — versioned, approved obligations and authority (immutable per approved version).
2. **Context Manifest** — mutable, provenance-bearing repository hypotheses (deferred).
3. **Evidence Record** — append-only facts about execution and results.

Phase 1A establishes the schema and storage foundation for contracts and canonical evidence events. Every significant state change is intended to emit a hash-chained event referencing immutable `sha256:` artifacts.

## Requirements

- Python **3.12+**
- pip

## Installation

```bash
git clone https://github.com/<your-org>/ai-sdlc.git
cd ai-sdlc
pip install -e ".[dev]"
```

## Development

Run the test suite:

```bash
python -m pytest -v
```

Lint:

```bash
python -m ruff check src tests
```

## Project layout

```text
src/aisdlc/
  canonical/          # RFC 8785 JCS serialization and SHA-256 digest helpers
  schemas/            # JSON Schema 2020-12 definitions
  validation/         # Contract and event envelope validation
  artifacts/          # Content-addressed immutable blob store
  ledger/             # SQLite metadata + per-task event hash chains
tests/
  fixtures/           # Sample contracts and event envelopes
docs/superpowers/
  specs/              # Architecture and design documents
  plans/              # Implementation plans
```

## Usage

### Validate an Execution Contract

```python
import json
from pathlib import Path

from aisdlc.schemas.registry import validate_contract_document
from aisdlc.validation.contract import validate_and_hash_contract_document

doc = json.loads(Path("tests/fixtures/contracts/valid_r1_minimal.json").read_text())
validate_contract_document(doc)
body_hash = validate_and_hash_contract_document(doc)
print(body_hash)  # sha256:...
```

Contracts are validated against `execution-contract/v0.1.0.schema.json` with `additionalProperties: false` and conditional requirements for approved status, elevated risk, and network policy.

### Append evidence events to the ledger

```python
import json
from datetime import datetime, timezone
from pathlib import Path
from ulid import ULID

from aisdlc.ledger.store import LedgerStore

store = LedgerStore(Path(".aisdlc/ledger.db"), Path(".aisdlc/artifacts"))

envelope = {
    "event_id": str(ULID()),
    "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "event_type": "contract.drafted",
    "actor": {"kind": "human", "id": "owner"},
    "artifact_refs": [],
    "payload_schema": "contract-drafted/v0.1",
}

stored = store.append_event("TASK-001", envelope, b'{"status": "draft"}')
events = store.get_events("TASK-001")  # verifies hash chain on read
head = store.export_chain_head("TASK-001")
```

`append_event` atomically allocates the next sequence number, links `previous_event_hash`, computes `event_hash`, stores the payload as a content-addressed artifact, and updates the chain head in a single SQLite transaction.

### Store immutable artifacts

```python
from pathlib import Path
from aisdlc.artifacts.store import ArtifactStore

artifacts = ArtifactStore(Path(".aisdlc/artifacts"))
ref = artifacts.put(b'{"example": true}')
data = artifacts.get(ref)  # verifies digest on read
```

## Integrity guarantees (Phase 1A)

- Events are serialized with **RFC 8785 JCS** before hashing.
- `event_hash` is SHA-256 over the canonical event body excluding `event_hash` itself.
- `contract_body_hash` omits `status`, `contract_body_hash`, and `approval_event_refs`.
- Digest references use the `sha256:<lowercase-hex>` format.
- Concurrent appends to the same task are serialized via SQLite `BEGIN IMMEDIATE`.
- Chain verification detects tampering, sequence gaps, and hash mismatches.

## Roadmap

Planned phases from the design spec:

| Phase | Focus |
|---|---|
| 1B | Projections and export |
| 1C | Observational adapters and discovery corpus |
| 2 | Execution runtime and enforcement |
| 3 | Verification subsystem |
| 4 | Context subsystem (retrieval, provenance) |
| 5 | Adaptive routing |
| 6 | Qualified parallelism |

## License

License not yet specified.
