#!/usr/bin/env python3
"""Versioned full-path identity normalization for read-only observations."""
from collections import Counter
import re

from release_pipeline_v104 import PROPS

REPORT_SCHEMA_VERSION = "107.release"
PATH_SCHEMA_VERSION = "107.path-identity.1"
ROOT_CLASSES = {
    "Workspace": "Workspace",
    "PlayerGui": "PlayerGui",
    "ReplicatedStorage": "ReplicatedStorage",
    "Players": "Players",
}
ROOTS = frozenset(ROOT_CLASSES)
SEGMENT = re.compile(r"^[A-Za-z0-9_ .:-]{1,80}$")
CLASS_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,79}$")
COLLECTION_KEYS = ("observations", "objects", "instances", "entries", "controls", "features")
MAX_INPUTS = 50000
MAX_OUTPUTS = 150
MAX_DEPTH = 12
MAX_ORDINAL = 100000


def _names(value):
    if isinstance(value, str):
        value = value.split(".")
        if value and value[0] == "game":
            value = value[1:]
    if not isinstance(value, list) or not 2 <= len(value) <= MAX_DEPTH:
        return None
    if value[0] not in ROOTS:
        return None
    if any(not isinstance(part, str) or not SEGMENT.fullmatch(part) for part in value):
        return None
    return list(value)


def _segment(value):
    if not isinstance(value, dict) or set(value) != {"name", "className", "ordinal"}:
        return None
    name = value.get("name")
    class_name = value.get("className")
    ordinal = value.get("ordinal")
    if not isinstance(name, str) or not SEGMENT.fullmatch(name):
        return None
    if not isinstance(class_name, str) or not CLASS_NAME.fullmatch(class_name):
        return None
    if type(ordinal) is not int or not 1 <= ordinal <= MAX_ORDINAL:
        return None
    return {"name": name, "className": class_name, "ordinal": ordinal}


def _identity(value, path):
    if not isinstance(value, list) or not value:
        return None, "invalid_path_identity"
    if isinstance(value[0], str):
        if value[0] not in ROOTS:
            return None, "invalid_path_identity"
        root = {"name": value[0], "className": ROOT_CLASSES[value[0]], "ordinal": 1}
        raw_segments = value[1:]
    else:
        root = None
        raw_segments = value
    segments = [_segment(item) for item in raw_segments]
    if any(item is None for item in segments):
        return None, "invalid_path_identity"
    if root is not None:
        segments.insert(0, root)
    elif segments and segments[0]["name"] in ROOTS:
        root_name = segments[0]["name"]
        if segments[0] != {"name": root_name, "className": ROOT_CLASSES[root_name], "ordinal": 1}:
            return None, "invalid_root_identity"
    elif path is not None and path[0] == "PlayerGui" and [item["name"] for item in segments] == path[1:]:
        segments.insert(0, {"name": "PlayerGui", "className": "PlayerGui", "ordinal": 1})
    else:
        return None, "missing_root_identity"
    if not 2 <= len(segments) <= MAX_DEPTH:
        return None, "invalid_path_identity"
    names = [item["name"] for item in segments]
    if path is not None and names != path:
        return None, "path_identity_mismatch"
    return segments, None


def _normalize_observation(row, default_root=None):
    if not isinstance(row, dict):
        return None, "invalid_record"
    raw_path = row.get("path", row.get("fullName", row.get("fullPath")))
    raw_identity = row.get("pathIdentity", row.get("uniquePath", row.get("segments")))
    if raw_identity is None and isinstance(raw_path, list) and raw_path and all(isinstance(item, dict) for item in raw_path):
        raw_identity = raw_path
        raw_path = None
    path = _names(raw_path)
    if path is None and default_root and isinstance(raw_path, list):
        path = _names([default_root, *raw_path])
    if raw_identity is None:
        if path is None:
            return None, "invalid_path"
        identity = None
        resolution = "legacy_terminal_identity"
    else:
        if path is None and isinstance(raw_identity, list):
            if raw_identity and isinstance(raw_identity[0], str):
                path = _names([raw_identity[0], *[item.get("name") for item in raw_identity[1:] if isinstance(item, dict)]])
            elif raw_identity and isinstance(raw_identity[0], dict):
                identity_names = [item.get("name") for item in raw_identity if isinstance(item, dict)]
                candidate = identity_names if identity_names and identity_names[0] in ROOTS else [default_root, *identity_names] if default_root else identity_names
                path = _names(candidate)
        if path is None:
            return None, "invalid_path"
        identity, reason = _identity(raw_identity, path)
        if reason:
            return None, reason
        resolution = "full_identity"
    class_name = row.get("className", row.get("class"))
    if not isinstance(class_name, str) or class_name not in PROPS:
        return None, "unsupported_class"
    if identity is not None and identity[-1]["className"] != class_name:
        return None, "identity_class_mismatch"
    if row.get("property", PROPS[class_name]) != PROPS[class_name]:
        return None, "property_mismatch"
    return {
        "path": path,
        "pathIdentity": identity,
        "pathResolution": resolution,
        "className": class_name,
        "property": PROPS[class_name],
        "canAutomate": False,
    }, None


def normalize_observation(row, default_root=None):
    """Normalize one observation or raise with a stable rejection reason."""
    normalized, reason = _normalize_observation(row, default_root)
    if reason:
        raise ValueError(reason)
    return normalized


