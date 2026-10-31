#!/usr/bin/env python3
"""Lycoles v10 one-command offline pipeline: scan -> plan -> Lua -> release ZIP.

Usage: python3 tools/build_release.py ./scan-parts --output ./build
No remote execution, network access, GitHub credentials or third-party modules.
"""
import argparse
import hashlib
import importlib.util
import json
import pathlib
import re
import sys
import zipfile

ROOT=pathlib.Path(__file__).resolve().parents[1]

def load_module(filename,name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"tools"/filename)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def sha(data):
    return hashlib.sha256(data).hexdigest()

def validate_lua(lua,place_id):
    """Conservative generated-source guard, not a full Luau parser."""
    if not isinstance(lua,str) or len(lua)>1_000_000:
        raise ValueError("Generated Lua missing or oversized")
    if f"assert(game.PlaceId == {place_id}" not in lua:
        raise ValueError("Missing place guard")
    required=('local Players = game:GetService("Players")',
              'LycolesGeneratedClose','gui:Destroy()',
              'button("Stats"','button("Menus"','button("Prompts"','button("Features"')
    for token in required:
        if token not in lua: raise ValueError("Missing generated component: "+token)
    # These must not appear in a diagnostic-only build, including comments.
    banned=("FireServer(", "InvokeServer(", "getrawmetatable(",
            "hookmetamethod(", "loadstring(", "setclipboard(")
    for pattern in banned:
        if pattern.lower() in lua.lower(): raise ValueError("Forbidden generated operation: "+pattern)
    if lua.count('button("')!=4:
        raise ValueError("Unexpected number of generated controls")
    return {"placeGuard":True,"expectedControls":4,"unsafeOperationsFound":False,
            "note":"Structural checks only; Luau syntax and runtime behaviour are not verified"}

def build(parts_dir,output):
    compiler=load_module("compile_scan.py","lycoles_compiler")
    generator=load_module("generate_script.py","lycoles_generator")
    workflows_compiler=load_module("compile_workflows.py","lycoles_workflows")
    plan=compiler.compile_scan(parts_dir)
    place=generator.validate(plan)
    workflows=workflows_compiler.compile_workflows(plan)
    lua=generator.render(plan)
    validation=validate_lua(lua,place)
    output=pathlib.Path(output)
    output.mkdir(parents=True,exist_ok=True)
    manifest={
        "schemaVersion":"14.0","placeId":place,"scanId":plan["integrity"]["scanId"],
        "sourceFeatureCandidates":len(plan["features"]),
        "workflowEvidenceSummary":workflows["summary"],
        "implementedClientControls":["Stats","Menus","Prompts","Features"],
        "implementedGameplayAutomation":[],
        "validation":validation,
        "runtimeVerified":False,
        "releaseStatus":"GENERATED_STATIC_CHECKED_NOT_LIVE_TESTED",
        "generatedLuaSHA256":sha(lua.encode("utf-8"))
    }
    files={
      "capability-plan.json":(json.dumps(plan,indent=2,sort_keys=True)+"\n").encode(),
      "workflow-specs.json":(json.dumps(workflows,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode(),
      "implementation-review.md":(workflows_compiler.render_review(workflows)+"\n").encode("utf-8"),
      "LycolesGeneratedUtility.lua":lua.encode(),
      "release-manifest.json":(json.dumps(manifest,indent=2,sort_keys=True)+"\n").encode(),
      "README.txt":(
          "Lycoles generated utility for Roblox place "+str(place)+"\n"
          "This release contains client-side diagnostics only.\n"
          "It has not been runtime-tested. Do not describe gameplay automation as implemented.\n"
      ).encode()
    }
    for name,contents in files.items():
        (output/name).write_bytes(contents)
    bundle=output/("Lycoles-"+str(place)+"-"+plan["integrity"]["scanId"]+".zip")
    with zipfile.ZipFile(bundle,"w",compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info=zipfile.ZipInfo(name,date_time=(2020,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o644<<16
            archive.writestr(info,files[name])
    print("PASS: generated static-checked release bundle",bundle)
    return manifest

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parts_dir");parser.add_argument("--output",default="build")
    args=parser.parse_args()
    try: build(args.parts_dir,args.output);return 0
    except (ValueError,TypeError,KeyError,OSError,json.JSONDecodeError) as exc:
        print("BUILD BLOCKED:",exc,file=sys.stderr);return 2

if __name__=="__main__":sys.exit(main())
