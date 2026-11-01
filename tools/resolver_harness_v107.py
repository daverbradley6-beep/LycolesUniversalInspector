#!/usr/bin/env python3
"""Evaluate v107 resolver behavior against a bounded synthetic hierarchy.

This models the generated resolver; it does not execute Luau or Roblox APIs.
"""
import argparse
import json
import math
from pathlib import Path

from feature_planner_v107 import validate_feature_plan
from path_identity_v107 import ROOT_CLASSES, ROOTS
from release_pipeline_v104 import canonical

SCHEMA_VERSION = "107.resolver-model"
FIXTURE_SCHEMA_VERSION = "107.hierarchy-fixture"
MAX_NODES = 10000
MAX_DEPTH = 16
MAX_CHILDREN = 1000
MAX_TEXT = 256


def _valid_scalar(value):
    if value is None or isinstance(value, (str, bool, int)):
        return not isinstance(value, str) or len(value) <= 4096
    return isinstance(value, float) and math.isfinite(value)


def _validate_node(value, depth, counter):
    if depth > MAX_DEPTH or not isinstance(value, dict):
        raise ValueError("invalid hierarchy depth or node")
    if set(value) != {"name", "className", "properties", "children"}:
        raise ValueError("invalid hierarchy node fields")
    name = value["name"]
    class_name = value["className"]
    if not isinstance(name, str) or not 0 < len(name) <= MAX_TEXT:
        raise ValueError("invalid hierarchy name")
    if not isinstance(class_name, str) or not 0 < len(class_name) <= MAX_TEXT:
        raise ValueError("invalid hierarchy class")
    properties = value["properties"]
    children = value["children"]
    if not isinstance(properties, dict) or any(
        not isinstance(key, str) or not 0 < len(key) <= MAX_TEXT or not _valid_scalar(item)
        for key, item in properties.items()
    ):
        raise ValueError("invalid hierarchy properties")
    if not isinstance(children, list) or len(children) > MAX_CHILDREN:
        raise ValueError("invalid hierarchy children")
    counter[0] += 1
    if counter[0] > MAX_NODES:
        raise ValueError("hierarchy node limit exceeded")
    for child in children:
        _validate_node(child, depth + 1, counter)


def _validate_hierarchy(hierarchy):
    if not isinstance(hierarchy, dict) or set(hierarchy) != {"schemaVersion", "placeId", "roots"}:
        raise ValueError("invalid hierarchy fixture fields")
    if hierarchy.get("schemaVersion") != FIXTURE_SCHEMA_VERSION:
        raise ValueError("invalid hierarchy fixture schema")
    if type(hierarchy.get("placeId")) is not int or hierarchy["placeId"] <= 0:
        raise ValueError("invalid hierarchy fixture place")
    roots = hierarchy.get("roots")
    if not isinstance(roots, list) or not roots:
        raise ValueError("invalid hierarchy roots")
    counter = [0]
    root_map = {}
    for root in roots:
        _validate_node(root, 0, counter)
        name = root["name"]
        if name not in ROOTS or root["className"] != ROOT_CLASSES[name] or name in root_map:
            raise ValueError("invalid or duplicate hierarchy root")
        root_map[name] = root
    return root_map, counter[0]


def _identity_child(parent, step):
    matches = [
        child for child in parent["children"]
        if child["name"] == step["name"] and child["className"] == step["className"]
    ]
    index = step["ordinal"] - 1
    return matches[index] if index < len(matches) else None


def _legacy_child(parent, name, class_name=None):
    matches = [
        child for child in parent["children"]
        if child["name"] == name and (class_name is None or child["className"] == class_name)
    ]
    if len(matches) == 1:
        return matches[0], None
    return None, "legacy_missing" if not matches else "legacy_ambiguity"


def _resolve(feature, roots):
    if feature["pathResolution"] == "full_identity":
        identity = feature["pathIdentity"]
        current = roots.get(identity[0]["name"])
        for step in identity[1:]:
            if current is None:
                break
            current = _identity_child(current, step)
        return current, None if current is not None else "identity_mismatch"
    path = feature["path"]
    current = roots.get(path[0])
    for name in path[1:-1]:
        if current is None:
            return None, "legacy_missing"
        current, reason = _legacy_child(current, name)
        if reason:
            return None, reason
    if current is None:
        return None, "legacy_missing"
    return _legacy_child(current, path[-1], feature["className"])


def evaluate(feature_plan, hierarchy, runtime_place_id):
    """Run deterministic resolver-model checks against a synthetic hierarchy."""
    validate_feature_plan(feature_plan)
    roots, node_count = _validate_hierarchy(hierarchy)
    if type(runtime_place_id) is not int or runtime_place_id <= 0:
        raise ValueError("invalid runtime place")
    place_matches = runtime_place_id == feature_plan["placeId"] == hierarchy["placeId"]
    results = []
    resolved = 0
    for feature in feature_plan["features"]:
        result = {
            "id": feature["id"],
            "pathResolution": feature["pathResolution"],
        }
        if not place_matches:
            result["status"] = "place_mismatch"
        else:
            target, reason = _resolve(feature, roots)
            if target is None:
                result["status"] = reason
            elif feature["property"] not in target["properties"]:
                result["status"] = "property_unavailable"
            else:
                result["status"] = "resolved"
                result["value"] = target["properties"][feature["property"]]
                resolved += 1
        results.append(result)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "placeId": feature_plan["placeId"],
        "fixtureNodes": node_count,
        "source": "synthetic_hierarchy_fixture",
        "readOnly": True,
        "features": results,
        "resolved": resolved,
        "failed": len(results) - resolved,
        "modelVerified": True,
        "luauExecuted": False,
        "robloxRuntimeVerified": False,
        "gameplayVerified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-plan", type=Path, required=True)
    parser.add_argument("--hierarchy", type=Path, required=True)
    parser.add_argument("--runtime-place-id", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    feature_plan = json.loads(args.feature_plan.read_text(encoding="utf-8-sig"))
    hierarchy = json.loads(args.hierarchy.read_text(encoding="utf-8-sig"))
    result = evaluate(feature_plan, hierarchy, args.runtime_place_id)
    if args.output.is_symlink():
        raise ValueError("symlink output forbidden")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(result))
    print(json.dumps({"ok": True, "resolved": result["resolved"], "failed": result["failed"]}, sort_keys=True))


if __name__ == "__main__":
    main()
