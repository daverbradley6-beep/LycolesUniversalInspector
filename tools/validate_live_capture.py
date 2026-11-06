#!/usr/bin/env python3
"""Validate a live inspector capture for generation readiness.

This utility accepts an inspector manifest JSON (required) and an optional
numbered parts directory. It reports evidence coverage, linkage quality,
outcome-candidate density, multipart completeness, and runs the existing
build_release pipeline to verify generated artifacts.
"""

from __future__ import annotations

import argparse
import collections
import contextlib
import importlib.util
import io
import json
import pathlib
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load_module(path: pathlib.Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"invalid JSON file: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object in {path}")
    return data


def _safe_int(value: Any, default: int = 0) -> int:
    return value if type(value) is int else default


def interaction_metrics(history: list[dict[str, Any]]) -> dict[str, Any]:
    transaction_counts: collections.Counter[str] = collections.Counter()
    events_with_state = 0
    events_with_gui = 0
    explicit_outcome_events = 0
    observable_change_events = 0
    path_identity_resolved = 0
    state_identity_resolved = 0
    outcome_verified_events = 0

    for event in history:
        state_change_count = _safe_int(event.get("stateChangeCount"))
        gui_change_count = _safe_int(event.get("guiStateChangeCount"))
        if state_change_count > 0:
            events_with_state += 1
        if gui_change_count > 0:
            events_with_gui += 1
        if state_change_count + gui_change_count > 0:
            observable_change_events += 1
        if isinstance(event.get("observableOutcomeCandidate"), dict):
            explicit_outcome_events += 1
        if event.get("outcomeVerified") is True:
            outcome_verified_events += 1

        transaction_id = event.get("transactionId")
        if transaction_id is not None:
            transaction_counts[str(transaction_id)] += 1

        if event.get("pathIdentityStatus") == "component-resolved" or isinstance(
            event.get("pathIdentity"), list
        ):
            path_identity_resolved += 1

        for change in event.get("stateChanges") or []:
            if not isinstance(change, dict):
                continue
            if change.get("stateIdentityStatus") == "component-resolved" or isinstance(
                change.get("stateIdentity"), list
            ):
                state_identity_resolved += 1

    reused_transactions = {k: v for k, v in transaction_counts.items() if v > 1}
    return {
        "events": len(history),
        "eventsWithStateChanges": events_with_state,
        "eventsWithGuiChanges": events_with_gui,
        "observableChangeEvents": observable_change_events,
        "explicitOutcomeCandidateEvents": explicit_outcome_events,
        "outcomeVerifiedEvents": outcome_verified_events,
        "eventsWithResolvedPathIdentity": path_identity_resolved,
        "stateChangesWithResolvedIdentity": state_identity_resolved,
        "transactionIdEvents": sum(transaction_counts.values()),
        "uniqueTransactionIds": len(transaction_counts),
        "reusedTransactionIds": len(reused_transactions),
        "maxEventsPerTransaction": max(transaction_counts.values(), default=0),
        "sampleReusedTransactions": [
            {"transactionId": key, "eventCount": reused_transactions[key]}
            for key in sorted(reused_transactions)[:10]
        ],
    }


def _inspect_parts(parts_dir: pathlib.Path, scan_id: str | None) -> dict[str, Any]:
    if parts_dir.is_symlink() or not parts_dir.is_dir():
        raise ValueError("parts directory must be a regular directory")

    index_map: dict[int, dict[str, Any]] = {}
    identity_mismatches = 0
    invalid_part_files = 0

    for candidate in sorted(parts_dir.glob("*.json")):
        if candidate.is_symlink() or not candidate.is_file():
            continue
        try:
            doc = _load_json(candidate)
        except Exception:
            invalid_part_files += 1
            continue
        part_index = doc.get("partIndex")
        part_count = doc.get("partCount")
        part_scan_id = doc.get("scanId")
        if type(part_index) is not int or type(part_count) is not int:
            continue
        if scan_id and part_scan_id != scan_id:
            identity_mismatches += 1
            continue
        if part_index < 1 or part_index > part_count:
            identity_mismatches += 1
            continue
        index_map[part_index] = {
            "file": candidate.name,
            "partCount": part_count,
            "scanId": part_scan_id,
            "objectCount": len(doc.get("objects") or []),
        }

    part_count_values = {entry["partCount"] for entry in index_map.values()}
    inferred_expected_parts = part_count_values.pop() if len(part_count_values) == 1 else None
    found_parts = len(index_map)
    missing = []
    if inferred_expected_parts and inferred_expected_parts >= 1:
        missing = [i for i in range(1, inferred_expected_parts + 1) if i not in index_map]

    return {
        "directory": str(parts_dir),
        "foundParts": found_parts,
        "inferredExpectedParts": inferred_expected_parts,
        "missingPartIndices": missing,
        "identityMismatchCount": identity_mismatches,
        "invalidPartFiles": invalid_part_files,
    }


