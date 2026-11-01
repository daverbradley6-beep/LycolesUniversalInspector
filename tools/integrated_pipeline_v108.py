#!/usr/bin/env python3
"""Generate and verify evidence-bounded v108 system/runtime artifact bundles."""
import argparse
import hashlib
import json
import re
import tempfile
from pathlib import Path

from feature_planner_v107 import plan
from integrated_pipeline_v107 import (
    API_COMPATIBILITY,
    DIAGNOSTICS,
    PLAN,
    QUALITY,
    REPORT,
    SCRIPT,
    generate as generate_v107,
)
from path_identity_v107 import PATH_SCHEMA_VERSION
from release_pipeline_v104 import canonical
from runtime_contract_v108 import (
    build_check_plan,
    compare_runtime,
    validate_observation,
)
from system_interpreter_v108 import interpret

SYSTEM_INTERPRETATION = "system-interpretation.json"
SYSTEM_PLAN = "system-plan.json"
RUNTIME_CHECK_PLAN = "runtime-check-plan.json"
RUNTIME_COMPARISON = "runtime-comparison.json"
FEATURE_VERIFICATION = "feature-verification.json"
UNSUPPORTED_REPORT = "unsupported-report.json"
RELATIONSHIP_EVIDENCE = "relationship-evidence.json"
RUNTIME_OBSERVATION = "runtime-observation.json"
MANIFEST = "manifest.json"
BASE_ARTIFACTS = (
    REPORT, PLAN, QUALITY, DIAGNOSTICS, API_COMPATIBILITY, SCRIPT,
)
ARTIFACTS = (*BASE_ARTIFACTS, SYSTEM_INTERPRETATION, SYSTEM_PLAN,
             RUNTIME_CHECK_PLAN, RUNTIME_COMPARISON,
             FEATURE_VERIFICATION, UNSUPPORTED_REPORT)
DIGEST = re.compile(r"^[0-9a-f]{64}$")
MAX_ARTIFACT_BYTES = 20_000_000


def _sha256(payload):
    return hashlib.sha256(payload).hexdigest()


