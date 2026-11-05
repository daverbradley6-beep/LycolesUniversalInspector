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



def _transport_stage_labels(status, attempted, acknowledged, expected, integrity, available):
    if status=="configuration-error":
        attempt_status=("attempted-previously-currently-blocked" if attempted
            else "blocked-before-attempt")
    elif status=="cancelled":
        attempt_status="attempted-cancelled" if attempted else "cancelled-before-attempt"
    else:
        attempt_status="attempted" if attempted else "not-attempted"
    if integrity:
        receiver_status="integrity-verified"
    elif expected>0 and acknowledged==expected:
        receiver_status="acknowledged-awaiting-integrity"
    elif status=="uploading":
        receiver_status="upload-in-progress"
    elif status=="cancelled" and acknowledged==0:
        receiver_status="upload-cancelled"
    elif acknowledged>0:
        receiver_status="partially-acknowledged"
    elif status in {"failed","incomplete"}:
        receiver_status="upload-incomplete"
    elif status=="configuration-error":
        receiver_status="configuration-blocked"
    else:
        receiver_status="unavailable"
    downstream_status=("available" if available else
        ("receiver-integrity-verified-not-available" if integrity else "not-validated"))
    return attempt_status,receiver_status,downstream_status


def _workflow_generation_diagnostics(value):
    if value is None:
        return {"available": False, "blockers": []}
    details = _mapping(value, "workflow generation diagnostics")
    available = details.get("available")
    if type(available) is not bool:
        raise ValueError("invalid workflow generation availability")
    blockers = details.get("blockers", [])
    if not isinstance(blockers, list) or len(blockers) > 64:
        raise ValueError("invalid workflow generation blockers")
    if any(not isinstance(item, str) or not item or len(item) > 120 for item in blockers):
        raise ValueError("invalid workflow generation blocker")
    if blockers != list(dict.fromkeys(blockers)):
        raise ValueError("duplicate workflow generation blocker")

    result = {"available": available, "blockers": blockers}
    for field in (
            "interactionEvents",
            "attributedInteractions",
            "unattributedInteractions",
            "linkedConfirmations",
            "corroboratedActionOutcomes",
            "completedWorkflowCandidates",
            "explicitWorkflowRecordings"):
        current = details.get(field)
        if current is not None:
            result[field] = _integer(current, f"workflow generation {field}")
    return result




def _transport_readiness(transport):
    status = transport["uploadStatus"]
    receiver_status = transport["receiverReportStatus"]
    downstream_status = transport["downstreamAvailabilityStatus"]
    local_export = transport.get("localExport") if isinstance(transport.get("localExport"), dict) else {}
    blockers = []
    if status == "unknown_legacy_manifest_snapshot":
        blockers.append("upload_attempt_status_unknown_legacy_manifest")
    elif status == "not-attempted":
        blockers.append("upload_not_attempted")
    elif status == "cancelled":
        blockers.append("upload_cancelled_before_completion")
    elif status in {"failed", "incomplete", "configuration-error"}:
        blockers.append("upload_not_completed")
    if receiver_status in {"unknown-legacy", "unavailable", "configuration-blocked", "upload-incomplete"}:
        blockers.append("receiver_report_not_confirmed")
    if downstream_status != "available":
        blockers.append("downstream_report_not_validated")
    if local_export.get("completeNumberedPartsClaimed") is not True:
        blockers.append("complete_local_numbered_parts_unavailable")

    if downstream_status == "available":
        readiness_status = "report-available"
    elif receiver_status == "integrity-verified":
        readiness_status = "receiver-integrity-verified-not-retrieved"
    elif receiver_status == "acknowledged-awaiting-integrity":
        readiness_status = "upload-acknowledged-awaiting-integrity"
    elif status == "uploading":
        readiness_status = "upload-in-progress"
    elif status == "cancelled":
        readiness_status = "upload-cancelled"
    elif status in {"failed", "incomplete", "configuration-error"}:
        readiness_status = "upload-failed-or-blocked"
    elif status == "not-attempted":
        readiness_status = "report-generated-upload-not-attempted"
    else:
        readiness_status = "report-generated-upload-state-unknown"

    if readiness_status == "report-generated-upload-state-unknown":
        next_step = "export complete numbered parts locally and/or run a fresh upload attempt to disambiguate lifecycle state"
    elif readiness_status == "report-generated-upload-not-attempted":
        next_step = "run upload attempt or save complete numbered parts locally"
    elif readiness_status in {"upload-cancelled", "upload-failed-or-blocked"}:
        next_step = "retry upload and/or export complete numbered parts for offline processing"
    elif readiness_status == "upload-acknowledged-awaiting-integrity":
        next_step = "verify receiver integrity for this scan ID or export complete numbered parts locally"
    elif readiness_status == "receiver-integrity-verified-not-retrieved":
        next_step = "retrieve and validate full multipart report from receiver"
    elif readiness_status == "upload-in-progress":
        next_step = "wait for upload completion and receiver acknowledgement"
    else:
        next_step = "receiver report is available; proceed with full evidence processing"

    return {
        "status": readiness_status,
        "uploadAttempted": transport["uploadAttempted"],
        "uploadStatus": status,
        "receiverReportStatus": receiver_status,
        "downstreamAvailabilityStatus": downstream_status,
        "completeLocalNumberedPartsClaimed": local_export.get("completeNumberedPartsClaimed") is True,
        "blockers": list(dict.fromkeys(blockers)),
        "nextAction": next_step,
    }


