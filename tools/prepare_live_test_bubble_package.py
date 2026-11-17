#!/usr/bin/env python3
"""Prepare the Bubble Gum INFINITY live-test package under build/live_test_bubble."""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import shutil
import subprocess
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]


GENERIC_SEGMENTS = {
    "localplayer",
    "playergui",
    "screengui",
    "frame",
    "main",
    "inner",
    "list",
    "items",
    "buttons",
    "button",
    "tabs",
    "sidebar",
    "top",
    "close",
    "action",
    "tray",
    "scrollingframe",
    "content",
    "track",
    "hud",
    "left",
    "right",
    "template",
}


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object JSON: {path}")
    return data


def _ensure_e2e_artifacts(manifest_path: pathlib.Path, artifact_dir: pathlib.Path, place_id: int) -> None:
    required = [
        artifact_dir / "LycolesManifestAssistedWorkflow.lua",
        artifact_dir / "manifest-assisted-workflow.json",
        artifact_dir / "manifest-readiness-v109.json",
    ]
    if all(path.exists() for path in required):
        return
    artifact_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(ROOT / "tools" / "integrated_pipeline_v108.py"),
        "--inspection",
        str(manifest_path),
        "--place-id",
        str(place_id),
        "--output",
        str(artifact_dir),
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if completed.returncode not in {0, 1}:
        raise RuntimeError(
            "failed to regenerate e2e artifacts\n"
            + completed.stdout
            + "\n"
            + completed.stderr
        )


def _find_events_for_path(history: list[dict[str, Any]], path: str) -> list[dict[str, Any]]:
    return [event for event in history if isinstance(event, dict) and event.get("path") == path]


def _path_text_hints(path: str, events: list[dict[str, Any]]) -> list[str]:
    del events  # legacy manifests may contain noisy ancestor names; use path-only hints.
    hints: list[str] = []
    for token in path.split("."):
        lower = token.lower()
        if lower in GENERIC_SEGMENTS:
            continue
        if token and token not in hints and (
            " " in token
            or any(ch.isdigit() for ch in token)
            or token in {"Lemon", "Playtime", "Bubbles", "Pets", "Items", "Best", "Prizes"}
        ):
            hints.append(token)
    return hints[:6]


def _prerequisite_hint(path: str) -> str:
    lower = path.lower()
    if "inventory.inputblocker" in lower:
        return "Likely overlay blocker; may only dismiss/consume clicks, not gameplay actions."
    if ".quests." in lower:
        return "Quests menu likely must be opened first (HUD Left > Quests)."
    if ".inventory." in lower and "hud.right.inventory.button" not in lower:
        return "Inventory UI likely must be open first (HUD Right > Inventory)."
    if ".gumshop." in lower:
        return "Gum Shop UI likely must be open before this control appears."
    if ".season." in lower:
        return "Season rewards panel likely must be open and relevant tier unlocked."
    return "No explicit prerequisite captured; control visibility may still depend on runtime UI state."


def _score_target(row: dict[str, Any]) -> int:
    score = 0
    if row["directlyActivatable"]:
        score += 3
    if row["meaningfulOutcomeEvidence"]:
        score += 8
    score += min(row["maxStateChangeCount"], 3) * 2
    score += min(row["maxGuiStateChangeCount"], 3)
    if row["feature"] != "unattributed":
        score += 2
    if "inputblocker" in row["path"].lower():
        score -= 4
    if "team-" in row["path"].lower() or "uuid" in row["path"].lower():
        score -= 2
    return score


