# Schemas and Ledger Integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Phase 1A of the Cost-Optimized AI Agent SDLC control plane — JSON Schema validation for Execution Contracts and canonical evidence events, plus a local append-only ledger with content-addressed artifacts, RFC 8785 hashing, and atomic per-task event chains.

**Architecture:** A Python 3.12+ library (`aisdlc`) exposes schema validation, canonical hashing, artifact storage, and a SQLite-backed event ledger. Larger payloads live in a content-addressed filesystem store (`sha256:<hex>`); the ledger stores metadata, sequence numbers, and chain heads. Each `append_event` runs in a single SQLite transaction that allocates the next sequence number, links `previous_event_hash`, computes `event_hash`, and updates the chain head.

**Tech Stack:** Python 3.12+, `jsonschema` (Draft 2020-12), `rfc8785`, `python-ulid`, SQLite (stdlib), `pytest`, `ruff`

## Global Constraints

- Phase 1A scope only: schema validation, atomic append, artifact identity, chain verification, crash/concurrency behavior — no projections, adapters, runtime enforcement, routing, or parallelism (spec §26, §21 Phase 1A).
- JSON Schema **2020-12** with explicit types, required properties, enums, conditional requirements, and **unknown-field rejection** (`additionalProperties: false` on all objects unless explicitly open).
- SQLite for ledger metadata; **content-addressed files** for artifact bodies (spec §7.5).
- Event serialization uses **RFC 8785 JSON Canonicalization Scheme (JCS)** before hashing (spec §8.8).
- `event_hash` is **SHA-256** over the canonical event **excluding** `event_hash` itself and **including** `previous_event_hash` (spec §8.8).
- `contract_body_hash` is SHA-256 over the canonical contract with `status`, `contract_body_hash`, and `approval_event_refs` **omitted** (spec §9.2).
- Digest references use the `sha256:<lowercase-hex>` prefix (spec §8.8, §9.2).
- `event_id` values are **ULIDs** (spec §8.8 example).
- Each task allocates its sequence number and updates its chain head **atomically in one SQLite transaction** (spec §8.8).
- Initial `schema_version` is **`0.1.0`** (spec §9.2).
- Impact risk levels: `R0`, `R1`, `R2`, `R3` (spec §12).
- Path authority `path_precedence` is `deny_overrides_allow` (spec §9.2).
- Network `mode` enum: `denied`, `allowlisted` (spec §9.2).
- Contract `status` enum for Phase 1A: `draft`, `approved` (lifecycle in spec §10).
- Tamper-evidence via **signed** chain-head export is **out of scope** for Phase 1A; unsigned chain-head export is included as a hook for Phase 1B (spec §21 Phase 1A exit condition).
- Context Manifest schema and payload-type schemas (e.g. `gate-completed/v0.1`) are **deferred** to later plans; Phase 1A validates the event **envelope** and stores opaque payload artifacts referenced by `payload_ref`.

---

## File Structure

| Path | Responsibility |
|---|---|
| `pyproject.toml` | Project metadata, runtime and dev dependencies, `aisdlc` entry point |
| `src/aisdlc/__init__.py` | Public package surface |
| `src/aisdlc/schemas/execution-contract/v0.1.0.schema.json` | Draft 2020-12 Execution Contract schema |
| `src/aisdlc/schemas/evidence-event/v0.1.0.schema.json` | Draft 2020-12 canonical evidence-event envelope schema |
| `src/aisdlc/schemas/registry.py` | Load schemas by id/version; expose validators |
| `src/aisdlc/canonical/jcs.py` | RFC 8785 canonical serialization |
| `src/aisdlc/canonical/hashing.py` | SHA-256 digests, `sha256:` ref formatting/parsing |
| `src/aisdlc/validation/contract.py` | Contract validation + `contract_body_hash` |
| `src/aisdlc/validation/event.py` | Event envelope validation |
| `src/aisdlc/artifacts/store.py` | Content-addressed immutable artifact read/write/verify |
| `src/aisdlc/ledger/db.py` | SQLite connection, schema DDL, WAL pragmas |
| `src/aisdlc/ledger/models.py` | Typed records: `TaskChainHead`, `StoredEvent`, `ArtifactRecord` |
| `src/aisdlc/ledger/chain.py` | `compute_event_hash`, `verify_task_chain` |
| `src/aisdlc/ledger/store.py` | `append_event`, `get_events`, `export_chain_head` |
| `src/aisdlc/errors.py` | `ValidationError`, `ChainIntegrityError`, `ArtifactMismatchError` |
| `tests/conftest.py` | Temp directory fixtures for DB and artifact store |
| `tests/fixtures/contracts/valid_r1_minimal.json` | Minimal valid draft contract fixture |
| `tests/fixtures/contracts/invalid_unknown_field.json` | Contract with extra top-level field |
| `tests/fixtures/events/valid_envelope.json` | Valid event envelope (pre-hash) |
| `tests/test_canonical.py` | JCS + hashing unit tests |
| `tests/test_contract_schema.py` | Contract schema acceptance/rejection |
| `tests/test_event_schema.py` | Event envelope schema tests |
| `tests/test_artifacts.py` | Artifact store round-trip and digest verification |
| `tests/test_ledger_append.py` | Atomic append and sequencing |
| `tests/test_ledger_chain.py` | Chain verification and corruption detection |
| `tests/test_ledger_crash.py` | Simulated crash / rollback behavior |
| `tests/test_ledger_concurrency.py` | Concurrent append ordering |

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/aisdlc/__init__.py`
- Create: `src/aisdlc/errors.py`
- Create: `tests/conftest.py`
- Create: `tests/test_import.py`

**Interfaces:**
- Consumes: nothing
- Produces: importable `aisdlc` package; `aisdlc.errors.ValidationError` base exception

- [ ] **Step 1: Write the failing test**

```python
# tests/test_import.py
import aisdlc
from aisdlc.errors import ValidationError


def test_package_imports():
    assert hasattr(aisdlc, "__version__")


def test_validation_error_is_exception():
    assert issubclass(ValidationError, Exception)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd c:\Users\ulder\GitHub\ai-sdlc && python -m pytest tests/test_import.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'aisdlc'`

- [ ] **Step 3: Write minimal implementation**

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "aisdlc"
version = "0.1.0"
description = "Cost-optimized AI Agent SDLC control plane — Phase 1A ledger"
requires-python = ">=3.12"
dependencies = [
  "jsonschema>=4.23.0",
  "python-ulid>=3.0.0",
  "rfc8785>=0.1.2",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3.0",
  "ruff>=0.9.0",
]

[tool.hatch.build.targets.wheel]
packages = ["src/aisdlc"]

[tool.hatch.build.targets.wheel.force-include]
"src/aisdlc/schemas" = "aisdlc/schemas"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.ruff]
line-length = 100
target-version = "py312"
```

```python
# src/aisdlc/__init__.py
__version__ = "0.1.0"
```

```python
# src/aisdlc/errors.py
class AisdlcError(Exception):
    """Base error for aisdlc."""


class ValidationError(AisdlcError):
    """Schema or semantic validation failure."""


class ChainIntegrityError(AisdlcError):
    """Event chain hash or sequence integrity failure."""


class ArtifactMismatchError(AisdlcError):
    """Stored artifact bytes do not match declared digest."""
```

