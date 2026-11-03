#!/usr/bin/env python3
"""Lycoles v8 offline scan compiler: multipart integrity -> feature evidence -> release plan.
No third-party packages, Roblox credentials, or game-specific hardcoding required.
Usage: python3 tools/compile_scan.py scan-parts-dir --output build
"""
import argparse, collections, hashlib, json, pathlib, sys, unicodedata

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

_RECEIVER_PROVENANCE_FIELDS={
    "schemaVersion","scanId","placeId","partCount","expectedParts","objectCount",
    "metadata","receiverIntegrity","receiverPartContentDigests",
    "resumableRetrievalEnabled","resumedPartCount","downloadedPartCount",
    "resumeCheckpointAuthenticated","receiverStoredPayloadDigestsRevalidatedThisRun",
    "receiverStoredPayloadDigestsVerified","receiverAcknowledgementDigestEquivalent",
    "receiverIntegrityVerified","receiverResponseAuthenticityVerified",
    "localPayloadEquivalent","note",
}
_LEGACY_RECEIVER_PROVENANCE_FIELDS={
    "schemaVersion","scanId","placeId","partCount","expectedParts","objectCount",
    "metadata","receiverIntegrity","receiverReportedIntegrity",
    "retrievedPartContentDigests","resumableRetrievalEnabled","resumedPartCount",
    "downloadedPartCount","resumeCheckpointAuthenticated",
    "receiverStoredPayloadDigestsRevalidatedThisRun",
    "receiverStoredPayloadDigestsVerified","receiverAcknowledgementDigestEquivalent",
    "receiverIntegrityVerified","receiverResponseAuthenticityVerified",
    "localPayloadEquivalent","note",
}

_RECEIVER_MARKERS={
    "receiverIntegrity","receiverPartContentDigests",
    "receiverStoredPayloadDigestsVerified","receiverIntegrityVerified",
    "receiverResponseAuthenticityVerified","localPayloadEquivalent",
}

def bounded_path_identity(value):
    if not isinstance(value,list) or not 1<=len(value)<=21:return None
    result=[]
    for segment in value:
        if not isinstance(segment,dict):return None
        name=segment.get("name");class_name=segment.get("className");ordinal=segment.get("ordinal")
        if (not isinstance(name,str) or not 1<=len(name)<=100 or not isinstance(class_name,str)
                or not 1<=len(class_name)<=100 or type(ordinal) is not int or not 1<=ordinal<=10000):return None
        result.append({"name":name,"className":class_name,"ordinal":ordinal})
    return result



def _local_source_provenance(scan_id,place_id,part_count):
    return {
        "schemaVersion":"30.2.source-provenance.1","inputMode":"local-multipart",
        "scanId":scan_id,"placeId":place_id,"partCount":part_count,
        "partContentDigests":[],"receiverStoredPayloadDigestsVerified":False,
        "receiverStoredPayloadDigestsRevalidatedThisRun":False,
        "receiverAcknowledgementDigestEquivalent":False,
        "receiverIntegrityVerified":False,"resumableRetrievalEnabled":False,
        "resumedPartCount":0,"downloadedPartCount":0,
        "resumeCheckpointAuthenticated":False,
        "receiverResponseAuthenticityVerified":False,"localPayloadEquivalent":False,
        "sourceAuthenticityVerified":False,"causalityProven":False,
        "serverAuthorityVerified":False,"replayable":False,
        "gameplayVerified":False,"actionOutcomesVerified":False,
    }