def _identity_key(item):
    return tuple(
        (segment["name"], segment["className"], segment["ordinal"])
        for segment in item["pathIdentity"]
    )


def _sort_key(item):
    identity = item["pathIdentity"]
    return (
        tuple(item["path"]),
        0 if identity is not None else 1,
        _identity_key(item) if identity is not None else (),
        item["className"],
    )


def _select(candidates, rejections):
    grouped = {}
    for candidate in candidates:
        grouped.setdefault(tuple(candidate["path"]), []).append(candidate)
    selected = []
    for path in sorted(grouped):
        group = grouped[path]
        rich = sorted((item for item in group if item["pathIdentity"] is not None), key=_sort_key)
        legacy = sorted((item for item in group if item["pathIdentity"] is None), key=_sort_key)
        if rich:
            if legacy:
                rejections["ambiguous_legacy_path"] += len(legacy)
            seen = set()
            for item in rich:
                key = _identity_key(item)
                if key in seen:
                    rejections["duplicate_identity"] += 1
                else:
                    seen.add(key)
                    selected.append(item)
        elif legacy:
            selected.append(legacy[0])
            for item in legacy[1:]:
                reason = "duplicate_path" if item["className"] == legacy[0]["className"] else "conflicting_class"
                rejections[reason] += 1
    return sorted(selected, key=_sort_key)


def _source_rows(source, place_id):
    default_root = None
    if isinstance(source, dict):
        if source.get("placeId") is not None and source["placeId"] != place_id:
            raise ValueError("place mismatch")
        schema = source.get("schemaVersion")
        if schema in {"72.import", "74.import", "72.candidates"}:
            default_root = "PlayerGui"
        rows = next((source[key] for key in COLLECTION_KEYS if isinstance(source.get(key), list)), None)
    else:
        rows = source
    if not isinstance(rows, list) or len(rows) > MAX_INPUTS:
        raise ValueError("invalid inspection")
    return rows, default_root


def build(source, place_id):
    """Build a deterministic v107 report from legacy or identity-rich observations."""
    if type(place_id) is not int or place_id <= 0:
        raise ValueError("invalid place")
    rows, default_root = _source_rows(source, place_id)
    rejections = Counter()
    candidates = []
    for row in rows:
        normalized, reason = _normalize_observation(row, default_root)
        if reason:
            rejections[reason] += 1
        else:
            candidates.append(normalized)
    objects = _select(candidates, rejections)
    if len(objects) > MAX_OUTPUTS:
        rejections["output_limit"] += len(objects) - MAX_OUTPUTS
        objects = objects[:MAX_OUTPUTS]
    result = {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "pathIdentityVersion": PATH_SCHEMA_VERSION,
        "placeId": place_id,
        "inputCount": len(rows),
        "acceptedCount": len(objects),
        "rejectedCount": sum(rejections.values()),
        "rejections": dict(sorted(rejections.items())),
        "objects": objects,
        "verifiedInGame": False,
        "gameplayFunctionsGenerated": 0,
        "readOnly": True,
    }
    if result["acceptedCount"] + result["rejectedCount"] != result["inputCount"]:
        raise AssertionError("observation accounting mismatch")
    return result


def migrate_v104_report(report):
    """Migrate a validated v104 report without inventing missing path identity."""
    if not isinstance(report, dict) or report.get("schemaVersion") != "104.release":
        raise ValueError("expected v104 release report")
    place_id = report.get("placeId")
    objects = report.get("objects")
    rejections = report.get("rejections")
    if type(place_id) is not int or place_id <= 0 or not isinstance(objects, list) or not isinstance(rejections, dict):
        raise ValueError("invalid v104 report")
    if report.get("readOnly") is not True or report.get("verifiedInGame") is not False or report.get("gameplayFunctionsGenerated") != 0:
        raise ValueError("invalid v104 claims")
    counts = (report.get("inputCount"), report.get("acceptedCount"), report.get("rejectedCount"))
    if any(type(value) is not int or value < 0 for value in counts):
        raise ValueError("invalid v104 counts")
    if counts[1] != len(objects) or counts[0] != counts[1] + counts[2]:
        raise ValueError("invalid v104 accounting")
    if any(not isinstance(key, str) or type(value) is not int or value < 0 for key, value in rejections.items()):
        raise ValueError("invalid v104 rejections")
    if sum(rejections.values()) != counts[2]:
        raise ValueError("invalid v104 rejection count")
    migrated = []
    for item in objects:
        normalized, reason = _normalize_observation(item)
        if reason or normalized["pathIdentity"] is not None or item.get("canAutomate") is not False:
            raise ValueError("invalid v104 object: " + str(reason))
        migrated.append(normalized)
    migrated.sort(key=_sort_key)
    return {
        "schemaVersion": REPORT_SCHEMA_VERSION,
        "pathIdentityVersion": PATH_SCHEMA_VERSION,
        "placeId": place_id,
        "inputCount": counts[0],
        "acceptedCount": counts[1],
        "rejectedCount": counts[2],
        "rejections": dict(sorted(rejections.items())),
        "objects": migrated,
        "migration": {
            "sourceSchemaVersion": "104.release",
            "preservedLegacyPaths": len(migrated),
            "fabricatedIdentitySegments": 0,
        },
        "verifiedInGame": False,
        "gameplayFunctionsGenerated": 0,
        "readOnly": True,
    }
