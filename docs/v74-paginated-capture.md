# Lycoles v74 — lossless page-oriented GUI capture

The v72 scan of Bubble Gum Simulator INFINITY found **2,175** controls, but a copied console export retained only items **1,688–2,175**. v74 avoids requiring a single huge console copy by exporting one independently complete page at a time.

## 1. Generate the v74 scanner

```powershell
py tools/gui_capture_v74.py --place-id 85896571713843 --output build/release-v74
```

Run `build/release-v74/gui-discovery-v74.luau` in Potassium. Open the relevant game interface, then click **Rescan**. Do not rescan between page exports: that starts a new capture session.

## 2. Capture pages

Click **Export page**, copy the output from `LYCOLES_V74_PAGE_BEGIN` to `LYCOLES_V74_PAGE_END` and save as `page-01.txt`. Click **Next**, export and save `page-02.txt`, and repeat until all pages are saved. With 2,175 controls and page size 100, expect 22 pages.

Every page includes a unique `captureId`, the Roblox place ID, its page number and the exact item range. Repeated pages are allowed if identical; conflicting copies are rejected. Never combine pages from different scans.

## 3. Merge saved pages

```powershell
$logs = Get-ChildItem ".\page-*.txt" | ForEach-Object { @("--gui-log", $_.FullName) }
py tools/gui_capture_v74.py --place-id 85896571713843 --output build/release-v74 @logs
```

Outputs: `gui-import-v74.json` with completeness diagnostics and `gui-candidates-v74.json`, compatible with the v73 contract compiler. Partial captures are permitted, and missing pages are explicitly listed.

## 4. Pass candidates to v73

```powershell
py tools/contract_pipeline_v73.py --candidates build/release-v74/gui-candidates-v74.json --outcomes examples/v73-outcomes.json --place-id 85896571713843 --output build/release-v73
```

The outcomes example is intentionally empty. Zero accepted contracts is expected until measurable outcomes are supplied.

## Tests

```powershell
py -m py_compile tools/gui_capture_v74.py
py -m unittest discover -s tests -p "test_gui_capture_v74.py" -v
```

**Verification boundary:** Python regression tests validate parsing and merging, not Roblox execution. Page export still relies on copying console blocks. No remote invocation, anti-ban bypass or automatic action-outcome inference is included. Dynamic UI rebuilding can invalidate sibling ordinals, and page size can be reduced with `--page-size 50` if the executor truncates a 100-control block.
