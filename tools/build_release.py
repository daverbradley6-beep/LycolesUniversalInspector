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

def build(parts_dir,output,contracts_path=None,observation_dirs=None,feedback_path=None):
    compiler=load_module("compile_scan.py","lycoles_compiler")
    generator=load_module("generate_script.py","lycoles_generator")
    workflows_compiler=load_module("compile_workflows.py","lycoles_workflows")
    plan=compiler.compile_scan(parts_dir)
    if observation_dirs:
        merger=load_module('merge_observations.py','lycoles_merge')
        observations=[compiler.compile_scan(folder) for folder in observation_dirs]
        plan=merger.merge_evidence(plan,observations)
    place=generator.validate(plan)
    workflows=workflows_compiler.compile_workflows(plan)
    sequence_compiler=load_module("compile_interaction_sequences.py","lycoles_sequences")
    sequences=sequence_compiler.compile_sequences(plan)
    proposer=load_module("propose_actions.py","lycoles_proposals")
    proposals=proposer.propose(plan)
    verification_generator=load_module("generate_verification_harness.py","lycoles_verification")
    verification_plan,verification_lua=verification_generator.compile_verification(sequences)
    feedback=None
    if feedback_path is not None:
        feedback_evaluator=load_module("evaluate_runtime_feedback.py","lycoles_feedback")
        feedback_document=json.loads(pathlib.Path(feedback_path).read_text(encoding="utf-8"))
        feedback=feedback_evaluator.evaluate(verification_plan,feedback_document)
    backlog_compiler=load_module("compile_implementation_backlog.py","lycoles_backlog")
    backlog=backlog_compiler.compile_backlog(plan,sequences,feedback)
    validated_contracts=None
    if contracts_path is not None:
        validator=load_module('validate_contracts.py','lycoles_contracts')
        data=json.loads(pathlib.Path(contracts_path).read_text(encoding='utf-8'))
        validated_contracts=validator.validate_contracts(plan,data)
    client_actions_lua=None
    actions_gui_lua=None
    if validated_contracts is not None:
        action_generator=load_module("generate_client_actions.py","lycoles_client_actions")
        client_actions_lua=action_generator.render(validated_contracts)
        if validated_contracts["contracts"]:
            gui_generator=load_module("generate_actions_gui.py","lycoles_actions_gui")
            actions_gui_lua=gui_generator.render(validated_contracts)
    lua=generator.render(plan)
    validation=validate_lua(lua,place)
    output=pathlib.Path(output)
    output.mkdir(parents=True,exist_ok=True)
    manifest={
        "schemaVersion":"25.0","placeId":place,"scanId":plan["integrity"]["scanId"],
        "sourceFeatureCandidates":len(plan["features"]),
        "implementationBacklogCandidates":backlog["candidateCount"],
        "readOnlyActionProposals":len(proposals["proposals"]),
        "observedWorkflowSequences":sequences["workflowCount"],
        "manualVerificationChecks":len(verification_plan["checks"]),
        "submittedRuntimeObservations":feedback["summary"]["submitted"] if feedback else 0,
        "dynamicEvidenceOverlays":len(plan.get("evidenceOverlays",[])),
        "workflowEvidenceSummary":workflows["summary"],
        "validatedClientActionContracts":len(validated_contracts["contracts"]) if validated_contracts else 0,
        "reviewedActionsGuiGenerated":actions_gui_lua is not None,
        "generatedReadOnlyClientActions":sorted(set(c["action"] for c in validated_contracts["contracts"])) if validated_contracts else [],
        "implementedClientControls":["Stats","Menus","Prompts","Features"],
        "implementedGameplayAutomation":[],
        "validation":validation,
        "runtimeVerified":False,
        "releaseStatus":"GENERATED_STATIC_CHECKED_NOT_LIVE_TESTED",
        "generatedLuaSHA256":sha(lua.encode("utf-8"))
    }
    files={
      "implementation-backlog.json":(json.dumps(backlog,indent=2,sort_keys=True)+"\\n").encode(),
      "manual-verification-plan.json":(json.dumps(verification_plan,indent=2,sort_keys=True)+"\n").encode(),
      "observed-workflows.json":(json.dumps(sequences,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode(),
      "action-proposals.json":(json.dumps(proposals,indent=2,sort_keys=True)+"\n").encode(),
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
    if feedback is not None:
        files["runtime-feedback.json"]=(json.dumps(feedback,indent=2,sort_keys=True)+"\n").encode()
    if verification_lua is not None:
        files["LycolesManualVerification.lua"]=verification_lua.encode("utf-8")
    if actions_gui_lua is not None:
        files['LycolesReviewedActionsGUI.lua']=actions_gui_lua.encode('utf-8')
    if client_actions_lua is not None:
        files['LycolesClientActions.lua']=client_actions_lua.encode('utf-8')
    if validated_contracts is not None:
        files['validated-contracts.json']=(json.dumps(validated_contracts,indent=2,sort_keys=True)+'\n').encode()
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
    parser.add_argument("--contracts",default=None)
    parser.add_argument("--observation",action="append",default=[],help="Additional complete dynamic observation scan folder; repeatable")
    parser.add_argument("--feedback",default=None,help="Optional manual runtime observation report (v22 schema)")
    args=parser.parse_args()
    try: build(args.parts_dir,args.output,args.contracts,args.observation,args.feedback);return 0
    except (ValueError,TypeError,KeyError,OSError,json.JSONDecodeError) as exc:
        print("BUILD BLOCKED:",exc,file=sys.stderr);return 2

if __name__=="__main__":sys.exit(main())
