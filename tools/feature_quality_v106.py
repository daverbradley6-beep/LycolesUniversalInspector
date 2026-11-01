"""Deterministic quality and feature-coverage diagnostics for Lycoles releases.

Never upgrades an observation into a server-authoritative gameplay claim.
"""
from collections import Counter

def assess(report, feature_plan, *, minimum_coverage=0.5, minimum_features=1):
    if not isinstance(report, dict) or not isinstance(feature_plan, dict):
        raise ValueError("invalid report")
    if report.get("schemaVersion") != "104.release" or feature_plan.get("schemaVersion") != "106.feature-plan":
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
    if not isinstance(objects, list) or not isinstance(features, list) or not isinstance(unsupported, list):
        raise ValueError("missing observations or features")
    if len(features) + len(unsupported) != len(objects):
        raise ValueError("feature accounting mismatch")
    if report.get("acceptedCount") != len(objects):
        raise ValueError("observation accounting mismatch")
    if report.get("readOnly") is not True or report.get("verifiedInGame") is not False:
        raise ValueError("invalid verification claim")
    feature_ids = [f.get("id") for f in features]
    if len(set(feature_ids)) != len(feature_ids):
        raise ValueError("duplicate feature IDs")
    coverage = len(features) / len(objects) if objects else 0.0
    reasons = Counter(item.get("reason", "unspecified") for item in unsupported)
    classes = Counter(obj.get("className", "unknown") for obj in objects)
    failures = []
    if len(features) < minimum_features:
        failures.append("insufficient_features")
    if coverage < minimum_coverage:
        failures.append("insufficient_coverage")
    return {
        "schemaVersion": "106.quality",
        "ok": not failures,
        "issues": failures,
        "placeId": report["placeId"],
        "observations": len(objects),
        "implementedObservationControls": len(features),
        "unsupportedObservations": len(unsupported),
        "coverage": round(coverage, 6),
        "classes": dict(sorted(classes.items())),
        "unsupportedReasons": dict(sorted(reasons.items())),
        "runtimeVerified": False,
        "gameplayVerified": False,
    }