def _receiver_source_provenance(manifest,scan_id,place_id,part_count,
                                object_count,actual_digests):
    if set(manifest)!=_RECEIVER_PROVENANCE_FIELDS:
        fail("Invalid receiver provenance schema")
    if (manifest.get("schemaVersion")!="30.2.receiver-import.2"
            or manifest.get("scanId")!=scan_id or manifest.get("placeId")!=place_id
            or manifest.get("partCount")!=part_count
            or manifest.get("expectedParts")!=part_count
            or manifest.get("objectCount")!=object_count):
        fail("Invalid receiver provenance identity")
    metadata=manifest.get("metadata")
    if (not isinstance(metadata,dict) or metadata.get("scanId")!=scan_id
            or metadata.get("placeId")!=place_id or metadata.get("partCount")!=part_count):
        fail("Invalid receiver provenance metadata")
    integrity=manifest.get("receiverIntegrity")
    if (not isinstance(integrity,dict) or integrity.get("scanId")!=scan_id
            or integrity.get("placeId")!=place_id
            or integrity.get("partCount")!=part_count
            or integrity.get("receivedParts")!=part_count
            or integrity.get("missingParts")!=[]
            or integrity.get("indexedObjects")!=object_count
            or integrity.get("uniqueObjectKeys")!=object_count
            or integrity.get("duplicateObjectKeys")!=0
            or integrity.get("identityErrors")!=[]
            or integrity.get("expectedObjects")!=object_count
            or integrity.get("complete") is not True
            or integrity.get("integrityStatus")!="verified-after-retrieval"):
        fail("Invalid receiver provenance integrity")
    entries=manifest.get("receiverPartContentDigests")
    if not isinstance(entries,list) or len(entries)!=part_count:
        fail("Invalid receiver provenance digests")
    digests={}
    for entry in entries:
        if not isinstance(entry,dict) or set(entry)!={"partIndex","sha256"}:
            fail("Invalid receiver provenance digest")
        index=entry.get("partIndex"); digest=entry.get("sha256")
        if (type(index) is not int or not 1<=index<=part_count or index in digests
                or not isinstance(digest,str) or len(digest)!=64
                or any(character not in "0123456789abcdef" for character in digest)
                or actual_digests.get(index)!=digest):
            fail("Invalid receiver provenance digest")
        digests[index]=digest
    resumed=manifest.get("resumedPartCount")
    downloaded=manifest.get("downloadedPartCount")
    if (type(resumed) is not int or type(downloaded) is not int
            or resumed<0 or downloaded<0 or resumed+downloaded!=part_count
            or type(manifest.get("resumableRetrievalEnabled")) is not bool
            or (resumed>0 and manifest.get("resumableRetrievalEnabled") is not True)
            or manifest.get("resumeCheckpointAuthenticated") is not False
            or manifest.get("receiverStoredPayloadDigestsRevalidatedThisRun") is not (resumed==0)
            or manifest.get("receiverStoredPayloadDigestsVerified") is not True
            or type(manifest.get("receiverAcknowledgementDigestEquivalent")) is not bool
            or manifest.get("receiverIntegrityVerified") is not True
            or manifest.get("receiverResponseAuthenticityVerified") is not False
            or manifest.get("localPayloadEquivalent") is not False
            or not isinstance(manifest.get("note"),str)):
        fail("Invalid receiver provenance claims")
    result=_local_source_provenance(scan_id,place_id,part_count)
    result.update({
        "inputMode":"receiver-import",
        "partContentDigests":[{"partIndex":index,"sha256":digests[index]}
                              for index in range(1,part_count+1)],
        "receiverStoredPayloadDigestsVerified":True,
        "receiverStoredPayloadDigestsRevalidatedThisRun":resumed==0,
        "receiverAcknowledgementDigestEquivalent":manifest["receiverAcknowledgementDigestEquivalent"],
        "receiverIntegrityVerified":True,
        "resumableRetrievalEnabled":manifest["resumableRetrievalEnabled"],
        "resumedPartCount":resumed,"downloadedPartCount":downloaded,
    })
    return result


