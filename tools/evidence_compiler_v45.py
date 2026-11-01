#!/usr/bin/env python3
"""Compile read-only feature evidence from v42 and v44 JSON reports."""
import argparse
import hashlib
import json
from pathlib import Path

def load(path):
    p = Path(path)
    if p.stat().st_size > 8_000_000:
        raise ValueError("Input exceeds size limit")
    return json.loads(p.read_text(encoding="utf-8-sig"))

def compile_contracts(manifest, report):
    if manifest.get("schemaVersion") != "42.0" or manifest.get("readOnly") is not True:
        raise ValueError("Expected v42 read-only manifest")
    if report.get("schemaVersion") != "44.0":
        raise ValueError("Expected v44 report")
    for key in ("placeId", "scanId", "sourceFingerprint"):
        if manifest.get(key) != report.get(key):
            raise ValueError("Identity mismatch: " + key)
    if any(report.get(key) is not False for key in ("runtimeVerified", "serverOutcomeVerified", "gameplayAutomationApproved")):
        raise ValueError("Unexpected verification claim")
    count = report.get("snapshotsAnalyzed")
    if type(count) is not int or not 1 <= count <= 32:
        raise ValueError("Invalid snapshot count")
    features = manifest.get("features")
    observations = report.get("paths")
    if not isinstance(features, list) or not isinstance(observations, dict):
        raise ValueError("Missing features or observations")
    expected = set()
    ids = set()
    for feature in features:
        if feature.get("kind") != "read-only-inspection" or feature.get("gameplayVerified") is not False:
            raise ValueError("Invalid feature")
        fid = feature.get("id")
        paths = feature.get("evidencePaths")
        if not isinstance(fid, str) or fid in ids or not isinstance(paths, list) or not paths:
            raise ValueError("Invalid feature paths")
        if any(not isinstance(p, str) for p in paths) or len(set(paths)) != len(paths):
            raise ValueError("Duplicate or invalid path")
        ids.add(fid)
        expected.update(paths)
    if set(observations) != expected or len(expected) > 10000:
        raise ValueError("Path inventory mismatch")
    for path, item in observations.items():
        found = item.get("foundSnapshots")
        reasons = item.get("reasons")
        if type(found) is not int or not 0 <= found <= count or item.get("totalSnapshots") != count:
            raise ValueError("Invalid observation count")
        status = "persistent" if found == count else "intermittent" if found else "not-observed"
        if item.get("status") != status:
            raise ValueError("Invalid status")
        if not isinstance(reasons, dict) or any(
            k not in ("found", "missing-segment", "unsupported-root") or type(v) is not int or v < 0
            for k, v in reasons.items()
        ) or sum(reasons.values()) != count or reasons.get("found", 0) != found:
            raise ValueError("Invalid reason counts")
    compiled = []
    for feature in sorted(features, key=lambda x: x["id"]):
        grouped = {
            state: sorted(p for p in feature["evidencePaths"] if observations[p]["status"] == state)
            for state in ("persistent", "intermittent", "not-observed")
        }
        compiled.append({
            "id": feature["id"],
            "family": feature["family"],
            "kind": "read-only-inspection",
            "status": "diagnostic-only",
            "evidence": grouped,
            "stablePathCount": len(grouped["persistent"]),
            "observedPathCount": len(grouped["persistent"]) + len(grouped["intermittent"]),
            "totalPathCount": len(feature["evidencePaths"]),
            "mechanicVerified": False,
            "gameplayAutomationApproved": False,
        })
    digest = hashlib.sha256(json.dumps(report, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "schemaVersion": "45.0",
        "placeId": manifest["placeId"],
        "scanId": manifest["scanId"],
        "sourceFingerprint": manifest["sourceFingerprint"],
        "inputEvidenceFingerprint": digest,
        "snapshotsAnalyzed": count,
        "featureCount": len(compiled),
        "features": compiled,
        "readOnly": True,
        "runtimeVerified": False,
        "serverOutcomeVerified": False,
        "gameplayAutomationApproved": False,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("report")
    parser.add_argument("--output", default="build/evidence-contracts-v45.json")
    args = parser.parse_args()
    result = compile_contracts(load(args.manifest), load(args.report))
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Compiled", result["featureCount"], "read-only evidence contracts into", dest)

if __name__ == "__main__":
    main()
