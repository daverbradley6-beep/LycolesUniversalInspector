"""Independent semantic checks for generated v107 Luau artifacts."""
import json
import re

from feature_planner_v107 import validate_feature_plan

_JSON_STRING = r'"(?:\\.|[^"\\])*"'
_PATH = rf'\{{(?:{_JSON_STRING}(?:,{_JSON_STRING})*)?\}}'
_SEGMENT = rf'\{{name=({_JSON_STRING}),className=({_JSON_STRING}),ordinal=([1-9][0-9]*)\}}'
_IDENTITY = rf'(nil|\{{(?:{_SEGMENT}(?:,{_SEGMENT})*)?\}})'
_ENTRY = re.compile(
    rf'^  \{{id=({_JSON_STRING}),label=({_JSON_STRING}),path=({_PATH}),' 
    rf'pathIdentity={_IDENTITY},pathResolution=({_JSON_STRING}),' 
    rf'className=({_JSON_STRING}),property=({_JSON_STRING})\}},$',
    re.MULTILINE,
)
_SEGMENT_RE = re.compile(_SEGMENT)
_STRING_RE = re.compile(_JSON_STRING)


def _parse_path(value):
    inner = value[1:-1]
    if not inner:
        return []
    tokens = _STRING_RE.findall(inner)
    if ",".join(tokens) != inner:
        raise ValueError("malformed Luau path")
    return [json.loads(token) for token in tokens]


def _parse_identity(value):
    if value == "nil":
        return None
    inner = value[1:-1]
    if not inner:
        raise ValueError("empty Luau identity")
    matches = list(_SEGMENT_RE.finditer(inner))
    if ",".join(match.group(0) for match in matches) != inner:
        raise ValueError("malformed Luau identity")
    return [
        {
            "name": json.loads(match.group(1)),
            "className": json.loads(match.group(2)),
            "ordinal": int(match.group(3)),
        }
        for match in matches
    ]


def parse_feature_table(source):
    """Parse canonical feature entries without trusting manifest hashes or plans."""
    if not isinstance(source, str):
        raise ValueError("invalid Luau source")
    prefix = "local features = {\n"
    suffix = "\n}\nlocal status ="
    if source.count(prefix) != 1 or source.count(suffix) != 1:
        raise ValueError("malformed Luau feature table")
    start = source.index(prefix) + len(prefix)
    end = source.index(suffix, start)
    table = source[start:end]
    lines = table.splitlines()
    matches = list(_ENTRY.finditer(table))
    if len(matches) != len(lines) or any(match.group(0) != line for match, line in zip(matches, lines)):
        raise ValueError("malformed Luau feature entry")
    features = []
    for match in matches:
        groups = match.groups()
        identity_text = groups[3]
        features.append({
            "id": json.loads(groups[0]),
            "label": json.loads(groups[1]),
            "path": _parse_path(groups[2]),
            "pathIdentity": _parse_identity(identity_text),
            "pathResolution": json.loads(groups[-3]),
            "className": json.loads(groups[-2]),
            "property": json.loads(groups[-1]),
        })
    return features


def _project_features(feature_plan):
    return [
        {
            "id": feature["id"],
            "label": feature["label"],
            "path": feature["path"],
            "pathIdentity": feature["pathIdentity"],
            "pathResolution": feature["pathResolution"],
            "className": feature["className"],
            "property": feature["property"],
        }
        for feature in feature_plan["features"]
    ]


def validate_source_semantics(source, feature_plan):
    """Compare parsed runtime data and place guard to the canonical feature plan."""
    validate_feature_plan(feature_plan)
    issues = []
    parsed = []
    try:
        parsed = parse_feature_table(source)
    except (ValueError, json.JSONDecodeError):
        issues.append("malformed_feature_table")
    if parsed != _project_features(feature_plan):
        issues.append("feature_table_mismatch")
    identifiers = [feature["id"] for feature in parsed]
    if len(identifiers) != len(set(identifiers)):
        issues.append("duplicate_runtime_feature")
    guards = [int(value) for value in re.findall(r"game\.PlaceId ~= ([0-9]+)", source)]
    if guards != [feature_plan["placeId"]]:
        issues.append("place_guard_mismatch")
    return {
        "ok": not issues,
        "issues": sorted(set(issues)),
        "features": len(parsed),
        "runtimeVerified": False,
    }
