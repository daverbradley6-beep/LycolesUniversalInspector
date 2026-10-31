#!/usr/bin/env python3
"""Lycoles v8 offline scan compiler: multipart integrity -> feature evidence -> release plan.
No third-party packages, Roblox credentials, or game-specific hardcoding required.
Usage: python3 tools/compile_scan.py scan-parts-dir --output build
"""
import argparse, collections, hashlib, json, pathlib, sys

def fail(message):
    raise ValueError(message)

def compile_scan(directory):
    files=sorted(pathlib.Path(directory).glob("*.json"))
    if not files: fail("No JSON scan parts found")
    parts=[]
    for file in files:
        raw=file.read_bytes()
        if len(raw)>3_000_000: fail(f"Part too large: {file.name}")
        data=json.loads(raw)
        if not isinstance(data,dict) or not isinstance(data.get("objects"),list): fail(f"Invalid part: {file.name}")
        parts.append(data)
    first=parts[0]
    scan_id=first.get("scanId"); place_id=first.get("placeId")
    count=first.get("partCount")
    if not isinstance(scan_id,str) or not isinstance(place_id,int) or not isinstance(count,int) or count<1 or count>2000:
        fail("Invalid scan identity")
    by_index={}
    for part in parts:
        index=part.get("partIndex")
        if part.get("scanId")!=scan_id or part.get("placeId")!=place_id or part.get("partCount")!=count:
            fail("Mixed scan IDs, place IDs, or part counts")
        if not isinstance(index,int) or not 1<=index<=count: fail("Invalid part index")
        fingerprint=hashlib.sha256(json.dumps(part,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        if index in by_index:
            if by_index[index][0]!=fingerprint: fail(f"Conflicting duplicate part {index}")
            continue
        by_index[index]=(fingerprint,part)
    missing=[i for i in range(1,count+1) if i not in by_index]
    if missing: fail(f"Missing parts: {missing[:30]} (total {len(missing)})")
    ordered=[by_index[i][1] for i in range(1,count+1)]
    objects=[o for p in ordered for o in p["objects"] if isinstance(o,dict)]
    metadata=next((p for p in ordered if isinstance(p.get("scanStats"),dict)),None)
    if metadata is None: fail("Missing scan metadata")
    expected=metadata["scanStats"].get("recorded")
    if expected is not None and expected!=len(objects):
        fail(f"Object count mismatch: expected {expected}, received {len(objects)}")
    history=[]
    for p in ordered:
        history.extend(p.get("interactionHistoryChunk") or [])
    if not history:
        history=(metadata.get("interactionDiagnostics") or {}).get("recentInteractions") or []
    feature_evidence=metadata.get("featureEvidence") or {}
    readiness=metadata.get("featureReadiness") or {}
    # Evidence is descriptive, never an authorization to invoke arbitrary remotes.
    feature_names=set()
    for source in (feature_evidence,readiness):
        if isinstance(source,dict): feature_names.update(str(k) for k in source.keys())
    for item in history:
        if isinstance(item,dict) and item.get("featureCandidate"):
            feature_names.add(str(item["featureCandidate"]))
    counts=collections.Counter(str(o.get("class","Unknown")) for o in objects)
    paths=collections.Counter((str(o.get("path","")),str(o.get("scanOrdinal",""))) for o in objects)
    duplicate_count=sum(v-1 for v in paths.values())
    if duplicate_count:
        fail(f"Duplicate object identities: {duplicate_count}")
    features=[]
    for name in sorted(feature_names):
        events=[e for e in history if isinstance(e,dict) and e.get("featureCandidate")==name]
        observed=sum(1 for e in events if e.get("evidenceLevel"))
        outcomes=sum(1 for e in events if e.get("outcomeVerified") is True)
        features.append({
            "feature":name,"interactionEvents":len(events),
            "observedEvents":observed,"verifiedClientOutcomes":outcomes,
            "status":"client-outcome-observed" if outcomes else ("interaction-observed" if observed else "discovered"),
            "implementationReady":False,
            "reason":"No verified, permitted reproducible implementation contract in passive scan",
            "evidence":feature_evidence.get(name) if isinstance(feature_evidence,dict) else None,
        })
    integrity={"scanId":scan_id,"placeId":place_id,"parts":count,"objects":len(objects),
               "uniqueObjectIdentities":len(paths),"interactionEvents":len(history),
               "scanComplete":bool(metadata["scanStats"].get("complete"))}
    if not integrity["scanComplete"]: fail("Source scan reports incomplete root coverage")
    plan={"schemaVersion":"8.0","integrity":integrity,"featureCount":len(features),
          "features":features,"classCounts":dict(counts),
          "releaseGate":{"gameplayAutomationApproved":False,
                         "reason":"Passive inspection cannot establish replayable server-authoritative actions",
                         "nextStep":"Review feature contracts and validate supported operations in a permitted environment"}}
    return plan

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parts_dir");parser.add_argument("--output",default="build")
    args=parser.parse_args()
    try: plan=compile_scan(args.parts_dir)
    except (ValueError,OSError,json.JSONDecodeError) as exc:
        print("INTEGRITY FAILURE:",exc,file=sys.stderr);return 2
    out=pathlib.Path(args.output);out.mkdir(parents=True,exist_ok=True)
    (out/"capability-plan.json").write_text(json.dumps(plan,indent=2,ensure_ascii=False)+"\n")
    lines=[f"# Scan capability plan — {plan['integrity']['placeId']}","",
           f"Verified parts: {plan['integrity']['parts']}; objects: {plan['integrity']['objects']}; interactions: {plan['integrity']['interactionEvents']}.","",
           "| Feature | Events | Client outcomes | Status |","|---|---:|---:|---|"]
    for f in plan["features"]:
        lines.append(f"| {f['feature'].replace('|','/')} | {f['interactionEvents']} | {f['verifiedClientOutcomes']} | {f['status']} |")
    lines+=["","**Gameplay automation is not automatically approved.** A scan proves observation, not a replayable API."]
    (out/"capability-plan.md").write_text("\n".join(lines)+"\n")
    print(f"PASS: {len(plan['features'])} feature candidates, {plan['integrity']['objects']} objects; outputs in {out}")
    return 0

if __name__=="__main__": sys.exit(main())
