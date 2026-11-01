"""Deterministic diagnostics for identity-aware v107 observations."""
from collections import Counter

from feature_planner_v107 import plan
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
    return {
        "schemaVersion": "107.inspection-diagnostics",
        "placeId": report["placeId"],
        "observations": len(objects),
        "supportedControls": len(features),
        "unsupportedObservations": len(unsupported),
        "coverage": round(len(features) / len(objects), 6) if objects else 0,
        "classCounts": dict(sorted(classes.items())),
        "resolutionModes": dict(sorted(resolutions.items())),
        "runtimeVerified": False,
        "gameplayVerified": False,
    }
