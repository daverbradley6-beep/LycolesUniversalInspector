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
