#!/usr/bin/env python3
"""Versioned Roblox API-dump extraction and v107 compatibility checks."""
import argparse
import hashlib
import json
import re
from pathlib import Path

from feature_planner_v106 import SUPPORTED
from feature_planner_v107 import validate_feature_plan
from release_pipeline_v104 import canonical

SNAPSHOT_SCHEMA_VERSION = "107.roblox-api-snapshot"
COMPATIBILITY_SCHEMA_VERSION = "107.api-compatibility"
SOURCE_CHANNEL = "QTStudio"
SOURCE_URL_PREFIX = "https://setup.rbxcdn.com/"
GLOBAL_ASSUMPTIONS = [
    "Instance.new",
    "RBXScriptSignal.Connect",
    "UDim.new",
    "UDim2.fromOffset",
    "UDim2.fromScale",
    "UDim2.new",
    "game",
    "task.spawn",
    "task.wait",
    "workspace",
]
RUNTIME_REQUIREMENTS = (
    ("DataModel", "GetService", "call"),
    ("DataModel", "PlaceId", "read"),
    ("Instance", "ClassName", "read"),
    ("Instance", "GetChildren", "call"),
    ("Instance", "Name", "read"),
    ("Player", "WaitForChild", "call"),
    ("PlayerGui", "FindFirstChild", "call"),
    ("Players", "LocalPlayer", "read"),
    ("ScreenGui", "Destroy", "call"),
    ("ScreenGui", "Name", "write"),
    ("ScreenGui", "Parent", "read"),
    ("ScreenGui", "Parent", "write"),
    ("ScreenGui", "ResetOnSpawn", "write"),
    ("ScrollingFrame", "CanvasSize", "write"),
    ("ScrollingFrame", "Parent", "write"),
    ("ScrollingFrame", "Position", "write"),
    ("ScrollingFrame", "Size", "write"),
    ("TextBox", "GetPropertyChangedSignal", "call"),
    ("TextBox", "Name", "write"),
    ("TextBox", "Parent", "write"),
    ("TextBox", "PlaceholderText", "write"),
    ("TextBox", "Size", "write"),
    ("TextBox", "Text", "write"),
    ("TextButton", "Activated", "event"),
    ("TextButton", "Parent", "write"),
    ("TextButton", "Size", "write"),
    ("TextButton", "Text", "write"),
    ("TextButton", "Visible", "write"),
    ("UIListLayout", "AbsoluteContentSize", "read"),
    ("UIListLayout", "GetPropertyChangedSignal", "call"),
    ("UIListLayout", "Padding", "write"),
    ("UIListLayout", "Parent", "write"),
)
EMITTED_NONCLASS_MEMBERS = {"Connect", "Y"}
MEMBER_REFERENCE = re.compile(r"[:.]([A-Z][A-Za-z0-9_]*)")


def _feature_requirements():
    return tuple(sorted((class_name, prop, "read") for class_name, prop in SUPPORTED.items()))


def _all_requirements():
    return tuple(sorted(set((*RUNTIME_REQUIREMENTS, *_feature_requirements()))))


def _member(classes, target, name):
    seen = set()
    current = target
    while current != "<<<ROOT>>>" and current not in seen:
        seen.add(current)
        value = classes.get(current)
        if value is None:
            return None, None
        for member in value.get("Members", []):
            if member.get("Name") == name:
                return current, member
        current = value.get("Superclass")
    return None, None


def _security(member):
    security = member.get("Security")
    if isinstance(security, dict):
        return security.get("Read"), security.get("Write")
    return security, None