def _workflow_linkage_diagnostics(total_interactions, attributed_interactions,
        linked_confirmations, corroborated_outcomes, completed_candidates,
        workflow_generation):
    if total_interactions <= 0:
        status = "no-interactions-observed"
    elif completed_candidates > 0:
        status = "completed-workflow-candidates-observed"
    elif linked_confirmations > 0 and corroborated_outcomes <= 0:
        status = "linked-confirmations-without-corroborated-outcomes"
    elif linked_confirmations <= 0 and attributed_interactions > 0:
        status = "attributed-interactions-without-linkage"
    elif attributed_interactions <= 0:
        status = "no-attributed-interactions"
    else:
        status = "interaction-linkage-insufficient"

    blockers = []
    if workflow_generation.get("available") is True:
        mapped = {
            "no-linked-confirmation-events": "workflow_linkage_not_observed",
            "no-corroborated-action-outcomes": "workflow_outcome_corroboration_unavailable",
            "no-completed-workflow-candidates": "completed_workflow_candidates_unavailable",
            "some-interactions-remain-unattributed": "interaction_attribution_incomplete",
            "no-feature-attributed-interactions": "no_attributed_interactions",
        }
        for blocker in workflow_generation.get("blockers", []):
            mapped_value = mapped.get(blocker)
            if mapped_value:
                blockers.append(mapped_value)
    else:
        if linked_confirmations <= 0 and total_interactions > 0:
            blockers.append("workflow_linkage_not_observed")
        if corroborated_outcomes <= 0 and total_interactions > 0:
            blockers.append("workflow_outcome_corroboration_unavailable")
        if completed_candidates <= 0 and total_interactions > 0:
            blockers.append("completed_workflow_candidates_unavailable")
        if attributed_interactions <= 0 and total_interactions > 0:
            blockers.append("no_attributed_interactions")

    if status == "no-interactions-observed":
        recommendation = "record at least one feature-relevant interaction sequence with observer enabled"
    elif status == "no-attributed-interactions":
        recommendation = "capture interactions on named feature controls and keep relevant menus visible"
    elif status == "attributed-interactions-without-linkage":
        recommendation = "capture one confirmation-style sequence (initiator then confirm/cancel) within the same menu"
    elif status == "linked-confirmations-without-corroborated-outcomes":
        recommendation = "capture linked actions while relevant observable values are visible before and after activation"
    elif status == "completed-workflow-candidates-observed":
        recommendation = "use completed workflow candidates as input to generation planning"
    else:
        recommendation = "capture additional linked interactions with observable outcomes"

    return {
        "status": status,
        "workflowGenerationDiagnosticsAvailable": workflow_generation.get("available") is True,
        "linkedConfirmationCoverage": (0 if total_interactions <= 0 else
            round(linked_confirmations / total_interactions, 4)),
        "corroboratedOutcomeCoverage": (0 if total_interactions <= 0 else
            round(corroborated_outcomes / total_interactions, 4)),
        "completedWorkflowCoverage": (0 if total_interactions <= 0 else
            round(completed_candidates / total_interactions, 4)),
        "blockers": list(dict.fromkeys(blockers)),
        "recommendedCapture": recommendation,
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
        inferred_attempt = True if legacy_uploaded > 0 else None
        diagnostic = (
            "legacy uploadedParts indicates an attempted upload, but lifecycle details are unavailable"
            if legacy_uploaded > 0 else
            "legacy uploadedParts is a pre-upload placeholder, not failure or success evidence"
        )
        return {
            "reportGenerated": True,
            "manifestSnapshotPhase": "legacy-unspecified",
            "uploadAttempted": inferred_attempt,
            "uploadAttemptStatus": "unknown-legacy",
            "uploadStatus": "unknown_legacy_manifest_snapshot",
            "receiverReportStatus": "unknown-legacy",
            "downstreamAvailabilityStatus": "not-validated",
            "acknowledgedParts": None,
            "expectedParts": expected,
            "acknowledgedDigestParts": None,
            "acknowledgementDigestCoverageComplete": False,
            "uploadFailed": False,
            "receiverIntegrityVerified": False,
            "downstreamReportAvailable": False,
            "legacyUploadedParts": legacy_uploaded,
            "legacyUploadAttemptInference": "attempted" if legacy_uploaded > 0 else "unknown",
            "diagnostic": diagnostic,
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
    if status not in {"not-attempted", "uploading", "acknowledged", "incomplete", "failed", "configuration-error", "cancelled"}:
        raise ValueError("invalid upload status")
    expected_phase = {
        "not-attempted": "pre-upload",
        "uploading": "upload-started",
        "acknowledged": "post-upload",
        "incomplete": "post-upload",
        "failed": "post-upload",
        "configuration-error": "upload-blocked",
        "cancelled": "upload-cancelled",
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
    attempt_status,receiver_status,downstream_status=_transport_stage_labels(
        status,attempted,acknowledged,expected,integrity,available)
    for field,actual in (("uploadAttemptStatus",attempt_status),
            ("receiverReportStatus",receiver_status),
            ("downstreamAvailabilityStatus",downstream_status)):
        if field in transport and transport[field]!=actual:
            raise ValueError(f"inconsistent {field}")
    return {
        "reportGenerated": generated,
        "manifestSnapshotPhase": phase,
        "uploadAttempted": attempted,
        "uploadAttemptStatus": attempt_status,
        "uploadStatus": status,
        "receiverReportStatus": receiver_status,
        "downstreamAvailabilityStatus": downstream_status,
        "acknowledgedParts": acknowledged,
        "expectedParts": expected,
        "acknowledgedDigestParts": digest_count,
        "acknowledgementDigestCoverageComplete": digest_complete,
        "uploadFailed": status in {"incomplete", "failed", "configuration-error"},
        "receiverIntegrityVerified": integrity,
        "downstreamReportAvailable": available,
        "diagnostic": transport.get("lastError"),
    }


def _local_export(manifest, expected):
    export = manifest.get("localExport")
    if export is None:
        return {"attempted": False, "status": "not-attempted", "exportedParts": 0,
                "expectedParts": expected, "manifestSaved": None,
                "manifestWriteAttempts": None, "completeNumberedPartsClaimed": False,
                "partContentDigestsComputed": False, "diagnostic": None}
    export = _mapping(export, "local export")
    attempted = export.get("attempted")
    if type(attempted) is not bool:
        raise ValueError("invalid local export attempted status")
    status = export.get("status")
    if status not in {"not-attempted", "complete", "incomplete", "failed"}:
        raise ValueError("invalid local export status")
    exported = _integer(export.get("exportedParts"), "local exported parts")
    export_expected = _integer(export.get("expectedParts"), "local export expected parts", minimum=1)
    if export_expected != expected or exported > expected:
        raise ValueError("invalid local export part accounting")
    prefix = export.get("filenamePrefix")
    if (prefix is not None and (not isinstance(prefix, str) or not 1 <= len(prefix) <= 200
            or re.fullmatch(r"[A-Za-z0-9_.-]+", prefix) is None)):
        raise ValueError("invalid local export filename prefix")
    manifest_saved = export.get("manifestSaved")
    if manifest_saved is not None and type(manifest_saved) is not bool:
        raise ValueError("invalid local manifest saved status")
    write_attempts = export.get("manifestWriteAttempts")
    if write_attempts is not None:
        _integer(write_attempts, "local manifest write attempts")
        if write_attempts > 2:
            raise ValueError("invalid local manifest write attempts")
    digests = export.get("localPartContentDigestsComputed", False)
    if type(digests) is not bool:
        raise ValueError("invalid local part digest status")
    if status == "not-attempted" and (attempted or exported != 0):
        raise ValueError("inconsistent local export status")
    if status in {"complete", "incomplete", "failed"} and not attempted:
        raise ValueError("inconsistent local export status")
    if status == "complete" and (exported != expected or manifest_saved is False):
        raise ValueError("incomplete local export marked complete")
    if manifest_saved is True and (write_attempts is not None and write_attempts < 1):
        raise ValueError("inconsistent local manifest write status")
    diagnostic = export.get("lastError")
    if diagnostic is not None and (not isinstance(diagnostic, str) or len(diagnostic) > 200):
        raise ValueError("invalid local export diagnostic")
    return {"attempted": attempted, "status": status, "exportedParts": exported,
            "expectedParts": expected, "manifestSaved": manifest_saved,
            "manifestWriteAttempts": write_attempts,
            "completeNumberedPartsClaimed": status == "complete" and exported == expected,
            "partContentDigestsComputed": digests, "diagnostic": diagnostic}


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
    local_export = _local_export(manifest, transport["expectedParts"])
    transport["localExport"] = local_export
    transport["receiverIntegrityLookupAvailable"] = scan_id is not None
    transport["receiverIntegrityPath"] = (
        f"/reports/READ_KEY/{scan_id}/integrity" if scan_id else None
    )
    transport["lifecycleStages"] = {
        "scanComplete": scan["complete"],
        "reportGenerated": transport["reportGenerated"],
        "localExportAttempted": local_export["attempted"],
        "completeLocalNumberedPartsClaimed": local_export["completeNumberedPartsClaimed"],
        "uploadAttempted": transport["uploadAttempted"],
        "uploadAttemptStatus": transport["uploadAttemptStatus"],
        "uploadAcknowledged": transport["acknowledgedParts"]==transport["expectedParts"],
        "receiverReportStatus": transport["receiverReportStatus"],
        "receiverIntegrityVerified": transport["receiverIntegrityVerified"],
        "downstreamAvailabilityStatus": transport["downstreamAvailabilityStatus"],
        "downstreamReportAvailable": transport["downstreamReportAvailable"],
    }
    diagnostics = _mapping(manifest.get("interactionDiagnostics"), "interaction diagnostics")
    workflow = _mapping(diagnostics.get("workflowStats"), "workflow stats")
    workflow_generation = _workflow_generation_diagnostics(
        diagnostics.get("workflowGenerationDiagnostics"))
    history = diagnostics.get("recentInteractions") or []
    if not isinstance(history, list) or len(history) > 2000:
        raise ValueError("invalid interaction history")
    history_total = _integer(diagnostics.get("historyTotal", len(history)), "interaction history total")
    if history_total < len(history):
        raise ValueError("invalid interaction history total")
    interactions = _integer(diagnostics.get("totalInteractionEvents"), "interaction count")
    attributed_interactions = _integer(diagnostics.get("attributedEvents"), "attributed interactions")
    unattributed_interactions = _integer(diagnostics.get("unattributedEvents"), "unattributed interactions")
    state_transitions = _integer(workflow.get("uniqueStateEvents"), "state transitions")
    gui_transitions = _integer(workflow.get("guiTransitions"), "GUI transitions")
    linked_confirmations = _integer(workflow.get("linkedConfirmations"), "linked confirmations")
    corroborated_outcomes = _integer(workflow.get("actionOutcomesCorroborated"), "corroborated outcomes")
    completed_candidates = _integer(workflow.get("completedCandidates"), "completed candidates")
    transport_readiness = _transport_readiness(transport)
    workflow_linkage = _workflow_linkage_diagnostics(
        interactions, attributed_interactions, linked_confirmations,
        corroborated_outcomes, completed_candidates, workflow_generation)
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
    if workflow_generation.get("available") is True:
        for blocker, mapped in (
                ("explicit-workflow-recording-not-armed", "explicit_workflow_recording_not_armed"),
                ("no-linked-confirmation-events", "workflow_linkage_not_observed"),
                ("no-corroborated-action-outcomes", "workflow_outcome_corroboration_unavailable"),
                ("no-completed-workflow-candidates", "completed_workflow_candidates_unavailable")):
            if blocker in workflow_generation["blockers"] and mapped not in blockers:
                blockers.append(mapped)
    elif interactions > 0:
        if linked_confirmations == 0 and "workflow_linkage_not_observed" not in blockers:
            blockers.append("workflow_linkage_not_observed")
        if corroborated_outcomes == 0 and "workflow_outcome_corroboration_unavailable" not in blockers:
            blockers.append("workflow_outcome_corroboration_unavailable")
        if completed_candidates == 0 and "completed_workflow_candidates_unavailable" not in blockers:
            blockers.append("completed_workflow_candidates_unavailable")
        if unattributed_interactions > 0 and "interaction_attribution_incomplete" not in blockers:
            blockers.append("interaction_attribution_incomplete")
    if history_subset:
        blockers.append("complete_interaction_history_unavailable")
    if scan_id is None:
        blockers.append("receiver_scan_id_unavailable")
    if local_export["completeNumberedPartsClaimed"]:
        recovery = "provide_complete_local_numbered_parts"
        next_artifact = "complete locally exported numbered parts plus their matching manifest"
    elif transport["receiverReportStatus"] in {
            "acknowledged-awaiting-integrity","integrity-verified"}:
        recovery = "verify_receiver_integrity_or_save_numbered_parts"
        next_artifact = "verified receiver integrity result or complete local numbered parts"
    elif transport["uploadFailed"]:
        recovery = "retry_upload_or_save_numbered_parts"
        next_artifact = "successful receiver integrity result or complete local numbered parts"
    else:
        recovery = "save_numbered_parts_or_upload"
        next_artifact = "complete numbered multipart report from local export or verified receiver retrieval"
    return {
        "schemaVersion": "109.manifest-readiness.3",
        "scanId": scan_id,
        "placeId": place_id,
        "inspectorVersion": manifest.get("version"),
        "scan": scan,
        "transport": transport,
        "transportReadiness": transport_readiness,
        "evidence": {
            "interactions": interactions,
            "attributedInteractions": attributed_interactions,
            "unattributedInteractions": unattributed_interactions,
            "stateTransitions": state_transitions,
            "guiTransitions": gui_transitions,
            "linkedConfirmations": linked_confirmations,
            "corroboratedActionOutcomes": corroborated_outcomes,
            "completedWorkflowCandidates": completed_candidates,
            "historyEventsAvailable": len(history),
            "historyEventsReported": history_total,
            "historyIsSubset": history_subset,
            "featureConsistentOutcomeCandidatesLowerBound": len(outcomes),
            "workflowGenerationDiagnostics": workflow_generation,
            "workflowLinkageDiagnostics": workflow_linkage,
            "uploadLifecycle": {
                "uploadAttempted": transport["uploadAttempted"],
                "uploadStatus": transport["uploadStatus"],
                "uploadAttemptStatus": transport["uploadAttemptStatus"],
                "receiverReportStatus": transport["receiverReportStatus"],
                "downstreamAvailabilityStatus": transport["downstreamAvailabilityStatus"],
                "reportGenerated": transport["reportGenerated"],
                "manifestSnapshotPhase": transport["manifestSnapshotPhase"],
            },
        },
        "outcomeCandidates": outcomes,
        "capabilities": capabilities,
        "generationReadiness": {
            "scriptGenerationReady": False,
            "v108SourceCompatible": False,
            "fullMultipartReportAvailable": False,
            "completeLocalNumberedPartsClaimed": local_export["completeNumberedPartsClaimed"],
            "blockers": blockers,
            "recommendedRecovery": recovery,
            "nextRequiredArtifact": next_artifact,
            "workflowCaptureRecommendation": workflow_linkage["recommendedCapture"],
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