def _run_build_release(input_path: pathlib.Path, output_dir: pathlib.Path) -> dict[str, Any]:
    builder = _load_module(ROOT / "tools" / "build_release.py", "lycoles_build_release_live_validator")
    output_dir.mkdir(parents=True, exist_ok=True)
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        result = builder.build(input_path, output_dir)

    artifacts = {
        "manifestReadiness": (output_dir / "manifest-readiness-v109.json").exists(),
        "manifestAssistedLua": (output_dir / "LycolesManifestAssistedWorkflow.lua").exists(),
        "manifestAssistedMetadata": (output_dir / "manifest-assisted-workflow.json").exists(),
        "generatedUtilityLua": (output_dir / "LycolesGeneratedUtility.lua").exists(),
        "generationReadiness": (output_dir / "generation-readiness.json").exists(),
        "capabilityPlan": (output_dir / "capability-plan.json").exists(),
        "releaseZipCount": len(list(output_dir.glob("Lycoles-*-*.zip"))),
    }

    return {
        "result": result,
        "artifacts": artifacts,
        "outputDir": str(output_dir),
        "buildReleaseLog": stream.getvalue().strip(),
    }


def _blocker_guidance(blockers: list[str]) -> list[str]:
    guidance: list[str] = []
    if "full_multipart_report_unavailable" in blockers:
        guidance.append("Capture and return complete numbered part JSON files plus manifest.")
    if "workflow_linkage_not_observed" in blockers:
        guidance.append("Arm RECORD FLOW and perform a multi-step sequence within one 60-second recording window.")
    if "workflow_outcome_corroboration_unavailable" in blockers:
        guidance.append("Repeat the same action sequence at least once to provide corroborated outcome windows.")
    if "completed_workflow_candidates_unavailable" in blockers:
        guidance.append("Use controls likely to change observable state (currency, hatches, rewards) before rescanning.")
    if "legacy_manifest_missing_outcome_candidate_field" in blockers:
        guidance.append("Use inspector v30.6.29+ and keep interaction observer active through completion.")
    if "explicit_outcome_candidate_events_unavailable" in blockers:
        guidance.append("Keep relevant scalar values visible and stable while actions are performed.")
    if "receiver_scan_id_unavailable" in blockers:
        guidance.append("Return manifest with scanId and/or receiver integrity metadata.")
    return guidance