```python
# tests/conftest.py
from pathlib import Path

import pytest


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    return tmp_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pip install -e ".[dev]" && python -m pytest tests/test_import.py -v`

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/aisdlc/__init__.py src/aisdlc/errors.py tests/conftest.py tests/test_import.py
git commit -m "chore: scaffold aisdlc Phase 1A project"
```

---

### Task 2: Canonical Serialization and Hashing

**Files:**
- Create: `src/aisdlc/canonical/__init__.py`
- Create: `src/aisdlc/canonical/jcs.py`
- Create: `src/aisdlc/canonical/hashing.py`
- Create: `tests/test_canonical.py`

**Interfaces:**
- Consumes: none
- Produces:
  - `canonicalize_json(obj: dict) -> bytes` — RFC 8785 JCS bytes
  - `sha256_digest(data: bytes) -> str` — lowercase hex, no prefix
  - `digest_ref(data: bytes) -> str` — `sha256:<hex>`
  - `parse_digest_ref(ref: str) -> bytes` — 32-byte digest

- [ ] **Step 1: Write the failing test**

```python
# tests/test_canonical.py
import json

from aisdlc.canonical.hashing import digest_ref, parse_digest_ref, sha256_digest
from aisdlc.canonical.jcs import canonicalize_json


def test_canonicalize_json_is_deterministic():
    obj = {"b": 2, "a": 1, "nested": {"z": True, "y": None}}
    first = canonicalize_json(obj)
    second = canonicalize_json({"a": 1, "b": 2, "nested": {"y": None, "z": True}})
    assert first == second
    assert json.loads(first) == {"a": 1, "b": 2, "nested": {"y": None, "z": True}}


def test_digest_ref_round_trip():
    data = b"artifact-body"
    ref = digest_ref(data)
    assert ref.startswith("sha256:")
    assert parse_digest_ref(ref) == bytes.fromhex(sha256_digest(data))


def test_sha256_digest_is_lowercase_hex():
    assert sha256_digest(b"hello") == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_canonical.py -v`

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# src/aisdlc/canonical/jcs.py
from __future__ import annotations

import rfc8785


def canonicalize_json(obj: dict) -> bytes:
    return rfc8785.dumps(obj).encode("utf-8")
```

```python
# src/aisdlc/canonical/hashing.py
from __future__ import annotations

import hashlib
import re

_DIGEST_REF_RE = re.compile(r"^sha256:([0-9a-f]{64})$")


def sha256_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_ref(data: bytes) -> str:
    return f"sha256:{sha256_digest(data)}"


def parse_digest_ref(ref: str) -> bytes:
    match = _DIGEST_REF_RE.fullmatch(ref)
    if match is None:
        raise ValueError(f"invalid digest reference: {ref!r}")
    return bytes.fromhex(match.group(1))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_canonical.py -v`

Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/aisdlc/canonical tests/test_canonical.py
git commit -m "feat(canonical): add RFC 8785 JCS and SHA-256 digest helpers"
```

---

### Task 3: Execution Contract JSON Schema

**Files:**
- Create: `src/aisdlc/schemas/execution-contract/v0.1.0.schema.json`
- Create: `src/aisdlc/schemas/registry.py`
- Create: `tests/fixtures/contracts/valid_r1_minimal.json`
- Create: `tests/fixtures/contracts/invalid_unknown_field.json`
- Create: `tests/test_contract_schema.py`

**Interfaces:**
- Consumes: `aisdlc.errors.ValidationError`
- Produces:
  - `get_contract_validator() -> jsonschema.protocols.Validator`
  - Schema id: `https://aisdlc.dev/schemas/execution-contract/v0.1.0`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_contract_schema.py
import json
from pathlib import Path

import pytest

from aisdlc.errors import ValidationError
from aisdlc.schemas.registry import get_contract_validator, validate_contract_document

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"


def test_valid_r1_minimal_contract_passes_schema():
    doc = json.loads((FIXTURES / "valid_r1_minimal.json").read_text(encoding="utf-8"))
    validate_contract_document(doc)  # should not raise


def test_unknown_top_level_field_rejected():
    doc = json.loads((FIXTURES / "invalid_unknown_field.json").read_text(encoding="utf-8"))
    with pytest.raises(ValidationError):
        validate_contract_document(doc)


def test_validator_is_draft_2020_12():
    validator = get_contract_validator()
    assert validator.schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
```

Fixture `valid_r1_minimal.json`:

```json
{
  "schema_version": "0.1.0",
  "contract": {
    "contract_id": "CONTRACT-001",
    "contract_version": 1,
    "task_id": "TASK-001",
    "status": "draft",
    "repository": {
      "base_revision": "git:abc123",
      "workspace_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000001",
      "environment_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000002"
    },
    "objective": "Fix the example handler bug described in AC-1.",
    "non_goals": ["Do not change public API surface."],
    "acceptance": [
      {
        "id": "AC-1",
        "criterion": "Example handler returns expected value for nominal input."
      }
    ],
    "impact_risk": {
      "level": "R1",
      "reasons": ["Single component behavior change with no public contract change."]
    },
    "oracle": {
      "independence": "visible",
      "protection": "visible",
      "determinism": "deterministic",
      "coverage": "partial",
      "derived_strength": "partial"
    },
    "constraints": {
      "compatibility": ["Existing callers remain backward compatible."],
      "interfaces": [],
      "invariants": [],
      "performance": []
    },
    "authority": {
      "read_allow": ["**"],
      "read_deny": [],
      "write_allow": ["src/example/**"],
      "write_deny": [".github/workflows/**"],
      "protected_paths": [".github/workflows/**"],
      "path_precedence": "deny_overrides_allow",
      "forbidden_actions": ["push_remote"],
      "network": { "mode": "denied", "hosts": [] },
      "external_side_effects": { "permitted": false, "actions": [] }
    },
    "verification": [
      {
        "id": "V-1",
        "oracle": "command",
        "run": "npm test -- example",
        "expect": { "exit_code": 0 },
        "protected": false
      }
    ],
    "reviewers": { "required": [] },
    "expected_change": {
      "anticipated_edits": ["src/example/handler.ts"],
      "changed_lines_alert": 100
    },
    "rollback": { "required": false, "reason": "Unmerged source patch only." },
    "release": { "mode": "pull_request", "staged_rollout_required": false },
    "budgets": {
      "model_usd": 5.0,
      "context_tokens": 100000,
      "tool_calls": 50,
      "ci_minutes": 20,
      "repair_cycles_total": 3,
      "wall_clock_minutes": 60
    },
    "handoff": {
      "require": ["diff", "check_results", "deviations", "limitations", "residual_risks"]
    },
    "escalation": {
      "on": ["repeated_failure_signature", "ambiguous_acceptance"]
    }
  }
}
```

Fixture `invalid_unknown_field.json`: copy `valid_r1_minimal.json` and add `"unexpected": true` at the top level.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_contract_schema.py -v`

Expected: FAIL — `validate_contract_document` or schema file not found

- [ ] **Step 3: Write minimal implementation**