def _load_json(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ValueError("invalid v108 input")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("v108 input must be an object")
    return value


def _prepare_output(output):
    root = Path(output)
    if root.exists():
        if root.is_symlink() or not root.is_dir() or any(root.iterdir()):
            raise ValueError("invalid nonempty or aliased output directory")
    else:
        root.mkdir(parents=True)
    return root


def _system_plan(interpretation, check_plan, comparison):
    comparison_by_system = {
        item["systemId"]: item for item in comparison["systems"]
    }
    check_ids = {
        item["featureId"]: item["id"] for item in check_plan["featureChecks"]
    }
    systems = []
    for system in interpretation["systems"]:
        observed = comparison_by_system[system["id"]]
        systems.append({
            "id": system["id"],
            "label": system["label"],
            "type": system["type"],
            "featureIds": list(system["featureIds"]),
            "relationshipIds": list(system["relationshipIds"]),
            "runtimeCheckIds": [check_ids[item] for item in system["featureIds"]],
            "runtimeOutcome": observed["outcome"],
            "confidence": system["confidence"],
            "unknowns": list(system["unknowns"]),
            "unsupportedCapabilities": list(system["unsupportedCapabilities"]),
            "systemVerified": False,
            "causalityProven": False,
            "serverAuthorityVerified": False,
            "gameplayVerified": False,
        })
    return {
        "schemaVersion": "108.system-plan.1",
        "placeId": interpretation["placeId"],
        "sourceSystemInterpretationSha256": _sha256(canonical(interpretation)),
        "sourceRuntimeCheckPlanSha256": _sha256(canonical(check_plan)),
        "sourceRuntimeComparisonSha256": _sha256(canonical(comparison)),
        "systems": systems,
        "summary": {
            "systems": len(systems),
            "matched": sum(item["runtimeOutcome"] == "matched" for item in systems),
            "drifted": sum(item["runtimeOutcome"] == "drifted" for item in systems),
            "notObserved": sum(
                item["runtimeOutcome"] == "not_observed" for item in systems
            ),
        },
        "readOnly": True,
        "runtimeVerified": False,
        "causalityProven": False,
        "serverAuthorityVerified": False,
        "gameplayVerified": False,
    }


def _feature_verification(feature_plan, check_plan, comparison):
    checks = {item["featureId"]: item for item in check_plan["featureChecks"]}
    results = {item["featureId"]: item for item in comparison["features"]}
    features = []
    for feature in feature_plan["features"]:
        check = checks[feature["id"]]
        result = results[feature["id"]]
        features.append({
            "featureId": feature["id"],
            "sourceDigest": feature["evidence"]["sourceDigest"],
            "runtimeCheckId": check["id"],
            "systemIds": list(check["systemIds"]),
            "staticArtifactsVerified": True,
            "expectedStatus": result["expectedStatus"],
            "observedStatus": result["observedStatus"],
            "runtimeOutcome": result["outcome"],
            "diagnosticCode": result["diagnosticCode"],
            "failedRuntimeChecks": list(result["failedRuntimeChecks"]),
            "valueCompared": result["valueCompared"],
            "runtimeVerified": False,
            "gameplayVerified": False,
        })
    return {
        "schemaVersion": "108.feature-verification.1",
        "placeId": feature_plan["placeId"],
        "sourceFeaturePlanSha256": _sha256(canonical(feature_plan)),
        "sourceRuntimeCheckPlanSha256": _sha256(canonical(check_plan)),
        "sourceRuntimeComparisonSha256": _sha256(canonical(comparison)),
        "features": features,
        "summary": {
            "features": len(features),
            "staticArtifactsVerified": len(features),
            "runtimeMatched": sum(item["runtimeOutcome"] == "matched" for item in features),
            "runtimeDrifted": sum(item["runtimeOutcome"] == "drifted" for item in features),
            "runtimeNotObserved": sum(
                item["runtimeOutcome"] == "not_observed" for item in features
            ),
        },
        "readOnly": True,
        "runtimeVerified": False,
        "gameplayVerified": False,
    }


def _unsupported_report(feature_plan, interpretation, check_plan, comparison):
    source_observations = [
        {**item, "classification": "unsupported_source_observation"}
        for item in feature_plan["unsupported"]
    ]
    return {
        "schemaVersion": "108.unsupported-report.1",
        "placeId": feature_plan["placeId"],
        "sourceFeaturePlanSha256": _sha256(canonical(feature_plan)),
        "sourceSystemInterpretationSha256": _sha256(canonical(interpretation)),
        "sourceRuntimeCheckPlanSha256": _sha256(canonical(check_plan)),
        "sourceRuntimeComparisonSha256": _sha256(canonical(comparison)),
        "sourceObservations": source_observations,
        "systemCapabilities": list(check_plan["unsupportedCapabilities"]),
        "runtimeApiUsages": list(comparison["unsupportedApiUsages"]),
        "reportingComplete": True,
        "summary": {
            "sourceObservations": len(source_observations),
            "systemCapabilities": len(check_plan["unsupportedCapabilities"]),
            "runtimeApiUsages": len(comparison["unsupportedApiUsages"]),
        },
        "readOnly": True,
        "runtimeVerified": False,
        "causalityProven": False,
        "serverAuthorityVerified": False,
        "gameplayVerified": False,
    }


def _derive(report, feature_plan, relationship_evidence, runtime_observation):
    interpretation = interpret(report, feature_plan, relationship_evidence)
    check_plan = build_check_plan(
        report, feature_plan, interpretation, relationship_evidence
    )
    if runtime_observation is not None:
        validate_observation(runtime_observation, feature_plan)
    comparison = compare_runtime(check_plan, runtime_observation)
    system_plan = _system_plan(interpretation, check_plan, comparison)
    feature_verification = _feature_verification(
        feature_plan, check_plan, comparison
    )
    unsupported = _unsupported_report(
        feature_plan, interpretation, check_plan, comparison
    )
    return {
        SYSTEM_INTERPRETATION: canonical(interpretation),
        SYSTEM_PLAN: canonical(system_plan),
        RUNTIME_CHECK_PLAN: canonical(check_plan),
        RUNTIME_COMPARISON: canonical(comparison),
        FEATURE_VERIFICATION: canonical(feature_verification),
        UNSUPPORTED_REPORT: canonical(unsupported),
    }


def generate(source, place_id, output, *, relationship_evidence=None,
             runtime_observation=None):
    """Generate a strict v108 superset bundle from v107-compatible input."""
    if type(place_id) is not int or place_id <= 0:
        raise ValueError("invalid place ID")
    root = _prepare_output(output)
    with tempfile.TemporaryDirectory(prefix="lycoles-v108-base-") as directory:
        base_result = generate_v107(source, place_id, directory)
        if not base_result.get("ok"):
            raise ValueError("v107 generation failed: " + base_result.get("error", "unknown"))
        base = {
            name: (Path(directory) / name).read_bytes()
            for name in BASE_ARTIFACTS
        }
    report = json.loads(base[REPORT])
    feature_plan = json.loads(base[PLAN])
    derived = _derive(
        report, feature_plan, relationship_evidence, runtime_observation
    )
    files = {**base, **derived}
    if relationship_evidence is not None:
        files[RELATIONSHIP_EVIDENCE] = canonical(relationship_evidence)
    if runtime_observation is not None:
        files[RUNTIME_OBSERVATION] = canonical(runtime_observation)
    for name, payload in files.items():
        path = root / name
        if path.exists() or path.is_symlink():
            raise ValueError("artifact output collision")
        path.write_bytes(payload)
    comparison = json.loads(derived[RUNTIME_COMPARISON])
    interpretation = json.loads(derived[SYSTEM_INTERPRETATION])
    manifest = {
        "schemaVersion": "108.integrated-manifest.1",
        "pathIdentityVersion": PATH_SCHEMA_VERSION,
        "placeId": place_id,
        "featureCount": len(feature_plan["features"]),
        "systemCount": len(interpretation["systems"]),
        "relationshipEvidenceSupplied": relationship_evidence is not None,
        "runtimeObservationSupplied": runtime_observation is not None,
        "comparisonComplete": comparison["comparisonComplete"],
        "comparisonPassed": comparison["comparisonPassed"],
        "driftDetected": comparison["driftDetected"],
        "files": {
            name: _sha256(payload) for name, payload in sorted(files.items())
        },
        "readOnly": True,
        "sourceAuthenticityVerified": False,
        "runtimeVerified": False,
        "liveGameVerified": False,
        "causalityProven": False,
        "serverAuthorityVerified": False,
        "gameplayVerified": False,
    }
    (root / MANIFEST).write_bytes(canonical(manifest))
    result = verify(root)
    if not result["ok"]:
        raise ValueError("generated v108 bundle failed verification: " + result["error"])
    return result


def _read_bounded(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_ARTIFACT_BYTES:
        raise ValueError("invalid artifact file")
    return path.read_bytes()


def verify(output):
    """Reconstruct every v108 artifact and require exact canonical bytes."""
    root = Path(output)
    try:
        if root.is_symlink() or not root.is_dir():
            raise ValueError("invalid artifact directory")
        manifest_bytes = _read_bounded(root / MANIFEST)
        manifest = json.loads(manifest_bytes)
        manifest_fields = {
            "schemaVersion", "pathIdentityVersion", "placeId", "featureCount",
            "systemCount", "relationshipEvidenceSupplied",
            "runtimeObservationSupplied", "comparisonComplete", "comparisonPassed",
            "driftDetected", "files", "readOnly", "sourceAuthenticityVerified", "runtimeVerified",
            "liveGameVerified", "causalityProven", "serverAuthorityVerified",
            "gameplayVerified",
        }
        if not isinstance(manifest, dict) or set(manifest) != manifest_fields:
            raise ValueError("invalid manifest fields")
        if manifest.get("schemaVersion") != "108.integrated-manifest.1":
            raise ValueError("invalid manifest schema")
        if manifest_bytes != canonical(manifest):
            raise ValueError("non-canonical manifest")
        if manifest.get("pathIdentityVersion") != PATH_SCHEMA_VERSION:
            raise ValueError("invalid path identity claim")
        if type(manifest.get("placeId")) is not int or manifest["placeId"] <= 0:
            raise ValueError("invalid manifest place")
        for name in ("featureCount", "systemCount"):
            if type(manifest.get(name)) is not int or manifest[name] < 0:
                raise ValueError("invalid manifest count")
        for name in (
            "relationshipEvidenceSupplied", "runtimeObservationSupplied",
            "comparisonComplete", "driftDetected",
        ):
            if type(manifest.get(name)) is not bool:
                raise ValueError("invalid manifest status")
        comparison_passed = manifest.get("comparisonPassed")
        if manifest["runtimeObservationSupplied"]:
            if type(comparison_passed) is not bool:
                raise ValueError("invalid manifest comparison pass")
        elif comparison_passed is not None:
            raise ValueError("unexpected manifest comparison pass")
        if manifest.get("readOnly") is not True or any(
            manifest.get(name) is not False for name in (
                "sourceAuthenticityVerified", "runtimeVerified", "liveGameVerified",
                "causalityProven", "serverAuthorityVerified", "gameplayVerified",
            )
        ):
            raise ValueError("invalid manifest claims")
        expected_names = set(ARTIFACTS)
        if manifest["relationshipEvidenceSupplied"]:
            expected_names.add(RELATIONSHIP_EVIDENCE)
        if manifest["runtimeObservationSupplied"]:
            expected_names.add(RUNTIME_OBSERVATION)
        files = manifest.get("files")
        if not isinstance(files, dict) or set(files) != expected_names:
            raise ValueError("invalid manifest files")
        if any(
            not isinstance(value, str) or DIGEST.fullmatch(value) is None
            for value in files.values()
        ):
            raise ValueError("invalid manifest hash")
        if {item.name for item in root.iterdir()} != {*expected_names, MANIFEST}:
            raise ValueError("unexpected artifact set")
        actual = {name: _read_bounded(root / name) for name in expected_names}
        report = json.loads(actual[REPORT])
        feature_plan = json.loads(actual[PLAN])
        relationship_evidence = (
            json.loads(actual[RELATIONSHIP_EVIDENCE])
            if manifest["relationshipEvidenceSupplied"] else None
        )
        runtime_observation = (
            json.loads(actual[RUNTIME_OBSERVATION])
            if manifest["runtimeObservationSupplied"] else None
        )
        with tempfile.TemporaryDirectory(prefix="lycoles-v108-verify-") as directory:
            base_result = generate_v107(report, report["placeId"], directory)
            if not base_result.get("ok"):
                raise ValueError("invalid v107 base artifacts")
            expected_base = {
                name: (Path(directory) / name).read_bytes()
                for name in BASE_ARTIFACTS
            }
        expected = {
            **expected_base,
            **_derive(
                report, feature_plan, relationship_evidence, runtime_observation
            ),
        }
        if relationship_evidence is not None:
            expected[RELATIONSHIP_EVIDENCE] = canonical(relationship_evidence)
        if runtime_observation is not None:
            expected[RUNTIME_OBSERVATION] = canonical(runtime_observation)
        for name, payload in expected.items():
            if actual[name] != payload:
                raise ValueError("artifact mismatch: " + name)
            if files[name] != _sha256(payload):
                raise ValueError("hash mismatch: " + name)
        comparison = json.loads(expected[RUNTIME_COMPARISON])
        interpretation = json.loads(expected[SYSTEM_INTERPRETATION])
        if manifest["placeId"] != report["placeId"]:
            raise ValueError("manifest place mismatch")
        if manifest["featureCount"] != len(feature_plan["features"]):
            raise ValueError("manifest feature count mismatch")
        if manifest["systemCount"] != len(interpretation["systems"]):
            raise ValueError("manifest system count mismatch")
        if manifest["comparisonComplete"] != comparison["comparisonComplete"]:
            raise ValueError("manifest comparison mismatch")
        if manifest["comparisonPassed"] != comparison["comparisonPassed"]:
            raise ValueError("manifest comparison pass mismatch")
        if manifest["driftDetected"] != comparison["driftDetected"]:
            raise ValueError("manifest drift mismatch")
        return {
            "ok": True,
            "features": len(feature_plan["features"]),
            "systems": len(interpretation["systems"]),
            "observationSupplied": runtime_observation is not None,
            "comparisonComplete": comparison["comparisonComplete"],
            "comparisonPassed": comparison["comparisonPassed"],
            "driftDetected": comparison["driftDetected"],
            "readOnly": True,
            "runtimeVerified": False,
            "gameplayVerified": False,
        }
    except (OSError, ValueError, TypeError, KeyError, AttributeError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "error": str(exc),
            "runtimeVerified": False,
            "gameplayVerified": False,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspection", "--source", dest="inspection", type=Path)
    parser.add_argument("--place-id", type=int)
    parser.add_argument("--relationship-evidence", type=Path)
    parser.add_argument("--runtime-observation", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        result = verify(args.output)
    else:
        if args.inspection is None or args.place_id is None:
            parser.error("--inspection/--source and --place-id are required")
        source = _load_json(args.inspection)
        relationships = (
            _load_json(args.relationship_evidence)
            if args.relationship_evidence else None
        )
        observation = (
            _load_json(args.runtime_observation)
            if args.runtime_observation else None
        )
        result = generate(
            source, args.place_id, args.output,
            relationship_evidence=relationships,
            runtime_observation=observation,
        )
    print(json.dumps(result, sort_keys=True))
    comparison_failed = (
        not args.verify_only
        and result.get("observationSupplied") is True
        and result.get("comparisonPassed") is not True
    )
    if not result["ok"] or comparison_failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