def _legacy_receiver_source_provenance(manifest,scan_id,place_id,part_count,
                                       object_count,actual_digests):
    if set(manifest)!=_LEGACY_RECEIVER_PROVENANCE_FIELDS:
        fail("Invalid legacy receiver provenance schema")
    if (manifest.get("schemaVersion")!="30.2.receiver-import-legacy.1"
            or manifest.get("scanId")!=scan_id or manifest.get("placeId")!=place_id
            or manifest.get("partCount")!=part_count
            or manifest.get("expectedParts")!=part_count
            or manifest.get("objectCount")!=object_count):
        fail("Invalid legacy receiver provenance identity")
    metadata=manifest.get("metadata")
    if (not isinstance(metadata,dict) or metadata.get("scanId")!=scan_id
            or metadata.get("placeId")!=place_id or metadata.get("partCount")!=part_count):
        fail("Invalid legacy receiver provenance metadata")
    for field,status in (("receiverIntegrity","verified-after-retrieval"),
                         ("receiverReportedIntegrity","verified")):
        integrity=manifest.get(field)
        if (not isinstance(integrity,dict) or integrity.get("scanId")!=scan_id
                or integrity.get("placeId")!=place_id
                or integrity.get("partCount")!=part_count
                or integrity.get("receivedParts")!=part_count
                or integrity.get("missingParts")!=[]
                or integrity.get("indexedObjects")!=object_count
                or integrity.get("uniqueObjectKeys")!=object_count
                or integrity.get("duplicateObjectKeys")!=0
                or integrity.get("identityErrors")!=[]
                or integrity.get("expectedObjects")!=object_count
                or integrity.get("complete") is not True
                or integrity.get("integrityStatus")!=status):
            fail("Invalid legacy receiver provenance integrity")
    entries=manifest.get("retrievedPartContentDigests")
    if not isinstance(entries,list) or len(entries)!=part_count:
        fail("Invalid legacy receiver provenance digests")
    digests={}
    for entry in entries:
        if not isinstance(entry,dict) or set(entry)!={"partIndex","sha256"}:
            fail("Invalid legacy receiver provenance digest")
        index=entry.get("partIndex");digest=entry.get("sha256")
        if (type(index) is not int or not 1<=index<=part_count or index in digests
                or not isinstance(digest,str) or len(digest)!=64
                or any(character not in "0123456789abcdef" for character in digest)
                or actual_digests.get(index)!=digest):
            fail("Invalid legacy receiver provenance digest")
        digests[index]=digest
    acknowledgement=manifest.get("receiverAcknowledgementDigestEquivalent")
    if (manifest.get("resumableRetrievalEnabled") is not False
            or manifest.get("resumedPartCount")!=0
            or manifest.get("downloadedPartCount")!=part_count
            or manifest.get("resumeCheckpointAuthenticated") is not False
            or manifest.get("receiverStoredPayloadDigestsRevalidatedThisRun") is not False
            or manifest.get("receiverStoredPayloadDigestsVerified") is not False
            or type(acknowledgement) is not bool
            or manifest.get("receiverIntegrityVerified") is not True
            or manifest.get("receiverResponseAuthenticityVerified") is not False
            or manifest.get("localPayloadEquivalent") is not False
            or not isinstance(manifest.get("note"),str)):
        fail("Invalid legacy receiver provenance claims")
    result=_local_source_provenance(scan_id,place_id,part_count)
    result.update({
        "inputMode":"receiver-import-legacy-v11",
        "partContentDigests":[{"partIndex":index,"sha256":digests[index]}
                              for index in range(1,part_count+1)],
        "receiverAcknowledgementDigestEquivalent":acknowledgement,
        "receiverIntegrityVerified":True,
        "downloadedPartCount":part_count,
    })
    return result



