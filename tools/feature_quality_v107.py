"""Deterministic quality metrics for identity-aware v107 observations."""
from collections import Counter

from feature_planner_v107 import PLAN_SCHEMA_VERSION
from path_identity_v107 import REPORT_SCHEMA_VERSION


def assess(report, feature_plan, *, minimum_coverage=0.5, minimum_features=1):
    if not isinstance(report, dict) or not isinstance(feature_plan, dict):
        raise ValueError("invalid report")
    if report.get("schemaVersion") != REPORT_SCHEMA_VERSION or feature_plan.get("schemaVersion") != PLAN_SCHEMA_VERSION:
        raise ValueError("invalid schema")
    if report.get("placeId") != feature_plan.get("placeId"):
        raise ValueError("place mismatch")
    if type(minimum_features) is not int or minimum_features < 0:
        raise ValueError("invalid feature minimum")
    if type(minimum_coverage) not in (float, int) or not 0 <= minimum_coverage <= 1:
        raise ValueError("invalid coverage minimum")
    objects = report.get("objects")
    features = feature_plan.get("features")
    unsupported = feature_plan.get("unsupported")
    if not all(isinstance(value, list) for value in (objects, features, unsupported)):
        raise ValueError("missing observations or features")
    if len(features) + len(unsupported) != len(objects):
        raise ValueError("feature accounting mismatch")
    if report.get("acceptedCount") != len(objects):
        raise ValueError("observation accounting mismatch")
    if report.get("readOnly") is not True or report.get("verifiedInGame") is not False:
        raise ValueError("invalid verification claim")
    feature_ids = [feature.get("id") for feature in features]
    if len(set(feature_ids)) != len(feature_ids):
        raise ValueError("duplicate feature IDs")
    coverage = len(features) / len(objects) if objects else 0.0
    issues = []
    if len(features) < minimum_features:
        issues.append("insufficient_features")
    if coverage < minimum_coverage:
        issues.append("insufficient_coverage")
    classes = Counter(item["className"] for item in objects)
    resolutions = Counter(item["pathResolution"] for item in objects)
    reasons = Counter(item.get("reason", "unspecified") for item in unsupported)
    return {
        "schemaVersion": "107.quality",
        "ok": not issues,
        "issues": issues,
        "placeId": report["placeId"],
        "observations": len(objects),
        "implementedObservationControls": len(features),
        "unsupportedObservations": len(unsupported),
        "coverage": round(coverage, 6),
        "classes": dict(sorted(classes.items())),
        "resolutionModes": dict(sorted(resolutions.items())),
        "unsupportedReasons": dict(sorted(reasons.items())),
        "runtimeVerified": False,
        "gameplayVerified": False,
    }