def _target_rows(manifest: dict[str, Any], assisted_meta: dict[str, Any]) -> list[dict[str, Any]]:
    interaction = manifest.get("interactionDiagnostics")
    interaction = interaction if isinstance(interaction, dict) else {}
    history = interaction.get("recentInteractions")
    history = history if isinstance(history, list) else []

    rows: list[dict[str, Any]] = []
    for index, target in enumerate(assisted_meta.get("targets") or [], start=1):
        path = target.get("path")
        if not isinstance(path, str):
            continue
        events = _find_events_for_path(history, path)
        max_state = 0
        max_gui = 0
        explicit_outcomes = 0
        unique_transactions = set()
        for event in events:
            max_state = max(max_state, int(event.get("stateChangeCount") or 0))
            max_gui = max(max_gui, int(event.get("guiStateChangeCount") or 0))
            if isinstance(event.get("observableOutcomeCandidate"), dict):
                explicit_outcomes += 1
            if event.get("transactionId") is not None:
                unique_transactions.add(str(event.get("transactionId")))

        hints = _path_text_hints(path, events)
        directly_activatable = target.get("controlType") == "GuiButton.Activated"
        meaningful = explicit_outcomes > 0 or max_state > 0
        row = {
            "id": index,
            "feature": target.get("feature") or "unattributed",
            "path": path,
            "guiName": path.split(".")[-1],
            "availableTextHints": hints,
            "interactionType": target.get("controlType") or "unknown",
            "directlyActivatable": directly_activatable,
            "evidenceEventCount": len(events),
            "maxStateChangeCount": max_state,
            "maxGuiStateChangeCount": max_gui,
            "explicitOutcomeCandidateEvents": explicit_outcomes,
            "meaningfulOutcomeEvidence": meaningful,
            "multiStepWorkflowPotential": len(unique_transactions) > 1 or max_gui > 0,
            "transactionIdsSeen": sorted(unique_transactions)[:8],
            "prerequisites": _prerequisite_hint(path),
            "limitations": (
                "No explicit outcome candidate observed in this legacy capture"
                if explicit_outcomes <= 0
                else "Outcome candidate observed"
            ),
        }
        row["workflowScore"] = _score_target(row)
        rows.append(row)

    rows.sort(key=lambda item: (-item["workflowScore"], item["feature"], item["path"]))
    return rows


def _choose_workflows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    primary = None
    for row in rows:
        if row["directlyActivatable"] and row["meaningfulOutcomeEvidence"] and row["feature"] == "shops":
            primary = row
            break
    if primary is None:
        for row in rows:
            if row["directlyActivatable"] and row["meaningfulOutcomeEvidence"]:
                primary = row
                break
    if primary is None and rows:
        primary = rows[0]

    backup = None
    for row in rows:
        if row["feature"] == "quests" and row["path"].endswith("Playtime.Button"):
            backup = row
            break
    if backup is None:
        for row in rows:
            if primary is None or row["path"] != primary["path"]:
                backup = row
                break

    # Secondary control preference for primary sequence.
    secondary = None
    if primary and primary["feature"] == "shops":
        for row in rows:
            if row["feature"] == "shops" and "Lemon.Button" in row["path"]:
                secondary = row
                break
    return {"primary": primary, "backup": backup, "secondary": secondary}


