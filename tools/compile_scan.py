#!/usr/bin/env python3
"""Lycoles v8 offline scan compiler: multipart integrity -> feature evidence -> release plan.
No third-party packages, Roblox credentials, or game-specific hardcoding required.
Usage: python3 tools/compile_scan.py scan-parts-dir --output build
"""
import argparse, collections, hashlib, json, pathlib, sys

def fail(message):
    raise ValueError(message)

_CORRELATION_CLASSIFICATION="feature-consistent-observable-change"
_CORRELATION_STATUS="candidate-needs-causal-validation"

def _false_claims(document,server_key):
    required=("sourceAuthenticityVerified","causalityProven",server_key,"gameplayVerified")
    aliases=("serverVerified","serverAuthorityVerified","outcomeVerified",
             "runtimeVerified","liveGameVerified","replayable")
    return (all(document.get(key) is False for key in required)
            and not any(document.get(key) is True for key in aliases))

def _correlation_evidence(event):
    feature=event.get("featureCandidate")
    state=event.get("featureStateEvidence")
    gui=event.get("featureGuiEvidence")
    candidate=event.get("observableOutcomeCandidate")
    kinds=[]
    for field,value,server_key,detail_key,kind in (
        ("featureStateEvidence",state,"serverVerified","matchedKeys","state-change"),
        ("featureGuiEvidence",gui,"serverVerified","matchedPaths","gui-change")):
        if value is None:
            continue
        if not isinstance(value,dict):
            fail(f"Malformed {field}")
        if value.get("classification")!=_CORRELATION_CLASSIFICATION:
            continue
        details=value.get(detail_key)
        if (value.get("feature")!=feature or value.get("status")!=_CORRELATION_STATUS
                or not isinstance(details,list) or not details
                or any(not isinstance(item,str) or not item for item in details)
                or not _false_claims(value,server_key)):
            fail("Feature correlation evidence claims verification or is malformed")
        kinds.append(kind)
    if candidate is None:
        if kinds:
            fail("Feature correlation evidence lacks observable outcome candidate")
        return {"candidate":False,"state":False,"gui":False}
    if not isinstance(candidate,dict):
        fail("Malformed observable outcome candidate")
    evidence_kinds=candidate.get("evidenceKinds")
    if (candidate.get("feature")!=feature
            or candidate.get("classification")!=_CORRELATION_CLASSIFICATION
            or not isinstance(evidence_kinds,list) or not evidence_kinds
            or any(kind not in ("state-change","gui-change") for kind in evidence_kinds)
            or len(set(evidence_kinds))!=len(evidence_kinds)
            or set(evidence_kinds)!=set(kinds)
            or type(candidate.get("overlappingInteractionsPossible")) is not bool
            or not _false_claims(candidate,"serverAuthorityVerified")
            or event.get("outcomeVerified") is not False):
        fail("Observable outcome candidate evidence claims verification or is malformed")
    return {"candidate":True,"state":"state-change" in kinds,"gui":"gui-change" in kinds}


def compile_scan(directory):
    files=sorted(pathlib.Path(directory).glob("*.json"))
    if not files: fail("No JSON scan parts found")
    parts=[]
    for file in files:
        raw=file.read_bytes()
        if len(raw)>3_000_000: fail(f"Part too large: {file.name}")
        data=json.loads(raw)
        if not isinstance(data,dict) or not isinstance(data.get("objects"),list):
            if isinstance(data,dict) and "partIndex" not in data and ("objectCount" in data or "metadata" in data):
                continue
            fail(f"Invalid part: {file.name}")
        parts.append(data)
    if not parts: fail("No multipart payloads found")
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
    if any(not isinstance(o,dict) for p in ordered for o in p["objects"]):
        fail("Malformed object record")
    objects=[o for p in ordered for o in p["objects"]]
    if len(objects)>2_000_000: fail("Object count exceeds safety limit")
    metadata=next((p for p in ordered if isinstance(p.get("scanStats"),dict)),None)
    if metadata is None: fail("Missing scan metadata")
    expected=metadata["scanStats"].get("recorded")
    if expected is None: expected=metadata["scanStats"].get("recordedObjects")
    if expected is not None and expected!=len(objects):
        fail(f"Object count mismatch: expected {expected}, received {len(objects)}")
    history=[]
    for p in ordered:
        history.extend(p.get("interactionHistoryChunk") or [])
    if not history:
        history=(metadata.get("interactionDiagnostics") or {}).get("recentInteractions") or []
    if len(history)>2000: fail("Interaction history exceeds 2000 events; refusing silent truncation")
    if any(not isinstance(event,dict) for event in history): fail("Malformed interaction history event")
    history_evidence=[(event,_correlation_evidence(event)) for event in history]
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
    if any(not o.get("path") for o in objects): fail("Object missing path")
    duplicate_count=sum(v-1 for v in paths.values())
    if duplicate_count:
        fail(f"Duplicate object identities: {duplicate_count}")
    features=[]
    for name in sorted(feature_names):
        event_records=[record for record in history_evidence if record[0].get("featureCandidate")==name]
        events=[record[0] for record in event_records]
        correlations=[record[1] for record in event_records]
        observed=sum(1 for e in events if e.get("evidenceLevel"))
        corroborated=sum(1 for e in events if e.get("clientStateCorroborated") is True
            or (isinstance(e.get("featureStateEvidence"),dict)
                and e["featureStateEvidence"].get("status")=="client-state-consistent"))
        transitions=sum(1 for e in events if e.get("stateChanges") or e.get("guiStateChanges"))
        outcomes=sum(1 for e in events if e.get("outcomeVerified") is True)
        candidates=sum(item["candidate"] for item in correlations)
        state_correlations=sum(item["state"] for item in correlations)
        gui_correlations=sum(item["gui"] for item in correlations)
        features.append({
            "feature":name,"interactionEvents":len(events),
            "observedEvents":observed,"verifiedClientOutcomes":outcomes,
            "clientCorroboratedEvents":corroborated,"temporalTransitionEvents":transitions,
            "observableOutcomeCandidates":candidates,
            "featureStateCorrelations":state_correlations,"featureGuiCorrelations":gui_correlations,
            "status":"client-outcome-observed" if outcomes else
                ("observable-outcome-candidate-unverified" if candidates else
                 ("interaction-observed" if observed else "discovered")),
            "implementationReady":False,
            "reason":"No verified, permitted reproducible implementation contract in passive scan",
            "evidence":feature_evidence.get(name) if isinstance(feature_evidence,dict) else None,
            "readiness":readiness.get(name) if isinstance(readiness,dict) else None,
        })
    source_diagnostics=metadata.get("diagnostics") or {}
    if source_diagnostics and source_diagnostics.get("complete") is False:
        fail("Source diagnostics indicate incomplete scan")
    integrity={"scanId":scan_id,"placeId":place_id,"parts":count,"objects":len(objects),
               "uniqueObjectIdentities":len(paths),"interactionEvents":len(history),
               "scanComplete":bool(metadata["scanStats"].get("complete"))}
    if not integrity["scanComplete"]: fail("Source scan reports incomplete root coverage")
    plan={"schemaVersion":"20.0","integrity":integrity,"featureCount":len(features),
          "features":features,"classCounts":dict(counts),
          "sourceDiagnostics":{"omittedObjects":metadata["scanStats"].get("omitted"),
              "rootAccountingValid":source_diagnostics.get("rootAccountingValid"),
              "scanMode":metadata["scanStats"].get("mode"),
              "snapshotId":metadata.get("snapshotId")},
          "interactionDiagnostics":metadata.get("interactionDiagnostics") or {},
          "observedInteractionHistory":history,
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
