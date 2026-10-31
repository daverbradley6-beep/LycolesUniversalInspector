#!/usr/bin/env python3
"""Lycoles v32 offline feature intelligence and provenance-aware matching.

Static analysis only. Never executes or downloads scripts, invokes game remotes,
or asserts server-side effects. No third-party dependencies.
"""
import argparse
import hashlib
import json
import pathlib
import re
from collections import Counter

VERSION="32.0"
MAX_BYTES=4_000_000
MAX_FILES=1000
MAX_FEATURES=10000
MAX_STRINGS=2000
FUNCTION=re.compile(r"(?m)^\s*(?:local\s+)?function\s+([A-Za-z_][\w.:]*)\s*\(|(?m:^\s*(?:local\s+)?([A-Za-z_]\w*)\s*=\s*function\s*\()")
CONNECTION=re.compile(r"([A-Za-z_]\w*(?:\.[A-Za-z_]\w*){0,5})\s*:\s*Connect\s*\(")
PATHS=re.compile(r"(?:game|workspace|Workspace|ReplicatedStorage|PlayerGui|Players|script)(?:\.[A-Za-z_]\w*){1,9}")
LOOKUP=re.compile(r":(?:WaitForChild|FindFirstChild)\s*\(\s*['\x22]([^'\x22\r\n]{1,100})['\x22]")
SERVICE=re.compile(r"game:GetService\s*\(\s*['\x22]([A-Za-z_]\w*)['\x22]\s*\)")
STRING=re.compile(r"['\x22]([A-Za-z_][\w \-]{1,70})['\x22]")
DANGEROUS=re.compile(r"\b(?:FireServer|InvokeServer|hookmetamethod|getrawmetatable|sethiddenproperty)\b")
STATE=re.compile(r"\b(?:Value|GetAttribute|FindFirstChild|WaitForChild|GetChildren|GetDescendants)\b")
GUI=re.compile(r"\b(?:MouseButton1Click|Activated|InputBegan|GuiButton|ScreenGui|TextButton)\b")
LIFECYCLE=re.compile(r"\b(?:Disconnect|Destroy|CharacterAdded|AncestryChanged)\b")
IDENTITY=re.compile(r"\b(?:PlaceId|GameId)\s*==\s*(\d{3,20})")
CATEGORY={
    "cashier":("cashier","burger","register","customer","order"),
    "hairdresser":("hairdresser","hairstyle","haircolor","haircolour","salon"),
    "inventory":("inventory","backpack","item","equip","unequip"),
    "navigation":("teleport","waypoint","location","destination"),
    "interface":("button","toggle","window","gui","menu"),
    "character":("character","humanoid","respawn","health"),
}
def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
def unique(items,limit=80):
    return sorted(set(items))[:limit]
def feature(name,body,start,filename,filehash):
    paths=unique(PATHS.findall(body))
    lookups=unique(LOOKUP.findall(body))
    services=unique(SERVICE.findall(body))
    calls=Counter(x for x in ("FireServer","InvokeServer","GetAttribute","FindFirstChild","WaitForChild","Destroy","Disconnect") if x in body)
    signal={"stateRead":len(STATE.findall(body)),"gui":len(GUI.findall(body)),
            "lifecycle":len(LIFECYCLE.findall(body)),"remote":len(DANGEROUS.findall(body))}
    words=(name+" "+" ".join(paths)+" "+" ".join(lookups)).lower()
    categories=sorted(k for k,terms in CATEGORY.items() if any(t in words for t in terms))
    return {"id":sha(filename+"\0"+filehash+"\0"+name+"\0"+str(start))[:20],
            "sourceFile":filename,"sourceSha256":filehash,"name":name,
            "line":start,"categories":categories,"dependencies":{"paths":paths,"lookups":lookups,"services":services},
            "signals":signal,"operations":dict(calls),
            "confidence":"source-pattern-only","reviewStatus":"unreviewed",
            "clientRuntimeVerified":False,"serverOutcomeVerified":False}
def extract(filename,source,filehash=None):
    if not isinstance(source,str):raise ValueError("Source must be text")
    if len(source.encode("utf-8"))>MAX_BYTES:raise ValueError("Source too large")
    filehash=filehash or sha(source)
    if any(x in source[:12000].lower() for x in ("luraph obfuscator","moonsec v3","ironbrew")):
        return {"sourceFile":filename,"sourceSha256":filehash,"classification":"opaque",
                "features":[],"limitations":["Protected source cannot be analysed reliably"]}
    matches=list(FUNCTION.finditer(source))
    features=[]
    for i,m in enumerate(matches[:MAX_FEATURES]):
        name=m.group(1) or m.group(2)
        end=matches[i+1].start() if i+1<len(matches) else len(source)
        # Approximate lexical span: a conservative slice, NOT a Luau AST.
        body=source[m.start():min(end,m.start()+12000)]
        line=source.count("\n",0,m.start())+1
        features.append(feature(name,body,line,filename,filehash))
    if not features and source.strip():
        features=[feature("<top-level>",source[:12000],1,filename,filehash)]
    return {"sourceFile":filename,"sourceSha256":filehash,
            "classification":"function-patterns" if matches else "top-level",
            "features":features,"limitations":["Regex spans are approximate, not parsed function bodies"]}