def build_summary(
    manifest_path: pathlib.Path,
    output_dir: pathlib.Path,
    parts_dir: pathlib.Path | None = None,
    expected_place_id: int | None = None,
) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    place_id = manifest.get("placeId")
    if expected_place_id is not None and place_id != expected_place_id:
        raise ValueError(f"placeId mismatch: expected {expected_place_id}, got {place_id}")

    interaction_diag = manifest.get("interactionDiagnostics")
    interaction_diag = interaction_diag if isinstance(interaction_diag, dict) else {}
    history = interaction_diag.get("recentInteractions")
    history = history if isinstance(history, list) else []
    history = [item for item in history if isinstance(item, dict)]

    interaction = interaction_metrics(history)
    interaction["eventsReportedByInspector"] = _safe_int(interaction_diag.get("totalInteractionEvents"))
    interaction["historyIsSubset"] = (
        interaction["eventsReportedByInspector"] > 0
        and interaction["events"] < interaction["eventsReportedByInspector"]
    )
    workflow_stats = interaction_diag.get("workflowStats")
    workflow_stats = workflow_stats if isinstance(workflow_stats, dict) else {}
    generation_diag = interaction_diag.get("workflowGenerationDiagnostics")
    generation_diag = generation_diag if isinstance(generation_diag, dict) else {}

    readiness_mod = _load_module(
        ROOT / "tools" / "manifest_readiness_v109.py", "lycoles_manifest_readiness_live_validator"
    )
    readiness = readiness_mod.analyze(manifest)

    pipeline_input = parts_dir if parts_dir is not None else manifest_path
    pipeline = _run_build_release(pipeline_input, output_dir / "pipeline")

    multipart = {
        "manifestPartCount": _safe_int(manifest.get("partCount")),
        "manifestExpectedParts": _safe_int(manifest.get("expectedParts")),
        "manifestUploadedParts": _safe_int(manifest.get("uploadedParts")),
        "localExport": manifest.get("localExport") if isinstance(manifest.get("localExport"), dict) else None,
    }
    if parts_dir is not None:
        multipart["partsDirectory"] = _inspect_parts(parts_dir, manifest.get("scanId"))

    blockers = readiness.get("generationReadiness", {}).get("blockers")
    blockers = blockers if isinstance(blockers, list) else []

    summary = {
        "schemaVersion": "30.6.live-capture-validation.1",
        "manifestPath": str(manifest_path),
        "manifest": {
            "scanId": manifest.get("scanId"),
            "placeId": place_id,
            "version": manifest.get("version"),
            "inspectedAt": manifest.get("inspectedAt"),
        },
        "multipart": multipart,
        "interaction": interaction,
        "workflowDiagnostics": {
            "linkedConfirmations": _safe_int(workflow_stats.get("linkedConfirmations")),
            "linkedFollowups": _safe_int(workflow_stats.get("linkedFollowups")),
            "linkedWorkflowEvents": _safe_int(workflow_stats.get("linkedConfirmations"))
            + _safe_int(workflow_stats.get("linkedFollowups")),
            "corroboratedActionOutcomes": _safe_int(workflow_stats.get("actionOutcomesCorroborated")),
            "completedWorkflowCandidates": _safe_int(workflow_stats.get("completedCandidates")),
            "backfilledOutcomeCandidates": _safe_int(workflow_stats.get("backfilledOutcomeCandidates")),
            "explicitWorkflowRecordings": _safe_int((interaction_diag.get("workflowRecordingStats") or {}).get("started")),
            "workflowGenerationBlockers": generation_diag.get("blockers")
            if isinstance(generation_diag.get("blockers"), list)
            else [],
        },
        "generationReadiness": {
            "scriptGenerationReady": bool((readiness.get("generationReadiness") or {}).get("scriptGenerationReady")),
            "blockers": blockers,
            "nextRequiredArtifact": (readiness.get("generationReadiness") or {}).get("nextRequiredArtifact"),
            "workflowCaptureRecommendation": (readiness.get("generationReadiness") or {}).get("workflowCaptureRecommendation"),
            "minimumMissingEvidence": _blocker_guidance(blockers),
        },
        "pipeline": {
            "artifacts": pipeline["artifacts"],
            "outputDir": pipeline["outputDir"],
            "buildReleaseLog": pipeline.get("buildReleaseLog"),
        },
        "claims": readiness.get("claims"),
    }
    return summary


