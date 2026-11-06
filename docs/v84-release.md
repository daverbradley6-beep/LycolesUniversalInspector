# Lycoles v84 — reproducible GUI release builder

v84 packages manually approved GUI actions into the v82 interactive runner and emits a SHA-256 integrity manifest. It fixes the earlier Python-to-Luau JSON escaping problem by embedding UTF-8 JSON in collision-safe Luau long strings.

## Generate

```powershell
py tools/release_pipeline_v84.py --place-id 85896571713843 --contracts approved.json --output build/release-v84
py -m unittest discover -s tests -p "test_release_pipeline_v84.py" -v
```

Output: `interactive-runner-v84.luau` and `release-manifest-v84.json`. Use `--force` to overwrite an existing release. The manifest includes action IDs, file size, and SHA-256 checksum. This version retains v82's manually clicked test buttons, status output, and capture IDs.

The packaged runner inherits v82's fail-closed behavior: it validates approved GUI paths but does not attempt synthetic button activation because Roblox provides no public `GuiButton:Activate()` method. No remote calls, anti-ban features, or automated action loops are generated. Actual interactions must use the game's normal UI, and client observations cannot establish server-authoritative gameplay behavior.
