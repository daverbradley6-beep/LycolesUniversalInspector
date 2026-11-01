#!/usr/bin/env python3
"""v68 universal evidence reconciliation: canonical paths, multi-session telemetry, audit.
Read-only: no remote invocation, exploit bypass, or unverified action generation.
"""
import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from evidence_pipeline_v62 import import_console, catalog
from live_telemetry_v66 import parse_log

MAX_BYTES=50_000_000
MAX_SESSIONS=100
SEGMENT=re.compile(r'"((?:\\\\.|[^"\\\\])*)"#\\d+@([A-Za-z][A-Za-z0-9]*)')
MARKER=re.compile(r'LYCOLES_V66_HEADER\\s+')
END=re.compile(r'LYCOLES_V66_END\\s+\\d+')

def repair_encoding(value):
    # Repair console mojibake only when it round-trips cleanly.
    if not any(c in value for c in ("ð","Ã","â")):
        return value
    try:
        fixed=value.encode("latin-1").decode("utf-8")
        return fixed if fixed else value
    except (UnicodeError,ValueError):
        return value

def canonical(path):
    """Convert v54 typed instance segments or v66 GetFullName into comparable names."""
    if not isinstance(path,str) or len(path)>10000:
        return ""
    if '/"' in path:
        parts=path.split("/")
        out=[parts[0]]
        for part in parts[1:]:
            m=SEGMENT.fullmatch(part)
            if not m:
                return ""
            try:
                name=json.loads('"'+m.group(1)+'"')
            except (ValueError,TypeError):
                return ""
            out.append(name)
    else:
        # v66 uses dot-separated GetFullName, which can be ambiguous if names contain dots.
        out=path.split(".")
    return ".".join(repair_encoding(x).casefold() for x in out if x)

def telemetry_sessions(text, place_id):
    """Isolate exports; select last independently validated, complete session."""
    lines=text.splitlines()
    starts=[i for i,line in enumerate(lines) if MARKER.search(line)]
    if len(starts)>MAX_SESSIONS:
        raise ValueError("too many telemetry sessions")
    candidates=[]
    for index,start in enumerate(starts):
        stop=starts[index+1] if index+1<len(starts) else len(lines)
        block=lines[start:stop]
        ends=[j for j,line in enumerate(block) if END.search(line)]
        if not ends:
            candidates.append({"index":index+1,"valid":False,"reason":"missing end"})
            continue
        raw="\\n".join(block[:ends[-1]+1])
        try:
            parsed=parse_log(raw,place_id)
            if not parsed["complete"]:
                raise ValueError("incomplete session")
            candidates.append({"index":index+1,"valid":True,"events":len(parsed["events"])})
            candidates[-1]["_data"]=parsed
        except (ValueError,KeyError,TypeError,IndexError) as exc:
            candidates.append({"index":index+1,"valid":False,"reason":str(exc)[:160]})
    valid=[x for x in candidates if x["valid"]]
    if not valid:
        raise ValueError("no valid complete telemetry session; "+str([{k:v for k,v in x.items() if k!="_data"} for x in candidates])[:500])
    chosen=valid[-1]
    return chosen["_data"], {"sessionsFound":len(candidates),
        "selectedSession":chosen["index"],
        "validSessions":len(valid),
        "rejectedSessions":[{k:v for k,v in x.items() if k!="_data"} for x in candidates if not x["valid"]]}

def reconcile(discovery_text,telemetry_text,place_id):
    if type(place_id) is not int or place_id<=0:
        raise ValueError("positive place ID required")
    receipt=import_console(discovery_text)
    if receipt["placeId"] is not None and receipt["placeId"]!=place_id:
        raise ValueError("discovery place ID mismatch")
    if not receipt["samples"]:
        raise ValueError("no recoverable discovery batches")
    cat=catalog(receipt)
    telemetry,session_info=telemetry_sessions(telemetry_text,place_id)
    by_path=defaultdict(list)
    for item in cat["capabilities"]:
        key=canonical(item["path"])
        if key:
            by_path[key].append(item)
    matches=[]; unmatched=[]; ambiguous=[]
    for event in telemetry["events"]:
        key=canonical(event.get("path"))
        candidates=by_path.get(key,[])
        entry={"path":event["path"],"canonicalPath":key,"tick":event["tick"],
               "kind":event["kind"],"before":event["before"],"after":event["after"]}
        if len(candidates)==1:
            matches.append({**entry,"discoveryPath":candidates[0]["path"],
                            "matchType":"canonical_exact","confidence":"structural_only",
                            "actionVerified":False,"causalityVerified":False})
        elif len(candidates)>1:
            ambiguous.append({**entry,"candidatePaths":[x["path"] for x in candidates[:20]]})
        else:
            unmatched.append(entry)
    missing=receipt["missing"]
    manifest={"schemaVersion":"68.release","placeId":place_id,
       "discoveryPlaceIdSource":"stream_header" if receipt["placeId"] is not None else "cli_unverified",
       "sourceHashes":{"discoverySha256":hashlib.sha256(discovery_text.encode()).hexdigest(),
                       "telemetrySha256":hashlib.sha256(telemetry_text.encode()).hexdigest()},
       "discovery":{"samples":len(receipt["samples"]),"complete":cat["sourceComplete"],
                    "missing":missing,"recoveredPartialBatches":receipt.get("recoveredPartialBatches",0),
                    "cataloguedCapabilities":len(cat["capabilities"])},
       "telemetry":{**session_info,"selectedEvents":len(telemetry["events"])},
       "correlation":{"matchedEvents":len(matches),"unmatchedEvents":len(unmatched),
                      "ambiguousEvents":len(ambiguous),
                      "matchKinds":dict(Counter(x["kind"] for x in matches))},
       "gates":{"discoveryPlaceIdVerified":receipt["placeId"] is not None,
                "discoveryComplete":cat["sourceComplete"],
                "telemetryComplete":telemetry["complete"],
                "allEventsMatched":not unmatched and not ambiguous and bool(matches),
                "executableActionsVerified":False},
       "readyForActionGeneration":False,
       "reason":"Object correlation and passive stat changes do not verify an action contract"}
    return {"manifest":manifest,"matches":matches,"unmatched":unmatched,"ambiguous":ambiguous,
            "catalog":cat}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--discovery",type=Path,required=True)
    p.add_argument("--telemetry",type=Path,required=True)
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--output",type=Path,default=Path("build/release-v68"))
    a=p.parse_args()
    for path in (a.discovery,a.telemetry):
        if not path.is_file(): p.error(f"missing input file: {path}")
        if path.stat().st_size>MAX_BYTES: p.error(f"input too large: {path}")
    result=reconcile(a.discovery.read_text(encoding="utf-8-sig",errors="replace"),
                     a.telemetry.read_text(encoding="utf-8-sig",errors="replace"),a.place_id)
    a.output.mkdir(parents=True,exist_ok=True)
    for key,filename in (("manifest","release-manifest-v68.json"),("matches","matches-v68.json"),
                         ("unmatched","unmatched-v68.json"),("ambiguous","ambiguous-v68.json"),
                         ("catalog","catalog-v68.json")):
        (a.output/filename).write_text(json.dumps(result[key],ensure_ascii=False,indent=2)+"\\n",encoding="utf-8")
    print(json.dumps(result["manifest"],ensure_ascii=False,indent=2))
if __name__=="__main__": main()
