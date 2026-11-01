#!/usr/bin/env python3
"""v93 release auditor: fail-closed verification of generated evidence artifacts.

Checks integrity, provenance, safe claims, and the generated Luau surface.
This is static verification, not an in-game execution test.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

KNOWN = {
    "90":("manifest-v90.json","outputs"),
    "91":("manifest-v91.json","outputs"),
    "92":("manifest-v92.json","files"),
}
FORBIDDEN = (
    "FireServer", "InvokeServer", "VirtualInputManager",
    "VirtualUser", "getrawmetatable", "hookmetamethod",
    "setreadonly", "loadstring(", "HttpGet(", ":Activate()",
)

def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def audit(directory, version="92", expected_place=None):
    root=Path(directory)
    if version not in KNOWN:
        raise ValueError("unsupported version")
    manifest_name,hash_field=KNOWN[version]
    issues=[]
    checked=[]
    manifest_path=root/manifest_name
    if not manifest_path.is_file():
        return {"ok":False,"version":version,"checked":[],"issues":["missing_manifest"]}
    try:
        manifest=_read_json(manifest_path)
    except (ValueError,UnicodeError):
        return {"ok":False,"version":version,"checked":[],"issues":["invalid_manifest_json"]}
    if not isinstance(manifest,dict):
        return {"ok":False,"version":version,"checked":[],"issues":["invalid_manifest_shape"]}
    hashes=manifest.get(hash_field)
    if not isinstance(hashes,dict) or not hashes:
        issues.append("missing_hashes")
        hashes={}
    if expected_place is not None and manifest.get("placeId")!=expected_place:
        issues.append("place_mismatch")
    if manifest.get("verifiedInGame") is not False:
        issues.append("unsubstantiated_game_verification")
    if manifest.get("automaticallyGeneratedExecutableActions",0)!=0:
        issues.append("unsubstantiated_executable_action")
    for name,expected in sorted(hashes.items()):
        if not isinstance(name,str) or not re.fullmatch(r"[A-Za-z0-9_.-]+",name) or name.startswith("."):
            issues.append("invalid_artifact_name")
            continue
        if not isinstance(expected,str) or not re.fullmatch(r"[0-9a-f]{64}",expected):
            issues.append("invalid_sha256:"+name)
            continue
        path=root/name
        if not path.is_file() or path.is_symlink():
            issues.append("missing_or_symlink_artifact:"+name)
            continue
        payload=path.read_bytes()
        if hashlib.sha256(payload).hexdigest()!=expected:
            issues.append("hash_mismatch:"+name)
            continue
        checked.append(name)
        if name.endswith(".json"):
            try:
                data=json.loads(payload)
            except (ValueError,UnicodeError):
                issues.append("invalid_json:"+name)
                continue
            if isinstance(data,dict):
                if data.get("verifiedInGame") is True:
                    issues.append("unsubstantiated_verification:"+name)
                for field in ("contracts","candidates","items"):
                    records=data.get(field,[])
                    if not isinstance(records,list):
                        issues.append("invalid_records:"+name)
                        continue
                    for record in records:
                        if not isinstance(record,dict):
                            issues.append("invalid_record:"+name)
                            break
                        if record.get("approved") is True or record.get("executionEnabled") is True:
                            issues.append("unapproved_execution:"+name)
                            break
        elif name.endswith(".luau"):
            try:
                script=payload.decode("utf-8")
            except UnicodeError:
                issues.append("invalid_luau_utf8:"+name)
                continue
            for forbidden in FORBIDDEN:
                if forbidden in script:
                    issues.append("forbidden_api:"+name+":"+forbidden)
            if "game.PlaceId" not in script:
                issues.append("missing_place_guard:"+name)
    if version=="92":
        for required in ("review-v92.json","implementation-backlog-v92.json","diagnostics-v92.luau"):
            if required not in checked:
                issues.append("missing_required:"+required)
    return {"schemaVersion":"93.audit","version":version,"placeId":manifest.get("placeId"),
            "ok":not issues,"checked":checked,"issues":sorted(set(issues)),
            "verifiedInGame":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directory",type=Path,required=True)
    p.add_argument("--version",choices=tuple(KNOWN),default="92")
    p.add_argument("--place-id",type=int)
    p.add_argument("--report",type=Path)
    args=p.parse_args()
    result=audit(args.directory,args.version,args.place_id)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(result))
    raise SystemExit(0 if result["ok"] else 1)
if __name__=="__main__":
    main()
