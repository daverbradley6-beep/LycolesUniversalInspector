# Lycoles v42 — Evidence provenance and generation contracts

v42 adds a **cross-report compiler** between game-first feature discovery and future implementations. It rejects fabricated feature paths, mismatched scan IDs, mismatched place IDs, duplicate feature identifiers, duplicate families, unsupported roots, and attempts to promote diagnostic features to gameplay implementations.

The compiler produces a deterministic `build/generation-manifest-v42.json` with per-feature evidence fingerprints, source fingerprints, explicit read-only contracts, and required runtime tests.

## New files
- `tools/generation_manifest_v42.py`
- `tests/test_v42_manifest.py` (14 regression cases)
- `tools/run_v42.ps1`

GitHub Actions has been extended to run v42 tests and compile the manifest from the included sanitized Muscle Legends inspection fixture.

## Windows
```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v42.ps1
```

This release improves correctness of the *offline feature-generation pipeline*. It does not automatically discover server-authoritative mechanics, produce working gameplay automation, or bypass anti-cheat. Tests and runtime results must be verified independently.
