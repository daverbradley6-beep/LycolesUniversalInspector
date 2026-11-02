#!/usr/bin/env python3
"""Analyze a local inspector manifest without treating it as a full scan report."""
import argparse
import hashlib
import json
import re
from pathlib import Path

MAX_INPUT_BYTES = 2_000_000
OUTCOME_MARKERS = ("claimed", "completed")
STATE_TERMS = {
    "pets": ("pet", "hatch", "egg"),
    "rewards": ("reward", "claim"),
    "rebirth": ("rebirth",),
    "training": ("strength", "agility", "training"),
    "inventory": ("inventory", "equip", "item"),
    "quests": ("quest", "mission"),
}


def _canonical(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _integer(value, name, *, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"invalid {name}")
    return value


def _mapping(value, name):
    if not isinstance(value, dict):
        raise ValueError(f"invalid {name}")
    return value

def _scan_id(manifest):
    value = manifest.get("scanId")
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", value):
        raise ValueError("invalid receiver scan ID")
    return value


def _object_accounting(manifest):
    diagnostics = _mapping(manifest.get("diagnostics"), "diagnostics")
    scanned = _integer(diagnostics.get("scannedObjects"), "scanned objects")
    recorded = _integer(diagnostics.get("recordedObjects"), "recorded objects")
    omitted = _integer(diagnostics.get("omittedObjects"), "omitted objects")
    object_count = _integer(manifest.get("objectCount"), "object count")
    if scanned != recorded + omitted or recorded != object_count:
        raise ValueError("invalid object accounting")
    scan_stats = _mapping(manifest.get("scanStats"), "scan stats")
    for field, expected in (("scanned", scanned), ("recorded", recorded), ("omitted", omitted)):
        if _integer(scan_stats.get(field), f"scan stats {field}") != expected:
            raise ValueError("invalid object accounting")
    return {
        "complete": diagnostics.get("complete") is True and scan_stats.get("complete") is True,
        "clientVisibleRootsOnly": diagnostics.get("completeButLimitedToClientVisibleRoots") is True,
        "objectAccountingValid": diagnostics.get("rootAccountingValid") is True,
        "scannedObjects": scanned,
        "recordedObjects": recorded,
        "omittedObjects": omitted,
    }


def _transport(manifest):
    expected = _integer(manifest.get("expectedParts", manifest.get("partCount")), "expected parts", minimum=1)
    part_count = _integer(manifest.get("partCount"), "part count", minimum=1)
    if expected != part_count:
        raise ValueError("invalid part accounting")
    transport = manifest.get("reportTransport")
    if transport is None:
        legacy_uploaded = _integer(manifest.get("uploadedParts", 0), "legacy uploaded parts")
        if legacy_uploaded > expected:
            raise ValueError("invalid legacy uploaded part count")
        return {
            "reportGenerated": True,
            "manifestSnapshotPhase": "legacy-unspecified",
            "uploadAttempted": None,
            "uploadStatus": "unknown_legacy_manifest_snapshot",
            "acknowledgedParts": None,
            "expectedParts": expected,
            "acknowledgedDigestParts": None,
            "acknowledgementDigestCoverageComplete": False,
            "uploadFailed": False,
            "receiverIntegrityVerified": False,
            "downstreamReportAvailable": False,
            "diagnostic": "legacy uploadedParts is a pre-upload placeholder, not failure or success evidence",
        }
    transport = _mapping(transport, "report transport")
    generated = transport.get("reportGenerated")
    if generated is not True:
        raise ValueError("invalid report generation status")
    phase = transport.get("manifestSnapshotPhase")
    if not isinstance(phase, str) or not phase or len(phase) > 80:
        raise ValueError("invalid manifest snapshot phase")
    attempted = transport.get("uploadAttempted")
    if type(attempted) is not bool:
        raise ValueError("invalid upload attempted status")
    acknowledged = _integer(transport.get("acknowledgedParts"), "acknowledged parts")
    transport_expected = _integer(transport.get("expectedParts"), "transport expected parts", minimum=1)
    if transport_expected != expected or acknowledged > expected:
        raise ValueError("invalid transport part accounting")
    digest_entries = transport.get("acknowledgedPartDigests", [])
    if not isinstance(digest_entries, list) or len(digest_entries) > expected:
        raise ValueError("invalid acknowledged digest list")
    digest_indexes = set()
    for entry in digest_entries:
        if not isinstance(entry, dict):
            raise ValueError("invalid acknowledged digest entry")
        index = _integer(entry.get("partIndex"), "acknowledged digest part index", minimum=1)
        digest = entry.get("sha256")
        if index > expected or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("invalid acknowledged digest entry")
        if index in digest_indexes:
            raise ValueError("duplicate acknowledged digest index")
        digest_indexes.add(index)
    digest_count = _integer(
        transport.get("acknowledgedDigestParts", len(digest_entries)),
        "acknowledged digest count")
    if digest_count != len(digest_entries) or digest_count > acknowledged:
        raise ValueError("invalid acknowledged digest accounting")
    digest_complete = digest_count == expected and digest_indexes == set(range(1, expected + 1))

    status = transport.get("uploadStatus")
    if status not in {"not-attempted", "uploading", "acknowledged", "incomplete", "failed", "configuration-error"}:
        raise ValueError("invalid upload status")
    expected_phase = {
        "not-attempted": "pre-upload",
        "uploading": "upload-started",
        "acknowledged": "post-upload",
        "incomplete": "post-upload",
        "failed": "post-upload",
        "configuration-error": "upload-blocked",
    }[status]
    if phase != expected_phase:
        raise ValueError("manifest snapshot phase is inconsistent with upload status")
    if status == "acknowledged" and acknowledged != expected:
        raise ValueError("acknowledged transport is incomplete")
    if status in {"uploading", "acknowledged", "incomplete", "failed"} and not attempted:
        raise ValueError("attempted transport status is inconsistent")
    if status == "not-attempted" and attempted:
        raise ValueError("not-attempted transport status is inconsistent")
    integrity = transport.get("receiverIntegrityVerified")
    available = transport.get("downstreamReportAvailable")
    if type(integrity) is not bool or type(available) is not bool:
        raise ValueError("invalid receiver verification status")
    if available and not integrity:
        raise ValueError("downstream availability requires receiver integrity verification")
    return {
        "reportGenerated": generated,
        "manifestSnapshotPhase": phase,
        "uploadAttempted": attempted,
        "uploadStatus": status,
        "acknowledgedParts": acknowledged,
        "expectedParts": expected,
        "acknowledgedDigestParts": digest_count,
        "acknowledgementDigestCoverageComplete": digest_complete,
        "uploadFailed": status in {"incomplete", "failed", "configuration-error"},
        "receiverIntegrityVerified": integrity,
        "downstreamReportAvailable": available,
        "diagnostic": transport.get("lastError"),
    }


def _state_candidate(feature, changes):
    terms = STATE_TERMS.get(feature, ())
    for change in changes or ():
        if not isinstance(change, dict):
            continue
        key = str(change.get("key", "")).lower()
        if any(term in key for term in terms) and change.get("before") != change.get("after"):
            return True
    return False


def _gui_candidate(feature, changes):
    if feature != "rewards":
        return False
    for change in changes or ():
        if not isinstance(change, dict) or change.get("afterVisible") is not True:
            continue
        path = str(change.get("path", "")).lower()
        if any(marker in path for marker in OUTCOME_MARKERS):
            return True
    return False


def _outcome_candidates(history):
    candidates = []
    for event in history:
        if not isinstance(event, dict):
            continue
        feature = event.get("featureCandidate")
        if not isinstance(feature, str):
            continue
        state = _state_candidate(feature, event.get("stateChanges"))
        gui = _gui_candidate(feature, event.get("guiStateChanges"))
        if not state and not gui:
            for window in event.get("observationWindows") or ():
                if isinstance(window, dict):
                    state = state or _state_candidate(feature, window.get("stateChanges"))
                    gui = gui or _gui_candidate(feature, window.get("guiChanges"))
        if not state and not gui:
            continue
        candidates.append({
            "sequence": event.get("sequence"),
            "feature": feature,
            "interactionPath": event.get("path"),
            "evidenceKinds": [name for name, present in (("feature_consistent_state_change", state), ("feature_consistent_gui_change", gui)) if present],
            "classification": "feature-consistent-observable-change",
            "sourceAuthenticityVerified": False,
            "causalityProven": False,
            "serverAuthorityVerified": False,
            "gameplayVerified": False,
        })
    return candidates


def analyze(manifest):
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    place_id = _integer(manifest.get("placeId"), "place ID", minimum=1)
    scan_id = _scan_id(manifest)
    scan = _object_accounting(manifest)
    transport = _transport(manifest)
    transport["receiverIntegrityLookupAvailable"] = scan_id is not None
    transport["receiverIntegrityPath"] = (
        f"/reports/READ_KEY/{scan_id}/integrity" if scan_id else None
    )
    diagnostics = _mapping(manifest.get("interactionDiagnostics"), "interaction diagnostics")
    workflow = _mapping(diagnostics.get("workflowStats"), "workflow stats")
    history = diagnostics.get("recentInteractions") or []
    if not isinstance(history, list) or len(history) > 2000:
        raise ValueError("invalid interaction history")
    history_total = _integer(diagnostics.get("historyTotal", len(history)), "interaction history total")
    if history_total < len(history):
        raise ValueError("invalid interaction history total")
    outcomes = _outcome_candidates(history)
    readiness = manifest.get("featureReadiness") or {}
    evidence = manifest.get("featureEvidence") or {}
    if not isinstance(readiness, dict) or not isinstance(evidence, dict):
        raise ValueError("invalid feature evidence")
    candidate_counts = {}
    for item in outcomes:
        candidate_counts[item["feature"]] = candidate_counts.get(item["feature"], 0) + 1
    capabilities = []
    for feature in sorted(set(readiness) | set(evidence)):
        item = readiness.get(feature) if isinstance(readiness.get(feature), dict) else {}
        lower_bound = candidate_counts.get(feature, 0)
        capabilities.append({
            "feature": feature,
            "discovered": item.get("discovered") is True,
            "observedInteractions": (item.get("interactionEvidence") or {}).get("count", 0),
            "observableOutcomeCandidatesLowerBound": lower_bound,
            "readiness": "observable-outcome-candidate-needs-causal-validation" if lower_bound else item.get("readiness", "unknown"),
            "implemented": False,
            "tested": False,
            "gameplayVerified": False,
        })
    history_subset = history_total > len(history) or bool((manifest.get("fixtureMetadata") or {}).get("historySubset"))
    blockers = [
        "full_multipart_report_unavailable",
        "canonical_object_identity_unavailable",
        "reviewed_implementation_contract_unavailable",
        "interaction_source_authenticity_unverified",
    ]
    if history_subset:
        blockers.append("complete_interaction_history_unavailable")
    if scan_id is None:
        blockers.append("receiver_scan_id_unavailable")
    return {
        "schemaVersion": "109.manifest-readiness.1",
        "scanId": scan_id,
        "placeId": place_id,
        "inspectorVersion": manifest.get("version"),
        "scan": scan,
        "transport": transport,
        "evidence": {
            "interactions": _integer(diagnostics.get("totalInteractionEvents"), "interaction count"),
            "attributedInteractions": _integer(diagnostics.get("attributedEvents"), "attributed interactions"),
            "unattributedInteractions": _integer(diagnostics.get("unattributedEvents"), "unattributed interactions"),
            "stateTransitions": _integer(workflow.get("uniqueStateEvents"), "state transitions"),
            "guiTransitions": _integer(workflow.get("guiTransitions"), "GUI transitions"),
            "linkedConfirmations": _integer(workflow.get("linkedConfirmations"), "linked confirmations"),
            "corroboratedActionOutcomes": _integer(workflow.get("actionOutcomesCorroborated"), "corroborated outcomes"),
            "completedWorkflowCandidates": _integer(workflow.get("completedCandidates"), "completed candidates"),
            "historyEventsAvailable": len(history),
            "historyEventsReported": history_total,
            "historyIsSubset": history_subset,
            "featureConsistentOutcomeCandidatesLowerBound": len(outcomes),
        },
        "outcomeCandidates": outcomes,
        "capabilities": capabilities,
        "generationReadiness": {
            "scriptGenerationReady": False,
            "v108SourceCompatible": False,
            "fullMultipartReportAvailable": False,
            "blockers": blockers,
            "nextRequiredArtifact": "complete numbered multipart report with verified receiver integrity",
        },
        "claims": {
            "readOnly": True,
            "sourceAuthenticityVerified": False,
            "runtimeVerified": False,
            "liveGameVerified": False,
            "serverAuthorityVerified": False,
            "causalityProven": False,
            "gameplayVerified": False,
        },
    }


def write(report, output):
    payload = _canonical(report)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_symlink():
        raise ValueError("output symlink forbidden")
    output.write_bytes(payload)
    return {
        "output": str(output),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "scriptGenerationReady": False,
        "gameplayVerified": False,
    }


def emit(manifest, output):
    return write(analyze(manifest), output)


def load(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError("invalid manifest input")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("build/manifest-readiness-v109.json"))
    args = parser.parse_args()
    try:
        result = emit(load(args.manifest), args.output)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        raise SystemExit(1)
    print(json.dumps({"ok": True, **result}, sort_keys=True))


if __name__ == "__main__":
    main()
