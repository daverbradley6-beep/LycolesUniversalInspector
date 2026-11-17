"""Identity-aware read-only feature planning for v107 observations."""
import hashlib
import re
from typing import Any

from feature_planner_v106 import SUPPORTED
from path_identity_v107 import PATH_SCHEMA_VERSION, normalize_observation, validate_report
from release_pipeline_v104 import canonical

LEGACY_PLAN_SCHEMA_VERSION = "107.feature-plan"
PLAN_SCHEMA_VERSION = "107.feature-plan.2"
SOURCE_ARTIFACT = "inspection-report.json"
BASE_FEATURE_FIELDS = {
    "id", "label", "kind", "path", "pathIdentity", "pathResolution",
    "className", "property", "status",
}
CONTRACT_FIELDS = {
    "evidence", "implementationStrategy", "runtimeChecks",
    "successCondition", "failureConditions", "unknowns",
}
UNKNOWNS = [
    "server_authority",
    "gameplay_causality",
    "runtime_property_value",
    "runtime_object_availability",
    "game_specific_action_semantics",
]


def _validate_report(report):
    validate_report(report)
    return report["objects"]


def _observed_facts(resolution):
    identity_fact = (
        "full_segment_identity_observed"
        if resolution == "full_identity"
        else "legacy_name_only_path_observed"
    )
    return [
        "client_visible_object_path",
        "terminal_class_observed",
        "supported_property_selected",
        identity_fact,
    ]


def _runtime_checks(resolution):
    resolution_checks = (
        ["each_segment_name_class_ordinal_matches"]
        if resolution == "full_identity"
        else ["each_legacy_name_is_unique", "terminal_name_class_is_unique"]
    )
    return ["place_id_matches", "root_available", *resolution_checks, "property_read_succeeds"]


def _failure_conditions(resolution):
    resolution_failures = (
        ["identity_mismatch"]
        if resolution == "full_identity"
        else ["legacy_missing", "legacy_ambiguity"]
    )
    return ["place_mismatch", *resolution_failures, "property_unavailable", "property_read_failed"]


def _evidence(item, index):
    return {
        "classification": "observed_client_object",
        "sourceArtifact": SOURCE_ARTIFACT,
        "sourceObjectIndex": index,
        "sourceDigest": hashlib.sha256(canonical(item)).hexdigest(),
        "observedFacts": _observed_facts(item["pathResolution"]),
        "inferences": [
            "supported_class_property_mapping",
            "read_only_property_control_is_implementable",
        ],
    }