def analyze_directory(directory):
    root=pathlib.Path(directory)
    if not root.is_dir():raise ValueError("Source directory not found")
    paths=sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in (".lua",".luau",".txt"))
    if len(paths)>MAX_FILES:raise ValueError("Too many files")
    sources=[];all_features=[];errors=[]
    for path in paths:
        try:
            if path.stat().st_size>MAX_BYTES:raise ValueError("File exceeds size limit")
            source=path.read_text(encoding="utf-8",errors="replace")
            record=extract(path.relative_to(root).as_posix(),source)
            sources.append({k:v for k,v in record.items() if k!="features"})
            all_features.extend(record["features"])
        except (OSError,ValueError) as e:errors.append({"file":path.name,"error":str(e)[:150]})
    if len(all_features)>MAX_FEATURES:raise ValueError("Too many features")
    return {"schemaVersion":VERSION,"source":"offline-feature-intelligence",
            "summary":{"sourceFiles":len(sources),"features":len(all_features),"errors":len(errors)},
            "sources":sources,"features":all_features,"errors":errors,
            "verification":{"executed":False,"gameplayConfirmed":False}}
def match_inspection(report,inspection):
    """Match only explicit observed paths/instance names. No fuzzy guesses."""
    if report.get("schemaVersion")!=VERSION:raise ValueError("Invalid feature report")
    if not isinstance(inspection,dict):raise ValueError("Inspection must be JSON object")
    place=inspection.get("placeId")
    scan=inspection.get("scanId")
    if type(place) is not int or place<=0 or not isinstance(scan,str) or not scan:
        raise ValueError("Inspection requires placeId and scanId")
    objects=inspection.get("objects")
    if not isinstance(objects,list) or len(objects)>200000:raise ValueError("Invalid inspection objects")
    observed_paths=set();observed_names=set()
    for obj in objects:
        if not isinstance(obj,dict):continue
        p=obj.get("path");n=obj.get("name")
        if isinstance(p,str):observed_paths.add(p)
        if isinstance(n,str):observed_names.add(n)
    results=[]
    for f in report.get("features",[]):
        dep=f["dependencies"]
        paths=dep["paths"];names=dep["lookups"]
        found_paths=[p for p in paths if p in observed_paths]
        found_names=[n for n in names if n in observed_names]
        missing_paths=[p for p in paths if p not in observed_paths]
        missing_names=[n for n in names if n not in observed_names]
        status="no-dependencies" if not paths and not names else (
            "all-observed" if not missing_paths and not missing_names else
            "partial" if found_paths or found_names else "none-observed")
        results.append({"featureId":f["id"],"featureName":f["name"],"status":status,
                        "foundPaths":found_paths,"foundNames":found_names,
                        "missingPaths":missing_paths,"missingNames":missing_names,
                        "runtimeVerified":False,"gameplayConfirmed":False})
    return {"schemaVersion":VERSION,"source":"offline-inspection-match",
            "placeId":place,"scanId":scan,"matches":results,
            "warning":"Exact name matches are weak evidence; path format may differ. Match is not execution or success."}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("source_dir",type=pathlib.Path)
    p.add_argument("--output",type=pathlib.Path,default=pathlib.Path("build/feature-intelligence.json"))
    p.add_argument("--inspection",type=pathlib.Path,help="Optional JSON with placeId, scanId, objects [{path,name}]")
    p.add_argument("--match-output",type=pathlib.Path,default=pathlib.Path("build/feature-inspection-match.json"))
    a=p.parse_args()
    report=analyze_directory(a.source_dir)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("Analysed",report["summary"]["sourceFiles"],"files;",report["summary"]["features"],"feature candidates;",report["summary"]["errors"],"errors")
    if a.inspection:
        inspection=json.loads(a.inspection.read_text(encoding="utf-8"))
        result=match_inspection(report,inspection)
        a.match_output.parent.mkdir(parents=True,exist_ok=True)
        a.match_output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print("Matched",len(result["matches"]),"feature candidates against inspection",result["scanId"])
    return 2 if report["errors"] else 0
if __name__=="__main__":
    raise SystemExit(main())
