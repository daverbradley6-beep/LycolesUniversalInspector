#!/usr/bin/env python3
"""Universal architecture milestone pipeline.

Consumes validated scan evidence and produces:
- architecture objective coverage/gap assessment
- evidence inventory and package integrity report
- machine-readable game understanding model
- universal tool discovery proposals
- feature configuration schemas
- feasibility lifecycle records
- unified GUI architecture blueprint

All outputs remain read-only, evidence-bounded, and non-authoritative.
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import pathlib
import re
from typing import Any

SCHEMA_ARCHITECTURE = "120.universal-architecture-audit.1"
SCHEMA_INVENTORY = "120.evidence-inventory.1"
SCHEMA_MODEL = "120.universal-game-model.1"
SCHEMA_DISCOVERY = "120.universal-tool-discovery.1"
SCHEMA_CONFIG = "120.feature-config-catalog.1"
SCHEMA_FEASIBILITY = "120.feature-feasibility.1"
SCHEMA_GUI = "120.unified-gui-architecture.1"

MAX_FILE_BYTES = 30_000_000

FALSE_CLAIMS = {
    "sourceAuthenticityVerified": False,
    "causalityProven": False,
    "serverAuthorityVerified": False,
    "runtimeVerified": False,
    "gameplayVerified": False,
    "actionOutcomesVerified": False,
}


def load_local_module(name: str, filename: str):
    source = pathlib.Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(name, source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMPILE_SCAN = load_local_module("compile_scan", "compile_scan.py")
UNDERSTAND_GAMEPLAY = load_local_module("understand_gameplay", "understand_gameplay.py")
UNIVERSAL_INTELLIGENCE = load_local_module("universal_gameplay_intelligence", "universal_gameplay_intelligence.py")


def _safe_json(path: pathlib.Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError(f"JSON exceeds size limit: {path}")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _part_index(path: pathlib.Path) -> int | None:
    match = re.search(r"_part-(\d{4,})\.json$", path.name)
    if not match:
        return None
    return int(match.group(1))


def architecture_assessment() -> dict[str, Any]:
    objectives = [
        {
            "id": 1,
            "name": "Universal Game Inspection",
            "coverage": "partially-verified",
            "reusedComponents": [
                "tools/compile_scan.py",
                "tools/evidence_replay_import.py",
                "tools/receiver_generation_pipeline.py",
                "LycolesUniversalInspector.lua",
            ],
            "strengths": [
                "multipart baseline validation with fail-closed accounting",
                "client-visible interaction capture and bounded diagnostics",
                "explicit non-authoritative claims separation",
            ],
            "gaps": [
                "no dedicated cross-game inspection inventory report artifact",
                "limited direct summary of camera/entity/tool relationships by genre",
            ],
        },
        {
            "id": 2,
            "name": "Game Understanding Engine",
            "coverage": "partially-verified",
            "reusedComponents": [
                "tools/understand_gameplay.py",
                "tools/universal_gameplay_intelligence.py",
            ],
            "strengths": [
                "machine-readable systems/resources/actions extraction",
                "workflow and temporal correlation summaries",
            ],
            "gaps": [
                "no explicit direct-vs-inference-vs-hypothesis-vs-unknown partition",
                "no game-model artifact designed for downstream universal tool ideation",
            ],
        },
        {
            "id": 3,
            "name": "Universal Tool Discovery Engine",
            "coverage": "unverified",
            "reusedComponents": [
                "tools/discover_action_capabilities.py",
                "tools/universal_discovery_v89.py",
            ],
            "strengths": [
                "bounded observed interaction capability extraction",
            ],
            "gaps": [
                "no objective->mechanic->challenge->tool synthesis stage",
                "feature categories are not unified into a reusable discovery catalog",
            ],
        },
        {
            "id": 4,
            "name": "Evidence and Feasibility Engine",
            "coverage": "partially-verified",
            "reusedComponents": [
                "tools/assess_generation_readiness.py",
                "tools/lycoles_generation_service.py",
            ],
            "strengths": [
                "fail-closed blockers and request readiness diagnostics",
                "delivery metadata separates runtime/gameplay verification claims",
            ],
            "gaps": [
                "feasibility lifecycle statuses are not standardized across universal proposals",
                "missing dependency reasoning is not surfaced for broad tool ideation",
            ],
        },
        {
            "id": 5,
            "name": "Script Generation and Testing",
            "coverage": "partially-verified",
            "reusedComponents": [
                "tools/generate_script.py",
                "tools/lycoles_generation_service.py",
                "tools/generated_result.py",
                "tests/test_luau_syntax.mjs",
            ],
            "strengths": [
                "deterministic Luau generation and syntax/contract validation",
                "runtime/gameplay claims remain false without evidence",
            ],
            "gaps": [
                "feature-specific modular generation is still constrained by limited executable contracts",
                "universal feature modules and runtime binding coverage are incomplete",
            ],
        },
        {
            "id": 6,
            "name": "Unified Game-Specific GUI",
            "coverage": "blocked",
            "reusedComponents": [
                "tools/generate_script.py",
                "tools/generate_admin_commands.py",
            ],
            "strengths": [
                "single combined utility pattern exists",
            ],
            "gaps": [
                "settings schemas are not systematically bound to generated controls",
                "standalone admin GUI pathway still exists outside unified architecture",
            ],
        },
    ]
    return {
        "schemaVersion": SCHEMA_ARCHITECTURE,
        "objectiveAssessments": objectives,
        "summary": {
            "verified": 0,
            "partiallyVerified": sum(1 for item in objectives if item["coverage"] == "partially-verified"),
            "unverified": sum(1 for item in objectives if item["coverage"] == "unverified"),
            "blocked": sum(1 for item in objectives if item["coverage"] == "blocked"),
        },
        "claims": dict(FALSE_CLAIMS),
    }


def validate_evidence_inventory(extracted_dir: pathlib.Path, observation_path: pathlib.Path | None) -> dict[str, Any]:
    if not extracted_dir.is_dir():
        raise ValueError("extracted evidence directory not found")
    files = sorted(path for path in extracted_dir.iterdir() if path.is_file() and path.suffix.lower() == ".json")
    manifests = [path for path in files if path.name.endswith("_manifest.json")]
    if not manifests:
        raise ValueError("manifest JSON not found in extracted evidence")
    manifest_path = manifests[0]
    manifest = _safe_json(manifest_path)

    parts = [path for path in files if _part_index(path) is not None]
    part_indices = sorted(index for index in (_part_index(path) for path in parts) if index is not None)
    contiguous = part_indices == list(range(1, (part_indices[-1] if part_indices else 0) + 1))

    first_part = parts[0].name if parts else None
    last_part = parts[-1].name if parts else None

    observation = None
    if observation_path is not None:
        observation = _safe_json(observation_path)

    manifest_uploaded_parts = manifest.get("uploadedParts")
    manifest_expected_parts = manifest.get("partCount")
    if type(manifest_expected_parts) is not int:
        manifest_expected_parts = manifest.get("expectedParts") if type(manifest.get("expectedParts")) is int else None

    scan_id = manifest.get("scanId")
    place_id = manifest.get("placeId")

    observation_identity = None
    identity_match = None
    if observation is not None:
        obs_integrity = observation.get("integrity") if isinstance(observation.get("integrity"), dict) else {}
        obs_live_scan_id = obs_integrity.get("scanId") if isinstance(obs_integrity.get("scanId"), str) else None
        obs_baseline_scan_id = (
            obs_integrity.get("baselineScanId")
            if isinstance(obs_integrity.get("baselineScanId"), str)
            else (observation.get("baselineScanId") if isinstance(observation.get("baselineScanId"), str) else None)
        )
        obs_root_scan_id = observation.get("scanId") if isinstance(observation.get("scanId"), str) else None
        obs_place_id = obs_integrity.get("placeId") if type(obs_integrity.get("placeId")) is int else observation.get("placeId")
        observation_identity = {
            "scanId": obs_root_scan_id,
            "liveObservationScanId": obs_live_scan_id,
            "baselineScanId": obs_baseline_scan_id,
            "placeId": obs_place_id,
        }
        identity_match = (
            obs_place_id == place_id
            and scan_id in {obs_root_scan_id, obs_baseline_scan_id}
        )

    return {
        "schemaVersion": SCHEMA_INVENTORY,
        "extractedDirectory": str(extracted_dir),
        "manifestPath": str(manifest_path),
        "scanId": scan_id,
        "placeId": place_id,
        "manifestVersion": manifest.get("version"),
        "manifestGameName": manifest.get("gameName"),
        "extractedPartCount": len(parts),
        "manifestExpectedParts": manifest_expected_parts,
        "manifestUploadedParts": manifest_uploaded_parts,
        "countsExplanation": {
            "extractedPartCount": "Count of baseline part JSON files physically present after archive extraction.",
            "manifestUploadedParts": "Uploader-side transport counter captured at scan time; may differ from local extraction coverage.",
            "manifestExpectedParts": "Manifest-declared multipart target when available.",
        },
        "partIndexContiguous": contiguous,
        "firstPart": first_part,
        "lastPart": last_part,
        "observationPath": str(observation_path) if observation_path is not None else None,
        "observationIdentity": observation_identity,
        "observationIdentityMatchesManifest": identity_match,
        "manifestPreliminarySignals": {
            "objectCount": manifest.get("objectCount"),
            "featureReadinessKeys": sorted((manifest.get("featureReadiness") or {}).keys())
            if isinstance(manifest.get("featureReadiness"), dict) else [],
            "scanMode": (manifest.get("diagnostics") or {}).get("scanMode") if isinstance(manifest.get("diagnostics"), dict) else None,
            "interactionWindowsExpected": ((manifest.get("interactionDiagnostics") or {}).get("observationWindowsExpected")
                if isinstance(manifest.get("interactionDiagnostics"), dict) else None),
        },
        "claims": dict(FALSE_CLAIMS),
    }


def _top_classes(class_counts: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    pairs = []
    for key, value in class_counts.items():
        if isinstance(key, str) and type(value) is int and value >= 0:
            pairs.append((key, value))
    pairs.sort(key=lambda item: (-item[1], item[0]))
    return [{"class": key, "count": value} for key, value in pairs[:limit]]


def _control_type_counts(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: collections.Counter[str] = collections.Counter()
    for event in history:
        control = event.get("controlType")
        if isinstance(control, str) and control:
            counts[control] += 1
    return [{"controlType": key, "count": value} for key, value in counts.most_common(20)]


def _state_key_counts(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: collections.Counter[str] = collections.Counter()
    for event in history:
        for change in event.get("stateChanges") or []:
            if isinstance(change, dict) and isinstance(change.get("key"), str):
                counts[change["key"]] += 1
    return [{"key": key, "count": value} for key, value in counts.most_common(20)]


def _genre_candidates(plan: dict[str, Any], observation: dict[str, Any] | None) -> list[dict[str, Any]]:
    features = {item.get("feature") for item in plan.get("features", []) if isinstance(item, dict)}
    controls = _control_type_counts(plan.get("observedInteractionHistory", []))
    control_tokens = {item["controlType"].casefold() for item in controls}
    camera_samples = len((observation or {}).get("cameraOrientationSamples") or []) if observation else 0
    game_name = (observation or {}).get("gameName") if observation else None

    values = []
    if isinstance(game_name, str) and "phantom forces" in game_name.casefold():
        values.append({
            "genre": "fps-combat",
            "evidenceLevel": "supported-inference",
            "confidence": "medium",
            "reasons": ["external game context includes Phantom Forces", "combat feature candidate present"],
        })
    if "combat" in features and any("mousebutton1" in token for token in control_tokens):
        values.append({
            "genre": "shooter-like",
            "evidenceLevel": "hypothesis",
            "confidence": "low",
            "reasons": ["combat interactions and mouse fire-like inputs observed"],
        })
    if camera_samples > 0:
        values.append({
            "genre": "camera-driven-3d-game",
            "evidenceLevel": "direct-observation",
            "confidence": "high",
            "reasons": ["camera orientation samples observed"],
        })
    return values or [{
        "genre": "unknown",
        "evidenceLevel": "unknown",
        "confidence": "unknown",
        "reasons": ["insufficient evidence"],
    }]


def build_game_model(
    plan: dict[str, Any],
    gameplay_understanding: dict[str, Any],
    universal_intelligence: dict[str, Any],
    observation: dict[str, Any] | None,
) -> dict[str, Any]:
    integrity = plan.get("integrity") if isinstance(plan.get("integrity"), dict) else {}
    history = [event for event in plan.get("observedInteractionHistory", []) if isinstance(event, dict)]
    class_counts = plan.get("classCounts") if isinstance(plan.get("classCounts"), dict) else {}
    universal_discovery = plan.get("universalDiscovery") if isinstance(plan.get("universalDiscovery"), dict) else {}

    feature_summary = []
    for feature in plan.get("features", []):
        if not isinstance(feature, dict) or not isinstance(feature.get("feature"), str):
            continue
        feature_summary.append({
            "feature": feature["feature"],
            "interactionEvents": feature.get("interactionEvents", 0),
            "observableOutcomeCandidates": feature.get("observableOutcomeCandidates", 0),
            "status": feature.get("status"),
            "evidenceLevel": "direct-observation",
        })

    combat_signals = {
        "mousePrimaryInputs": sum(1 for event in history if event.get("controlType") == "InputBegan.MouseButton1"),
        "mouseSecondaryInputs": sum(1 for event in history if event.get("controlType") == "InputBegan.MouseButton2"),
        "combatFeatureEvents": sum(feature.get("interactionEvents", 0) for feature in plan.get("features", [])
            if isinstance(feature, dict) and feature.get("feature") == "combat"),
        "toolClassCount": class_counts.get("Tool", 0),
        "stateSignals": [item for item in _state_key_counts(history)
            if any(token in item["key"].casefold() for token in ("ammo", "health", "hp", "damage", "kill"))][:10],
        "evidenceLevel": "direct-observation",
    }

    camera_samples = len((observation or {}).get("cameraOrientationSamples") or []) if observation else 0
    gesture_samples = len((observation or {}).get("inputGestureObservations") or []) if observation else 0
    click_targets = len((observation or {}).get("clickTargetObservations") or []) if observation else 0

    direct = {
        "scanIdentity": {
            "scanId": integrity.get("scanId"),
            "placeId": integrity.get("placeId"),
            "parts": integrity.get("parts"),
            "objects": integrity.get("objects"),
            "interactionEvents": integrity.get("interactionEvents"),
            "scanComplete": integrity.get("scanComplete") is True,
            "evidenceLevel": "direct-observation",
        },
        "classDistributionTop": _top_classes(class_counts),
        "featureSummary": feature_summary,
        "inputControlTypes": _control_type_counts(history),
        "stateChangeSignals": _state_key_counts(history),
        "worldRegions": len(universal_discovery.get("regions") or []),
        "interactables": len(universal_discovery.get("interactables") or []),
        "cameraSamples": camera_samples,
        "gestureSamples": gesture_samples,
        "clickTargetSamples": click_targets,
        "combatSignals": combat_signals,
        "claims": dict(FALSE_CLAIMS),
    }

    inferred = {
        "genreCandidates": _genre_candidates(plan, observation),
        "primaryObjectives": [
            {
                "id": "objective-round-survival",
                "description": "Compete in combat rounds and outlast opponents.",
                "evidenceLevel": "hypothesis",
                "confidence": "low",
                "support": [
                    "combat feature interactions observed",
                    "mouse fire-like input activity observed",
                ],
            }
        ],
        "secondaryObjectives": [
            {
                "id": "objective-loadout-management",
                "description": "Adjust loadout, inventory, and progression choices.",
                "evidenceLevel": "supported-inference",
                "confidence": "medium",
                "support": [
                    "inventory and shops feature candidates discovered",
                    "menu gui structures in click target candidates",
                ],
            }
        ],
        "unknownMechanisms": [
            "server-side hit registration and damage authority",
            "replicated team assignment semantics",
            "projectile simulation authority and lag compensation",
            "match objective scoring and victory logic",
        ],
        "hypothesesRequiringValidation": [
            "weapon fire action is currently represented by mouse input but lacks callback attribution",
            "world click targets may include camera-only gestures without gameplay causality",
            "movement and camera patterns may indicate aiming/scouting but are not outcome-verified",
        ],
    }

    mechanics = []
    for system in gameplay_understanding.get("systems", []) if isinstance(gameplay_understanding, dict) else []:
        if isinstance(system, dict) and isinstance(system.get("id"), str):
            mechanics.append({
                "id": system["id"],
                "label": system.get("label"),
                "evidenceTier": system.get("evidenceTier"),
                "observedInteractions": system.get("observedInteractions", 0),
                "observableOutcomeCandidates": system.get("observableOutcomeCandidates", 0),
                "evidenceLevel": "direct-observation",
            })

    challenges = [
        {
            "id": "challenge-target-identification",
            "description": "Quickly identify relevant opponents and context in a dynamic scene.",
            "evidenceLevel": "supported-inference",
            "support": ["combat feature candidate", "high object count and camera gesture activity"],
        },
        {
            "id": "challenge-combat-consistency",
            "description": "Maintain consistent action timing and control under camera movement.",
            "evidenceLevel": "hypothesis",
            "support": ["mouse button gesture observations without corroborated outcomes"],
        },
        {
            "id": "challenge-loadout-and-progression-clarity",
            "description": "Understand inventory/loadout state and progression signals during matches.",
            "evidenceLevel": "supported-inference",
            "support": ["inventory/shops/progression feature presence"],
        },
    ]

    return {
        "schemaVersion": SCHEMA_MODEL,
        "scanId": integrity.get("scanId"),
        "placeId": integrity.get("placeId"),
        "directObservations": direct,
        "inferenceModel": inferred,
        "mechanics": mechanics,
        "challenges": challenges,
        "universalIntelligenceSummary": universal_intelligence.get("summary") if isinstance(universal_intelligence, dict) else {},
        "claims": dict(FALSE_CLAIMS),
    }


def _feature_template_library() -> dict[str, dict[str, Any]]:
    return {
        "combat_target_assist": {
            "title": "Target Assistance",
            "category": "combat_and_targeting",
            "toolType": "aim_assist",
            "mechanicTags": {"combat", "target", "aim"},
            "requiredEvidence": ["combatSignals.mousePrimaryInputs", "inputControlTypes"],
            "runtimeRequirements": ["entity tracking", "team relationship signal", "camera orientation signal"],
            "missingDependencyHints": ["replicated opponent entity map", "validated visibility check primitive"],
            "baseStatus": "evidence_required",
        },
        "combat_trigger_assist": {
            "title": "Trigger Assistance",
            "category": "combat_and_targeting",
            "toolType": "trigger_assist",
            "mechanicTags": {"combat", "reaction", "fire"},
            "requiredEvidence": ["combatSignals.mousePrimaryInputs", "stateChangeSignals"],
            "runtimeRequirements": ["crosshair overlap detection", "team filter"],
            "missingDependencyHints": ["crosshair-target correlation evidence"],
            "baseStatus": "evidence_required",
        },
        "combat_recoil_assist": {
            "title": "Recoil Assistance",
            "category": "combat_and_targeting",
            "toolType": "recoil_assist",
            "mechanicTags": {"combat", "camera", "weapon"},
            "requiredEvidence": ["cameraSamples", "combatSignals.mousePrimaryInputs"],
            "runtimeRequirements": ["camera delta tracking", "weapon firing cadence signal"],
            "missingDependencyHints": ["weapon-specific recoil pattern observations"],
            "baseStatus": "evidence_required",
        },
        "esp_player_overlay": {
            "title": "Player Awareness Overlay",
            "category": "esp_and_visuals",
            "toolType": "player_esp",
            "mechanicTags": {"combat", "awareness", "entities"},
            "requiredEvidence": ["classDistributionTop", "worldRegions"],
            "runtimeRequirements": ["character list", "camera projection", "team coloring"],
            "missingDependencyHints": ["stable enemy/friendly identity signal"],
            "baseStatus": "evidence_required",
        },
        "movement_navigation_assist": {
            "title": "Navigation Assistance",
            "category": "movement_and_navigation",
            "toolType": "navigation_assist",
            "mechanicTags": {"movement", "navigation"},
            "requiredEvidence": ["worldRegions", "cameraSamples"],
            "runtimeRequirements": ["pathable anchor points", "character root availability"],
            "missingDependencyHints": ["persistent humanoid root availability"],
            "baseStatus": "evidence_required",
        },
        "loadout_information_suite": {
            "title": "Loadout and Weapon Intelligence",
            "category": "weapons_and_loadout",
            "toolType": "loadout_info",
            "mechanicTags": {"inventory", "weapons", "progression"},
            "requiredEvidence": ["featureSummary", "inputControlTypes"],
            "runtimeRequirements": ["current weapon identity", "ammo/weapon state signals"],
            "missingDependencyHints": ["weapon stat extraction contract"],
            "baseStatus": "proposed",
        },
        "profile_and_keybind_manager": {
            "title": "Profiles and Keybinds",
            "category": "quality_of_life",
            "toolType": "profile_manager",
            "mechanicTags": {"qol", "settings"},
            "requiredEvidence": ["featureSummary"],
            "runtimeRequirements": ["config persistence layer"],
            "missingDependencyHints": [],
            "baseStatus": "feasible",
        },
        "objective_status_dashboard": {
            "title": "Objective and Match Status Dashboard",
            "category": "information",
            "toolType": "status_dashboard",
            "mechanicTags": {"information", "progression"},
            "requiredEvidence": ["stateChangeSignals", "featureSummary"],
            "runtimeRequirements": ["state signal subscriptions", "ui presentation"],
            "missingDependencyHints": ["match objective state key mapping"],
            "baseStatus": "evidence_required",
        },
    }


def _feature_status_criteria() -> list[dict[str, Any]]:
    return [
        {"status": "Proposed", "criteria": "Concept derived from objective->mechanic->challenge reasoning."},
        {"status": "Evidence required", "criteria": "One or more required runtime/evidence dependencies are missing."},
        {"status": "Feasible", "criteria": "Required evidence exists for bounded implementation planning."},
        {"status": "Implementation ready", "criteria": "Feasible plus explicit runtime contract and safe-stop behavior definition."},
        {"status": "Implemented", "criteria": "Feature logic exists in generated/runtime script modules."},
        {"status": "Static validation passed", "criteria": "Compilation/schema/dependency checks pass."},
        {"status": "Runtime tested", "criteria": "Feature executed in live environment with bounded telemetry."},
        {"status": "Gameplay verified", "criteria": "Observed gameplay outcome aligns with intended feature effect."},
        {"status": "Blocked", "criteria": "Policy or missing evidence prevents safe implementation."},
    ]


def _status_from_template(template: dict[str, Any], model: dict[str, Any]) -> tuple[str, list[str]]:
    direct = model.get("directObservations") if isinstance(model.get("directObservations"), dict) else {}
    missing = []
    for req in template.get("requiredEvidence", []):
        value = direct
        for segment in str(req).split("."):
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(segment)
        empty = value is None or value == [] or value == 0
        if empty:
            missing.append(f"missing evidence: {req}")
    for hint in template.get("missingDependencyHints", []):
        if hint:
            missing.append(f"dependency: {hint}")

    if template.get("baseStatus") == "feasible" and not missing:
        return "Feasible", []
    if not missing and template.get("baseStatus") in {"proposed", "evidence_required"}:
        return "Feasible", []
    if missing:
        return "Evidence required", missing
    return "Proposed", []


def discover_universal_tools(model: dict[str, Any]) -> dict[str, Any]:
    templates = _feature_template_library()
    direct = model.get("directObservations") if isinstance(model.get("directObservations"), dict) else {}
    genre_candidates = model.get("inferenceModel", {}).get("genreCandidates") if isinstance(model.get("inferenceModel"), dict) else []
    fps_hint = any(isinstance(item, dict) and "fps" in str(item.get("genre", "")) for item in genre_candidates)

    proposals = []
    for feature_id, template in sorted(templates.items()):
        status, blockers = _status_from_template(template, model)
        if not fps_hint and template["category"] == "combat_and_targeting":
            status = "Proposed"
            blockers = ["context mismatch: combat evidence is weak for this model"]
        proposals.append({
            "id": feature_id,
            "title": template["title"],
            "category": template["category"],
            "toolType": template["toolType"],
            "status": status,
            "mechanicsAddressed": sorted(template["mechanicTags"]),
            "challengeLinks": [item.get("id") for item in model.get("challenges", []) if isinstance(item, dict)][:5],
            "usefulness": {
                "summary": f"Addresses {template['category'].replace('_', ' ')} workflows with bounded evidence-aware controls.",
                "evidenceLevel": "supported-inference" if status != "Proposed" else "hypothesis",
            },
            "evidenceSupport": {
                "requiredEvidence": template["requiredEvidence"],
                "availableSignals": {
                    "interactionEvents": direct.get("scanIdentity", {}).get("interactionEvents"),
                    "cameraSamples": direct.get("cameraSamples"),
                    "clickSamples": direct.get("clickTargetSamples"),
                    "featureCount": len(direct.get("featureSummary") or []),
                },
            },
            "implementation": {
                "runtimeRequirements": template["runtimeRequirements"],
                "missingDependencies": blockers,
                "runtimeBindingStatus": "not-implemented",
            },
            "claims": dict(FALSE_CLAIMS),
        })

    return {
        "schemaVersion": SCHEMA_DISCOVERY,
        "scanId": model.get("scanId"),
        "placeId": model.get("placeId"),
        "statusCriteria": _feature_status_criteria(),
        "proposals": proposals,
        "summary": {
            "proposalCount": len(proposals),
            "categories": sorted({item["category"] for item in proposals}),
            "evidenceRequired": sum(1 for item in proposals if item["status"] == "Evidence required"),
            "feasible": sum(1 for item in proposals if item["status"] == "Feasible"),
            "proposed": sum(1 for item in proposals if item["status"] == "Proposed"),
        },
        "claims": dict(FALSE_CLAIMS),
    }


def _setting(
    *,
    setting_id: str,
    data_type: str,
    default: Any,
    valid_range: dict[str, Any] | None = None,
    choices: list[str] | None = None,
    dependencies: list[str] | None = None,
    runtime_binding: str = "planned",
) -> dict[str, Any]:
    return {
        "id": setting_id,
        "type": data_type,
        "default": default,
        "validRange": valid_range,
        "choices": choices,
        "dependencies": dependencies or [],
        "runtimeBinding": {
            "status": runtime_binding,
            "bindingKey": setting_id,
            "notes": "No runtime behavior claim until implemented and validated.",
        },
        "validation": {
            "required": True,
            "allowNull": False,
        },
        "persistence": {
            "scope": "profile",
            "serializable": True,
        },
    }


def build_feature_configuration_catalog(discovery: dict[str, Any]) -> dict[str, Any]:
    schemas = {}
    for proposal in discovery.get("proposals", []):
        if not isinstance(proposal, dict) or not isinstance(proposal.get("id"), str):
            continue
        feature_id = proposal["id"]
        tool_type = proposal.get("toolType")
        settings = [_setting(setting_id="enabled", data_type="boolean", default=False)]

        if tool_type == "aim_assist":
            settings.extend([
                _setting(setting_id="fovRadius", data_type="number", default=110, valid_range={"min": 5, "max": 800}),
                _setting(setting_id="showFovCircle", data_type="boolean", default=True),
                _setting(setting_id="fovColor", data_type="color", default="#33D1FF"),
                _setting(setting_id="smoothness", data_type="number", default=0.18, valid_range={"min": 0, "max": 1}),
                _setting(setting_id="targetPart", data_type="choice", default="Head", choices=["Head", "Torso", "Closest"], dependencies=["enabled"]),
                _setting(setting_id="teamFilter", data_type="boolean", default=True),
                _setting(setting_id="visibilityCheck", data_type="boolean", default=True),
                _setting(setting_id="maxDistance", data_type="number", default=1200, valid_range={"min": 50, "max": 5000}),
                _setting(setting_id="activationMode", data_type="choice", default="hold", choices=["hold", "toggle"]),
                _setting(setting_id="activationKeybind", data_type="keybind", default="MouseButton2"),
                _setting(setting_id="prediction", data_type="number", default=0, valid_range={"min": 0, "max": 0.5}),
                _setting(setting_id="targetPersistence", data_type="number", default=0.2, valid_range={"min": 0, "max": 2}),
            ])
        elif tool_type == "player_esp":
            settings.extend([
                _setting(setting_id="boxes", data_type="boolean", default=True),
                _setting(setting_id="skeleton", data_type="boolean", default=False),
                _setting(setting_id="names", data_type="boolean", default=True),
                _setting(setting_id="healthBars", data_type="boolean", default=True),
                _setting(setting_id="distance", data_type="boolean", default=True),
                _setting(setting_id="tracers", data_type="boolean", default=False),
                _setting(setting_id="teamColors", data_type="boolean", default=True),
                _setting(setting_id="customColor", data_type="color", default="#FF4D4D"),
                _setting(setting_id="transparency", data_type="number", default=0.35, valid_range={"min": 0, "max": 1}),
                _setting(setting_id="maxRenderDistance", data_type="number", default=2000, valid_range={"min": 50, "max": 5000}),
                _setting(setting_id="updateRateHz", data_type="number", default=20, valid_range={"min": 2, "max": 60}),
            ])
        elif tool_type == "trigger_assist":
            settings.extend([
                _setting(setting_id="activationMode", data_type="choice", default="hold", choices=["hold", "toggle"]),
                _setting(setting_id="activationKeybind", data_type="keybind", default="MouseButton1"),
                _setting(setting_id="reactionDelayMs", data_type="number", default=80, valid_range={"min": 0, "max": 500}),
                _setting(setting_id="teamFilter", data_type="boolean", default=True),
                _setting(setting_id="cooldownMs", data_type="number", default=90, valid_range={"min": 0, "max": 1000}),
                _setting(setting_id="targetCondition", data_type="choice", default="visible", choices=["visible", "crosshair-overlap"]),
            ])
        else:
            settings.extend([
                _setting(setting_id="profileName", data_type="string", default="default"),
                _setting(setting_id="hotkey", data_type="keybind", default="None"),
            ])

        runtime_state = "planned" if proposal.get("status") != "Implemented" else "implemented"
        for setting in settings:
            setting["runtimeBinding"]["status"] = runtime_state

        schemas[feature_id] = {
            "featureId": feature_id,
            "featureTitle": proposal.get("title"),
            "category": proposal.get("category"),
            "toolType": tool_type,
            "availability": "planned" if proposal.get("status") != "Implemented" else "active",
            "settings": settings,
        }

    return {
        "schemaVersion": SCHEMA_CONFIG,
        "featureSchemas": schemas,
        "summary": {
            "featureSchemaCount": len(schemas),
            "settingsCount": sum(len(item.get("settings", [])) for item in schemas.values()),
            "activeSchemas": sum(1 for item in schemas.values() if item.get("availability") == "active"),
            "plannedSchemas": sum(1 for item in schemas.values() if item.get("availability") == "planned"),
        },
        "claims": dict(FALSE_CLAIMS),
    }


def build_feasibility_records(discovery: dict[str, Any], config_catalog: dict[str, Any]) -> dict[str, Any]:
    records = []
    for proposal in discovery.get("proposals", []):
        if not isinstance(proposal, dict):
            continue
        feature_id = proposal.get("id")
        if not isinstance(feature_id, str):
            continue
        blockers = proposal.get("implementation", {}).get("missingDependencies")
        blockers = blockers if isinstance(blockers, list) else []
        records.append({
            "featureId": feature_id,
            "title": proposal.get("title"),
            "category": proposal.get("category"),
            "currentStatus": proposal.get("status"),
            "lifecycle": {
                "Proposed": True,
                "Evidence required": proposal.get("status") in {"Evidence required", "Proposed"},
                "Feasible": proposal.get("status") == "Feasible",
                "Implementation ready": False,
                "Implemented": False,
                "Static validation passed": False,
                "Runtime tested": False,
                "Gameplay verified": False,
                "Blocked": bool(blockers),
            },
            "statusCriteria": discovery.get("statusCriteria"),
            "whyUseful": proposal.get("usefulness", {}).get("summary"),
            "mechanicsAddressed": proposal.get("mechanicsAddressed"),
            "evidenceSupport": proposal.get("evidenceSupport"),
            "requiredRuntimeData": proposal.get("implementation", {}).get("runtimeRequirements"),
            "missingDependencies": blockers,
            "configurationSchemaAvailable": feature_id in (config_catalog.get("featureSchemas") or {}),
            "claims": dict(FALSE_CLAIMS),
        })

    return {
        "schemaVersion": SCHEMA_FEASIBILITY,
        "records": records,
        "summary": {
            "count": len(records),
            "feasible": sum(1 for item in records if item.get("currentStatus") == "Feasible"),
            "evidenceRequired": sum(1 for item in records if item.get("currentStatus") == "Evidence required"),
            "blocked": sum(1 for item in records if item.get("lifecycle", {}).get("Blocked") is True),
        },
        "claims": dict(FALSE_CLAIMS),
    }


def build_unified_gui_blueprint(discovery: dict[str, Any], config_catalog: dict[str, Any]) -> dict[str, Any]:
    categories = collections.defaultdict(list)
    for proposal in discovery.get("proposals", []):
        if not isinstance(proposal, dict):
            continue
        feature_id = proposal.get("id")
        category = proposal.get("category") if isinstance(proposal.get("category"), str) else "uncategorized"
        schema = (config_catalog.get("featureSchemas") or {}).get(feature_id, {})
        categories[category].append({
            "featureId": feature_id,
            "title": proposal.get("title"),
            "status": proposal.get("status"),
            "availability": schema.get("availability", "planned"),
            "settingsCount": len(schema.get("settings", [])) if isinstance(schema, dict) else 0,
        })

    ordered_categories = []
    for category in sorted(categories):
        ordered_categories.append({
            "id": category,
            "title": category.replace("_", " ").title(),
            "features": sorted(categories[category], key=lambda item: (item.get("status") != "Feasible", item.get("title") or "")),
        })

    return {
        "schemaVersion": SCHEMA_GUI,
        "window": {
            "id": "lycoles-universal-main",
            "title": "Lycoles Universal Toolkit",
            "singleWindow": True,
            "sections": [
                "feature-categories",
                "feature-settings",
                "profiles",
                "keybinds",
                "diagnostics",
                "errors",
            ],
        },
        "categories": ordered_categories,
        "profiles": {
            "enabled": True,
            "schema": {
                "id": "profileName",
                "type": "string",
                "default": "default",
            },
        },
        "diagnostics": {
            "integrated": True,
            "sources": ["feature-status", "feasibility-blockers", "runtime-validation"],
            "separateAdminGuiAllowed": False,
        },
        "claims": dict(FALSE_CLAIMS),
    }


def _write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_markdown_summary(path: pathlib.Path, *, audit: dict[str, Any], inventory: dict[str, Any], model: dict[str, Any], discovery: dict[str, Any], feasibility: dict[str, Any]) -> None:
    lines = [
        "# Phantom Forces Universal Architecture Milestone",
        "",
        f"- Scan: `{inventory.get('scanId')}`",
        f"- Place: `{inventory.get('placeId')}`",
        f"- Extracted parts: **{inventory.get('extractedPartCount')}**",
        f"- Manifest uploadedParts: **{inventory.get('manifestUploadedParts')}**",
        "",
        "## Architecture objective coverage",
        "",
        "| Objective | Coverage | Key gap |",
        "|---|---|---|",
    ]
    for item in audit.get("objectiveAssessments", []):
        gap = (item.get("gaps") or ["-"])[0]
        lines.append(f"| {item.get('name')} | {item.get('coverage')} | {str(gap).replace('|','/')} |")

    lines.extend([
        "",
        "## Game understanding",
        "",
        f"- Genre candidates: {len(model.get('inferenceModel', {}).get('genreCandidates', []))}",
        f"- Mechanics entries: {len(model.get('mechanics', []))}",
        f"- Challenges: {len(model.get('challenges', []))}",
        "",
        "## Universal tool discovery",
        "",
        f"- Proposals: {discovery.get('summary', {}).get('proposalCount')}",
        f"- Feasible now: {discovery.get('summary', {}).get('feasible')}",
        f"- Evidence required: {discovery.get('summary', {}).get('evidenceRequired')}",
        "",
        "## Feasibility lifecycle",
        "",
        f"- Records: {feasibility.get('summary', {}).get('count')}",
        f"- Blocked: {feasibility.get('summary', {}).get('blocked')}",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_pipeline(*, parts_dir: pathlib.Path, observation_file: pathlib.Path | None, output_dir: pathlib.Path) -> dict[str, Any]:
    plan = COMPILE_SCAN.compile_scan(str(parts_dir))
    gameplay = UNDERSTAND_GAMEPLAY.analyze(plan)
    intelligence = UNIVERSAL_INTELLIGENCE.analyze(plan)
    observation = _safe_json(observation_file) if observation_file is not None else None

    audit = architecture_assessment()
    inventory = validate_evidence_inventory(parts_dir, observation_file)
    model = build_game_model(plan, gameplay, intelligence, observation)
    discovery = discover_universal_tools(model)
    config_catalog = build_feature_configuration_catalog(discovery)
    feasibility = build_feasibility_records(discovery, config_catalog)
    gui_blueprint = build_unified_gui_blueprint(discovery, config_catalog)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "capability-plan.json", plan)
    _write_json(output_dir / "gameplay-understanding.json", gameplay)
    _write_json(output_dir / "universal-gameplay-intelligence.json", intelligence)
    _write_json(output_dir / "architecture-audit.json", audit)
    _write_json(output_dir / "evidence-inventory.json", inventory)
    _write_json(output_dir / "game-model.json", model)
    _write_json(output_dir / "tool-discovery.json", discovery)
    _write_json(output_dir / "feature-config-schemas.json", config_catalog)
    _write_json(output_dir / "feature-feasibility.json", feasibility)
    _write_json(output_dir / "unified-gui-blueprint.json", gui_blueprint)
    _write_markdown_summary(output_dir / "milestone-summary.md",
        audit=audit, inventory=inventory, model=model, discovery=discovery, feasibility=feasibility)

    return {
        "outputDir": str(output_dir),
        "scanId": inventory.get("scanId"),
        "placeId": inventory.get("placeId"),
        "files": {
            "architectureAudit": str(output_dir / "architecture-audit.json"),
            "evidenceInventory": str(output_dir / "evidence-inventory.json"),
            "gameModel": str(output_dir / "game-model.json"),
            "toolDiscovery": str(output_dir / "tool-discovery.json"),
            "featureConfigSchemas": str(output_dir / "feature-config-schemas.json"),
            "featureFeasibility": str(output_dir / "feature-feasibility.json"),
            "unifiedGuiBlueprint": str(output_dir / "unified-gui-blueprint.json"),
            "milestoneSummary": str(output_dir / "milestone-summary.md"),
        },
        "summary": {
            "extractedPartCount": inventory.get("extractedPartCount"),
            "manifestUploadedParts": inventory.get("manifestUploadedParts"),
            "proposalCount": discovery.get("summary", {}).get("proposalCount"),
            "feasibleCount": discovery.get("summary", {}).get("feasible"),
            "evidenceRequiredCount": discovery.get("summary", {}).get("evidenceRequired"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parts-dir", required=True)
    parser.add_argument("--observation-file", required=False)
    parser.add_argument("--output-dir", default="build/universal-milestone")
    args = parser.parse_args()

    parts_dir = pathlib.Path(args.parts_dir).resolve()
    observation_file = pathlib.Path(args.observation_file).resolve() if args.observation_file else None
    output_dir = pathlib.Path(args.output_dir).resolve()

    result = run_pipeline(parts_dir=parts_dir, observation_file=observation_file, output_dir=output_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