def build_snapshot(api_dump, *, source_version, source_sha256):
    """Extract the bounded API member set required by v107 generation."""
    if not isinstance(api_dump, dict) or api_dump.get("Version") != 1 or not isinstance(api_dump.get("Classes"), list):
        raise ValueError("invalid Roblox API dump")
    if not isinstance(source_version, str) or re.fullmatch(r"version-[0-9a-f]{16}", source_version) is None:
        raise ValueError("invalid source version")
    if not isinstance(source_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", source_sha256) is None:
        raise ValueError("invalid source hash")
    classes = {value.get("Name"): value for value in api_dump["Classes"] if isinstance(value, dict)}
    members = []
    member_keys = sorted({(target, name) for target, name, _ in _all_requirements()})
    for target, name in member_keys:
        owner, member = _member(classes, target, name)
        if owner is None:
            raise ValueError(f"missing API member: {target}.{name}")
        read_security, write_security = _security(member)
        members.append({
            "targetClass": target,
            "member": name,
            "ownerClass": owner,
            "memberType": member.get("MemberType"),
            "readSecurity": read_security,
            "writeSecurity": write_security,
            "tags": sorted(member.get("Tags", [])),
        })
    snapshot = {
        "schemaVersion": SNAPSHOT_SCHEMA_VERSION,
        "source": {
            "channel": SOURCE_CHANNEL,
            "version": source_version,
            "url": f"{SOURCE_URL_PREFIX}{source_version}-API-Dump.json",
            "sha256": source_sha256,
            "formatVersion": api_dump["Version"],
        },
        "members": members,
    }
    return validate_snapshot(snapshot)


def validate_snapshot(snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) != {"schemaVersion", "source", "members"}:
        raise ValueError("invalid API snapshot fields")
    if snapshot.get("schemaVersion") != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError("invalid API snapshot schema")
    source = snapshot.get("source")
    source_fields = {"channel", "version", "url", "sha256", "formatVersion"}
    if not isinstance(source, dict) or set(source) != source_fields:
        raise ValueError("invalid API snapshot source")
    version = source.get("version")
    if source.get("channel") != SOURCE_CHANNEL or not isinstance(version, str) or re.fullmatch(r"version-[0-9a-f]{16}", version) is None:
        raise ValueError("invalid API snapshot version")
    if source.get("url") != f"{SOURCE_URL_PREFIX}{version}-API-Dump.json" or source.get("formatVersion") != 1:
        raise ValueError("invalid API snapshot source")
    if not isinstance(source.get("sha256"), str) or re.fullmatch(r"[0-9a-f]{64}", source["sha256"]) is None:
        raise ValueError("invalid API snapshot hash")
    members = snapshot.get("members")
    fields = {"targetClass", "member", "ownerClass", "memberType", "readSecurity", "writeSecurity", "tags"}
    if not isinstance(members, list) or not members or len(members) > 200:
        raise ValueError("invalid API snapshot members")
    keys = []
    for item in members:
        if not isinstance(item, dict) or set(item) != fields:
            raise ValueError("invalid API snapshot member")
        if any(not isinstance(item[field], str) or not item[field] for field in ("targetClass", "member", "ownerClass")):
            raise ValueError("invalid API snapshot member identity")
        if item["memberType"] not in {"Property", "Function", "Event"}:
            raise ValueError("invalid API member type")
        if any(value is not None and not isinstance(value, str) for value in (item["readSecurity"], item["writeSecurity"])):
            raise ValueError("invalid API member security")
        tags = item["tags"]
        if not isinstance(tags, list) or tags != sorted(set(tags)) or any(not isinstance(tag, str) for tag in tags):
            raise ValueError("invalid API member tags")
        keys.append((item["targetClass"], item["member"]))
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise ValueError("noncanonical API snapshot members")
    return snapshot


def load_snapshot(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if canonical(value) != Path(path).read_bytes():
        raise ValueError("noncanonical API snapshot")
    return validate_snapshot(value)


def _requirements(requirements, kind):
    return [
        {"targetClass": target, "member": member, "access": access, "kind": kind}
        for target, member, access in requirements
    ]


def validate_emitted_source_members(source):
    """Require every emitted member token to be represented by this contract."""
    if not isinstance(source, str):
        raise ValueError("invalid emitted source")
    expected = {member for _, member, _ in RUNTIME_REQUIREMENTS} | EMITTED_NONCLASS_MEMBERS
    actual = set(MEMBER_REFERENCE.findall(source))
    missing = sorted(expected - actual)
    unaccounted = sorted(actual - expected)
    if missing or unaccounted:
        raise ValueError(f"emitted API member drift: missing={missing}, unaccounted={unaccounted}")
    return {"members": sorted(actual), "globalMembers": sorted(EMITTED_NONCLASS_MEMBERS)}


def assess_compatibility(snapshot, feature_plan):
    """Check every emitted class member and supported read property."""
    validate_snapshot(snapshot)
    validate_feature_plan(feature_plan)
    records = {(item["targetClass"], item["member"]): item for item in snapshot["members"]}
    runtime = _requirements(RUNTIME_REQUIREMENTS, "runtime")
    features = _requirements(_feature_requirements(), "feature")
    issues = []
    expected_types = {"read": "Property", "write": "Property", "call": "Function", "event": "Event"}
    for requirement in (*runtime, *features):
        target = requirement["targetClass"]
        member = requirement["member"]
        access = requirement["access"]
        prefix = f"{requirement['kind']}:{access}:{target}.{member}"
        record = records.get((target, member))
        if record is None:
            issues.append("missing:" + prefix)
            continue
        if record["memberType"] != expected_types[access]:
            issues.append("type_mismatch:" + prefix)
            continue
        security = record["writeSecurity"] if access == "write" else record["readSecurity"]
        if security != "None" or access == "write" and "ReadOnly" in record["tags"]:
            issues.append("inaccessible:" + prefix)
    return {
        "schemaVersion": COMPATIBILITY_SCHEMA_VERSION,
        "snapshotVersion": snapshot["source"]["version"],
        "snapshotSha256": hashlib.sha256(canonical(snapshot)).hexdigest(),
        "sourceDumpSha256": snapshot["source"]["sha256"],
        "runtimeRequirements": runtime,
        "featureRequirements": features,
        "globalAssumptions": list(GLOBAL_ASSUMPTIONS),
        "issues": sorted(issues),
        "compatible": not issues,
        "runtimeVerified": False,
        "gameplayVerified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-dump", type=Path, required=True)
    parser.add_argument("--source-version", required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = args.api_dump.read_bytes()
    if hashlib.sha256(payload).hexdigest() != args.source_sha256:
        raise SystemExit("source hash mismatch")
    snapshot = build_snapshot(
        json.loads(payload),
        source_version=args.source_version,
        source_sha256=args.source_sha256,
    )
    if args.output.exists() and args.output.is_symlink():
        raise SystemExit("symlink output forbidden")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(snapshot))
    print(json.dumps({"ok": True, "members": len(snapshot["members"]), "output": str(args.output)}, sort_keys=True))


if __name__ == "__main__":
    main()
