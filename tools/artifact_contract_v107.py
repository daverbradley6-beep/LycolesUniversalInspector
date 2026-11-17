"""Independent semantic checks for generated v107 Luau artifacts."""
import re

from feature_planner_v107 import validate_feature_plan

_LUAU_STRING = r'"(?:\\(?:[0-9]{3}|["\\])|[^"\\])*"'
_PATH = rf'\{{(?:{_LUAU_STRING}(?:,{_LUAU_STRING})*)?\}}'
_SEGMENT = rf'\{{name=({_LUAU_STRING}),className=({_LUAU_STRING}),ordinal=([1-9][0-9]*)\}}'
_IDENTITY = rf'(nil|\{{(?:{_SEGMENT}(?:,{_SEGMENT})*)?\}})'
_ENTRY = re.compile(
    rf'^  \{{id=({_LUAU_STRING}),label=({_LUAU_STRING}),path=({_PATH}),'
    rf'pathIdentity={_IDENTITY},pathResolution=({_LUAU_STRING}),'
    rf'className=({_LUAU_STRING}),property=({_LUAU_STRING})\}},$',
    re.MULTILINE,
)
_SEGMENT_RE = re.compile(_SEGMENT)
_STRING_RE = re.compile(_LUAU_STRING)


def _decode_luau_string(value):
    if not isinstance(value, str) or _STRING_RE.fullmatch(value) is None:
        raise ValueError("invalid Luau string")
    data = bytearray()
    index = 1
    while index < len(value) - 1:
        character = value[index]
        if character != "\\":
            codepoint = ord(character)
            if not 32 <= codepoint <= 126:
                raise ValueError("non-canonical Luau string")
            data.append(codepoint)
            index += 1
            continue
        if value[index + 1] in {'"', "\\"}:
            data.append(ord(value[index + 1]))
            index += 2
            continue
        byte = int(value[index + 1:index + 4])
        if byte > 255:
            raise ValueError("invalid Luau byte escape")
        data.append(byte)
        index += 4
    return data.decode("utf-8")


def _parse_path(value):
    inner = value[1:-1]
    if not inner:
        return []
    tokens = _STRING_RE.findall(inner)
    if ",".join(tokens) != inner:
        raise ValueError("malformed Luau path")
    return [_decode_luau_string(token) for token in tokens]


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
            "name": _decode_luau_string(match.group(1)),
            "className": _decode_luau_string(match.group(2)),
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
            "id": _decode_luau_string(groups[0]),
            "label": _decode_luau_string(groups[1]),
            "path": _parse_path(groups[2]),
            "pathIdentity": _parse_identity(identity_text),
            "pathResolution": _decode_luau_string(groups[-3]),
            "className": _decode_luau_string(groups[-2]),
            "property": _decode_luau_string(groups[-1]),
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
    except (UnicodeDecodeError, ValueError):
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