def compile_scan(directory):
    files=sorted(pathlib.Path(directory).glob("*.json"))
    if not files: fail("No JSON scan parts found")
    parts=[]
    part_file_digests=[]
    local_manifests=[]
    receiver_manifests=[]
    for file in files:
        raw=file.read_bytes()
        if len(raw)>3_000_000: fail(f"Part too large: {file.name}")
        data=json.loads(raw)
        if not isinstance(data,dict) or not isinstance(data.get("objects"),list):
            if isinstance(data,dict) and "partIndex" not in data and _RECEIVER_MARKERS & set(data):
                receiver_manifests.append(data)
                continue
            if isinstance(data,dict) and "partIndex" not in data and ("objectCount" in data or "metadata" in data):
                local_manifests.append(data)
                continue
            fail(f"Invalid part: {file.name}")
        parts.append(data)
        part_file_digests.append(hashlib.sha256(raw).hexdigest())
    if not parts: fail("No multipart payloads found")
    first=parts[0]
    scan_id=first.get("scanId"); place_id=first.get("placeId")
    count=first.get("partCount")
    if not isinstance(scan_id,str) or not isinstance(place_id,int) or not isinstance(count,int) or count<1 or count>2000:
        fail("Invalid scan identity")
    if len(receiver_manifests)>1:
        fail("Multiple receiver provenance manifests")

    for manifest in local_manifests:
        if ((manifest.get("scanId") is not None and manifest.get("scanId")!=scan_id)
                or (manifest.get("placeId") is not None and manifest.get("placeId")!=place_id)
                or (manifest.get("partCount") is not None and manifest.get("partCount")!=count)
                or (manifest.get("expectedParts") is not None and manifest.get("expectedParts")!=count)):
            fail("Local manifest identity mismatch")

    by_index={}
    for part,raw_digest in zip(parts,part_file_digests):
        index=part.get("partIndex")
        if part.get("scanId")!=scan_id or part.get("placeId")!=place_id or part.get("partCount")!=count:
            fail("Mixed scan IDs, place IDs, or part counts")
        if not isinstance(index,int) or not 1<=index<=count: fail("Invalid part index")
        fingerprint=hashlib.sha256(json.dumps(part,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        if index in by_index:
            if by_index[index][0]!=fingerprint: fail(f"Conflicting duplicate part {index}")
            continue
        by_index[index]=(fingerprint,part,raw_digest)
    missing=[i for i in range(1,count+1) if i not in by_index]
    if missing: fail(f"Missing parts: {missing[:30]} (total {len(missing)})")
    ordered=[by_index[i][1] for i in range(1,count+1)]
    actual_part_digests={i:by_index[i][2] for i in range(1,count+1)}
    if any(not isinstance(o,dict) for p in ordered for o in p["objects"]):
        fail("Malformed object record")
    objects=[o for p in ordered for o in p["objects"]]
    if len(objects)>2_000_000: fail("Object count exceeds safety limit")

    metadata=next((p for p in ordered if isinstance(p.get("scanStats"),dict)),None)
    if metadata is None: fail("Missing scan metadata")
    requested_capability=metadata.get("featureRequest")
    if requested_capability is not None:
        if (not isinstance(requested_capability,str) or not requested_capability
                or len(requested_capability.encode("utf-8"))>240
                or requested_capability!=requested_capability.strip()
                or any(unicodedata.category(character)=="Cc"
                       for character in requested_capability)):
            fail("Invalid feature request")

    expected=metadata["scanStats"].get("recorded")
    if expected is None: expected=metadata["scanStats"].get("recordedObjects")
    if expected is not None and expected!=len(objects):
        fail(f"Object count mismatch: expected {expected}, received {len(objects)}")
    if any(manifest.get("objectCount") is not None
           and manifest.get("objectCount")!=len(objects) for manifest in local_manifests):
        fail("Local manifest object count mismatch")
    history=[]
    for p in ordered:
        history.extend(p.get("interactionHistoryChunk") or [])
    if not history:
        history=(metadata.get("interactionDiagnostics") or {}).get("recentInteractions") or []
    if len(history)>2000: fail("Interaction history exceeds 2000 events; refusing silent truncation")
    if any(not isinstance(event,dict) for event in history): fail("Malformed interaction history event")
    for event in history:
        if "pathIdentity" in event:
            identity=bounded_path_identity(event["pathIdentity"])
            if (identity is None or not isinstance(event.get("path"),str)
                    or ".".join(segment["name"] for segment in identity)!=event["path"]):
                fail("Malformed interaction path identity")
            event["pathIdentity"]=identity
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
    actionable_classes={"ProximityPrompt","ClickDetector","TextButton","ImageButton","Tool"}
    actionable=[]
    actionable_total=0
    for obj in objects:
        if obj.get("class") not in actionable_classes:continue
        actionable_total+=1
        if len(actionable)>=20_000:continue
        actionable.append({key:obj[key] for key in (
            "path","class","scanOrdinal","interaction","guiControl","position","size","tool")
            if key in obj})
    duplicate_count=sum(v-1 for v in paths.values())
    if duplicate_count:
        fail(f"Duplicate object identities: {duplicate_count}")
    if receiver_manifests:
        receiver_manifest=receiver_manifests[0]
        if receiver_manifest.get("schemaVersion")=="30.2.receiver-import-legacy.1":
            source_provenance=_legacy_receiver_source_provenance(
                receiver_manifest,scan_id,place_id,count,len(objects),actual_part_digests)
        else:
            source_provenance=_receiver_source_provenance(
                receiver_manifest,scan_id,place_id,count,len(objects),actual_part_digests)
    else:
        source_provenance=_local_source_provenance(scan_id,place_id,count)

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
          "requestedCapability":requested_capability,
          "sourceProvenance":source_provenance,
          "sourceDiagnostics":{"omittedObjects":metadata["scanStats"].get("omitted"),
              "rootAccountingValid":source_diagnostics.get("rootAccountingValid"),
              "scanMode":metadata["scanStats"].get("mode"),
              "snapshotId":metadata.get("snapshotId")},
          "interactionDiagnostics":metadata.get("interactionDiagnostics") or {},
          "observedInteractionHistory":history,
          "actionableObjects":actionable,"actionableObjectCount":actionable_total,
          "actionableObjectsTruncated":actionable_total>len(actionable),
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
