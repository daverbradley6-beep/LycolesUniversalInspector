"""Identity-aware read-only feature planning for v107 observations."""
from typing import Any

from feature_planner_v106 import SUPPORTED
from path_identity_v107 import PATH_SCHEMA_VERSION, normalize_observation, validate_report

PLAN_SCHEMA_VERSION = "107.feature-plan"


def _validate_report(report):
    validate_report(report)
    return report["objects"]


def plan(report: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic feature plan from a canonical v107 report."""
    objects = _validate_report(report)
    features = []
    unsupported = []
    for index, item in enumerate(objects):
        class_name = item["className"]
        if class_name in SUPPORTED and item["property"] == SUPPORTED[class_name]:
            features.append({
                "id": f"observe_{index:04d}",
                "label": f"Observe {item['path'][-1]}",
                "kind": "read_property",
                "path": list(item["path"]),
                "pathIdentity": item["pathIdentity"],
                "pathResolution": item["pathResolution"],
                "className": class_name,
                "property": item["property"],
                "status": "implemented_not_runtime_verified",
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


def validate_feature_plan(feature_plan):
    """Validate a persisted or caller-supplied v107 feature plan."""
    expected_fields = {
        "schemaVersion", "pathIdentityVersion", "placeId", "features",
        "unsupported", "runtimeVerified", "gameplayVerified",
    }
    if not isinstance(feature_plan, dict) or set(feature_plan) != expected_fields:
        raise ValueError("invalid feature plan fields")
    if feature_plan.get("schemaVersion") != PLAN_SCHEMA_VERSION or feature_plan.get("pathIdentityVersion") != PATH_SCHEMA_VERSION:
        raise ValueError("invalid feature plan schema")
    if type(feature_plan.get("placeId")) is not int or feature_plan["placeId"] <= 0:
        raise ValueError("invalid feature plan place")
    if feature_plan.get("runtimeVerified") is not False or feature_plan.get("gameplayVerified") is not False:
        raise ValueError("invalid feature plan claims")
    features = feature_plan.get("features")
    unsupported = feature_plan.get("unsupported")
    if not isinstance(features, list) or not isinstance(unsupported, list):
        raise ValueError("invalid feature plan collections")
    expected_feature_fields = {
        "id", "label", "kind", "path", "pathIdentity", "pathResolution",
        "className", "property", "status",
    }
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
    for item in unsupported:
        if not isinstance(item, dict) or set(item) != {"index", "reason"}:
            raise ValueError("invalid unsupported feature")
        if type(item["index"]) is not int or item["index"] < 0 or not isinstance(item["reason"], str):
            raise ValueError("invalid unsupported feature")
    return feature_plan

