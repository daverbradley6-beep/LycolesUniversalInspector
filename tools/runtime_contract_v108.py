"""Strict expected-versus-observed runtime contracts for v108."""
import copy
import hashlib
import math
import re

from feature_planner_v106 import SUPPORTED
from feature_planner_v107 import plan, validate_feature_plan
from path_identity_v107 import normalize_observation, validate_report
from release_pipeline_v104 import canonical
from system_interpreter_v108 import UNSUPPORTED_CAPABILITIES, validate_interpretation

CHECK_PLAN_SCHEMA_VERSION = "108.runtime-check-plan.1"
OBSERVATION_SCHEMA_VERSION = "108.runtime-observation.1"
COMPARISON_SCHEMA_VERSION = "108.runtime-comparison.1"
MAX_FEATURES = 10_000
MAX_UNSUPPORTED = 1_000
MAX_STRING_BYTES = 10_000
MAX_SAFE_INTEGER = 2 ** 53
DIGEST = re.compile(r"^[0-9a-f]{64}$")
TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,98}$")
ARTIFACT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,98}\.json$")
OBSERVATION_STATUSES = frozenset({
    "resolved",
    "place_mismatch",
    "identity_mismatch",
    "legacy_resolution_failed",
    "property_unavailable",
    "unsupported_path_resolution",
})
FEATURE_ID = re.compile(r"^observe_[0-9]{4}$")
SYSTEM_ID = re.compile(r"^system_[0-9]{4}$")
SYSTEM_TYPES = frozenset({
    "interaction_feedback_candidate",
    "interaction_state_candidate",
    "state_feedback_candidate",
    "interface_cluster_candidate",
    "interaction_affordance_observation",
    "feedback_surface_observation",
    "state_observation",
    "interface_observation",
})
EXPECTED_RUNTIME_CHECKS = {
    "full_identity": [
        "place_id_matches", "root_available",
        "each_segment_name_class_ordinal_matches", "property_read_succeeds",
    ],
    "legacy_terminal_identity": [
        "place_id_matches", "root_available", "each_legacy_name_is_unique",
        "terminal_name_class_is_unique", "property_read_succeeds",
    ],
}
EXPECTED_FAILURES = {
    "full_identity": [
        "place_mismatch", "identity_mismatch", "property_unavailable",
        "property_read_failed",
    ],
    "legacy_terminal_identity": [
        "place_mismatch", "legacy_missing", "legacy_ambiguity",
        "property_unavailable", "property_read_failed",
    ],
}
EXPECTED_UNKNOWNS = [
    "server_authority",
    "gameplay_causality",
    "runtime_property_value",
    "runtime_object_availability",
    "game_specific_action_semantics",
]
EXPECTED_VALUE_TYPES = {
    "TextLabel": "string",
    "TextButton": "string",
    "TextBox": "string",
    "IntValue": "integer",
    "NumberValue": "number",
    "BoolValue": "boolean",
    "StringValue": "string",
    "ImageButton": "boolean",
    "ProximityPrompt": "boolean",
    "ClickDetector": "string",
    "Tool": "string",
    "ScreenGui": "boolean",
}


CLAIM_FIELDS = (
    "sourceAuthenticityVerified",
    "runtimeVerified",
    "liveGameVerified",
    "serverAuthorityVerified",
    "gameplayVerified",
)
OBSERVATION_FIELDS = {
    "schemaVersion", "placeId", "sourceFeaturePlanSha256", "environment",
    "features", "unsupportedApiUsages", "observationComplete", "readOnly",
    *CLAIM_FIELDS,
}
ENVIRONMENT_FIELDS = {
    "kind", "captureId", "sourceArtifact", "sourceDigest",
}
OBSERVED_FEATURE_FIELDS = {"featureId", "status", "value"}


