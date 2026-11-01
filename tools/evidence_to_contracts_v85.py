#!/usr/bin/env python3
"""v85: turn validated v83 action evidence into reviewable, disabled GUI contracts.

This is an evidence-to-review bridge, not an automatic executor.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

def make_id(value, used):
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value)).strip("_")
    if not stem or not stem[0].isalpha():
        stem = "action_" + stem
    stem = stem[:30] or "action"
    candidate = stem
    n = 2
    while candidate in used:
        suffix = "_" + str(n)
        candidate = stem[:40 - len(suffix)] + suffix
        n += 1
    used.add(candidate)
    return candidate

def convert(report, catalog, place_id):
    if type(place_id) is not int or place_id <= 0:
        raise ValueError("invalid place")
    if not isinstance(report, dict) or report.get("schemaVersion") != "83.review":
        raise ValueError("v83 review required")
    if not isinstance(report.get("actions"), list):
        raise ValueError("v83 actions array required")
    if not isinstance(catalog, dict) or catalog.get("placeId") != place_id:
        raise ValueError("catalog place mismatch")
    entries = catalog.get("contracts")
    if not isinstance(entries, list):
        raise ValueError("catalog contracts array required")
    index = {}
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        if item["id"] in index:
            raise ValueError("duplicate catalog ID")
        index[item["id"]] = item
    used = set()
    contracts = []
    skipped = []
    for row in report["actions"]:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            continue
        old_id = row["id"]
        original = index.get(old_id)
        if original is None:
            skipped.append({"id": old_id, "reason": "not in catalog"})
            continue
        action = original.get("input")
        if not isinstance(action, list) or len(action) != 2 or action[0] != "gui":
            skipped.append({"id": old_id, "reason": "unsupported input"})
            continue
        path = action[1]
        if isinstance(path, str):
            try:
                path = json.loads(path)
            except json.JSONDecodeError:
                skipped.append({"id": old_id, "reason": "invalid GUI path"})
                continue
        if not isinstance(path, list):
            skipped.append({"id": old_id, "reason": "invalid GUI path"})
            continue
        signals = row.get("expectedSignals", [])
        if not isinstance(signals, list):
            signals = []
        contracts.append({
            "id": make_id(old_id, used),
            "sourceActionId": old_id,
            "approved": False,
            "executionEnabled": False,
            "input": ["gui", path],
            "expectedSignals": signals,
            "evidence": {
                "attempts": row.get("attempts", 0),
                "activationRequests": row.get("activationRequests", 0),
                "independentCaptures": row.get("independentCaptures", 0),
                "expectedMatches": row.get("expectedMatches"),
                "verifiedInGame": False
            }
        })
    return {
        "placeId": place_id, "schemaVersion": "85.review",
        "contracts": contracts, "skipped": skipped,
        "automaticallyApproved": 0, "automaticallyExecuted": 0
    }

def review_digest(document):
    payload = json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--place-id", type=int, required=True)
    p.add_argument("--review", type=Path, required=True, help="v83 action-results-v83.json")
    p.add_argument("--catalog", type=Path, required=True, help="existing contracts file containing GUI paths")
    p.add_argument("--output", type=Path, default=Path("build/release-v85"))
    a = p.parse_args()
    report = json.loads(a.review.read_text(encoding="utf-8-sig"))
    catalog = json.loads(a.catalog.read_text(encoding="utf-8-sig"))
    doc = convert(report, catalog, a.place_id)
    a.output.mkdir(parents=True, exist_ok=True)
    dest = a.output / "contracts-for-review-v85.json"
    dest.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "reviewContracts": len(doc["contracts"]),
        "skipped": len(doc["skipped"]),
        "automaticallyApproved": 0,
        "reviewSha256": review_digest(doc)
    }))

if __name__ == "__main__":
    main()