Create `src/aisdlc/schemas/execution-contract/v0.1.0.schema.json` with the full Draft 2020-12 schema. Key enums and conditionals from spec §9.2:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://aisdlc.dev/schemas/execution-contract/v0.1.0",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "contract"],
  "properties": {
    "schema_version": { "type": "string", "const": "0.1.0" },
    "contract": { "$ref": "#/$defs/contract" }
  },
  "$defs": {
    "digestRef": {
      "type": "string",
      "pattern": "^sha256:[0-9a-f]{64}$"
    },
    "contract": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "contract_id", "contract_version", "task_id", "status", "repository",
        "objective", "non_goals", "acceptance", "impact_risk", "oracle",
        "constraints", "authority", "verification", "reviewers",
        "expected_change", "rollback", "release", "budgets", "handoff", "escalation"
      ],
      "properties": {
        "contract_id": { "type": "string", "minLength": 1 },
        "contract_version": { "type": "integer", "minimum": 1 },
        "task_id": { "type": "string", "minLength": 1 },
        "status": { "type": "string", "enum": ["draft", "approved"] },
        "contract_body_hash": { "$ref": "#/$defs/digestRef" },
        "approval_event_refs": {
          "type": "array",
          "items": { "type": "string", "minLength": 1 }
        },
        "repository": { "$ref": "#/$defs/repository" },
        "objective": { "type": "string", "minLength": 1 },
        "non_goals": { "type": "array", "items": { "type": "string" } },
        "acceptance": {
          "type": "array",
          "minItems": 1,
          "items": { "$ref": "#/$defs/acceptanceItem" }
        },
        "impact_risk": { "$ref": "#/$defs/impactRisk" },
        "oracle": { "$ref": "#/$defs/oracle" },
        "constraints": { "$ref": "#/$defs/constraints" },
        "authority": { "$ref": "#/$defs/authority" },
        "verification": {
          "type": "array",
          "minItems": 1,
          "items": { "$ref": "#/$defs/verificationItem" }
        },
        "reviewers": { "$ref": "#/$defs/reviewers" },
        "expected_change": { "$ref": "#/$defs/expectedChange" },
        "rollback": { "$ref": "#/$defs/rollback" },
        "release": { "$ref": "#/$defs/release" },
        "budgets": { "$ref": "#/$defs/budgets" },
        "handoff": { "$ref": "#/$defs/handoff" },
        "escalation": { "$ref": "#/$defs/escalation" }
      },
      "allOf": [
        {
          "if": { "properties": { "status": { "const": "approved" } }, "required": ["status"] },
          "then": {
            "required": ["contract_body_hash", "approval_event_refs"],
            "properties": {
              "approval_event_refs": { "type": "array", "minItems": 1 }
            }
          }
        },
        {
          "if": {
            "properties": {
              "impact_risk": { "properties": { "level": { "enum": ["R2", "R3"] } } }
            }
          },
          "then": {
            "properties": {
              "constraints": {
                "required": ["interfaces"],
                "properties": {
                  "interfaces": { "type": "array", "minItems": 1 }
                }
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "impact_risk": { "properties": { "level": { "const": "R3" } } }
            }
          },
          "then": {
            "required": ["rollback"],
            "properties": {
              "rollback": {
                "required": ["required", "plan"],
                "properties": {
                  "required": { "const": true },
                  "plan": { "type": "string", "minLength": 1 }
                }
              },
              "release": {
                "required": ["staged_rollout_required"],
                "properties": { "staged_rollout_required": { "const": true } }
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "authority": {
                "properties": { "network": { "properties": { "mode": { "const": "allowlisted" } } } }
              }
            }
          },
          "then": {
            "properties": {
              "authority": {
                "properties": {
                  "network": {
                    "required": ["hosts"],
                    "properties": { "hosts": { "type": "array", "minItems": 1 } }
                  }
                }
              }
            }
          }
        }
      ]
    },
    "repository": {
      "type": "object",
      "additionalProperties": false,
      "required": ["base_revision", "workspace_digest", "environment_digest"],
      "properties": {
        "base_revision": { "type": "string", "pattern": "^git:[0-9a-f]{7,40}$" },
        "workspace_digest": { "$ref": "#/$defs/digestRef" },
        "environment_digest": { "$ref": "#/$defs/digestRef" },
        "lockfile_digests": {
          "type": "array",
          "items": { "$ref": "#/$defs/digestRef" }
        }
      }
    },
    "acceptanceItem": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "criterion"],
      "properties": {
        "id": { "type": "string", "pattern": "^AC-[0-9]+$" },
        "criterion": { "type": "string", "minLength": 1 }
      }
    },
    "impactRisk": {
      "type": "object",
      "additionalProperties": false,
      "required": ["level", "reasons"],
      "properties": {
        "level": { "type": "string", "enum": ["R0", "R1", "R2", "R3"] },
        "reasons": { "type": "array", "minItems": 1, "items": { "type": "string" } }
      }
    },
    "oracle": {
      "type": "object",
      "additionalProperties": false,
      "required": ["independence", "protection", "determinism", "coverage", "derived_strength"],
      "properties": {
        "independence": { "type": "string", "enum": ["independent", "visible", "generated"] },
        "protection": { "type": "string", "enum": ["hidden", "visible", "none"] },
        "determinism": { "type": "string", "enum": ["deterministic", "flaky", "unknown"] },
        "coverage": { "type": "string", "enum": ["full", "partial", "weak"] },
        "derived_strength": { "type": "string", "enum": ["strong", "partial", "weak"] },
        "notes": { "type": "string" }
      }
    },
    "constraints": {
      "type": "object",
      "additionalProperties": false,
      "required": ["compatibility", "interfaces", "invariants", "performance"],
      "properties": {
        "compatibility": { "type": "array", "items": { "type": "string" } },
        "interfaces": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["ref", "rule"],
            "properties": {
              "ref": { "type": "string", "minLength": 1 },
              "rule": { "type": "string", "minLength": 1 }
            }
          }
        },
        "invariants": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["id", "rule"],
            "properties": {
              "id": { "type": "string", "pattern": "^INV-[0-9]+$" },
              "rule": { "type": "string", "minLength": 1 }
            }
          }
        },
        "performance": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["metric", "maximum_regression_percent"],
            "properties": {
              "metric": { "type": "string", "minLength": 1 },
              "maximum_regression_percent": { "type": "number", "minimum": 0 }
            }
          }
        }
      }
    },
    "authority": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "read_allow", "read_deny", "write_allow", "write_deny",
        "protected_paths", "path_precedence", "forbidden_actions",
        "network", "external_side_effects"
      ],
      "properties": {
        "read_allow": { "type": "array", "items": { "type": "string" } },
        "read_deny": { "type": "array", "items": { "type": "string" } },
        "write_allow": { "type": "array", "items": { "type": "string" } },
        "write_deny": { "type": "array", "items": { "type": "string" } },
        "protected_paths": { "type": "array", "items": { "type": "string" } },
        "path_precedence": { "type": "string", "const": "deny_overrides_allow" },
        "forbidden_actions": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": [
              "modify_protected_evaluator",
              "push_remote",
              "deploy",
              "migrate_data",
              "rotate_secrets"
            ]
          }
        },
        "network": {
          "type": "object",
          "additionalProperties": false,
          "required": ["mode", "hosts"],
          "properties": {
            "mode": { "type": "string", "enum": ["denied", "allowlisted"] },
            "hosts": { "type": "array", "items": { "type": "string" } }
          }
        },
        "external_side_effects": {
          "type": "object",
          "additionalProperties": false,
          "required": ["permitted", "actions"],
          "properties": {
            "permitted": { "type": "boolean" },
            "actions": { "type": "array", "items": { "type": "string" } }
          }
        }
      }
    },
    "verificationItem": {
      "type": "object",
      "additionalProperties": false,
      "required": ["id", "oracle", "run", "expect", "protected"],
      "properties": {
        "id": { "type": "string", "pattern": "^V-[0-9]+$" },
        "oracle": { "type": "string", "enum": ["command", "reviewer", "human"] },
        "run": { "type": "string", "minLength": 1 },
        "expect": {
          "type": "object",
          "additionalProperties": false,
          "required": ["exit_code"],
          "properties": { "exit_code": { "type": "integer" } }
        },
        "protected": { "type": "boolean" }
      }
    },
    "reviewers": {
      "type": "object",
      "additionalProperties": false,
      "required": ["required"],
      "properties": {
        "required": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["role", "condition"],
            "properties": {
              "role": {
                "type": "string",
                "enum": [
                  "human_owner",
                  "different_provider_frontier",
                  "security_specialist",
                  "domain_specialist"
                ]
              },
              "condition": { "type": "string", "minLength": 1 }
            }
          }
        }
      }
    },
    "expectedChange": {
      "type": "object",
      "additionalProperties": false,
      "required": ["anticipated_edits", "changed_lines_alert"],
      "properties": {
        "anticipated_edits": { "type": "array", "items": { "type": "string" } },
        "changed_lines_alert": { "type": "integer", "minimum": 1 }
      }
    },
    "rollback": {
      "type": "object",
      "additionalProperties": false,
      "required": ["required"],
      "properties": {
        "required": { "type": "boolean" },
        "reason": { "type": "string" },
        "plan": { "type": "string" }
      }
    },
    "release": {
      "type": "object",
      "additionalProperties": false,
      "required": ["mode", "staged_rollout_required"],
      "properties": {
        "mode": { "type": "string", "enum": ["pull_request", "direct", "staged"] },
        "staged_rollout_required": { "type": "boolean" }
      }
    },
    "budgets": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "model_usd", "context_tokens", "tool_calls",
        "ci_minutes", "repair_cycles_total", "wall_clock_minutes"
      ],
      "properties": {
        "model_usd": { "type": "number", "minimum": 0 },
        "context_tokens": { "type": "integer", "minimum": 1 },
        "tool_calls": { "type": "integer", "minimum": 1 },
        "ci_minutes": { "type": "integer", "minimum": 0 },
        "repair_cycles_total": { "type": "integer", "minimum": 0, "maximum": 10 },
        "wall_clock_minutes": { "type": "integer", "minimum": 1 }
      }
    },
    "handoff": {
      "type": "object",
      "additionalProperties": false,
      "required": ["require"],
      "properties": {
        "require": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "string",
            "enum": [
              "diff",
              "changed_files_with_reasons",
              "acceptance_matrix",
              "check_results",
              "deviations",
              "limitations",
              "residual_risks"
            ]
          }
        }
      }
    },
    "escalation": {
      "type": "object",
      "additionalProperties": false,
      "required": ["on"],
      "properties": {
        "on": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "string",
            "enum": [
              "snapshot_mismatch",
              "required_scope_expansion",
              "destructive_action",
              "ambiguous_acceptance",
              "repeated_failure_signature"
            ]
          }
        }
      }
    }
  }
}
```

```python
# src/aisdlc/schemas/registry.py
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from aisdlc.errors import ValidationError


