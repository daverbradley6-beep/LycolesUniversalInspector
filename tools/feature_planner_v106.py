"""Evidence-gated feature planner for client-visible Lycoles observations.

Only explicitly implemented, local, read-only feature types are emitted.
This module does not infer server authority from client visibility.
"""
from dataclasses import dataclass
from typing import Any

SUPPORTED = {
    "TextLabel": "Text",
    "TextButton": "Text",
    "TextBox": "Text",
    "IntValue": "Value",
    "NumberValue": "Value",
    "BoolValue": "Value",
    "StringValue": "Value",
}

@dataclass(frozen=True)
class Feature:
    identifier: str
    label: str
    kind: str
    path: tuple[str, ...]
    property: str
    status: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.identifier, "label": self.label,
            "kind": self.kind, "path": list(self.path),
            "property": self.property, "status": self.status,
        }

def plan(report: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic plan from the existing v104 report contract."""
    if not isinstance(report, dict) or report.get("schemaVersion") != "104.release":
        raise ValueError("expected v104 release report")
    if not isinstance(report.get("objects"), list):
        raise ValueError("missing objects")
    features = []
    unsupported = []
    for index, item in enumerate(report["objects"]):
        if not isinstance(item, dict):
            raise ValueError("invalid object")
        path = item.get("path")
        cls = item.get("className")
        prop = item.get("property")
        if not isinstance(path, list) or not all(isinstance(p, str) for p in path):
            raise ValueError("invalid path")
        if cls in SUPPORTED and prop == SUPPORTED[cls]:
            features.append(Feature(
                identifier=f"observe_{index:04d}",
                label=f"Observe {path[-1]}", kind="read_property",
                path=tuple(path), property=prop,
                status="implemented_not_runtime_verified",
            ).as_dict())
        else:
            unsupported.append({
                "index": index, "reason": "no_supported_local_implementation"
            })
    return {
        "schemaVersion": "106.feature-plan",
        "placeId": report.get("placeId"),
        "features": features,
        "unsupported": unsupported,
        "runtimeVerified": False,
        "gameplayVerified": False,
    }
