"""Deterministic diagnostics for identity-aware v107 observations."""
from collections import Counter

from feature_planner_v107 import CONTRACT_FIELDS, plan
from path_identity_v107 import REPORT_SCHEMA_VERSION


def analyze(report, feature_plan):
    if not isinstance(report, dict) or report.get("schemaVersion") != REPORT_SCHEMA_VERSION:
        raise ValueError("expected v107 report")
    if feature_plan != plan(report):
        raise ValueError("feature mapping mismatch")
    objects = report["objects"]
    features = feature_plan["features"]
    unsupported = feature_plan["unsupported"]
    classes = Counter(item["className"] for item in objects)
    resolutions = Counter(item["pathResolution"] for item in objects)
    evidence = Counter(feature["evidence"]["classification"] for feature in features)
    statuses = Counter(feature["status"] for feature in features)
    unknowns = Counter(value for feature in features for value in feature["unknowns"])
    explicit_contracts = sum(CONTRACT_FIELDS <= set(feature) for feature in features)
    return {
        "schemaVersion": "107.inspection-diagnostics",
        "placeId": report["placeId"],
        "observations": len(objects),
        "supportedControls": len(features),
        "unsupportedObservations": len(unsupported),
        "coverage": round(len(features) / len(objects), 6) if objects else 0,
        "classCounts": dict(sorted(classes.items())),
        "resolutionModes": dict(sorted(resolutions.items())),
        "evidenceClassifications": dict(sorted(evidence.items())),
        "verificationStatuses": dict(sorted(statuses.items())),
        "featuresWithExplicitContracts": explicit_contracts,
        "unknownBoundaries": dict(sorted(unknowns.items())),
        "runtimeVerified": False,
        "gameplayVerified": False,
    }
