# Lycoles Universal Inspector

Current release: **v4.1.0**  
Previous release: v4.0.0

## Release v4.1.0

This release strengthens read-only inspection metadata and scan diagnostics:

- Multi-label system classification. An object can be tagged for more than one system; tags are explicitly marked as name/path/parent inference.
- Parent and ancestor hierarchy context for cross-system dependency analysis.
- Bounded sibling ValueBase snapshots and semantic value roles (requirements, rewards, costs, multipliers, timing, quantities and stats).
- Better controller/service candidate metadata, explicitly heuristic and without reading script source.
- GUI control metadata for buttons and text boxes. Text entered into text boxes is never collected.
- Per-root coverage, per-class counts, ValueBase coverage, GUI control counts and script-candidate counts.
- Duplicate-root exclusion for LocalPlayer descendants already covered by dedicated PlayerGui and Character roots.
- A real scan-completeness calculation based on required-root success and object accounting. A scan can be complete for required client-visible roots while remaining explicitly limited to client-visible data.

## Installation

1. Run the script in the same supported client environment used for the existing Inspector.
2. Keep the receiver endpoint in the local `LycolesInspectorReceiver.txt` configuration file; never commit receiver secrets.
3. Run a scan and verify the root coverage and diagnostics fields in the uploaded report.

## Existing behaviour retained

- Multipart JSON uploads and verified acknowledgements.
- Bounded upload parts, retries and retry delays.
- Optional automatic uploads and dynamic discovery.
- Passive, opt-in manual interaction observation.
- Read-only inspection; no remote invocation, gameplay automation or script-source extraction.

## Interpretation limits

This tool inspects privacy-filtered, client-visible instances. It cannot inspect server-only state or implementation, prove server validation, establish remote argument contracts, or guarantee that client-visible values are authoritative. System tags, controller candidates and hierarchy-based relationships are evidence for further analysis, not confirmed gameplay rules.
