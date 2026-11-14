#!/usr/bin/env python3
"""v107 explicit client-action registry with runtime-evidence correlation.

Builds deterministic, read-only action metadata from the v107 feature plan and
optional client runtime evidence. Completed workflow candidates are correlation
records only and never proof of server-authoritative gameplay behaviour.
"""
import json
from collections import defaultdict

from feature_planner_v107 import validate_feature_plan

SCHEMA = "107.action-registry"
EVIDENCE_SCHEMA = "107.runtime-evidence"
_ALLOWED_PROPERTIES = {"Text", "Value", "Visible", "Enabled", "Name"}
_ALLOWED_STATUSES = {"success", "failure"}


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _validate_feature_plan(feature_plan):
    if not isinstance(feature_plan, dict):
        raise ValueError("expected v107 feature plan")
    schema_version = feature_plan.get("schemaVersion")
    if not isinstance(schema_version, str) or not schema_version.startswith("107.feature-plan"):
        raise ValueError("expected v107 feature plan")
    validate_feature_plan(feature_plan)

    place_id = feature_plan.get("placeId")
    features = feature_plan.get("features")
    seen = set()
    validated = []
    for feature in features:
        feature_id = feature.get("id")
        label = feature.get("label")
        kind = feature.get("kind")
        status = feature.get("status")
        path = feature.get("path")
        prop = feature.get("property")
        if (not isinstance(feature_id, str) or not feature_id or len(feature_id) > 80 or
                feature_id in seen):
            raise ValueError("invalid feature ID")
        if not isinstance(label, str) or not label:
            raise ValueError("invalid feature label")
        if kind != "read_property" or status not in {
            "implemented_not_runtime_verified",
            "implemented_runtime_observed",
        }:
            raise ValueError("unsupported feature kind")
        if (not isinstance(path, list) or not (2 <= len(path) <= 12) or
                path[0] not in {"Workspace", "PlayerGui", "ReplicatedStorage", "Players"} or
                any(not isinstance(part, str) or not part or len(part) > 80 for part in path)):
            raise ValueError("invalid feature path")
        if prop not in _ALLOWED_PROPERTIES:
            raise ValueError("unsupported property")
        seen.add(feature_id)
        validated.append(feature)
    return place_id, validated


def normalize_runtime_evidence(runtime_evidence, place_id):
    if runtime_evidence is None:
        return {"schemaVersion": EVIDENCE_SCHEMA, "placeId": place_id, "records": []}
    if not isinstance(runtime_evidence, dict) or runtime_evidence.get("schemaVersion") != EVIDENCE_SCHEMA:
        raise ValueError("invalid runtime evidence schema")
    if runtime_evidence.get("placeId") != place_id:
        raise ValueError("runtime evidence place mismatch")
    records = runtime_evidence.get("records")
    if not isinstance(records, list) or len(records) > 10000:
        raise ValueError("invalid runtime records")

    normalized = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError("invalid runtime record")
        feature_id = record.get("featureId")
        status = record.get("status")
        if not isinstance(feature_id, str) or not feature_id or len(feature_id) > 80:
            raise ValueError("invalid runtime feature ID")
        if status not in _ALLOWED_STATUSES:
            raise ValueError("invalid runtime status")
        timestamp = record.get("timestamp", index)
        if type(timestamp) is not int or timestamp < 0:
            raise ValueError("invalid runtime timestamp")
        workflow_id = record.get("workflowId")
        if workflow_id is not None and (not isinstance(workflow_id, str) or not workflow_id or len(workflow_id) > 80):
            raise ValueError("invalid workflow ID")
        step_index = record.get("stepIndex")
        step_count = record.get("stepCount")
        if step_index is not None and (type(step_index) is not int or step_index <= 0):
            raise ValueError("invalid workflow step index")
        if step_count is not None and (type(step_count) is not int or step_count <= 0):
            raise ValueError("invalid workflow step count")
        if step_index is not None and step_count is not None and step_index > step_count:
            raise ValueError("workflow step index exceeds step count")
        observed = record.get("observedValue")
        if observed is not None:
            if isinstance(observed, bool):
                observed = "true" if observed else "false"
            elif isinstance(observed, (int, float)):
                observed = str(observed)
            elif not isinstance(observed, str):
                raise ValueError("invalid observed value")
            if len(observed) > 240:
                raise ValueError("observed value too long")
        normalized.append({
            "featureId": feature_id,
            "status": status,
            "timestamp": timestamp,
            "workflowId": workflow_id,
            "stepIndex": step_index,
            "stepCount": step_count,
            "observedValue": observed,
        })
    return {"schemaVersion": EVIDENCE_SCHEMA, "placeId": place_id, "records": normalized}


