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

## Limits

Sibling ordinals can change when a dynamic hierarchy is rebuilt. Full identity removes same-name ambiguity only while the observed class-qualified sibling ordering remains valid. The schema represents client-visible evidence and does not establish server authority, gameplay causality, or runtime success.