def _write_target_inventory(output_dir: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    json_path = output_dir / "targets-18-analysis.json"
    json_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    table_lines = [
        "# Bubble Gum INFINITY — 18 Target Analysis",
        "",
        "| # | Feature | GUI path | GUI name | Available text hints (captured/path-derived) | Interaction | Directly activatable | Meaningful outcome evidence | Multi-step potential | Prerequisites / limitations |",
        "|---:|---|---|---|---|---|---|---|---|---|",
    ]
    for row in sorted(rows, key=lambda item: item["id"]):
        hints = ", ".join(row["availableTextHints"]) if row["availableTextHints"] else "none captured"
        meaningful = (
            f"yes (state max {row['maxStateChangeCount']}, explicit outcomes {row['explicitOutcomeCandidateEvents']})"
            if row["meaningfulOutcomeEvidence"]
            else f"no (state max {row['maxStateChangeCount']}, explicit outcomes {row['explicitOutcomeCandidateEvents']})"
        )
        prereq = row["prerequisites"] + " / " + row["limitations"]
        table_lines.append(
            "| {id} | {feature} | `{path}` | `{gui}` | {hints} | `{itype}` | {direct} | {meaningful} | {multi} | {prereq} |".format(
                id=row["id"],
                feature=row["feature"],
                path=row["path"],
                gui=row["guiName"],
                hints=hints,
                itype=row["interactionType"],
                direct="yes" if row["directlyActivatable"] else "no",
                meaningful=meaningful,
                multi="yes" if row["multiStepWorkflowPotential"] else "limited",
                prereq=prereq,
            )
        )

    ranking_lines = [
        "",
        "## Ranked live-capture candidates",
        "",
        "| Rank | Score | Feature | Path | Why ranked |",
        "|---:|---:|---|---|---|",
    ]
    for index, row in enumerate(rows[:8], start=1):
        reasons = [
            f"state max {row['maxStateChangeCount']}",
            f"gui max {row['maxGuiStateChangeCount']}",
            f"explicit outcomes {row['explicitOutcomeCandidateEvents']}",
        ]
        ranking_lines.append(
            f"| {index} | {row['workflowScore']} | {row['feature']} | `{row['path']}` | {', '.join(reasons)} |"
        )

    (output_dir / "targets-18-analysis.md").write_text(
        "\n".join(table_lines + ranking_lines) + "\n", encoding="utf-8"
    )


def _write_workflow_docs(output_dir: pathlib.Path, selected: dict[str, Any], manifest: dict[str, Any]) -> None:
    primary = selected.get("primary")
    backup = selected.get("backup")
    secondary = selected.get("secondary")

    primary_lines = [
        "# Workflow Selection",
        "",
        "## Primary workflow (selected)",
    ]
    if primary is None:
        primary_lines.append("No target available.")
    else:
        primary_lines.extend(
            [
                f"- Feature under test: `{primary['feature']}`",
                f"- Primary control: `{primary['path']}`",
                f"- Interaction type: `{primary['interactionType']}`",
                f"- Prior evidence: state max `{primary['maxStateChangeCount']}`, GUI max `{primary['maxGuiStateChangeCount']}`, explicit outcomes `{primary['explicitOutcomeCandidateEvents']}`",
                "- Observable value to watch: `leaderstats.🟣 Bubbles` (if visible), plus GUI transition state.",
                "- Success signal for this milestone: one explicit workflow recording with linked multi-step actions and at least one explicit outcome-candidate event.",
                "- Inspector evidence expected: shared recording transaction ID, observation windows, attributable feature path, and before/after scalar or GUI-state deltas.",
            ]
        )
        if secondary is not None:
            primary_lines.append(f"- Secondary supporting control: `{secondary['path']}`")

    primary_lines.extend(["", "## Backup workflow", ""])
    if backup is None:
        primary_lines.append("No backup target available.")
    else:
        primary_lines.extend(
            [
                f"- Feature under test: `{backup['feature']}`",
                f"- Control: `{backup['path']}`",
                "- Intended evidence: repeatable GUI transitions with linked transaction recording when primary control is unavailable.",
                "- Limitation: may produce little scalar-state change; use only if primary path is inaccessible.",
            ]
        )

    (output_dir / "workflow-selection.md").write_text("\n".join(primary_lines) + "\n", encoding="utf-8")

    place_id = manifest.get("placeId")
    checklist_lines = [
        "# Beginner Operator Checklist",
        "",
        f"1. Open Roblox game **Bubble Gum Simulator INFINITY** (Place ID `{place_id}`).",
        "2. Execute `LycolesUniversalInspector.lua` (version shown in header must be v30.6.35 or newer).",
        "3. In inspector panel, verify `SCAN MODE: FULL`. If not, click `SCAN MODE` until FULL appears.",
        "4. Verify interaction observer is active: `INTERACT: ON (AUTO)` or `INTERACT: ON (...)`.",
        "5. Keep `EVIDENCE: ON` and `WATCH: ON`.",
        "6. Click `RECORD FLOW: OFF` once to arm recording; status should mention 60 seconds / 8 interactions.",
    ]
    if primary is not None:
        checklist_lines.extend(
            [
                "7. Perform the **primary workflow** without long pauses:",
                "   - Open Gum Shop UI in-game if not already open.",
                f"   - Click `{secondary['path']}` once." if secondary else "   - Perform prerequisite shop selection control once.",
                f"   - Click `{primary['path']}` once.",
                f"   - Click `{primary['path']}` a second time (repeat evidence).",
                "   - Wait 4 seconds for observation windows to complete.",
            ]
        )
    checklist_lines.extend(
        [
            "8. Press `SCAN` once. Wait for completion status (complete or partial snapshot text).",
            "9. Press `SAVE REPORT` and confirm status says complete report saved (parts + manifest).",
            "10. In your executor workspace, confirm files exist: `Lycoles_<placeId>_<scanId>_part-XXXX.json` and `_manifest.json`.",
            "11. Count part files and ensure count equals `expectedParts` in manifest JSON.",
            "12. Optional: if receiver configured, press `SEND JSON` and keep ACK status for logs.",
            "13. Return to OpenHands: upload/copy the saved `_manifest.json` and part files (or receiver scan ID + integrity output).",
        ]
    )
    (output_dir / "operator-checklist.md").write_text("\n".join(checklist_lines) + "\n", encoding="utf-8")


def _write_export_docs(output_dir: pathlib.Path) -> None:
    lines = [
        "# Export and Retrieval Instructions",
        "",
        "## Preferred path (local export, no receiver dependency)",
        "1. Use inspector `SAVE REPORT`.",
        "2. Keep all part files and the matching `_manifest.json` together.",
        "3. Verify part count equals manifest `expectedParts`.",
        "",
        "## Receiver path (optional)",
        "- Receiver ingest endpoint format expected by inspector: `https://<host>/ingest/<INGEST_KEY>`.",
        "- ACK is not full integrity proof. Retrieve metadata/integrity via receiver read key endpoints.",
        "",
        "### Safe retrieval command (if receiver used)",
        "```bash",
        "export LYCOLES_READ_KEY='<read-key>'",
        "python3 tools/fetch_receiver_scan.py https://<receiver-origin> <scan_id> \\",
        "  --output build/live_test_bubble/retrieved_parts \\",
        "  --local-manifest <local_manifest.json> \\",
        "  --resume build/live_test_bubble/retrieval_resume",
        "```",
        "",
        "### Reconcile local vs receiver integrity",
        "```bash",
        "python3 tools/reconcile_receiver.py <local_manifest.json> <receiver_integrity_or_manifest.json> \\",
        "  --output build/live_test_bubble/reconcile-result.json",
        "```",
    ]
    (output_dir / "export-and-retrieval.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_post_test_validation_doc(output_dir: pathlib.Path) -> None:
    lines = [
        "# Post-test Validation",
        "",
        "Run this after you return the new manifest and part files:",
        "",
        "```bash",
        "python3 tools/validate_live_capture.py \\",
        "  --manifest <new_manifest.json> \\",
        "  --parts-dir <directory_with_part_json_files> \\",
        "  --output build/live_test_bubble/post_test_validation \\",
        "  --place-id 85896571713843",
        "```",
        "",
        "Then inspect:",
        "- `build/live_test_bubble/post_test_validation/live-capture-validation.md`",
        "- `build/live_test_bubble/post_test_validation/live-capture-validation.json`",
        "",
        "Required progression checks:",
        "- Multipart completeness and missing part indices",
        "- Transaction reuse/linkage",
        "- Explicit outcome-candidate coverage",
        "- Corroborated outcomes and completed workflow candidates",
        "- Generation readiness blockers and next required artifact",
        "- Produced Luau artifacts (`LycolesGeneratedUtility.lua` vs manifest-assisted fallback)",
    ]
    (output_dir / "post-test-validation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_troubleshooting(output_dir: pathlib.Path) -> None:
    lines = [
        "# Troubleshooting",
        "",
        "- **RECORD FLOW button unavailable**: wait until observer sweep completes; ensure `INTERACT` is ON.",
        "- **SCAN blocked by unsent parts**: press `SEND JSON` retry or `SAVE REPORT` before rescanning.",
        "- **SAVE REPORT incomplete**: ensure writefile support and enough storage; repeat SAVE until complete.",
        "- **No state change observed**: repeat action after opening the corresponding menu and keep target scalar visible.",
        "- **Upload ACK partial**: treat as incomplete; use local saved parts for offline validation.",
        "- **Script generation still blocked**: inspect blocker list in validation report and capture only missing evidence next.",
    ]
    (output_dir / "troubleshooting.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_readme(output_dir: pathlib.Path, selected: dict[str, Any]) -> None:
    primary = selected.get("primary")
    backup = selected.get("backup")
    lines = [
        "# Bubble Gum INFINITY Live Test Package",
        "",
        "Generated package for the first live end-to-end workflow capture.",
        "",
        "## Files",
        "- `inspector-version.txt`",
        "- `LycolesManifestAssistedWorkflow.lua`",
        "- `manifest-assisted-workflow.json`",
        "- `manifest-readiness-v109.json`",
        "- `targets-18-analysis.md` and `targets-18-analysis.json`",
        "- `workflow-selection.md`",
        "- `operator-checklist.md`",
        "- `export-and-retrieval.md`",
        "- `post-test-validation.md`",
        "- `troubleshooting.md`",
        "",
        "## Selected workflows",
        f"- Primary: `{primary['path']}`" if primary else "- Primary: none",
        f"- Backup: `{backup['path']}`" if backup else "- Backup: none",
        "",
        "## Regeneration",
        "```bash",
        "python3 tools/prepare_live_test_bubble_package.py \\",
        "  --manifest \"Pasted text(20261102-152723).txt\" \\",
        "  --artifact-dir build/e2e_bubble_v108 \\",
        "  --output build/live_test_bubble \\",
        "  --place-id 85896571713843",
        "```",
    ]
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def prepare_package(manifest_path: pathlib.Path, artifact_dir: pathlib.Path,
                    output_dir: pathlib.Path, place_id: int) -> dict[str, Any]:
    _ensure_e2e_artifacts(manifest_path, artifact_dir, place_id)
    manifest = _load_json(manifest_path)
    assisted_meta = _load_json(artifact_dir / "manifest-assisted-workflow.json")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Copy core artifacts into package.
    for name in [
        "LycolesManifestAssistedWorkflow.lua",
        "manifest-assisted-workflow.json",
        "manifest-readiness-v109.json",
    ]:
        shutil.copy2(artifact_dir / name, output_dir / name)

    version = (ROOT / "version.txt").read_text(encoding="utf-8").strip()
    (output_dir / "inspector-version.txt").write_text(version + "\n", encoding="utf-8")

    rows = _target_rows(manifest, assisted_meta)
    selected = _choose_workflows(rows)

    _write_target_inventory(output_dir, rows)
    _write_workflow_docs(output_dir, selected, manifest)
    _write_export_docs(output_dir)
    _write_post_test_validation_doc(output_dir)
    _write_troubleshooting(output_dir)
    _write_readme(output_dir, selected)

    return {
        "outputDir": str(output_dir),
        "targetCount": len(rows),
        "primaryPath": selected.get("primary", {}).get("path") if selected.get("primary") else None,
        "backupPath": selected.get("backup", {}).get("path") if selected.get("backup") else None,
        "version": version,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare Bubble live-test package.")
    parser.add_argument("--manifest", default="Pasted text(20261102-152723).txt")
    parser.add_argument("--artifact-dir", default="build/e2e_bubble_v108")
    parser.add_argument("--output", default="build/live_test_bubble")
    parser.add_argument("--place-id", type=int, default=85896571713843)
    args = parser.parse_args()

    result = prepare_package(
        pathlib.Path(args.manifest),
        pathlib.Path(args.artifact_dir),
        pathlib.Path(args.output),
        args.place_id,
    )
    print(json.dumps({"ok": True, **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
