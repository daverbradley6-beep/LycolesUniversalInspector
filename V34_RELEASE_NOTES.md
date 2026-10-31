# Lycoles v34 — Source Evidence & Corroboration

This is an **offline analysis update**, not an in-game universal script generator.

## New tools
- `tools/luau_evidence_v34.py`: lexical evidence extractor; excludes comments and quoted/long-bracket strings from API detections. Records source hashes, named function definitions, Roblox API calls, service lookups, object paths, and line numbers.
- `tools/audit_feature_evidence_v34.py`: checks v32 feature names against independently extracted v34 definitions, requiring matching source SHA-256 before marking a function *lexically corroborated*.
- `tools/run_v34.ps1`: Windows entrypoint that stops if regression tests or any analysis stage fails.

## One command on Windows

Open PowerShell at the **latest repository root**, with readable `.lua`, `.luau`, or `.txt` source files in `examples`:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_v34.ps1
```

Reports:
- `build/script-corpus.json`
- `build/workflow-specs.json`
- `build/feature-intelligence.json`
- `build/luau-evidence-v34.json`
- `build/evidence-audit-v34.json`

To run only the v34 tests:

```powershell
py -m unittest discover -s tests -p "test_v34*.py"
```

## Interpretation

A `lexically-corroborated` feature means that a matching named function appears in a source file with the same SHA-256 as the v32 report. It does **not** mean that the function is callable, reachable, authorized, safe, or effective in Roblox. No generated gameplay automation or anti-cheat bypass is included.

Known limits: lexical scanning is not full Luau parsing; source files can contain nested functions, aliases, dynamic names, and runtime dependencies that cannot be resolved statically. The existing v33 reviewed diagnostic generator remains the only bounded executable generator in this branch. The main in-game inspector remains v30 unless separately updated.

## Testing status

An earlier, closely related local lexical implementation passed 12 Python unit tests. The committed v34 version and combined repository test suite require a fresh full run; do not infer live Roblox verification from unit-test results.