@lru_cache(maxsize=1)
def get_contract_validator() -> Draft202012Validator:
    raw = resources.files("aisdlc.schemas.execution-contract").joinpath("v0.1.0.schema.json").read_text(
        encoding="utf-8"
    )
    schema = json.loads(raw)
    return Draft202012Validator(schema)


def validate_contract_document(doc: dict[str, Any]) -> None:
    validator = get_contract_validator()
    errors = sorted(validator.iter_errors(doc), key=lambda e: e.path)
    if errors:
        messages = "; ".join(e.message for e in errors)
        raise ValidationError(messages)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_contract_schema.py -v`

Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/aisdlc/schemas tests/fixtures/contracts tests/test_contract_schema.py
git commit -m "feat(schema): add Execution Contract JSON Schema v0.1.0"
```

---

### Task 4: Contract Body Hashing

**Files:**
- Create: `src/aisdlc/validation/contract.py`
- Create: `tests/test_contract_hash.py`

**Interfaces:**
- Consumes: `canonicalize_json`, `digest_ref`, `validate_contract_document`
- Produces:
  - `contract_body_for_hash(contract: dict) -> dict`
  - `compute_contract_body_hash(contract: dict) -> str` — returns `sha256:<hex>`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_contract_hash.py
import json
from pathlib import Path

from aisdlc.validation.contract import compute_contract_body_hash, contract_body_for_hash

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"


def test_contract_body_hash_omits_status_and_hash_fields():
    doc = json.loads((FIXTURES / "valid_r1_minimal.json").read_text(encoding="utf-8"))
    contract = doc["contract"]
    body = contract_body_for_hash(contract)
    assert "status" not in body
    assert "contract_body_hash" not in body
    assert "approval_event_refs" not in body


def test_contract_body_hash_is_stable():
    doc = json.loads((FIXTURES / "valid_r1_minimal.json").read_text(encoding="utf-8"))
    first = compute_contract_body_hash(doc["contract"])
    second = compute_contract_body_hash(doc["contract"])
    assert first == second
    assert first.startswith("sha256:")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_contract_hash.py -v`

Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

```python
# src/aisdlc/validation/contract.py
from __future__ import annotations

import copy
from typing import Any

from aisdlc.canonical.hashing import digest_ref
from aisdlc.canonical.jcs import canonicalize_json
from aisdlc.schemas.registry import validate_contract_document

_OMIT_FOR_HASH = frozenset({"status", "contract_body_hash", "approval_event_refs"})


def contract_body_for_hash(contract: dict[str, Any]) -> dict[str, Any]:
    body = copy.deepcopy(contract)
    for key in _OMIT_FOR_HASH:
        body.pop(key, None)
    return body


def compute_contract_body_hash(contract: dict[str, Any]) -> str:
    body = contract_body_for_hash(contract)
    return digest_ref(canonicalize_json(body))