def _write_markdown(summary: dict[str, Any], output_path: pathlib.Path) -> None:
    interaction = summary["interaction"]
    workflow = summary["workflowDiagnostics"]
    readiness = summary["generationReadiness"]
    multipart = summary["multipart"]
    artifacts = summary["pipeline"]["artifacts"]

    lines = [
        "# Live Capture Validation Summary",
        "",
        f"- Scan ID: `{summary['manifest'].get('scanId')}`",
        f"- Place ID: `{summary['manifest'].get('placeId')}`",
        f"- Inspector version: `{summary['manifest'].get('version')}`",
        "",
        "## Multipart completeness",
        f"- Manifest parts: `{multipart.get('manifestPartCount')}` expected `{multipart.get('manifestExpectedParts')}` uploaded `{multipart.get('manifestUploadedParts')}`",
    ]
    parts_dir = multipart.get("partsDirectory")
    if isinstance(parts_dir, dict):
        lines.extend(
            [
                f"- Parts directory found: `{parts_dir.get('foundParts')}` expected `{parts_dir.get('inferredExpectedParts')}`",
                f"- Missing part indices: `{parts_dir.get('missingPartIndices')}`",
                f"- Identity mismatch count: `{parts_dir.get('identityMismatchCount')}`",
            ]
        )

    lines.extend(
        [
            "",
            "## Interaction coverage",
            f"- Interaction events available: `{interaction['events']}`",
            f"- Interaction events reported by inspector: `{interaction['eventsReportedByInspector']}`",
            f"- History subset: `{interaction['historyIsSubset']}`",
            f"- Events with state changes: `{interaction['eventsWithStateChanges']}`",
            f"- Events with GUI changes: `{interaction['eventsWithGuiChanges']}`",
            f"- Explicit outcome-candidate events: `{interaction['explicitOutcomeCandidateEvents']}`",
            f"- Reused transaction IDs: `{interaction['reusedTransactionIds']}`",
            f"- Max events per transaction: `{interaction['maxEventsPerTransaction']}`",
            f"- Resolved path identities: `{interaction['eventsWithResolvedPathIdentity']}`",
            f"- Resolved state identities: `{interaction['stateChangesWithResolvedIdentity']}`",
            "",
            "## Workflow diagnostics",
            f"- Linked workflow events: `{workflow['linkedWorkflowEvents']}`",
            f"- Corroborated action outcomes: `{workflow['corroboratedActionOutcomes']}`",
            f"- Completed workflow candidates: `{workflow['completedWorkflowCandidates']}`",
            f"- Explicit workflow recordings: `{workflow['explicitWorkflowRecordings']}`",
            "",
            "## Generation readiness",
            f"- scriptGenerationReady: `{readiness['scriptGenerationReady']}`",
            f"- blockers: `{readiness['blockers']}`",
            f"- nextRequiredArtifact: `{readiness.get('nextRequiredArtifact')}`",
            "",
            "## Pipeline artifacts",
            f"- generated utility lua: `{artifacts.get('generatedUtilityLua')}`",
            f"- manifest-assisted lua: `{artifacts.get('manifestAssistedLua')}`",
            f"- generation readiness json: `{artifacts.get('generationReadiness')}`",
            f"- release zip count: `{artifacts.get('releaseZipCount')}`",
            "",
        ]
    )

    if readiness.get("minimumMissingEvidence"):
        lines.append("## Minimum additional evidence guidance")
        for item in readiness["minimumMissingEvidence"]:
            lines.append(f"- {item}")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate live inspector capture readiness.")
    parser.add_argument("--manifest", required=True, help="inspector manifest JSON path")
    parser.add_argument("--parts-dir", help="optional numbered part directory")
    parser.add_argument("--output", required=True, help="output directory for validation report")
    parser.add_argument("--place-id", type=int, help="optional expected place ID guard")
    args = parser.parse_args()

    manifest_path = pathlib.Path(args.manifest)
    parts_dir = pathlib.Path(args.parts_dir) if args.parts_dir else None
    output_dir = pathlib.Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = build_summary(manifest_path, output_dir, parts_dir, args.place_id)
    json_path = output_dir / "live-capture-validation.json"
    md_path = output_dir / "live-capture-validation.md"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_markdown(summary, md_path)

    print(json.dumps({
        "ok": True,
        "output": str(output_dir),
        "summaryJson": str(json_path),
        "summaryMarkdown": str(md_path),
        "scriptGenerationReady": summary["generationReadiness"]["scriptGenerationReady"],
        "blockerCount": len(summary["generationReadiness"]["blockers"]),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
