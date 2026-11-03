#!/usr/bin/env python3
"""Validate bounded prompt-trial feedback against exact discovery evidence."""
import argparse
import hashlib
import json
import math
import pathlib

SCHEMA = "112.prompt-trial-feedback.1"
OUTPUT_SCHEMA = "112.prompt-trial-evaluation.1"
FALSE_CLAIMS = {
    "sourceAuthenticityVerified", "causalityProven", "serverAuthorityVerified",
    "runtimeVerified", "gameplayVerified", "actionOutcomesVerified",
}
STATUSES = {
    "target-unresolved", "prompt-disabled", "activation-unavailable", "teleport-failed",
    "activation-failed", "expected-change-observed", "expected-change-not-observed",
}
ENTRY_FIELDS = {
    "sequence", "targetPath", "outcomeKey", "expected", "before", "after",
    "observedExpectedChange", "status", "message", "observedAtUnix",
}


def _digest(document):
    raw = json.dumps(document, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _scalar(value):
    if value is None:
        return None
    if type(value) in (int, float):
        if not math.isfinite(value):
            raise ValueError("Invalid feedback scalar")
        return value
    if type(value) is bool or isinstance(value, str) and len(value) <= 128:
        return value
    raise ValueError("Invalid feedback scalar")


def _observed(expected, before, after):
    if expected == "increased":
        return (type(before) in (int, float) and type(after) in (int, float)
                and math.isfinite(before) and math.isfinite(after) and after > before)
    if expected == "decreased":
        return (type(before) in (int, float) and type(after) in (int, float)
                and math.isfinite(before) and math.isfinite(after) and after < before)
    return before is not None and after is not None and before != after


def _contracts(discovery):
    if (not isinstance(discovery, dict)
            or discovery.get("schemaVersion") != "111.action-capabilities.1"
            or type(discovery.get("placeId")) is not int
            or (discovery.get("scanId") is not None
                and not isinstance(discovery.get("scanId"), str))):
        raise ValueError("Invalid action capability discovery")
    claims = discovery.get("claims")
    if not isinstance(claims, dict) or set(claims) != FALSE_CLAIMS or any(claims.values()):
        raise ValueError("Action capability discovery claims unsupported verification")
    prompt = discovery.get("promptInteractions")
    if not isinstance(prompt, dict) or not isinstance(prompt.get("targets"), list):
        raise ValueError("Invalid prompt interaction discovery")
    contracts = {}
    for target in prompt["targets"]:
        if not isinstance(target, dict) or target.get("trialGenerationReady") is not True:
            continue
        selected = target.get("selectedOutcome")
        signals = target.get("outcomeSignals")
        if (not isinstance(selected, dict) or not isinstance(signals, list)
                or selected not in signals or selected.get("generationResolvable") is not True
                or not isinstance(selected.get("selection"), dict)
                or selected["selection"].get("selectedForTrial") is not True
                or selected.get("change") not in ("increased", "decreased", "changed")
                or not isinstance(target.get("path"), str)
                or not isinstance(selected.get("key"), str)):
            raise ValueError("Invalid selected prompt outcome")
        key = target["path"]
        if key in contracts:
            raise ValueError("Duplicate prompt target path")
        contracts[key] = {"outcomeKey": selected["key"], "expected": selected["change"]}
    if not contracts:
        raise ValueError("No feedback-ready prompt targets")
    return contracts


def evaluate(discovery, feedback):
    contracts = _contracts(discovery)
    scan_id = discovery.get("scanId") or "UNAVAILABLE"
    if not isinstance(feedback, dict) or set(feedback) != {
            "schemaVersion", "placeId", "scanId", "discoverySHA256", "sessionId",
            "entries", "claims"}:
        raise ValueError("Invalid prompt feedback schema")
    if (feedback.get("schemaVersion") != SCHEMA
            or feedback.get("placeId") != discovery["placeId"]
            or feedback.get("scanId") != scan_id
            or feedback.get("discoverySHA256") != _digest(discovery)):
        raise ValueError("Prompt feedback identity mismatch")
    session = feedback.get("sessionId")
    entries = feedback.get("entries")
    claims = feedback.get("claims")
    if (not isinstance(session, str) or not 1 <= len(session) <= 128
            or not isinstance(entries, list) or len(entries) > 100
            or not isinstance(claims, dict) or set(claims) != FALSE_CLAIMS
            or any(claims.values())):
        raise ValueError("Invalid prompt feedback claims or inventory")
    previous_sequence = None
    evaluated = []
    for entry in entries:
        if not isinstance(entry, dict) or not set(entry) <= ENTRY_FIELDS or not {
                "sequence", "targetPath", "outcomeKey", "expected", "observedExpectedChange",
                "status", "message", "observedAtUnix"} <= set(entry):
            raise ValueError("Invalid prompt feedback entry")
        sequence = entry["sequence"]
        path = entry["targetPath"]
        contract = contracts.get(path)
        if (type(sequence) is not int or sequence < 1
                or previous_sequence is not None and sequence <= previous_sequence
                or contract is None or entry["outcomeKey"] != contract["outcomeKey"]
                or entry["expected"] != contract["expected"]
                or entry["status"] not in STATUSES
                or not isinstance(entry["message"], str) or len(entry["message"]) > 240
                or type(entry["observedAtUnix"]) is not int or entry["observedAtUnix"] < 1
                or type(entry["observedExpectedChange"]) is not bool):
            raise ValueError("Invalid prompt feedback entry")
        previous_sequence = sequence
        before = _scalar(entry.get("before"))
        after = _scalar(entry.get("after"))
        observed = _observed(contract["expected"], before, after)
        if (entry["observedExpectedChange"] is not observed
                or (entry["status"] == "expected-change-observed") is not observed):
            raise ValueError("Prompt feedback outcome claim mismatch")
        evaluated.append({
            "sequence": sequence, "targetPath": path,
            "outcomeKey": contract["outcomeKey"], "expected": contract["expected"],
            "before": before, "after": after, "status": entry["status"],
            "expectedChangeObserved": observed,
        })
    grouped = []
    for path in sorted({entry["targetPath"] for entry in evaluated}):
        rows = [entry for entry in evaluated if entry["targetPath"] == path]
        grouped.append({
            "targetPath": path, "outcomeKey": contracts[path]["outcomeKey"],
            "expected": contracts[path]["expected"], "attempts": len(rows),
            "expectedChangesObserved": sum(row["expectedChangeObserved"] for row in rows),
            "statuses": {status: sum(row["status"] == status for row in rows)
                         for status in sorted({row["status"] for row in rows})},
            "runtimeCorrelationObserved": any(row["expectedChangeObserved"] for row in rows),
            "runtimeVerified": False, "gameplayVerified": False,
            "causalityProven": False,
        })
    return {
        "schemaVersion": OUTPUT_SCHEMA, "placeId": discovery["placeId"],
        "scanId": scan_id, "discoverySHA256": _digest(discovery),
        "sessionId": session, "entries": evaluated, "targets": grouped,
        "summary": {"submittedAttempts": len(evaluated),
                    "expectedChangesObserved": sum(row["expectedChangeObserved"] for row in evaluated)},
        "sourceAuthenticityVerified": False, "causalityProven": False,
        "serverAuthorityVerified": False, "runtimeVerified": False,
        "gameplayVerified": False, "actionOutcomesVerified": False,
        "note": "Feedback is bound to generated evidence but remains operator-supplied client observation, not causal or server-authoritative proof.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("discovery", type=pathlib.Path)
    parser.add_argument("feedback", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path,
                        default=pathlib.Path("build/prompt-trial-evaluation.json"))
    args = parser.parse_args()
    result = evaluate(json.loads(args.discovery.read_text(encoding="utf-8-sig")),
                      json.loads(args.feedback.read_text(encoding="utf-8-sig")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True,
                                      ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), **result["summary"],
                      "runtimeVerified": False, "gameplayVerified": False}, sort_keys=True))


if __name__ == "__main__":
    main()
