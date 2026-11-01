#!/usr/bin/env python3
"""v67 offline evidence correlation and release quality gate.

Combines passive v54 discovery with v66 change events. Correlation is not causality;
this module does not infer executable remote signatures or anti-cheat bypasses.
"""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from evidence_pipeline_v62 import import_console, catalog
from live_telemetry_v66 import parse_log

MAX_INPUT = 50_000_000
MAX_EVENTS = 1000

def normalize(path):
    if not isinstance(path, str):
        return ""
    return path.replace("/", ".").strip().casefold()

def compile_evidence(discovery_text, telemetry_text, place_id):
    if type(place_id) is not int or place_id <= 0:
        raise ValueError("place_id must be a positive integer")
    discovery = import_console(discovery_text)
    if discovery["placeId"] != place_id:
        raise ValueError("discovery place ID mismatch or missing")
    telemetry = parse_log(telemetry_text, place_id)
    cat = catalog(discovery)
    indexed = defaultdict(list)
    for item in cat["capabilities"]:
        indexed[normalize(item["path"])].append(item)
    events = telemetry["events"]
    if len(events) > MAX_EVENTS:
        raise ValueError("too many events")
    grouped = defaultdict(list)
    unmatched = []
    for event in events:
        path = normalize(event["path"])
        matches = indexed.get(path, [])
        record = {"tick": event["tick"], "kind": event["kind"],
                  "before": str(event["before"])[:120], "after": str(event["after"])[:120]}
        if matches:
            grouped[path].append(record)
        else:
            unmatched.append({"path": event["path"], **record})
    ranked = []
    for item in cat["capabilities"]:
        key = normalize(item["path"])
        related = grouped.get(key, [])
        if not related:
            continue
        ranked.append({"path": item["path"], "kind": item["kind"],
                       "className": item["className"],
                       "changeCount": len(related),
                       "distinctTicks": len({x["tick"] for x in related}),
                       "observations": related[:25],
                       "evidenceStatus": "observed_only",
                       "actionVerified": False,
                       "serverOutcomeVerified": False,
                       "causalityVerified": False})
    ranked.sort(key=lambda x: (-x["changeCount"], x["path"]))
    gates = {
        "placeIdsMatch": True,
        "discoveryComplete": cat["sourceComplete"],
        "telemetryComplete": telemetry["complete"],
        "hasCorrelatedObservations": bool(ranked),
        "verifiedExecutableActions": False
    }
    manifest = {
        "schemaVersion": "67.release",
        "placeId": place_id,
        "sourceHashes": {
            "discoverySha256": hashlib.sha256(discovery_text.encode("utf-8")).hexdigest(),
            "telemetrySha256": hashlib.sha256(telemetry_text.encode("utf-8")).hexdigest()},
        "gates": gates,
        "readyForActionGeneration": False,
        "reason": "Passive observations alone cannot establish an executable action contract",
        "cataloguedCapabilities": len(cat["capabilities"]),
        "correlatedPaths": len(ranked),
        "unmatchedTelemetryEvents": len(unmatched),
        "automaticExecutableActions": 0
    }
    return {"manifest": manifest, "correlations": ranked,
            "unmatchedEvents": unmatched[:100],
            "telemetrySummary": {"events": len(events),
                                 "eventKinds": dict(Counter(x["kind"] for x in events)),
                                 "complete": telemetry["complete"]}}

def build(discovery_text, telemetry_text, place_id, output):
    result = compile_evidence(discovery_text, telemetry_text, place_id)
    output.mkdir(parents=True, exist_ok=True)
    for filename, key in (("release-manifest-v67.json", "manifest"),
                          ("correlations-v67.json", "correlations"),
                          ("unmatched-events-v67.json", "unmatchedEvents"),
                          ("telemetry-summary-v67.json", "telemetrySummary")):
        (output / filename).write_text(json.dumps(result[key], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--discovery",type=Path,required=True)
    p.add_argument("--telemetry",type=Path,required=True)
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--output",type=Path,default=Path("build/release-v67"))
    a=p.parse_args()
    for path in (a.discovery,a.telemetry):
        if path.stat().st_size > MAX_INPUT: p.error("input exceeds 50 MB")
    result=build(a.discovery.read_text(encoding="utf-8-sig",errors="replace"),
                 a.telemetry.read_text(encoding="utf-8-sig",errors="replace"),
                 a.place_id,a.output)
    print(json.dumps(result["manifest"],indent=2))
if __name__=="__main__": main()
