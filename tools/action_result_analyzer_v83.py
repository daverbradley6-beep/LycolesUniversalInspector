#!/usr/bin/env python3
"""v83: replayable GUI test-result analysis, evidence linkage, and safe review reports.

Consumes LYCOLES_V82_RESULT lines; never treats an activation request as success.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

MARKER = "LYCOLES_V82_RESULT "
MAX_LOG_BYTES = 30_000_000

def parse_logs(paths, place_id):
    results = {}
    warnings = []
    for source in paths:
        path = Path(source)
        if not path.is_file() or path.stat().st_size > MAX_LOG_BYTES:
            raise ValueError(f"Missing or oversized log: {path}")
        for line_number, line in enumerate(path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1):
            if MARKER not in line:
                continue
            try:
                item = json.loads(line.split(MARKER, 1)[1])
            except json.JSONDecodeError:
                warnings.append(f"{path}:{line_number}: malformed JSON")
                continue
            if not isinstance(item, dict) or item.get("schemaVersion") != "82.result":
                warnings.append(f"{path}:{line_number}: unsupported result schema")
                continue
            if item.get("placeId") != place_id:
                warnings.append(f"{path}:{line_number}: place mismatch")
                continue
            if not isinstance(item.get("id"), str) or not item["id"] or type(item.get("requested")) is not bool:
                warnings.append(f"{path}:{line_number}: invalid result fields")
                continue
            changes = item.get("observedChanges", [])
            if not isinstance(changes, list) or len(changes) > 200:
                warnings.append(f"{path}:{line_number}: invalid changes")
                continue
            valid_changes = []
            for change in changes:
                if not isinstance(change, dict) or not isinstance(change.get("stat"), str):
                    continue
                if "before" not in change or "after" not in change:
                    continue
                valid_changes.append({"stat": change["stat"], "before": change["before"], "after": change["after"]})
            result = {
                "id": item["id"], "requested": item["requested"],
                "observedChanges": valid_changes, "verified": False,
                "source": str(path), "line": line_number
            }
            results[(str(path), line_number)] = result
    return list(results.values()), warnings

def direction(before, after):
    if type(before) is not type(after) or before == after:
        return None
    if type(before) in (int, float):
        return "increase" if after > before else "decrease"
    if type(before) is bool:
        return "toggle"
    if type(before) is str:
        return "change"
    return None

def analyze(results, expected=None):
    expected = expected or {}
    groups = defaultdict(list)
    for result in results:
        groups[result["id"]].append(result)
    rows = []
    for action_id, items in sorted(groups.items()):
        requested = [x for x in items if x["requested"]]
        errors = len(items) - len(requested)
        observed = defaultdict(int)
        for item in requested:
            seen = set()
            for change in item["observedChanges"]:
                op = direction(change["before"], change["after"])
                if op:
                    seen.add((change["stat"], op))
            for key in seen:
                observed[key] += 1
        expected_signals = expected.get(action_id, [])
        matching = sum(
            1 for item in requested
            if all(any(
                c["stat"] == sig["stat"] and direction(c["before"], c["after"]) == sig["operator"]
                for c in item["observedChanges"]
            ) for sig in expected_signals)
        ) if expected_signals else 0
        rows.append({
            "id": action_id,
            "attempts": len(items),
            "activationRequests": len(requested),
            "activationFailures": errors,
            "observedSignals": [
                {"stat": stat, "operator": op, "observations": count}
                for (stat, op), count in sorted(observed.items())
            ],
            "expectedSignals": expected_signals,
            "expectedMatches": matching if expected_signals else None,
            "status": "observed_not_verified" if requested else "activation_failed",
            "verified": False,
        })
    return {"schemaVersion": "83.review", "totalResults": len(results),
            "actions": rows, "verified": False, "executionEnabled": False}

def load_expected(path, place_id):
    if path is None:
        return {}
    doc = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if doc.get("placeId") != place_id or not isinstance(doc.get("contracts"), list):
        raise ValueError("Expected contract file does not match place")
    output = {}
    for c in doc["contracts"]:
        if not isinstance(c, dict) or c.get("approved") is not True:
            continue
        cid = c.get("id")
        if not isinstance(cid, str):
            continue
        # Explicit expectations only; never infer an outcome from the activation itself.
        signals = c.get("expectedSignals", [])
        if not isinstance(signals, list):
            raise ValueError("expectedSignals must be an array")
        cleaned = []
        for s in signals:
            if not isinstance(s, dict) or not isinstance(s.get("stat"), str) or s.get("operator") not in ("increase", "decrease", "toggle", "change"):
                raise ValueError(f"Invalid expected signal for {cid}")
            cleaned.append({"stat": s["stat"], "operator": s["operator"]})
        output[cid] = cleaned
    return output

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--place-id", type=int, required=True)
    parser.add_argument("--result-log", type=Path, action="append", required=True)
    parser.add_argument("--contracts", type=Path)
    parser.add_argument("--output", type=Path, default=Path("build/release-v83"))
    args = parser.parse_args()
    if args.place_id <= 0:
        parser.error("Place ID must be positive")
    results, warnings = parse_logs(args.result_log, args.place_id)
    report = analyze(results, load_expected(args.contracts, args.place_id))
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data in (
        ("action-results-v83.json", report),
        ("parse-warnings-v83.json", warnings),
    ):
        (args.output / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"results": len(results), "actions": len(report["actions"]), "warnings": len(warnings), "verified": False}))

if __name__ == "__main__":
    main()