def _sha256(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _scalar(value):
    if value is None or isinstance(value, (dict, list)):
        raise ValueError("invalid runtime value")
    if isinstance(value, str):
        if len(value.encode("utf-8")) > MAX_STRING_BYTES:
            raise ValueError("runtime value exceeds limit")
        return value
    if isinstance(value, bool):
        return value
    if type(value) is int:
        if abs(value) > MAX_SAFE_INTEGER:
            raise ValueError("runtime integer exceeds exact range")
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("invalid runtime number")
        return value
    raise ValueError("invalid runtime value")


def _value_type(value):
    if isinstance(value, bool):
        return "boolean"
    if type(value) is int:
        return "integer"
    if type(value) is float:
        return "number"
    if isinstance(value, str):
        return "string"
    raise ValueError("invalid runtime value")


def _type_matches(expected, observed):
    return expected == observed or expected == "number" and observed == "integer"


def build_check_plan(report, feature_plan, interpretation, relationship_evidence=None):
    """Build deterministic expected runtime checks from exact source artifacts."""
    validate_report(report)
    expected_plan = plan(report)
    if feature_plan != expected_plan:
        raise ValueError("feature plan mismatch")
    validate_feature_plan(feature_plan)
    validate_interpretation(
        interpretation, report, feature_plan, relationship_evidence
    )
    systems_by_feature = {}
    for system in interpretation["systems"]:
        for feature_id in system["featureIds"]:
            systems_by_feature.setdefault(feature_id, []).append(system["id"])
    feature_checks = []
    for feature in feature_plan["features"]:
        identifier = feature["id"]
        feature_checks.append({
            "id": "runtime_check_" + identifier[8:],
            "featureId": identifier,
            "systemIds": sorted(systems_by_feature.get(identifier, [])),
            "path": list(feature["path"]),
            "pathIdentity": copy.deepcopy(feature["pathIdentity"]),
            "pathResolution": feature["pathResolution"],
            "className": feature["className"],
            "property": feature["property"],
            "sourceObjectIndex": feature["evidence"]["sourceObjectIndex"],
            "sourceDigest": feature["evidence"]["sourceDigest"],
            "expectedStatus": "resolved",
            "expectedValueType": EXPECTED_VALUE_TYPES[feature["className"]],
            "runtimeChecks": list(feature["runtimeChecks"]),
            "successCondition": feature["successCondition"],
            "failureConditions": list(feature["failureConditions"]),
            "unknowns": list(feature["unknowns"]),
            "runtimeVerified": False,
        })
    check_ids = {item["featureId"]: item["id"] for item in feature_checks}
    system_plans = [
        {
            "systemId": system["id"],
            "type": system["type"],
            "featureIds": list(system["featureIds"]),
            "runtimeCheckIds": [check_ids[item] for item in system["featureIds"]],
            "expectedOutcome": "all_features_resolved",
            "unsupportedCapabilities": list(system["unsupportedCapabilities"]),
            "runtimeVerified": False,
            "causalityProven": False,
            "gameplayVerified": False,
        }
        for system in interpretation["systems"]
    ]
    unsupported_capabilities = list(UNSUPPORTED_CAPABILITIES)
    return {
        "schemaVersion": CHECK_PLAN_SCHEMA_VERSION,
        "placeId": feature_plan["placeId"],
        "sourceReportSha256": _sha256(report),
        "sourceFeaturePlanSha256": _sha256(feature_plan),
        "sourceSystemInterpretationSha256": _sha256(interpretation),
        "featureChecks": feature_checks,
        "systemPlans": system_plans,
        "unsupportedObservations": [
            {**item, "classification": "unsupported_source_observation"}
            for item in feature_plan["unsupported"]
        ],
        "unsupportedCapabilities": unsupported_capabilities,
        "readOnly": True,
        "runtimeVerified": False,
        "causalityProven": False,
        "serverAuthorityVerified": False,
        "gameplayVerified": False,
    }


def _validate_check_plan(value):
    fields = {
        "schemaVersion", "placeId", "sourceReportSha256",
        "sourceFeaturePlanSha256", "sourceSystemInterpretationSha256",
        "featureChecks", "systemPlans", "unsupportedObservations",
        "unsupportedCapabilities", "readOnly", "runtimeVerified",
        "causalityProven", "serverAuthorityVerified", "gameplayVerified",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("invalid runtime check plan fields")
    if value.get("schemaVersion") != CHECK_PLAN_SCHEMA_VERSION:
        raise ValueError("invalid runtime check plan schema")
    if type(value.get("placeId")) is not int or value["placeId"] <= 0:
        raise ValueError("invalid runtime check plan place")
    for name in (
        "sourceReportSha256", "sourceFeaturePlanSha256",
        "sourceSystemInterpretationSha256",
    ):
        if not isinstance(value.get(name), str) or DIGEST.fullmatch(value[name]) is None:
            raise ValueError("invalid runtime check plan digest")
    if value.get("readOnly") is not True or any(
        value.get(name) is not False for name in (
            "runtimeVerified", "causalityProven", "serverAuthorityVerified",
            "gameplayVerified",
        )
    ):
        raise ValueError("invalid runtime check plan claims")
    checks = value.get("featureChecks")
    systems = value.get("systemPlans")
    if not isinstance(checks, list) or len(checks) > MAX_FEATURES:
        raise ValueError("invalid runtime feature checks")
    if not isinstance(systems, list) or len(systems) > MAX_FEATURES:
        raise ValueError("invalid runtime system plans")
    feature_ids = []
    check_ids = set()
    check_by_feature = {}
    check_fields = {
        "id", "featureId", "systemIds", "path", "pathIdentity",
        "pathResolution", "className", "property", "sourceObjectIndex",
        "sourceDigest", "expectedStatus", "expectedValueType", "runtimeChecks",
        "successCondition", "failureConditions", "unknowns", "runtimeVerified",
    }
    for check in checks:
        if not isinstance(check, dict) or set(check) != check_fields:
            raise ValueError("invalid runtime feature check")
        identifier = check.get("featureId")
        check_id = check.get("id")
        if not isinstance(identifier, str) or FEATURE_ID.fullmatch(identifier) is None:
            raise ValueError("invalid runtime feature ID")
        if check_id != "runtime_check_" + identifier[8:]:
            raise ValueError("invalid runtime check ID")
        if identifier in check_by_feature or check_id in check_ids:
            raise ValueError("duplicate runtime check")
        if check.get("expectedStatus") != "resolved" or check.get("runtimeVerified") is not False:
            raise ValueError("invalid runtime check expectation")
        resolution = check.get("pathResolution")
        if resolution not in EXPECTED_RUNTIME_CHECKS:
            raise ValueError("invalid runtime path resolution")
        normalized = normalize_observation({
            "path": check.get("path"),
            "pathIdentity": check.get("pathIdentity"),
            "className": check.get("className"),
            "property": check.get("property"),
        })
        if normalized["pathResolution"] != resolution:
            raise ValueError("runtime check identity mismatch")
        class_name = check.get("className")
        if check.get("property") != SUPPORTED.get(class_name):
            raise ValueError("invalid runtime class property")
        if check.get("expectedValueType") != EXPECTED_VALUE_TYPES.get(class_name):
            raise ValueError("invalid expected runtime value type")
        if check.get("sourceObjectIndex") != int(identifier[8:]):
            raise ValueError("invalid runtime source object index")
        source_digest = check.get("sourceDigest")
        if not isinstance(source_digest, str) or DIGEST.fullmatch(source_digest) is None:
            raise ValueError("invalid runtime source digest")
        source_object = {
            "path": list(check["path"]),
            "pathIdentity": copy.deepcopy(check["pathIdentity"]),
            "pathResolution": resolution,
            "className": class_name,
            "property": check["property"],
            "canAutomate": False,
        }
        if source_digest != _sha256(source_object):
            raise ValueError("runtime source digest mismatch")
        if check.get("runtimeChecks") != EXPECTED_RUNTIME_CHECKS[resolution]:
            raise ValueError("invalid runtime checks")
        if check.get("failureConditions") != EXPECTED_FAILURES[resolution]:
            raise ValueError("invalid runtime failure conditions")
        if check.get("unknowns") != EXPECTED_UNKNOWNS:
            raise ValueError("invalid runtime unknowns")
        if check.get("successCondition") != "target_resolved_and_property_read_succeeded":
            raise ValueError("invalid runtime success condition")
        system_ids = check.get("systemIds")
        if not isinstance(system_ids, list) or system_ids != sorted(set(system_ids)):
            raise ValueError("noncanonical runtime system IDs")
        if any(not isinstance(item, str) or SYSTEM_ID.fullmatch(item) is None for item in system_ids):
            raise ValueError("invalid runtime system ID")
        feature_ids.append(identifier)
        check_ids.add(check_id)
        check_by_feature[identifier] = check
    if feature_ids != sorted(feature_ids):
        raise ValueError("noncanonical runtime check order")
    system_fields = {
        "systemId", "type", "featureIds", "runtimeCheckIds", "expectedOutcome",
        "unsupportedCapabilities", "runtimeVerified", "causalityProven",
        "gameplayVerified",
    }
    system_ids = []
    for system in systems:
        if not isinstance(system, dict) or set(system) != system_fields:
            raise ValueError("invalid runtime system plan")
        identifier = system.get("systemId")
        if not isinstance(identifier, str) or SYSTEM_ID.fullmatch(identifier) is None:
            raise ValueError("invalid runtime system ID")
        if system.get("type") not in SYSTEM_TYPES:
            raise ValueError("invalid runtime system type")
        features = system.get("featureIds")
        runtime_ids = system.get("runtimeCheckIds")
        unsupported = system.get("unsupportedCapabilities")
        if not isinstance(features, list) or features != sorted(set(features)):
            raise ValueError("invalid runtime system features")
        if any(item not in check_by_feature for item in features):
            raise ValueError("unknown runtime system feature")
        if runtime_ids != [check_by_feature[item]["id"] for item in features]:
            raise ValueError("runtime system check mismatch")
        if unsupported != UNSUPPORTED_CAPABILITIES:
            raise ValueError("invalid runtime unsupported capabilities")
        if system.get("expectedOutcome") != "all_features_resolved":
            raise ValueError("invalid runtime system outcome")
        if any(system.get(name) is not False for name in (
            "runtimeVerified", "causalityProven", "gameplayVerified",
        )):
            raise ValueError("invalid runtime system claims")
        system_ids.append(identifier)
    expected_system_ids = [f"system_{index:04d}" for index in range(len(systems))]
    if system_ids != expected_system_ids:
        raise ValueError("noncanonical runtime system order")
    for feature_id, check in check_by_feature.items():
        expected_systems = [
            system["systemId"] for system in systems if feature_id in system["featureIds"]
        ]
        if check["systemIds"] != expected_systems:
            raise ValueError("runtime feature system mismatch")
    unsupported_observations = value.get("unsupportedObservations")
    if not isinstance(unsupported_observations, list) or len(unsupported_observations) > MAX_FEATURES:
        raise ValueError("invalid unsupported observations")
    unsupported_indices = []
    for item in unsupported_observations:
        if not isinstance(item, dict) or set(item) != {"index", "reason", "classification"}:
            raise ValueError("invalid unsupported observation")
        if type(item.get("index")) is not int or item["index"] < 0:
            raise ValueError("invalid unsupported observation index")
        if item.get("reason") != "no_supported_local_implementation":
            raise ValueError("invalid unsupported observation reason")
        if item.get("classification") != "unsupported_source_observation":
            raise ValueError("invalid unsupported observation classification")
        unsupported_indices.append(item["index"])
    if unsupported_indices != sorted(set(unsupported_indices)):
        raise ValueError("noncanonical unsupported observations")
    if value.get("unsupportedCapabilities") != UNSUPPORTED_CAPABILITIES:
        raise ValueError("invalid unsupported capabilities")
    return value


def validate_observation(value, feature_plan):
    """Validate bounded caller-supplied permitted-environment observations."""
    validate_feature_plan(feature_plan)
    if not isinstance(value, dict) or set(value) != OBSERVATION_FIELDS:
        raise ValueError("invalid runtime observation fields")
    if value.get("schemaVersion") != OBSERVATION_SCHEMA_VERSION:
        raise ValueError("invalid runtime observation schema")
    if value.get("placeId") != feature_plan["placeId"]:
        raise ValueError("runtime observation place mismatch")
    if value.get("sourceFeaturePlanSha256") != _sha256(feature_plan):
        raise ValueError("runtime observation plan digest mismatch")
    if value.get("readOnly") is not True or any(
        value.get(name) is not False for name in CLAIM_FIELDS
    ):
        raise ValueError("invalid runtime observation claims")
    environment = value.get("environment")
    if not isinstance(environment, dict) or set(environment) != ENVIRONMENT_FIELDS:
        raise ValueError("invalid runtime environment")
    if environment.get("kind") != "permitted_client_observation":
        raise ValueError("unsupported runtime environment")
    if not isinstance(environment.get("captureId"), str) or TOKEN.fullmatch(environment["captureId"]) is None:
        raise ValueError("invalid runtime capture ID")
    if not isinstance(environment.get("sourceArtifact"), str) or ARTIFACT.fullmatch(environment["sourceArtifact"]) is None:
        raise ValueError("invalid runtime source artifact")
    if not isinstance(environment.get("sourceDigest"), str) or DIGEST.fullmatch(environment["sourceDigest"]) is None:
        raise ValueError("invalid runtime source digest")
    complete = value.get("observationComplete")
    if type(complete) is not bool:
        raise ValueError("invalid runtime completeness")
    features = value.get("features")
    if not isinstance(features, list) or len(features) > MAX_FEATURES:
        raise ValueError("invalid runtime features")
    expected_ids = [item["id"] for item in feature_plan["features"]]
    expected = set(expected_ids)
    observed_ids = []
    for feature in features:
        if not isinstance(feature, dict) or set(feature) != OBSERVED_FEATURE_FIELDS:
            raise ValueError("invalid observed feature fields")
        identifier = feature.get("featureId")
        if identifier not in expected:
            raise ValueError("unknown observed feature")
        if identifier in observed_ids:
            raise ValueError("duplicate observed feature")
        if feature.get("status") not in OBSERVATION_STATUSES:
            raise ValueError("invalid observed feature status")
        _scalar(feature.get("value"))
        observed_ids.append(identifier)
    if observed_ids != sorted(observed_ids):
        raise ValueError("noncanonical observed feature order")
    if complete and observed_ids != expected_ids:
        raise ValueError("complete observation missing feature")
    unsupported = value.get("unsupportedApiUsages")
    if not isinstance(unsupported, list) or len(unsupported) > MAX_UNSUPPORTED:
        raise ValueError("invalid unsupported API usages")
    if any(
        not isinstance(item, str) or not item or len(item.encode("utf-8")) > 500
        for item in unsupported
    ) or unsupported != sorted(set(unsupported)):
        raise ValueError("invalid unsupported API usage")
    return value


def _failed_checks(check, status):
    runtime_checks = check["runtimeChecks"]
    if status == "place_mismatch":
        candidates = {"place_id_matches"}
    elif status == "identity_mismatch":
        candidates = {
            "root_available", "each_segment_name_class_ordinal_matches",
        }
    elif status == "legacy_resolution_failed":
        candidates = {
            "root_available", "each_legacy_name_is_unique",
            "terminal_name_class_is_unique",
        }
    elif status == "property_unavailable":
        candidates = {"property_read_succeeds"}
    else:
        candidates = set(runtime_checks)
    return [item for item in runtime_checks if item in candidates]


def _diagnostic(status):
    return {
        "place_mismatch": "place_drift",
        "identity_mismatch": "identity_drift",
        "legacy_resolution_failed": "legacy_resolution_drift",
        "property_unavailable": "property_drift",
        "unsupported_path_resolution": "unsupported_resolution_drift",
    }.get(status)


def compare_runtime(check_plan, observation):
    """Compare runtime evidence with expectations without upgrading provenance claims."""
    _validate_check_plan(check_plan)
    observed_by_id = {}
    environment = None
    observation_digest = None
    complete = False
    unsupported = []
    if observation is not None:
        if not isinstance(observation, dict) or set(observation) != OBSERVATION_FIELDS:
            raise ValueError("invalid runtime observation fields")
        if observation.get("sourceFeaturePlanSha256") != check_plan["sourceFeaturePlanSha256"]:
            raise ValueError("runtime observation check-plan digest mismatch")
        if observation.get("placeId") != check_plan["placeId"]:
            raise ValueError("runtime observation check-plan place mismatch")
        if observation.get("schemaVersion") != OBSERVATION_SCHEMA_VERSION:
            raise ValueError("invalid runtime observation schema")
        if observation.get("readOnly") is not True or any(
            observation.get(name) is not False for name in CLAIM_FIELDS
        ):
            raise ValueError("invalid runtime observation claims")
        environment = observation.get("environment")
        if not isinstance(environment, dict) or set(environment) != ENVIRONMENT_FIELDS:
            raise ValueError("invalid runtime environment")
        if environment.get("kind") != "permitted_client_observation":
            raise ValueError("unsupported runtime environment")
        if not isinstance(environment.get("captureId"), str) or TOKEN.fullmatch(environment["captureId"]) is None:
            raise ValueError("invalid runtime capture ID")
        if not isinstance(environment.get("sourceArtifact"), str) or ARTIFACT.fullmatch(environment["sourceArtifact"]) is None:
            raise ValueError("invalid runtime source artifact")
        if not isinstance(environment.get("sourceDigest"), str) or DIGEST.fullmatch(environment["sourceDigest"]) is None:
            raise ValueError("invalid runtime source digest")
        complete = observation.get("observationComplete")
        if type(complete) is not bool:
            raise ValueError("invalid runtime completeness")
        observed = observation.get("features")
        expected_ids = [item["featureId"] for item in check_plan["featureChecks"]]
        if not isinstance(observed, list) or len(observed) > MAX_FEATURES:
            raise ValueError("invalid runtime features")
        for feature in observed:
            if not isinstance(feature, dict) or set(feature) != OBSERVED_FEATURE_FIELDS:
                raise ValueError("invalid observed feature fields")
            identifier = feature.get("featureId")
            if identifier not in expected_ids or identifier in observed_by_id:
                raise ValueError("unknown or duplicate observed feature")
            if feature.get("status") not in OBSERVATION_STATUSES:
                raise ValueError("invalid observed feature status")
            _scalar(feature.get("value"))
            observed_by_id[identifier] = feature
        if list(observed_by_id) != sorted(observed_by_id):
            raise ValueError("noncanonical observed feature order")
        if complete and list(observed_by_id) != expected_ids:
            raise ValueError("complete observation missing feature")
        unsupported = observation.get("unsupportedApiUsages")
        if not isinstance(unsupported, list) or len(unsupported) > MAX_UNSUPPORTED:
            raise ValueError("invalid unsupported API usages")
        if any(
            not isinstance(item, str) or not item or len(item.encode("utf-8")) > 500
            for item in unsupported
        ) or unsupported != sorted(set(unsupported)):
            raise ValueError("invalid unsupported API usage")
        observation_digest = _sha256(observation)
    features = []
    for check in check_plan["featureChecks"]:
        observed = observed_by_id.get(check["featureId"])
        if observed is None:
            outcome = "not_observed"
            status = None
            value = None
            observed_type = None
            diagnostic = None
            failed = []
            type_compared = False
        else:
            status = observed["status"]
            value = observed["value"]
            observed_type = _value_type(value)
            type_compared = status == "resolved"
            status_matches = status == check["expectedStatus"]
            type_matches = _type_matches(check["expectedValueType"], observed_type)
            if status_matches and type_matches:
                outcome = "matched"
                diagnostic = None
                failed = []
            elif status_matches:
                outcome = "drifted"
                diagnostic = "value_type_drift"
                failed = []
            else:
                outcome = "drifted"
                diagnostic = _diagnostic(status)
                failed = _failed_checks(check, status)
        features.append({
            "runtimeCheckId": check["id"],
            "featureId": check["featureId"],
            "systemIds": list(check["systemIds"]),
            "expectedStatus": check["expectedStatus"],
            "expectedValueType": check["expectedValueType"],
            "observedStatus": status,
            "observedValueType": observed_type,
            "observedValue": value,
            "outcome": outcome,
            "diagnosticCode": diagnostic,
            "failedRuntimeChecks": failed,
            "typeCompared": type_compared,
            "valueCompared": False,
            "runtimeVerified": False,
        })
    feature_by_id = {item["featureId"]: item for item in features}
    systems = []
    for system in check_plan["systemPlans"]:
        outcomes = [feature_by_id[item]["outcome"] for item in system["featureIds"]]
        outcome = (
            "drifted" if "drifted" in outcomes
            else "not_observed" if "not_observed" in outcomes
            else "matched"
        )
        systems.append({
            "systemId": system["systemId"],
            "featureIds": list(system["featureIds"]),
            "outcome": outcome,
            "driftedFeatureIds": [
                item for item in system["featureIds"]
                if feature_by_id[item]["outcome"] == "drifted"
            ],
            "notObservedFeatureIds": [
                item for item in system["featureIds"]
                if feature_by_id[item]["outcome"] == "not_observed"
            ],
            "systemVerified": False,
            "causalityProven": False,
            "gameplayVerified": False,
        })
    global_diagnostics = []
    if observation is not None and not features:
        global_diagnostics.append({
            "code": "empty_runtime_check_plan",
            "count": 0,
            "classification": "runtime_contract_failure",
        })
    if unsupported:
        global_diagnostics.append({
            "code": "unsupported_api_usage",
            "count": len(unsupported),
            "classification": "runtime_contract_failure",
        })
    matched = sum(item["outcome"] == "matched" for item in features)
    drifted = sum(item["outcome"] == "drifted" for item in features)
    not_observed = sum(item["outcome"] == "not_observed" for item in features)
    comparison_complete = (
        observation is not None and bool(features) and complete and not_observed == 0
    )
    comparison_passed = (
        None if observation is None
        else comparison_complete and drifted == 0 and not global_diagnostics
    )
    return {
        "schemaVersion": COMPARISON_SCHEMA_VERSION,
        "placeId": check_plan["placeId"],
        "sourceRuntimeCheckPlanSha256": _sha256(check_plan),
        "sourceRuntimeObservationSha256": observation_digest,
        "environment": environment,
        "observationSupplied": observation is not None,
        "observationComplete": complete,
        "comparisonComplete": comparison_complete,
        "comparisonPassed": comparison_passed,
        "driftDetected": drifted > 0 or bool(global_diagnostics),
        "valueComparisonAvailable": False,
        "features": features,
        "systems": systems,
        "globalDiagnostics": global_diagnostics,
        "unsupportedApiUsages": list(unsupported),
        "summary": {
            "expectedFeatures": len(features),
            "matchedFeatures": matched,
            "driftedFeatures": drifted,
            "notObservedFeatures": not_observed,
            "unsupportedApiUsages": len(unsupported),
        },
        "readOnly": True,
        "sourceAuthenticityVerified": False,
        "runtimeVerified": False,
        "liveGameVerified": False,
        "serverAuthorityVerified": False,
        "causalityProven": False,
        "gameplayVerified": False,
    }
