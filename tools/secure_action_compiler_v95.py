#!/usr/bin/env python3
"""v95 secure Studio compiler: deny-by-default authorisation and release audit.

Generates client/server code for a Roblox experience the developer controls.
No executor, arbitrary remote access, or third-party game integration.
"""
import argparse
import hashlib
import json
from pathlib import Path
from authorized_action_compiler_v94 import validate as validate_v94, compile_server, compile_client

def validate(spec):
    if not isinstance(spec,dict) or spec.get("schemaVersion")!="95.actions":
        raise ValueError("expected 95.actions")
    ids=spec.get("authorizedUserIds")
    if not isinstance(ids,list) or not 1<=len(ids)<=100:
        raise ValueError("authorizedUserIds must contain 1-100 user IDs")
    if any(type(n)!=int or n<=0 or n>9223372036854775807 for n in ids):
        raise ValueError("invalid authorized user ID")
    if len(set(ids))!=len(ids):
        raise ValueError("duplicate authorized user ID")
    if spec.get("enabled") is not True:
        raise ValueError("explicit enabled=true required")
    legacy={k:v for k,v in spec.items() if k not in ("authorizedUserIds","enabled")}
    legacy["schemaVersion"]="94.actions"
    validate_v94(legacy)
    return legacy

def compile_secure_server(spec):
    legacy=validate(spec)
    server=compile_server(legacy)
    needle="local lastUsed = {}"
    if server.count(needle)!=1:
        raise RuntimeError("v94 server template changed: lastUsed marker")
    ids=", ".join("["+str(n)+"] = true" for n in spec["authorizedUserIds"])
    server=server.replace(needle,
        "local authorizedUserIds = { "+ids+" }\n"+needle,1)
    needle="remote.OnServerEvent:Connect(function(player, actionId)"
    if server.count(needle)!=1:
        raise RuntimeError("v94 server template changed: handler marker")
    server=server.replace(needle,needle+
        "\n if not authorizedUserIds[player.UserId] then return end",1)
    return server.replace("-- v94:","-- v95: secure allowlisted compiler; v94 template")

def compile_secure_client(spec):
    legacy=validate(spec)
    client=compile_client(legacy)
    needle="local player = Players.LocalPlayer"
    if client.count(needle)!=1:
        raise RuntimeError("v94 client template changed")
    ids=", ".join("["+str(n)+"] = true" for n in spec["authorizedUserIds"])
    client=client.replace(needle,needle+
        "\nlocal authorizedUserIds = { "+ids+" }"+
        "\nif not authorizedUserIds[player.UserId] then return end",1)
    return client.replace("-- v94:","-- v95: secure allowlisted compiler; v94 template")

def generate(spec,output):
    validate(spec)
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    artifacts={
        "LycolesActionsV95.server.lua":compile_secure_server(spec).encode("utf-8"),
        "LycolesActionsV95.client.lua":compile_secure_client(spec).encode("utf-8"),
        "actions-v95.json":json.dumps(spec,sort_keys=True,indent=2,ensure_ascii=False).encode("utf-8"),
    }
    hashes={}
    for name,data in artifacts.items():
        (output/name).write_bytes(data)
        hashes[name]=hashlib.sha256(data).hexdigest()
    manifest={"schemaVersion":"95.manifest","placeId":spec["placeId"],
        "authorizedUserCount":len(spec["authorizedUserIds"]),
        "files":hashes,"requiresStudioInstallation":True,
        "verifiedInGame":False,"generatedActionCount":len(spec["actions"])}
    (output/"manifest-v95.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    return manifest

def audit(output):
    root=Path(output)
    manifest=json.loads((root/"manifest-v95.json").read_text(encoding="utf-8"))
    problems=[]
    if manifest.get("schemaVersion")!="95.manifest" or manifest.get("verifiedInGame") is not False:
        problems.append("invalid_manifest")
    files=manifest.get("files")
    if not isinstance(files,dict) or set(files)!={"LycolesActionsV95.server.lua","LycolesActionsV95.client.lua","actions-v95.json"}:
        problems.append("unexpected_file_manifest")
    else:
        for name,digest in files.items():
            path=root/name
            if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                problems.append("hash_mismatch:"+name)
        if not problems:
            spec=json.loads((root/"actions-v95.json").read_text(encoding="utf-8"))
            try:
                if (root/"LycolesActionsV95.server.lua").read_text(encoding="utf-8")!=compile_secure_server(spec):
                    problems.append("server_not_reproducible")
                if (root/"LycolesActionsV95.client.lua").read_text(encoding="utf-8")!=compile_secure_client(spec):
                    problems.append("client_not_reproducible")
                if spec["placeId"]!=manifest.get("placeId"):
                    problems.append("place_mismatch")
            except (ValueError,KeyError,TypeError):
                problems.append("invalid_action_spec")
    return {"schemaVersion":"95.audit","ok":not problems,"issues":problems,
        "verifiedInGame":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--spec",type=Path)
    p.add_argument("--output",type=Path,default=Path("build/release-v95"))
    p.add_argument("--audit-only",action="store_true")
    a=p.parse_args()
    if not a.audit_only:
        if a.spec is None:
            p.error("--spec is required unless --audit-only is used")
        spec=json.loads(a.spec.read_text(encoding="utf-8-sig"))
        print(json.dumps(generate(spec,a.output)))
    result=audit(a.output)
    print(json.dumps(result))
    if not result["ok"]:
        raise SystemExit(1)
if __name__=="__main__":
    main()