def validate_and_hash_contract_document(doc: dict[str, Any]) -> str:
    validate_contract_document(doc)
    return compute_contract_body_hash(doc["contract"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_contract_hash.py -v`

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/aisdlc/validation/contract.py tests/test_contract_hash.py
git commit -m "feat(validation): compute canonical contract body hash"
```

---

### Task 5: Evidence Event Envelope Schema

**Files:**
- Create: `src/aisdlc/schemas/evidence-event/v0.1.0.schema.json`
- Create: `src/aisdlc/validation/event.py`
- Create: `tests/fixtures/events/valid_envelope.json`
- Create: `tests/test_event_schema.py`

**Interfaces:**
- Consumes: `ValidationError`, schema registry pattern from Task 3
- Produces:
  - `get_event_validator() -> Draft202012Validator`
  - `validate_event_envelope(event: dict) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_event_schema.py
import json
from pathlib import Path

import pytest

from aisdlc.errors import ValidationError
from aisdlc.validation.event import validate_event_envelope

FIXTURES = Path(__file__).parent / "fixtures" / "events"


def test_valid_event_envelope_passes():
    event = json.loads((FIXTURES / "valid_envelope.json").read_text(encoding="utf-8"))
    validate_event_envelope(event)


def test_missing_event_id_rejected():
    event = json.loads((FIXTURES / "valid_envelope.json").read_text(encoding="utf-8"))
    del event["event_id"]
    with pytest.raises(ValidationError):
        validate_event_envelope(event)
```

Fixture `valid_envelope.json`:

```json
{
  "event_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "task_id": "TASK-001",
  "sequence": 1,
  "occurred_at": "2026-07-11T14:36:00Z",
  "event_type": "contract.drafted",
  "actor": { "kind": "human", "id": "owner" },
  "artifact_refs": [],
  "payload_schema": "contract-drafted/v0.1",
  "payload_ref": "sha256:00000000000000000000000000000000000000000000000000000000000000aa",
  "previous_event_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000"
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_event_schema.py -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://aisdlc.dev/schemas/evidence-event/v0.1.0",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "event_id", "task_id", "sequence", "occurred_at", "event_type",
    "actor", "artifact_refs", "payload_schema", "payload_ref", "previous_event_hash"
  ],
  "properties": {
    "event_id": { "type": "string", "minLength": 1 },
    "task_id": { "type": "string", "minLength": 1 },
    "sequence": { "type": "integer", "minimum": 1 },
    "occurred_at": { "type": "string", "format": "date-time" },
    "event_type": {
      "type": "string",
      "pattern": "^[a-z][a-z0-9]*(\\.[a-z][a-z0-9]*)+$"
    },
    "actor": {
      "type": "object",
      "additionalProperties": false,
      "required": ["kind", "id"],
      "properties": {
        "kind": { "type": "string", "enum": ["human", "model", "tool", "system"] },
        "id": { "type": "string", "minLength": 1 }
      }
    },
    "artifact_refs": {
      "type": "array",
      "items": { "type": "string", "pattern": "^sha256:[0-9a-f]{64}$" }
    },
    "payload_schema": { "type": "string", "minLength": 1 },
    "payload_ref": { "type": "string", "pattern": "^sha256:[0-9a-f]{64}$" },
    "previous_event_hash": { "type": "string", "pattern": "^sha256:[0-9a-f]{64}$" },
    "event_hash": { "type": "string", "pattern": "^sha256:[0-9a-f]{64}$" }
  }
}
```

```python
# src/aisdlc/validation/event.py
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator

from aisdlc.errors import ValidationError


@lru_cache(maxsize=1)
def get_event_validator() -> Draft202012Validator:
    raw = resources.files("aisdlc.schemas.evidence-event").joinpath("v0.1.0.schema.json").read_text(
        encoding="utf-8"
    )
    return Draft202012Validator(json.loads(raw))


def validate_event_envelope(event: dict[str, Any]) -> None:
    validator = get_event_validator()
    errors = sorted(validator.iter_errors(event), key=lambda e: e.path)
    if errors:
        raise ValidationError("; ".join(e.message for e in errors))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_event_schema.py -v`

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/aisdlc/schemas/evidence-event src/aisdlc/validation/event.py tests/fixtures/events tests/test_event_schema.py
git commit -m "feat(schema): add canonical evidence-event envelope v0.1.0"
```

---

### Task 6: Event Hashing and Chain Logic

**Files:**
- Create: `src/aisdlc/ledger/chain.py`
- Create: `tests/test_event_hash.py`

**Interfaces:**
- Consumes: `canonicalize_json`, `digest_ref`, `validate_event_envelope`
- Produces:
  - `GENESIS_PREVIOUS_HASH = "sha256:" + "0" * 64`
  - `event_body_for_hash(event: dict) -> dict` — excludes `event_hash`
  - `compute_event_hash(event: dict) -> str`
  - `verify_task_chain(events: list[dict]) -> None` — raises `ChainIntegrityError` on break

- [ ] **Step 1: Write the failing test**

```python
# tests/test_event_hash.py
import copy
import json
from pathlib import Path

import pytest

from aisdlc.errors import ChainIntegrityError
from aisdlc.ledger.chain import (
    GENESIS_PREVIOUS_HASH,
    compute_event_hash,
    event_body_for_hash,
    verify_task_chain,
)

FIXTURES = Path(__file__).parent / "fixtures" / "events"


def test_event_body_for_hash_excludes_event_hash():
    event = json.loads((FIXTURES / "valid_envelope.json").read_text(encoding="utf-8"))
    event["event_hash"] = "sha256:" + "f" * 64
    body = event_body_for_hash(event)
    assert "event_hash" not in body
    assert body["previous_event_hash"] == event["previous_event_hash"]


def test_compute_event_hash_is_deterministic():
    event = json.loads((FIXTURES / "valid_envelope.json").read_text(encoding="utf-8"))
    assert compute_event_hash(event) == compute_event_hash(copy.deepcopy(event))


def test_verify_task_chain_detects_tamper():
    event = json.loads((FIXTURES / "valid_envelope.json").read_text(encoding="utf-8"))
    event["previous_event_hash"] = GENESIS_PREVIOUS_HASH
    event["event_hash"] = compute_event_hash(event)
    tampered = copy.deepcopy(event)
    tampered["payload_schema"] = "mutated/v0.1"
    with pytest.raises(ChainIntegrityError):
        verify_task_chain([tampered])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_event_hash.py -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# src/aisdlc/ledger/chain.py
from __future__ import annotations

import copy
from typing import Any

from aisdlc.canonical.hashing import digest_ref
from aisdlc.canonical.jcs import canonicalize_json
from aisdlc.errors import ChainIntegrityError

GENESIS_PREVIOUS_HASH = "sha256:" + ("0" * 64)


def event_body_for_hash(event: dict[str, Any]) -> dict[str, Any]:
    body = copy.deepcopy(event)
    body.pop("event_hash", None)
    return body


def compute_event_hash(event: dict[str, Any]) -> str:
    return digest_ref(canonicalize_json(event_body_for_hash(event)))


def verify_task_chain(events: list[dict[str, Any]]) -> None:
    if not events:
        return
    expected_sequence = 1
    expected_previous = GENESIS_PREVIOUS_HASH
    for event in events:
        if event.get("sequence") != expected_sequence:
            raise ChainIntegrityError(
                f"sequence gap: expected {expected_sequence}, got {event.get('sequence')}"
            )
        if event.get("previous_event_hash") != expected_previous:
            raise ChainIntegrityError("previous_event_hash does not match chain head")
        declared = event.get("event_hash")
        computed = compute_event_hash(event)
        if declared != computed:
            raise ChainIntegrityError(
                f"event_hash mismatch at sequence {event.get('sequence')}"
            )
        expected_sequence += 1
        expected_previous = declared
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_event_hash.py -v`

Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/aisdlc/ledger/chain.py tests/test_event_hash.py
git commit -m "feat(ledger): add event hashing and chain verification"
```

---

### Task 7: Content-Addressed Artifact Store

**Files:**
- Create: `src/aisdlc/artifacts/store.py`
- Create: `tests/test_artifacts.py`

**Interfaces:**
- Consumes: `digest_ref`, `parse_digest_ref`, `ArtifactMismatchError`
- Produces:
  - `ArtifactStore(root: Path)`
  - `put(self, data: bytes) -> str` — returns `sha256:<hex>`
  - `get(self, ref: str) -> bytes`
  - `verify(self, ref: str, data: bytes) -> None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_artifacts.py
import pytest

from aisdlc.artifacts.store import ArtifactStore
from aisdlc.errors import ArtifactMismatchError


def test_put_get_round_trip(tmp_data_dir):
    store = ArtifactStore(tmp_data_dir / "artifacts")
    data = b'{"payload": true}'
    ref = store.put(data)
    assert store.get(ref) == data


def test_verify_detects_mismatch(tmp_data_dir):
    store = ArtifactStore(tmp_data_dir / "artifacts")
    ref = store.put(b"original")
    with pytest.raises(ArtifactMismatchError):
        store.verify(ref, b"tampered")


def test_put_is_idempotent(tmp_data_dir):
    store = ArtifactStore(tmp_data_dir / "artifacts")
    data = b"same-bytes"
    assert store.put(data) == store.put(data)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_artifacts.py -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# src/aisdlc/artifacts/store.py
from __future__ import annotations

from pathlib import Path

from aisdlc.canonical.hashing import digest_ref, parse_digest_ref, sha256_digest
from aisdlc.errors import ArtifactMismatchError


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path_for_ref(self, ref: str) -> Path:
        digest = parse_digest_ref(ref)
        hex_digest = digest.hex()
        return self.root / hex_digest[:2] / hex_digest[2:]

    def put(self, data: bytes) -> str:
        ref = digest_ref(data)
        path = self._path_for_ref(ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(data)
        else:
            existing = path.read_bytes()
            if sha256_digest(existing) != sha256_digest(data):
                raise ArtifactMismatchError(f"digest collision for {ref}")
        return ref

    def get(self, ref: str) -> bytes:
        path = self._path_for_ref(ref)
        if not path.exists():
            raise FileNotFoundError(ref)
        data = path.read_bytes()
        self.verify(ref, data)
        return data

    def verify(self, ref: str, data: bytes) -> None:
        if digest_ref(data) != ref:
            raise ArtifactMismatchError(f"artifact bytes do not match {ref}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_artifacts.py -v`

Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/aisdlc/artifacts/store.py tests/test_artifacts.py
git commit -m "feat(artifacts): add content-addressed immutable artifact store"
```

---

### Task 8: SQLite Ledger Schema

**Files:**
- Create: `src/aisdlc/ledger/db.py`
- Create: `src/aisdlc/ledger/models.py`
- Create: `tests/test_ledger_db.py`

**Interfaces:**
- Consumes: none
- Produces:
  - `connect(db_path: Path) -> sqlite3.Connection`
  - `init_schema(conn) -> None`
  - `TaskChainHead` dataclass: `task_id`, `latest_sequence`, `latest_event_hash`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ledger_db.py
import sqlite3

from aisdlc.ledger.db import connect, init_schema


def test_init_schema_creates_tables(tmp_data_dir):
    db_path = tmp_data_dir / "ledger.db"
    conn = connect(db_path)
    init_schema(conn)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"tasks", "events", "artifacts", "chain_heads"}.issubset(tables)
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ledger_db.py -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# src/aisdlc/ledger/models.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskChainHead:
    task_id: str
    latest_sequence: int
    latest_event_hash: str


@dataclass(frozen=True)
class StoredEvent:
    event_id: str
    task_id: str
    sequence: int
    event_hash: str
    envelope_json: str
```

```python
# src/aisdlc/ledger/db.py
from __future__ import annotations

import sqlite3
from pathlib import Path

DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS artifacts (
  digest_ref TEXT PRIMARY KEY,
  size_bytes INTEGER NOT NULL,
  stored_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS chain_heads (
  task_id TEXT PRIMARY KEY REFERENCES tasks(task_id),
  latest_sequence INTEGER NOT NULL,
  latest_event_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL REFERENCES tasks(task_id),
  sequence INTEGER NOT NULL,
  occurred_at TEXT NOT NULL,
  event_type TEXT NOT NULL,
  event_hash TEXT NOT NULL,
  previous_event_hash TEXT NOT NULL,
  payload_ref TEXT NOT NULL,
  envelope_json TEXT NOT NULL,
  UNIQUE(task_id, sequence),
  UNIQUE(task_id, event_hash)
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(DDL)
    conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ledger_db.py -v`

Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add src/aisdlc/ledger/db.py src/aisdlc/ledger/models.py tests/test_ledger_db.py
git commit -m "feat(ledger): add SQLite schema for tasks, events, and chain heads"
```

---

### Task 9: Atomic Event Append

**Files:**
- Create: `src/aisdlc/ledger/store.py`
- Create: `tests/test_ledger_append.py`

**Interfaces:**
- Consumes: all prior modules
- Produces:
  - `LedgerStore(db_path: Path, artifact_root: Path)`
  - `append_event(self, task_id: str, envelope: dict, payload: bytes) -> dict` — returns stored event with `event_hash`
  - `get_events(self, task_id: str) -> list[dict]`
  - `get_chain_head(self, task_id: str) -> TaskChainHead | None`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ledger_append.py
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from ulid import ULID

from aisdlc.ledger.chain import GENESIS_PREVIOUS_HASH, compute_event_hash
from aisdlc.ledger.store import LedgerStore


def _envelope(task_id: str) -> dict:
    return {
        "event_id": str(ULID()),
        "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event_type": "contract.drafted",
        "actor": {"kind": "human", "id": "owner"},
        "artifact_refs": [],
        "payload_schema": "contract-drafted/v0.1",
    }


def test_append_event_assigns_sequence_and_hash(tmp_data_dir):
    store = LedgerStore(tmp_data_dir / "ledger.db", tmp_data_dir / "artifacts")
    task_id = f"TASK-{uuid4().hex[:8]}"
    payload1 = json.dumps({"n": 1}).encode("utf-8")
    payload2 = json.dumps({"n": 2}).encode("utf-8")

    first = store.append_event(task_id, _envelope(task_id), payload1)
    assert first["sequence"] == 1
    assert first["previous_event_hash"] == GENESIS_PREVIOUS_HASH
    assert first["event_hash"] == compute_event_hash(first)

    second = store.append_event(task_id, _envelope(task_id), payload2)
    assert second["sequence"] == 2
    assert second["previous_event_hash"] == first["event_hash"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ledger_append.py -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# src/aisdlc/ledger/store.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aisdlc.artifacts.store import ArtifactStore
from aisdlc.errors import ValidationError
from aisdlc.ledger.chain import GENESIS_PREVIOUS_HASH, compute_event_hash, verify_task_chain
from aisdlc.ledger.db import connect, init_schema
from aisdlc.ledger.models import TaskChainHead
from aisdlc.validation.event import validate_event_envelope


class LedgerStore:
    def __init__(self, db_path: Path, artifact_root: Path) -> None:
        self._db_path = db_path
        self._artifacts = ArtifactStore(artifact_root)
        conn = connect(db_path)
        init_schema(conn)
        conn.close()

    def _conn(self):
        return connect(self._db_path)

    def get_chain_head(self, task_id: str) -> TaskChainHead | None:
        conn = self._conn()
        row = conn.execute(
            "SELECT task_id, latest_sequence, latest_event_hash FROM chain_heads WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return TaskChainHead(row["task_id"], row["latest_sequence"], row["latest_event_hash"])

    def append_event(self, task_id: str, envelope: dict[str, Any], payload: bytes) -> dict[str, Any]:
        payload_ref = self._artifacts.put(payload)
        envelope = dict(envelope)
        envelope["task_id"] = task_id
        envelope["payload_ref"] = payload_ref

        conn = self._conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT OR IGNORE INTO tasks(task_id) VALUES (?)", (task_id,))
            head = conn.execute(
                "SELECT latest_sequence, latest_event_hash FROM chain_heads WHERE task_id = ?",
                (task_id,),
            ).fetchone()

            if head is None:
                sequence = 1
                previous_hash = GENESIS_PREVIOUS_HASH
            else:
                sequence = int(head["latest_sequence"]) + 1
                previous_hash = head["latest_event_hash"]

            envelope["sequence"] = sequence
            envelope["previous_event_hash"] = previous_hash
            validate_event_envelope(envelope)
            event_hash = compute_event_hash(envelope)
            envelope["event_hash"] = event_hash

            conn.execute(
                """
                INSERT INTO artifacts(digest_ref, size_bytes) VALUES (?, ?)
                ON CONFLICT(digest_ref) DO NOTHING
                """,
                (payload_ref, len(payload)),
            )
            conn.execute(
                """
                INSERT INTO events(
                  event_id, task_id, sequence, occurred_at, event_type,
                  event_hash, previous_event_hash, payload_ref, envelope_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    envelope["event_id"],
                    task_id,
                    sequence,
                    envelope["occurred_at"],
                    envelope["event_type"],
                    event_hash,
                    previous_hash,
                    payload_ref,
                    json.dumps(envelope),
                ),
            )
            conn.execute(
                """
                INSERT INTO chain_heads(task_id, latest_sequence, latest_event_hash)
                VALUES (?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                  latest_sequence = excluded.latest_sequence,
                  latest_event_hash = excluded.latest_event_hash
                """,
                (task_id, sequence, event_hash),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return envelope

    def get_events(self, task_id: str) -> list[dict[str, Any]]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT envelope_json FROM events WHERE task_id = ? ORDER BY sequence ASC",
            (task_id,),
        ).fetchall()
        conn.close()
        events = [json.loads(row["envelope_json"]) for row in rows]
        verify_task_chain(events)
        return events

    def export_chain_head(self, task_id: str) -> dict[str, Any]:
        head = self.get_chain_head(task_id)
        if head is None:
            raise ValidationError(f"no chain head for task {task_id}")
        return {
            "task_id": head.task_id,
            "latest_sequence": head.latest_sequence,
            "latest_event_hash": head.latest_event_hash,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ledger_append.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/aisdlc/ledger/store.py tests/test_ledger_append.py
git commit -m "feat(ledger): add atomic per-task event append with chain linking"
```

---

### Task 10: Chain Verification Integration Tests

**Files:**
- Create: `tests/test_ledger_chain.py`

**Interfaces:**
- Consumes: `LedgerStore`, `verify_task_chain`, `ChainIntegrityError`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ledger_chain.py
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from ulid import ULID

from aisdlc.errors import ChainIntegrityError
from aisdlc.ledger.chain import GENESIS_PREVIOUS_HASH
from aisdlc.ledger.store import LedgerStore


def _env(task_id: str) -> dict:
    return {
        "event_id": str(ULID()),
        "task_id": task_id,
        "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event_type": "gate.completed",
        "actor": {"kind": "tool", "id": "verification-service"},
        "artifact_refs": [],
        "payload_schema": "gate-completed/v0.1",
    }


def test_get_events_verifies_chain(tmp_data_dir):
    store = LedgerStore(tmp_data_dir / "ledger.db", tmp_data_dir / "artifacts")
    task_id = f"TASK-{uuid4().hex[:8]}"
    store.append_event(task_id, _env(task_id), b'{"exit_code": 0}')
    store.append_event(task_id, _env(task_id), b'{"exit_code": 0}')
    events = store.get_events(task_id)
    assert len(events) == 2
    assert events[0]["previous_event_hash"] == GENESIS_PREVIOUS_HASH
    assert events[1]["previous_event_hash"] == events[0]["event_hash"]


def test_corrupted_envelope_detected_on_read(tmp_data_dir):
    store = LedgerStore(tmp_data_dir / "ledger.db", tmp_data_dir / "artifacts")
    task_id = f"TASK-{uuid4().hex[:8]}"
    store.append_event(task_id, _env(task_id), b"{}")
    conn = store._conn()  # noqa: SLF001
    conn.execute(
        "UPDATE events SET envelope_json = json_set(envelope_json, '$.event_type', 'tampered') WHERE task_id = ?",
        (task_id,),
    )
    conn.commit()
    conn.close()
    with pytest.raises(ChainIntegrityError):
        store.get_events(task_id)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ledger_chain.py::test_corrupted_envelope_detected_on_read -v`

Expected: FAIL if corruption not detected, or PASS if already implemented — ensure tamper test fails before Step 3 fixes

- [ ] **Step 3: Confirm implementation** (no code change if Task 9 `get_events` already calls `verify_task_chain`)

- [ ] **Step 4: Run full ledger test suite**

Run: `python -m pytest tests/test_ledger_chain.py tests/test_ledger_append.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_ledger_chain.py
git commit -m "test(ledger): add chain integrity integration coverage"
```

---

### Task 11: Crash Recovery Behavior

**Files:**
- Create: `tests/test_ledger_crash.py`

**Interfaces:**
- Consumes: `LedgerStore`, SQLite transaction semantics

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ledger_crash.py
import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from ulid import ULID

from aisdlc.ledger.db import connect, init_schema
from aisdlc.ledger.store import LedgerStore


class CrashLedgerStore(LedgerStore):
    def __init__(self, db_path, artifact_root, crash_after_insert: bool = False):
        super().__init__(db_path, artifact_root)
        self.crash_after_insert = crash_after_insert

    def append_event(self, task_id, envelope, payload):
        payload_ref = self._artifacts.put(payload)
        envelope = dict(envelope)
        envelope["task_id"] = task_id
        envelope["payload_ref"] = payload_ref
        conn = connect(self._db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT OR IGNORE INTO tasks(task_id) VALUES (?)", (task_id,))
            head = conn.execute(
                "SELECT latest_sequence, latest_event_hash FROM chain_heads WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            sequence = 1 if head is None else int(head["latest_sequence"]) + 1
            previous_hash = (
                "sha256:" + "0" * 64 if head is None else head["latest_event_hash"]
            )
            envelope["sequence"] = sequence
            envelope["previous_event_hash"] = previous_hash
            from aisdlc.ledger.chain import compute_event_hash
            from aisdlc.validation.event import validate_event_envelope

            validate_event_envelope(envelope)
            envelope["event_hash"] = compute_event_hash(envelope)
            conn.execute(
                """
                INSERT INTO events(
                  event_id, task_id, sequence, occurred_at, event_type,
                  event_hash, previous_event_hash, payload_ref, envelope_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    envelope["event_id"],
                    task_id,
                    sequence,
                    envelope["occurred_at"],
                    envelope["event_type"],
                    envelope["event_hash"],
                    previous_hash,
                    payload_ref,
                    json.dumps(envelope),
                ),
            )
            if self.crash_after_insert:
                raise RuntimeError("simulated crash before commit")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return envelope


def _env(task_id: str) -> dict:
    return {
        "event_id": str(ULID()),
        "task_id": task_id,
        "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event_type": "tool.called",
        "actor": {"kind": "tool", "id": "shell"},
        "artifact_refs": [],
        "payload_schema": "tool-called/v0.1",
    }


def test_crash_before_commit_leaves_no_partial_chain_head(tmp_data_dir):
    db_path = tmp_data_dir / "ledger.db"
    artifacts = tmp_data_dir / "artifacts"
    task_id = f"TASK-{uuid4().hex[:8]}"
    store = CrashLedgerStore(db_path, artifacts, crash_after_insert=True)
    with pytest.raises(RuntimeError):
        store.append_event(task_id, _env(task_id), b"{}")
    recovery = LedgerStore(db_path, artifacts)
    assert recovery.get_chain_head(task_id) is None
    assert recovery.get_events(task_id) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ledger_crash.py -v`

Expected: FAIL if chain head or event partially persisted

- [ ] **Step 3: Fix `LedgerStore.append_event` if needed** — ensure `chain_heads` update and `events` insert share one transaction and rollback together (already required in Task 9).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ledger_crash.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_ledger_crash.py
git commit -m "test(ledger): verify rollback on simulated crash before commit"
```

---

### Task 12: Concurrent Append Ordering

**Files:**
- Create: `tests/test_ledger_concurrency.py`

**Interfaces:**
- Consumes: `LedgerStore`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ledger_concurrency.py
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from uuid import uuid4

from ulid import ULID

from aisdlc.ledger.store import LedgerStore


def _env(task_id: str, idx: int) -> dict:
    return {
        "event_id": str(ULID()),
        "task_id": task_id,
        "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event_type": "tool.called",
        "actor": {"kind": "tool", "id": f"worker-{idx}"},
        "artifact_refs": [],
        "payload_schema": "tool-called/v0.1",
    }


def test_concurrent_appends_preserve_total_order(tmp_data_dir):
    db_path = tmp_data_dir / "ledger.db"
    artifacts = tmp_data_dir / "artifacts"
    task_id = f"TASK-{uuid4().hex[:8]}"
    worker_count = 8
    events_per_worker = 5

    def append_one(i: int) -> None:
        store = LedgerStore(db_path, artifacts)
        payload = json.dumps({"worker": i}).encode("utf-8")
        store.append_event(task_id, _env(task_id, i), payload)

    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        futures = [pool.submit(append_one, i) for i in range(worker_count * events_per_worker)]
        for fut in as_completed(futures):
            fut.result()

    store = LedgerStore(db_path, artifacts)
    events = store.get_events(task_id)
    assert len(events) == worker_count * events_per_worker
    sequences = [e["sequence"] for e in events]
    assert sequences == list(range(1, len(events) + 1))
    assert len({e["event_hash"] for e in events}) == len(events)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ledger_concurrency.py -v`

Expected: FAIL on constraint violation or duplicate sequence without `BEGIN IMMEDIATE`

- [ ] **Step 3: Confirm `BEGIN IMMEDIATE` in `append_event`** serializes writers (Task 9). If failures persist on Windows, document `timeout=30.0` on `sqlite3.connect`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ledger_concurrency.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_ledger_concurrency.py
git commit -m "test(ledger): verify concurrent append ordering under SQLite locking"
```

---

### Task 13: Phase 1A Exit Verification Suite

**Files:**
- Create: `tests/test_phase1a_acceptance.py`
- Modify: `pyproject.toml` (add `[project.scripts]` optional CLI stub)

**Interfaces:**
- Consumes: entire `aisdlc` package

- [ ] **Step 1: Write the failing acceptance test**

```python
# tests/test_phase1a_acceptance.py
"""Phase 1A exit criteria from spec section 21."""
import json
from pathlib import Path

import pytest

from aisdlc.errors import ChainIntegrityError, ValidationError
from aisdlc.schemas.registry import validate_contract_document
from aisdlc.validation.contract import validate_and_hash_contract_document

FIXTURES = Path(__file__).parent / "fixtures"


def test_schemas_reject_invalid_inputs():
    bad = json.loads((FIXTURES / "contracts" / "invalid_unknown_field.json").read_text())
    with pytest.raises(ValidationError):
        validate_contract_document(bad)


def test_valid_contract_hashes_and_validates():
    good = json.loads((FIXTURES / "contracts" / "valid_r1_minimal.json").read_text())
    digest = validate_and_hash_contract_document(good)
    assert digest.startswith("sha256:")


def test_full_ledger_round_trip(tmp_data_dir):
    from datetime import datetime, timezone
    from uuid import uuid4

    from ulid import ULID

    from aisdlc.ledger.store import LedgerStore

    store = LedgerStore(tmp_data_dir / "ledger.db", tmp_data_dir / "artifacts")
    task_id = f"TASK-{uuid4().hex[:8]}"
    env = {
        "event_id": str(ULID()),
        "occurred_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event_type": "contract.approved",
        "actor": {"kind": "human", "id": "owner"},
        "artifact_refs": [],
        "payload_schema": "contract-approved/v0.1",
    }
    stored = store.append_event(task_id, env, b'{"approved": true}')
    events = store.get_events(task_id)
    assert events[0]["event_hash"] == stored["event_hash"]
    head = store.export_chain_head(task_id)
    assert head["latest_event_hash"] == stored["event_hash"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_phase1a_acceptance.py -v`

Expected: FAIL until all prior tasks complete

- [ ] **Step 3: Run entire test suite**

Run: `python -m pytest -v && ruff check src tests`

Expected: all tests PASS, ruff clean

- [ ] **Step 4: Run test to verify acceptance passes**

Run: `python -m pytest tests/test_phase1a_acceptance.py -v`

Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add tests/test_phase1a_acceptance.py
git commit -m "test: add Phase 1A acceptance coverage for schemas and ledger"
```

---

## Spec Coverage Self-Review

| Spec requirement | Task |
|---|---|
| JSON Schema 2020-12 for Execution Contract | Task 3 |
| Conditional contract requirements (§9.2) | Task 3 schema `allOf` |
| `contract_body_hash` omission rules | Task 4 |
| Canonical evidence-event envelope | Task 5 |
| RFC 8785 JCS + SHA-256 `event_hash` | Tasks 2, 6 |
| ULID `event_id` | Task 9 (caller supplies; tests use `ULID()`) |
| SQLite metadata store | Task 8 |
| Content-addressed artifact files | Task 7 |
| Atomic sequence + chain head per transaction | Task 9 |
| Chain verification / corruption detection | Tasks 6, 10 |
| Crash recovery | Task 11 |
| Concurrent write ordering | Task 12 |
| Phase 1A exit verification | Task 13 |
| Context Manifest schema | Deferred (Phase 1B+) |
| Payload-type schemas (`gate-completed/v0.1`, etc.) | Deferred |
| Signed chain-head export | Deferred |
| Projections, adapters, runtime | Deferred per §26 |

## Follow-On Plans (Not This Document)

1. `2026-07-11-projections-and-export.md` — Phase 1B
2. `2026-07-11-observational-adapters.md` — Phase 1C
3. `2026-07-11-execution-runtime.md` — Phase 2
