# Lycoles v69 — universal evidence dashboard

v69 compiles v68 read-only discovery evidence into a working Roblox GUI. It does **not** generate or verify gameplay actions, remote argument contracts, or bypasses.

## Prepare evidence

Run from the repository root with your existing v54 inspection and v66 telemetry exports:

```powershell
py tools/evidence_reconciler_v68.py --discovery inspection.txt --telemetry telemetry.txt --place-id 85896571713843 --output build/release-v68
```

v68 supports multiple complete v66 exports in one file, selecting the last valid complete session. It retains partial v54 batches with provenance warnings.

## Generate the GUI

```powershell
py tools/dashboard_generator_v69.py --manifest build/release-v68/release-manifest-v68.json --catalog build/release-v68/catalog-v68.json --place-id 85896571713843 --output build/release-v69
```

The output is `build/release-v69/dashboard-v69.luau`. Run it in the intended Roblox experience. It checks the place ID, replaces an existing v69 GUI, and provides:

- Dragging from the title bar, minimise/restore, close
- Search and manual refresh
- Live local leaderstats refreshed every three seconds while expanded
- A searchable read-only catalog of discovered objects

Discovery entries are capped at 300 for UI responsiveness. Entries remain **unverified**; GUI display is not proof that any gameplay action is callable.

## Test

```powershell
py -m py_compile tools/dashboard_generator_v69.py
py -m unittest discover -s tests -p "test_dashboard_generator_v69.py" -v
```

GitHub Actions: `.github/workflows/v69-dashboard.yml`.

## Troubleshooting

- **Wrong place:** confirm `--place-id` matches the game where you execute the script.
- **Missing manifest/catalog:** run v68 first.
- **No leaderstats:** not all games expose their stats as `Players.LocalPlayer.leaderstats`; the discovered-object list can still appear.
- **Missing action buttons:** deliberate; passive inspection cannot prove safe, valid server action contracts.
- **Partial evidence:** v68 retains partial discovery but marks its provenance and completeness accurately.
