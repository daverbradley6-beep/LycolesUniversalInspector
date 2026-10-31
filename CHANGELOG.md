## 4.6.0
- Add per-feature implementation readiness records (discovered, observed, implemented, tested), with conservative default false for unverified stages.
- Add successive-scan feature-candidate count deltas. These are not causal before/after gameplay verification.
- Include readiness and deltas in saved manifest and first multipart upload part.
- Preserve v4.5.1 token matching and upload byte diagnostics.
- Not implemented in this release: guided interaction labeling, feature-specific state-change verification, GUI/controller behavioral mapping, verified formulas, or executable regression tests. Runtime test required.

## 4.5.1
- Token-aware feature detection splits PascalCase and camelCase object names and avoids matching `quest` inside `Request`.
- Include `localPerformance.uploadBytes`, `uploadParts`, and `serializationSeconds` in the saved JSON manifest for measurable multipart size comparisons.
- Preserve read-only scanning and existing multipart upload behavior; Potassium runtime test pending.

## 4.5.0
- Restrict feature evidence to object names instead of full ancestor paths to reduce false-positive classifications.
- Limit feature examples to six per category and shorten example paths to reduce repeated upload metadata.
- Preserve v4.4.1 multipart byte validation and first-part-only summary metadata.
- Add GAME_SPECIFIC_GUI_MASTER_PROMPT.md integrating the new evidence rules and game-specific GUI workflow.
- Requires live Potassium test; receiver deployment unchanged.

## 4.4.1
- Validate every multipart payload against the actual encoded byte size and split oversized object chunks.
- Send scan-wide counts, diagnostics and feature evidence only in the first part to avoid repeated metadata.
- Add scan-local ordinal identifiers; these are not stable across sessions.
- Preserve read-only inspection and existing acknowledgement/retry handling.
- Receiver indexing changes and Potassium runtime verification are not included.

## v4.3.0 — Scan identity and payload tuning

- Distinguish objects sharing the same hierarchy path using scan-local occurrence suffixes; retain all objects instead of discarding path collisions.
- Count resolved path collisions in scan statistics.
- Reduce bounded sibling ValueBase snapshots from 20 to 8 related entries, reducing repeated JSON metadata without removing inspected objects.
- Preserve existing multipart JSON schema, acknowledgement and retry behavior.

**Receiver indexing limitation:** The deployed Cloudflare Worker/MCP index is a separate service. This client update does not change its indexing behavior or retroactively repair previous scan metadata. Detailed diagnostics already verified all 844 parts of the prior scan. No in-game benchmark has been performed for this release.

## v4.2.0 — Performance update

- Bounded concurrent upload workers (3 simultaneous requests) with per-part acknowledgement and retry.
- Per-scan cached sibling ValueBase context to avoid repeated parent enumeration.
- Adaptive scan yielding with a 12 ms processing budget rather than fixed 500-object yields.
- Slower background discovery polling (30 seconds) to reduce idle overhead.
- Per-root scan timings, scan duration and yield count in scan statistics.
- Upload completion reports elapsed upload time.
- Preserves v4.1 report JSON format and the existing Cloudflare Worker interface.

**Not included yet:** compressed report schema or true incremental full-snapshot reconstruction. Those require coordinated receiver changes. Client runtime performance has not been measured in Potassium; benchmark against v4.1 before treating this as a verified speedup.

# Changelog

## 4.1.0
- Added multi-label system classification and semantic ValueBase roles.
- Added parent/ancestor context and bounded sibling value relationships.
- Improved controller candidate and GUI control metadata.
- Added per-root coverage and per-class/configuration/GUI/script diagnostics.
- Excluded PlayerGui and Character from duplicate LocalPlayer-root captures.
- Replaced unconditional complete=true with required-root and object-accounting validation.
- Retained read-only behaviour, multipart delivery, acknowledgements and retry logic.

## 4.0.0
- Added universal client-visible root inspection, bounded metadata, GUI and interaction observation, dynamic discovery, and multipart reporting.
