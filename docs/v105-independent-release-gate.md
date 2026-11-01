# Lycoles v105 — Independent release quality gate

The v105 verifier checks v104 observation releases for: missing or symlinked files, SHA-256 mismatches, inconsistent place IDs, unsupported verification/automation claims, invalid observation accounting, too few accepted observations, excessive rejected observations, mismatched object counts, and deterministic regeneration of the Luau script and canonical report.

## Usage

```powershell
py tools/release_pipeline_v104.py --inspection examples/v102-client-inventory.json --place-id 85896571713843 --output build/release-v104
py tools/release_gate_v105.py --directory build/release-v104 --minimum 1 --max-rejection-rate 0.5
py -m unittest discover -s tests -p test_release_gate_v105.py -v
```

The gate returns a nonzero exit status if verification fails. It does not establish gameplay functionality, third-party game authorization, or in-game execution. No gameplay automation or anti-cheat bypass is generated.

## Testing scope

12 v105 unit tests were run successfully locally using a lightweight fixture implementation of the v104 release interface because network restrictions prevented cloning the actual repository into the local test container. **This is not a full v104/v105 integration test.** GitHub Actions is configured to execute the tests against the actual repository files on Python 3.10–3.13; its result must be checked separately.

## Next development milestone

Integrate actual inspection reports and observed outcomes, rather than adding unsupported claims of automatic gameplay actions.
