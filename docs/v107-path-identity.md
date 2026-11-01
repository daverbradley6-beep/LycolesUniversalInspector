# v107 full-path identity schema

v107 preserves the evidence needed to distinguish same-named client-visible objects without changing or weakening the v104 release contract.

## Canonical identity

Each v107 object retains the display-oriented `path` and adds `pathIdentity`:

```json
{
  "path": ["Workspace", "Stats", "Coins"],
  "pathIdentity": [
    {"name": "Workspace", "className": "Workspace", "ordinal": 1},
    {"name": "Stats", "className": "Folder", "ordinal": 1},
    {"name": "Coins", "className": "IntValue", "ordinal": 2}
  ],
  "pathResolution": "full_identity",
  "className": "IntValue",
  "property": "Value"
}
```

`ordinal` is one-based among siblings with the same name and class. The service root is explicit, has its expected class, and always uses ordinal 1. The terminal identity class must equal the observation class.

The report advertises both `schemaVersion: "107.release"` and `pathIdentityVersion: "107.path-identity.1"`. Identity segments are strictly bounded and contain exactly `name`, `className`, and `ordinal`.

## Supported inputs

The normalizer accepts:

- canonical `pathIdentity` segments;
- existing v72/v74 `uniquePath` segments, adding the known `PlayerGui` root without inventing descendant metadata;
- existing v55 `segments` values;
- identity segments supplied directly as `path`;
- legacy name-only `path`, `fullName`, or `fullPath` observations.

A complete identity is the deduplication key. Objects with the same names but different class-qualified sibling ordinals remain distinct. Exact identities are rejected as duplicates. A name-only observation is rejected as ambiguous when identity-rich evidence exists for the same names.

## Backward compatibility

`migrate_v104_report()` validates the complete v104 accounting, safety claims, class/property contracts, and objects before producing a v107 report. Migrated objects use:

```json
{
  "pathIdentity": null,
  "pathResolution": "legacy_terminal_identity"
}
```

The migration never fabricates missing intermediate classes or ordinals. Existing v104 builders and artifacts remain unchanged and reproducible; v107 is a one-way opt-in schema for identity-aware consumers.

## Evidence-backed feature plans

New plans use schema `107.feature-plan.2`. Every generated feature links to its canonical `inspection-report.json` object index and SHA-256 digest, classifies the source as an observed client object, lists directly observed facts separately from bounded implementation inferences, and records:

- the read-only implementation strategy;
- resolution-specific runtime checks;
- explicit success and failure conditions;
- `implemented_not_runtime_verified` verification status; and
- unknown server authority, gameplay causality, runtime value/availability, and game-specific action semantics.

The quality and diagnostics artifacts count evidence classifications, verification statuses, explicit contracts, and unknown boundaries. Legacy `107.feature-plan` plans remain strictly valid for existing consumers and emit identical Luau. `migrate_feature_plan_v1()` upgrades a v1 plan only when it exactly matches a validated source report; it never invents evidence detached from that report.

## Integrated generation

```bash
python tools/integrated_pipeline_v107.py \
  --inspection inspection.json \
  --place-id 85896571713843 \
  --output build/v107
python tools/integrated_pipeline_v107.py --output build/v107 --verify-only
```

The pipeline accepts raw supported observations, canonical v107 reports, and validated v104 reports. It emits deterministic inspection, feature-plan, quality, diagnostics, API compatibility, Luau, and manifest artifacts.

Full-identity features resolve each descendant by matching name and class, then selecting the observed one-based ordinal among matching siblings. Legacy migrated features are explicitly labeled `legacy_terminal_identity`: each name-only intermediate segment must have exactly one matching child, and the terminal name/class pair must also have exactly one match. Missing or ambiguous legacy evidence fails closed and is never implied to be exact.

## Public Roblox API compatibility

`api-definitions/roblox-api-version-d0e8cfcd943d4ae2-v107.json` is a bounded snapshot extracted from Roblox's public `QTStudio` API dump. It records the source URL, the full 4,070,157-byte dump SHA-256 (`02276f872886a6bc29e2e05a2e551a8c92c0e1745276520f4203d52a15679856`), inherited member owners, member kinds, access security, and tags for every class member used by the v107 emitter or supported property map.

`tools/roblox_api_contract_v107.py` reproducibly extracts the snapshot from a matching downloaded dump. Integrated generation emits `api-compatibility.json`, fails when a required member is missing, has the wrong kind, or requires non-public access, and includes that report in strict manifest verification. Global facilities not represented as class members by the dump, including `Instance.new`, `RBXScriptSignal.Connect`, `UDim`, `UDim2`, `game`, `task`, and `workspace`, remain explicit assumptions.

Compatibility means the pinned public API definitions contain the emitted class members with the required public read/write/call/event access. It is static evidence, not proof of Luau execution, live object availability, property value, server behavior, gameplay causality, or current compatibility with a newer Roblox release.

The verifier reconstructs every derived artifact, validates report and feature-plan schemas, checks identity-mode counts and safety claims, enforces the static Luau contract, and compares canonical bytes plus SHA-256 hashes. It also independently parses the generated Luau feature table and compares every runtime ID, label, path, identity segment, resolution mode, class, and property to the canonical feature plan. Verification rejects noncanonical table lines, duplicate runtime entries, place-guard drift, extra artifact files, extra manifest fields, malformed hashes, and noncanonical manifest bytes.

## Controlled resolver model

`tools/resolver_harness_v107.py` evaluates a validated feature plan against a bounded synthetic `107.hierarchy-fixture` tree. It exercises class-qualified sibling ordinals, legacy uniqueness, place guards, and property availability with deterministic fail-closed outcomes.

```bash
python tools/resolver_harness_v107.py \
  --feature-plan build/v107/feature-plan.json \
  --hierarchy hierarchy-fixture.json \
  --runtime-place-id 85896571713843 \
  --output build/v107/resolver-model.json
```

The output always distinguishes `modelVerified` from `luauExecuted`, `robloxRuntimeVerified`, and `gameplayVerified`. The harness does not execute generated Luau, load Roblox API definitions, connect to Roblox, or replace user-supplied observations from a permitted client environment. Target-game Studio ownership is not required or assumed.

## Limits

Sibling ordinals can change when a dynamic hierarchy is rebuilt. Full identity removes same-name ambiguity only while the observed class-qualified sibling ordering remains valid. The schema represents client-visible evidence and does not establish server authority, gameplay causality, or runtime success.
