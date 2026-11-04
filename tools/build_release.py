#!/usr/bin/env python3
"""Lycoles offline pipeline: multipart scan -> release, or manifest -> blockers.

Usage: python3 tools/build_release.py ./scan-parts --output ./build
       python3 tools/build_release.py ./local-manifest.json --output ./build
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

def build_manifest_readiness(manifest_path,output):
    analyzer=load_module("manifest_readiness_v109.py","lycoles_manifest_readiness_v109")
    source=pathlib.Path(manifest_path)
    document=analyzer.load(source)
    output=pathlib.Path(output)
    output.mkdir(parents=True,exist_ok=True)
    target=output/"manifest-readiness-v109.json"
    result=analyzer.analyze(document)
    analyzer.write(result,target)
    print("BLOCKED: manifest-only input cannot generate a release; readiness written to",target)
    return result



def build(parts_dir,output,contracts_path=None,observation_dirs=None,feedback_path=None,
          audit_path=None,prompt_feedback_path=None,guided_feedback_path=None,
          guided_feedback_paths=None):
    parts_path=pathlib.Path(parts_dir)
    if parts_path.is_file():
        return build_manifest_readiness(parts_path,output)
    compiler=load_module("compile_scan.py","lycoles_compiler")
    generator=load_module("generate_script.py","lycoles_generator")
    workflows_compiler=load_module("compile_workflows.py","lycoles_workflows")
    plan=compiler.compile_scan(parts_dir)
    source_provenance=plan["sourceProvenance"]
    if observation_dirs:
        merger=load_module('merge_observations.py','lycoles_merge')
        observations=[compiler.compile_scan(folder) for folder in observation_dirs]
        plan=merger.merge_evidence(plan,observations)
    evidence_overlays=plan.get("evidenceOverlays",[])
    overlay_provenance={
        "schemaVersion":"30.3.evidence-overlay-provenance.1",
        "baselineScanId":plan["integrity"]["scanId"],
        "overlayCount":len(evidence_overlays),"overlays":evidence_overlays,
        "sourceAuthenticityVerified":False,"causalityProven":False,
        "serverAuthorityVerified":False,"replayable":False,
        "gameplayVerified":False,"actionOutcomesVerified":False,
    }
    overlay_provenance_bytes=(json.dumps(overlay_provenance,indent=2,sort_keys=True)+"\n").encode()
    gameplay_compiler=load_module("understand_gameplay.py","lycoles_gameplay_understanding")
    gameplay_understanding=gameplay_compiler.analyze(plan)
    gameplay_understanding_bytes=(json.dumps(
        gameplay_understanding,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8")

    action_discovery_builder=load_module("discover_action_capabilities.py","lycoles_action_discovery")
    action_discovery=action_discovery_builder.analyze(plan)
    action_discovery_bytes=(json.dumps(
        action_discovery,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8")
    workflow_planner=load_module("plan_generated_workflows.py","lycoles_generated_workflows")
    generated_workflows=workflow_planner.plan(plan,action_discovery)
    generated_workflows_bytes=(json.dumps(
        generated_workflows,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8")
    guided_workflow_builder=load_module(
        "generate_guided_workflow.py","lycoles_guided_workflow")
    guided_workflow_candidates=guided_workflow_builder.validate(generated_workflows)
    guided_workflow_candidate_id=(guided_workflow_candidates[0]["id"]
        if guided_workflow_candidates else None)

    guided_workflow_lua=guided_workflow_builder.render(generated_workflows)
    guided_workflow_bytes=(guided_workflow_lua.encode("utf-8")
        if guided_workflow_lua is not None else None)
    guided_feedback=None
    guided_feedback_bytes=None
    guided_feedback_aggregate=None
    guided_feedback_aggregate_bytes=None
    guided_documents=[]
    if (guided_feedback_paths is not None
            and (not isinstance(guided_feedback_paths,(list,tuple))
                or any(not isinstance(path,(str,pathlib.Path)) for path in guided_feedback_paths))):
        raise TypeError("guided feedback paths must be a list or tuple of paths")
    guided_paths=list(guided_feedback_paths or [])
    if guided_feedback_path is not None:
        guided_paths.insert(0,guided_feedback_path)
    if guided_paths:
        guided_documents=[json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
            for path in guided_paths]
        guided_feedback_aggregator=load_module(
            "aggregate_guided_workflow_feedback.py","lycoles_guided_feedback_aggregate")
        guided_feedback_aggregate=guided_feedback_aggregator.aggregate(
            generated_workflows,guided_documents)
        guided_feedback_aggregate_bytes=(json.dumps(guided_feedback_aggregate,
            indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8")
        if len(guided_documents)==1:
            guided_feedback_evaluator=load_module(
                "evaluate_guided_workflow_feedback.py","lycoles_guided_feedback")
            guided_feedback=guided_feedback_evaluator.evaluate(
                generated_workflows,guided_documents[0])
            guided_feedback_bytes=(json.dumps(guided_feedback,indent=2,
                sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8")


    readiness_builder=load_module(
        "assess_generation_readiness.py","lycoles_generation_readiness")
    generation_readiness=readiness_builder.assess(plan,gameplay_understanding,
        action_discovery,generated_workflows,guided_documents if guided_paths else None)
    generation_readiness_bytes=(json.dumps(
        generation_readiness,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8")

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
    template_builder=load_module("create_review_template.py","lycoles_review_template")
    review_template=template_builder.make_template(plan,proposals)
    contract_drafter=load_module("draft_client_contracts.py","lycoles_contract_draft")
    contract_draft=contract_drafter.draft(plan)
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
    audit_evaluation=None
    if audit_path is not None:
        if validated_contracts is None:raise ValueError("Audit requires reviewed contracts")
        audit_evaluator=load_module("evaluate_action_audit.py","lycoles_action_audit")
        audit_data=json.loads(pathlib.Path(audit_path).read_text(encoding="utf-8"))
        audit_evaluation=audit_evaluator.evaluate(validated_contracts,audit_data)
    coverage_reporter=load_module("report_feature_coverage.py","lycoles_coverage")
    coverage=coverage_reporter.report(plan,backlog,validated_contracts,audit_evaluation)
    gui_validation=None
    if actions_gui_lua is not None:
        gui_validator=load_module("validate_generated_gui.py","lycoles_gui_validator")
        gui_validation=gui_validator.validate(actions_gui_lua,sorted(set(c["action"] for c in validated_contracts["contracts"])))
    utility_lua=generator.render(plan,gameplay_understanding,generation_readiness)
    prompt_generator=load_module("generate_prompt_interactions.py","lycoles_prompt_interactions")
    prompt_interactions_lua=prompt_generator.render(action_discovery)
    prompt_trial_generated=action_discovery["promptInteractions"]["trialReadyTargets"]>0
    tool_trial_generated=action_discovery["toolInteractions"]["generationReadyTargets"]>0
    gui_trial_generated=action_discovery["guiInteractions"]["generationReadyTargets"]>0
    egg_trial_generated=action_discovery["eggHatching"]["automaticSingleTrialReady"] is True

    admin_generator=load_module("generate_admin_commands.py","lycoles_admin_commands")
    prompt_feedback=None
    prompt_feedback_bytes=None
    if prompt_feedback_path is not None:
        prompt_feedback_evaluator=load_module(
            "evaluate_prompt_trial_feedback.py","lycoles_prompt_feedback")
        prompt_feedback_document=json.loads(
            pathlib.Path(prompt_feedback_path).read_text(encoding="utf-8"))
        prompt_feedback=prompt_feedback_evaluator.evaluate(
            action_discovery,prompt_feedback_document)
        prompt_feedback_bytes=(json.dumps(
            prompt_feedback,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8")

    admin_lua=admin_generator.render(
        place,gameplay_understanding,generation_readiness)
    lua=utility_lua+"\n"+(prompt_interactions_lua+"\n" if prompt_interactions_lua else "")+admin_lua
    validation=validate_lua(lua,place)
    output=pathlib.Path(output)
    if guided_workflow_bytes is None:
        (output/"LycolesGuidedWorkflow.lua").unlink(missing_ok=True)
    if guided_feedback_bytes is None:
        (output/"guided-workflow-evaluation.json").unlink(missing_ok=True)
    if guided_feedback_aggregate_bytes is None:
        (output/"guided-workflow-feedback-aggregate.json").unlink(missing_ok=True)

    output.mkdir(parents=True,exist_ok=True)
    manifest={
        "schemaVersion":"30.0","placeId":place,"scanId":plan["integrity"]["scanId"],
        "sourceFeatureCandidates":len(plan["features"]),
        "requestedCapability":plan.get("requestedCapability"),
        "gameplayUnderstanding":{"schemaVersion":gameplay_understanding["schemaVersion"],
            "artifact":"gameplay-understanding.json",
            "sha256":sha(gameplay_understanding_bytes),
            "summary":gameplay_understanding["summary"],
            "requestedCapabilityAssessment":gameplay_understanding["requestedCapabilityAssessment"]},
        "actionCapabilities":{"artifact":"action-capabilities.json",
            "schemaVersion":action_discovery["schemaVersion"],
            "sha256":sha(action_discovery_bytes),
            "promptTargets":len(action_discovery["promptInteractions"]["targets"]),
            "trialReadyPromptTargets":action_discovery["promptInteractions"]["trialReadyTargets"],
            "toolTargets":len(action_discovery["toolInteractions"]["targets"]),
            "generationReadyToolTargets":action_discovery["toolInteractions"]["generationReadyTargets"],
            "guiTargets":len(action_discovery["guiInteractions"]["targets"]),
            "generationReadyGuiTargets":action_discovery["guiInteractions"]["generationReadyTargets"],
            "eggTargets":len(action_discovery["eggHatching"]["targets"]),
            "correlatedEggTargets":action_discovery["eggHatching"]["correlatedTargets"]},
        "generatedWorkflowPlan":{"artifact":"generated-workflow-plan.json",
            "schemaVersion":generated_workflows["schemaVersion"],
            "sha256":sha(generated_workflows_bytes),"summary":generated_workflows["summary"],
            "automaticallyExecutable":False,"runtimeVerified":False,
            "gameplayVerified":False,"causalityProven":False},
        "guidedWorkflowTrial":{"artifact":"LycolesGuidedWorkflow.lua" if guided_workflow_lua else None,
            "candidateId":guided_workflow_candidate_id,
            "sha256":sha(guided_workflow_bytes) if guided_workflow_bytes else None,
            "feedbackSchema":"115.guided-workflow-feedback.1" if guided_workflow_lua else None,
            "feedbackWorkflowPlanSHA256":guided_workflow_builder.digest(generated_workflows)
                if guided_workflow_lua else None,
            "generated":guided_workflow_lua is not None,"automaticActivation":False,
            "manualActivationRequired":guided_workflow_lua is not None,
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False},
        "guidedWorkflowFeedback":{"sessionCount":len(guided_paths),
            "artifact":"guided-workflow-evaluation.json" if guided_feedback is not None else None,
            "sha256":sha(guided_feedback_bytes) if guided_feedback_bytes else None,
            "summary":guided_feedback["summary"] if guided_feedback is not None else None,
            "aggregateArtifact":"guided-workflow-feedback-aggregate.json"
                if guided_feedback_aggregate is not None else None,
            "aggregateSHA256":sha(guided_feedback_aggregate_bytes)
                if guided_feedback_aggregate_bytes else None,
            "aggregateSummary":guided_feedback_aggregate["summary"]
                if guided_feedback_aggregate is not None else None,
            "completeSequenceRecurrenceObserved":guided_feedback_aggregate[
                "completeSequenceRecurrenceObserved"] if guided_feedback_aggregate is not None else False,
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False},
        "generationReadiness":{"schemaVersion":generation_readiness["schemaVersion"],
            "artifact":"generation-readiness.json",
            "sha256":sha(generation_readiness_bytes),
            "summary":generation_readiness["summary"],
            "request":generation_readiness["request"],
            "runtimeVerified":False,"gameplayVerified":False,
            "causalityProven":False,"actionOutcomesVerified":False},
        "promptInteractionTrial":{"artifact":"LycolesPromptInteractions.lua" if prompt_trial_generated else None,
            "generated":prompt_trial_generated,"automaticMovement":prompt_trial_generated,
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False},
        "toolActivationTrial":{"artifact":"LycolesPromptInteractions.lua" if tool_trial_generated else None,
            "generated":tool_trial_generated,"officialActivation":tool_trial_generated,
            "boundedEquip":tool_trial_generated,"automaticMovement":False,
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False},
        "guidedGuiTrial":{"artifact":"LycolesPromptInteractions.lua" if gui_trial_generated else None,
            "generated":gui_trial_generated,"automaticActivation":False,
            "manualActivationRequired":gui_trial_generated,
            "exactControlHighlighting":gui_trial_generated,
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False},

        "eggAutofarmTrial":{"artifact":"LycolesPromptInteractions.lua" if egg_trial_generated else None,
            "generated":egg_trial_generated,"runtimeVerified":False,"gameplayVerified":False,
            "multiHatchReady":action_discovery["eggHatching"]["multiHatchTrialReady"],
            "compatibilityAlias":True},
        "promptTrialFeedback":{"artifact":"prompt-trial-evaluation.json" if prompt_feedback else None,
            "sha256":sha(prompt_feedback_bytes) if prompt_feedback_bytes else None,
            "submitted":prompt_feedback is not None,
            "attempts":prompt_feedback["summary"]["submittedAttempts"] if prompt_feedback else 0,
            "expectedChangesObserved":prompt_feedback["summary"]["expectedChangesObserved"] if prompt_feedback else 0,
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False,
            "actionOutcomesVerified":False},

        "implementationBacklogCandidates":backlog["candidateCount"],
        "reviewRequiredContractCandidates":len(contract_draft["proposals"]),
        "reviewTemplateContracts":len(review_template["contracts"]),
        "coverageFeatures":coverage["featureCount"],
        "clientActionsReturned":sum(len(f["clientActionsReturned"]) for f in coverage["features"]),
        "clientActionsFailed":sum(len(f["clientActionsFailed"]) for f in coverage["features"]),
        "featuresByReadiness":{state:sum(f["readiness"]==state for f in coverage["features"]) for state in sorted({f["readiness"] for f in coverage["features"]})},
        "actionAuditObservedActions":audit_evaluation["observedActions"] if audit_evaluation else 0,
        "readOnlyActionProposals":len(proposals["proposals"]),
        "observedWorkflowSequences":sequences["workflowCount"],
        "manualVerificationChecks":len(verification_plan["checks"]),
        "submittedRuntimeObservations":feedback["summary"]["submitted"] if feedback else 0,
        "dynamicEvidenceOverlays":len(plan.get("evidenceOverlays",[])),
        "evidenceOverlayProvenance":{"schemaVersion":overlay_provenance["schemaVersion"],
            "artifact":"evidence-overlay-provenance.json",
            "overlayCount":overlay_provenance["overlayCount"],
            "sha256":sha(overlay_provenance_bytes)},
        "workflowEvidenceSummary":workflows["summary"],
        "validatedClientActionContracts":len(validated_contracts["contracts"]) if validated_contracts else 0,
        "reviewedActionsGuiGenerated":actions_gui_lua is not None,
        "reviewedActionsGuiValidation":gui_validation,
        "generatedReadOnlyClientActions":sorted(set(c["action"] for c in validated_contracts["contracts"])) if validated_contracts else [],
        "implementedClientControls":["Stats","Menus","Prompts","Features","Admin Commands"]+
            (["Prompt Interactions"] if prompt_trial_generated else [])+
            (["Tool Activation Trial"] if tool_trial_generated else [])+
            (["Guided GUI Trial"] if gui_trial_generated else []),
        "implementedGameplayAutomation":[],
        "adminCommandFramework":{"artifact":"LycolesAdminCommands.lua",
            "commands":list(admin_generator.COMMANDS),"prefix":";",
            "keyboardShortcut":"RightBracket","chatCommandSupport":"where-player-chat-events-are-supported",
            "sharedFeatureState":True,"staticValidationPassed":True,"runtimeVerified":False,
            "sha256":sha(admin_lua.encode("utf-8"))},
        "sourceProvenance":source_provenance,
        "validation":validation,
        "runtimeVerified":False,
        "releaseStatus":"GENERATED_STATIC_CHECKED_NOT_LIVE_TESTED",
        "generatedLuaSHA256":sha(lua.encode("utf-8"))
    }
    result_builder=load_module("generated_result.py","lycoles_generated_result")
    generated_result=result_builder.build(place,plan["integrity"]["scanId"],lua,
        plan.get("requestedCapability"),validation,manifest["implementedClientControls"],
        generation_readiness)
    generated_result_name="Lycoles-"+str(place)+"-generated-result.json"
    generated_result_bytes=(json.dumps(
        generated_result,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8")
    manifest["generatedResult"]={"artifact":generated_result_name,
        "schemaVersion":generated_result["schemaVersion"],
        "sha256":sha(generated_result_bytes),"displayOnly":True,"executionAuthorized":False}

    files={
      "feature-coverage.json":(json.dumps(coverage,indent=2,sort_keys=True)+"\n").encode(),
      "generated-workflow-plan.json":generated_workflows_bytes,
      "review-contracts-template.json":(json.dumps(review_template,indent=2,sort_keys=True)+"\n").encode(),
      "contract-draft.json":(json.dumps(contract_draft,indent=2,sort_keys=True)+"\n").encode(),
      "implementation-backlog.json":(json.dumps(backlog,indent=2,sort_keys=True)+"\n").encode(),
      "manual-verification-plan.json":(json.dumps(verification_plan,indent=2,sort_keys=True)+"\n").encode(),
      "observed-workflows.json":(json.dumps(sequences,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode(),
      "gameplay-understanding.json":gameplay_understanding_bytes,
      "generation-readiness.json":generation_readiness_bytes,

      "action-capabilities.json":action_discovery_bytes,

      "action-proposals.json":(json.dumps(proposals,indent=2,sort_keys=True)+"\n").encode(),
      "capability-plan.json":(json.dumps(plan,indent=2,sort_keys=True)+"\n").encode(),
      "evidence-overlay-provenance.json":overlay_provenance_bytes,
      "source-provenance.json":(json.dumps(source_provenance,indent=2,sort_keys=True)+"\n").encode(),
      "workflow-specs.json":(json.dumps(workflows,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode(),
      "implementation-review.md":(workflows_compiler.render_review(workflows)+"\n").encode("utf-8"),
      "LycolesAdminCommands.lua":admin_lua.encode("utf-8"),
      "LycolesGeneratedUtility.lua":lua.encode(),
      generated_result_name:generated_result_bytes,
      "release-manifest.json":(json.dumps(manifest,indent=2,sort_keys=True)+"\n").encode(),
      "README.txt":(
          "Lycoles generated utility for Roblox place "+str(place)+"\n"
          "This release contains client-side diagnostics and, when evidence permits, bounded prompt, official Tool, or user-mediated guided GUI trials.\n"
          "Baseline source input: "+source_provenance["inputMode"]+".\n"
          "Dynamic evidence overlays: "+str(overlay_provenance["overlayCount"])+"; each retains separate provenance in evidence-overlay-provenance.json.\n"
          "Receiver payload digests verified: "+str(source_provenance["receiverStoredPayloadDigestsVerified"]).lower()+".\n"
          "Gameplay system candidates: "+str(gameplay_understanding["summary"]["systems"])+"; progression loops: "+str(gameplay_understanding["summary"]["progressionLoops"])+".\n"
          "Generated bounded capabilities: "+str(generation_readiness["summary"]["generatedCapabilities"])+"; request status: "+generation_readiness["request"]["status"]+".\n"
          "Reviewable linked workflow candidates: "+str(generated_workflows["summary"]["workflowCandidates"])+"; guided manual trials: "+str(generated_workflows["summary"]["guidedTrialGenerationReadyWorkflows"])+"; automatically executable: false.\n"
          "Gameplay understanding and generation readiness do not verify objectives, causality, runtime behavior, or gameplay success.\n"
          "Admin Commands provides local client utilities only; it does not grant server administrator privileges.\n"
          "Command wiring is statically checked but not verified in the live Roblox engine.\n"
          "Inspector ACK digest equivalence: "+str(source_provenance["receiverAcknowledgementDigestEquivalent"]).lower()+".\n"
          "Resume checkpoint authentication, receiver response authenticity, and original local payload equivalence are unverified.\n"
          "Generated prompt, Tool, and user-mediated guided GUI trials have not been live runtime-tested; do not claim gameplay functionality or causality.\n"
      ).encode()
    }
    if prompt_interactions_lua is not None:
        files["LycolesPromptInteractions.lua"]=prompt_interactions_lua.encode("utf-8")
    if guided_workflow_bytes is not None:
        files["LycolesGuidedWorkflow.lua"]=guided_workflow_bytes

    if audit_evaluation is not None:
        files["action-audit-evaluation.json"]=(json.dumps(audit_evaluation,indent=2,sort_keys=True)+"\n").encode()
    if feedback is not None:
        files["runtime-feedback.json"]=(json.dumps(feedback,indent=2,sort_keys=True)+"\n").encode()
    if prompt_feedback_bytes is not None:
        files["prompt-trial-evaluation.json"]=prompt_feedback_bytes
    if guided_feedback_bytes is not None:
        files["guided-workflow-evaluation.json"]=guided_feedback_bytes
    if guided_feedback_aggregate_bytes is not None:
        files["guided-workflow-feedback-aggregate.json"]=guided_feedback_aggregate_bytes
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
    parser.add_argument("--prompt-feedback",default=None,
        help="Optional generated prompt trial feedback (v112 schema)")
    parser.add_argument("--guided-feedback",action="append",default=[],
        help="Generated guided workflow feedback (v115 schema); repeatable")
    parser.add_argument("--audit",default=None,help="Optional reviewed-actions GUI audit JSON (v28 schema)")
    args=parser.parse_args()
    try:
        result=build(args.parts_dir,args.output,args.contracts,args.observation,args.feedback,
            args.audit,args.prompt_feedback,guided_feedback_paths=args.guided_feedback)
        if result.get("schemaVersion")=="109.manifest-readiness.1":
            print("BUILD BLOCKED: manifest-only input lacks numbered object parts; see manifest-readiness-v109.json",file=sys.stderr)
            return 2
        return 0
    except (ValueError,TypeError,KeyError,OSError,json.JSONDecodeError) as exc:
        print("BUILD BLOCKED:",exc,file=sys.stderr);return 2

if __name__=="__main__":sys.exit(main())