def plan(report: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic evidence-backed feature plan from a v107 report."""
    objects = _validate_report(report)
    features = []
    unsupported = []
    for index, item in enumerate(objects):
        class_name = item["className"]
        if class_name in SUPPORTED and item["property"] == SUPPORTED[class_name]:
            resolution = item["pathResolution"]
            features.append({
                "id": f"observe_{index:04d}",
                "label": f"Observe {item['path'][-1]}",
                "kind": "read_property",
                "path": list(item["path"]),
                "pathIdentity": item["pathIdentity"],
                "pathResolution": resolution,
                "className": class_name,
                "property": item["property"],
                "status": "implemented_not_runtime_verified",
                "evidence": _evidence(item, index),
                "implementationStrategy": "resolve_client_identity_then_read_property",
                "runtimeChecks": _runtime_checks(resolution),
                "successCondition": "target_resolved_and_property_read_succeeded",
                "failureConditions": _failure_conditions(resolution),
                "unknowns": list(UNKNOWNS),
            })
        else:
            unsupported.append({
                "index": index,
                "reason": "no_supported_local_implementation",
            })
    return {
        "schemaVersion": PLAN_SCHEMA_VERSION,
        "pathIdentityVersion": PATH_SCHEMA_VERSION,
        "placeId": report.get("placeId"),
        "features": features,
        "unsupported": unsupported,
        "runtimeVerified": False,
        "gameplayVerified": False,
    }


def _validate_contract(feature, identifier):
    evidence = feature.get("evidence")
    evidence_fields = {
        "classification", "sourceArtifact", "sourceObjectIndex", "sourceDigest",
        "observedFacts", "inferences",
    }
    if not isinstance(evidence, dict) or set(evidence) != evidence_fields:
        raise ValueError("invalid feature evidence")
    if evidence.get("classification") != "observed_client_object" or evidence.get("sourceArtifact") != SOURCE_ARTIFACT:
        raise ValueError("invalid feature evidence source")
    if evidence.get("sourceObjectIndex") != int(identifier[8:]):
        raise ValueError("invalid feature evidence index")
    digest = evidence.get("sourceDigest")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("invalid feature evidence digest")
    resolution = feature["pathResolution"]
    if evidence.get("observedFacts") != _observed_facts(resolution):
        raise ValueError("invalid observed facts")
    if evidence.get("inferences") != [
        "supported_class_property_mapping",
        "read_only_property_control_is_implementable",
    ]:
        raise ValueError("invalid feature inferences")
    if feature.get("implementationStrategy") != "resolve_client_identity_then_read_property":
        raise ValueError("invalid implementation strategy")
    if feature.get("runtimeChecks") != _runtime_checks(resolution):
        raise ValueError("invalid runtime checks")
    if feature.get("successCondition") != "target_resolved_and_property_read_succeeded":
        raise ValueError("invalid success condition")
    if feature.get("failureConditions") != _failure_conditions(resolution):
        raise ValueError("invalid failure conditions")
    if feature.get("unknowns") != UNKNOWNS:
        raise ValueError("invalid feature unknowns")


def validate_feature_plan(feature_plan):
    """Validate current v2 or backward-compatible v1 feature plans."""
    expected_fields = {
        "schemaVersion", "pathIdentityVersion", "placeId", "features",
        "unsupported", "runtimeVerified", "gameplayVerified",
    }
    if not isinstance(feature_plan, dict) or set(feature_plan) != expected_fields:
        raise ValueError("invalid feature plan fields")
    schema = feature_plan.get("schemaVersion")
    if schema not in {PLAN_SCHEMA_VERSION, LEGACY_PLAN_SCHEMA_VERSION} or feature_plan.get("pathIdentityVersion") != PATH_SCHEMA_VERSION:
        raise ValueError("invalid feature plan schema")
    if type(feature_plan.get("placeId")) is not int or feature_plan["placeId"] <= 0:
        raise ValueError("invalid feature plan place")
    if feature_plan.get("runtimeVerified") is not False or feature_plan.get("gameplayVerified") is not False:
        raise ValueError("invalid feature plan claims")
    features = feature_plan.get("features")
    unsupported = feature_plan.get("unsupported")
    if not isinstance(features, list) or not isinstance(unsupported, list):
        raise ValueError("invalid feature plan collections")
    expected_feature_fields = BASE_FEATURE_FIELDS | (CONTRACT_FIELDS if schema == PLAN_SCHEMA_VERSION else set())
    seen_ids = set()
    for feature in features:
        if not isinstance(feature, dict) or set(feature) != expected_feature_fields:
            raise ValueError("invalid feature fields")
        identifier = feature.get("id")
        if not isinstance(identifier, str) or not identifier.startswith("observe_") or not identifier[8:].isdigit() or len(identifier) != 12:
            raise ValueError("invalid feature ID")
        if identifier in seen_ids:
            raise ValueError("duplicate feature ID")
        seen_ids.add(identifier)
        if not isinstance(feature.get("label"), str) or not feature["label"]:
            raise ValueError("invalid feature label")
        if feature.get("kind") != "read_property" or feature.get("status") != "implemented_not_runtime_verified":
            raise ValueError("unsupported feature")
        observation = normalize_observation({
            "path": feature.get("path"),
            "pathIdentity": feature.get("pathIdentity"),
            "className": feature.get("className"),
            "property": feature.get("property"),
        })
        if observation["pathResolution"] != feature.get("pathResolution"):
            raise ValueError("feature resolution mismatch")
        if schema == PLAN_SCHEMA_VERSION:
            _validate_contract(feature, identifier)
    for item in unsupported:
        if not isinstance(item, dict) or set(item) != {"index", "reason"}:
            raise ValueError("invalid unsupported feature")
        if type(item["index"]) is not int or item["index"] < 0 or not isinstance(item["reason"], str):
            raise ValueError("invalid unsupported feature")
    return feature_plan


def migrate_feature_plan_v1(feature_plan, report):
    """Upgrade a canonical v1 plan using its validated report as evidence."""
    validate_feature_plan(feature_plan)
    if feature_plan["schemaVersion"] != LEGACY_PLAN_SCHEMA_VERSION:
        raise ValueError("expected legacy feature plan")
    current = plan(report)
    legacy = {
        **current,
        "schemaVersion": LEGACY_PLAN_SCHEMA_VERSION,
        "features": [
            {key: value for key, value in feature.items() if key in BASE_FEATURE_FIELDS}
            for feature in current["features"]
        ],
    }
    if feature_plan != legacy:
        raise ValueError("legacy plan does not match report")
    return current