def _action_runtime_status(success_count, failure_count):
    if success_count >= 2 and failure_count == 0:
        return "runtime_observed"
    if success_count >= 1 and failure_count == 0:
        return "runtime_partially_observed"
    if success_count >= 1 and failure_count >= 1:
        return "runtime_observed_with_errors"
    if failure_count >= 1:
        return "runtime_errors_observed"
    return "not_runtime_verified"


def build_registry(feature_plan, runtime_evidence=None):
    place_id, features = _validate_feature_plan(feature_plan)
    evidence = normalize_runtime_evidence(runtime_evidence, place_id)

    feature_ids = {feature["id"] for feature in features}
    feature_records = defaultdict(list)
    workflow_records = defaultdict(list)
    for record in evidence["records"]:
        feature_id = record["featureId"]
        if feature_id not in feature_ids:
            raise ValueError("runtime evidence references unknown feature")
        feature_records[feature_id].append(record)
        workflow_id = record["workflowId"]
        if workflow_id:
            workflow_records[workflow_id].append(record)

    completed = []
    partial = []
    completed_hits = defaultdict(int)
    partial_hits = defaultdict(int)
    for workflow_id, rows in sorted(workflow_records.items()):
        success_rows = [row for row in rows if row["status"] == "success" and row["stepIndex"] is not None]
        if not success_rows:
            continue
        steps = sorted({row["stepIndex"] for row in success_rows})
        expected = max(row["stepCount"] for row in success_rows if row["stepCount"] is not None) if any(row["stepCount"] is not None for row in success_rows) else max(steps)
        span_complete = steps == list(range(1, expected + 1)) and expected >= 2
        feature_ids = sorted({row["featureId"] for row in success_rows})
        payload = {
            "workflowId": workflow_id,
            "expectedSteps": expected,
            "observedSteps": steps,
            "featureIds": feature_ids,
            "runtimeVerified": False,
            "gameplayVerified": False,
            "status": "completed_runtime_observation" if span_complete else "partial_runtime_observation",
        }
        if span_complete:
            completed.append(payload)
            for feature_id in feature_ids:
                completed_hits[feature_id] += 1
        else:
            partial.append(payload)
            for feature_id in feature_ids:
                partial_hits[feature_id] += 1

    actions = []
    runtime_observed_actions = 0
    workflow_correlated_actions = 0
    for feature in features:
        rows = sorted(feature_records.get(feature["id"], []), key=lambda item: item["timestamp"])
        success_count = sum(1 for row in rows if row["status"] == "success")
        failure_count = sum(1 for row in rows if row["status"] == "failure")
        status = _action_runtime_status(success_count, failure_count)
        if status == "runtime_observed":
            runtime_observed_actions += 1
        successful = [row for row in rows if row["status"] == "success"]
        completed_workflow_hits = completed_hits[feature["id"]]
        partial_workflow_hits = partial_hits[feature["id"]]
        if completed_workflow_hits:
            workflow_correlated_actions += 1
        generation_readiness = (
            "high"
            if status == "runtime_observed" or completed_workflow_hits
            else ("medium" if success_count else "low")
        )
        actions.append({
            "id": f"refresh_{feature['id']}",
            "featureId": feature["id"],
            "label": feature["label"],
            "kind": "read_property_refresh",
            "path": feature["path"],
            "property": feature["property"],
            "implemented": True,
            "runtimeStatus": status,
            "generationReadiness": generation_readiness,
            "runtimeEvidence": {
                "records": len(rows),
                "successes": success_count,
                "failures": failure_count,
                "workflowHits": len({row["workflowId"] for row in rows if row["workflowId"]}),
                "completedWorkflowHits": completed_workflow_hits,
                "partialWorkflowHits": partial_workflow_hits,
                "latestTimestamp": rows[-1]["timestamp"] if rows else None,
                "lastObservedValue": successful[-1]["observedValue"] if successful else None,
            },
            "runtimeVerified": False,
            "gameplayVerified": False,
        })

    return {
        "schemaVersion": SCHEMA,
        "placeId": place_id,
        "readOnly": True,
        "runtimeVerified": False,
        "gameplayVerified": False,
        "actions": actions,
        "workflows": {
            "completed": completed,
            "partial": partial,
        },
        "summary": {
            "totalActions": len(actions),
            "runtimeObservedActions": runtime_observed_actions,
            "workflowCorrelatedActions": workflow_correlated_actions,
            "completedWorkflowCandidates": len(completed),
            "partialWorkflowCandidates": len(partial),
            "runtimeEvidenceRecords": len(evidence["records"]),
        },
    }
