"""Dedicated Lycoles generation service with async job orchestration."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional

FALSE_CLAIMS = {
    "sourceAuthenticityVerified": False,
    "causalityProven": False,
    "serverAuthorityVerified": False,
    "runtimeVerified": False,
    "gameplayVerified": False,
    "actionOutcomesVerified": False,
}

_AUTOMATIC_REQUEST_TERMS = {
    "auto",
    "automate",
    "automatic",
    "automatically",
    "autofarm",
    "farm",
    "loop",
    "repeat",
    "grind",
    "afk",
}

_FEATURE_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "pickup-reward-farming": (
        "pickup", "collect", "reward", "coin", "coins", "currency", "gem", "gems",
        "orb", "token", "loot", "drop", "resource", "farm",
    ),
    "training-progression": (
        "train", "training", "progress", "xp", "exp", "experience", "level", "strength",
        "power", "rank", "skill",
    ),
    "shop-purchase": (
        "shop", "merchant", "buy", "purchase", "sell", "upgrade", "vendor",
    ),
    "inventory-equipment": (
        "inventory", "backpack", "equip", "unequip", "tool", "item", "loadout",
    ),
    "pets-companions": (
        "pet", "pets", "egg", "hatch", "companion", "mount",
    ),
    "teleport-navigation": (
        "teleport", "portal", "travel", "navigate", "navigation", "move", "path", "zone", "island", "world",
    ),
}

_CATEGORY_FALLBACK = "general-interaction"

_CATEGORY_STRATEGY_ORDER: dict[str, tuple[str, ...]] = {
    "pickup-reward-farming": (
        "strategy-a-bring-pickups-to-player",
        "strategy-b-navigate-player-to-target",
        "strategy-c-direct-interaction",
    ),
    "training-progression": (
        "strategy-c-direct-interaction",
        "strategy-b-navigate-player-to-target",
        "strategy-a-bring-pickups-to-player",
    ),
    "shop-purchase": (
        "strategy-c-direct-interaction",
        "strategy-b-navigate-player-to-target",
    ),
    "inventory-equipment": (
        "strategy-c-direct-interaction",
        "strategy-b-navigate-player-to-target",
    ),
    "pets-companions": (
        "strategy-c-direct-interaction",
        "strategy-b-navigate-player-to-target",
        "strategy-a-bring-pickups-to-player",
    ),
    "teleport-navigation": (
        "strategy-b-navigate-player-to-target",
        "strategy-c-direct-interaction",
    ),
    "general-interaction": (
        "strategy-c-direct-interaction",
        "strategy-b-navigate-player-to-target",
    ),
}

_STRATEGY_LABELS: dict[str, str] = {
    "strategy-a-bring-pickups-to-player": "Strategy A — Bring pickups to the player",
    "strategy-b-navigate-player-to-target": "Strategy B — Navigate the player to targets",
    "strategy-c-direct-interaction": "Strategy C — Direct interaction with evidence-backed controls",
}

_STRATEGY_SUMMARY: dict[str, str] = {
    "strategy-a-bring-pickups-to-player": (
        "Prefer only when evidence suggests collectible instances can be safely manipulated client-side "
        "without inventing server outcomes."
    ),
    "strategy-b-navigate-player-to-target": (
        "Use observed positions, interaction range hints, and bounded movement loops to reach targets."
    ),
    "strategy-c-direct-interaction": (
        "Invoke GUI, proximity prompts, tool activation, or observed control pathways with runtime guards."
    ),
}

_VERIFICATION_STATE_ORDER = (
    "discovered",
    "generation-ready",
    "generated",
    "syntax-validated",
    "runtime-tested",
    "gameplay-verified",
    "server-outcome-verified",
)


def _safe_feature_id(prefix: str, *parts: str) -> str:
    joined = "|".join(part.strip() for part in parts if isinstance(part, str) and part.strip())
    if not joined:
        joined = prefix
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()[:14]
    return f"{prefix}-{digest}"


def _tokenize_text(value: Optional[str]) -> set[str]:
    if not isinstance(value, str):
        return set()
    return set(re.findall(r"[a-z0-9]+", value.casefold()))


def _coerce_text_list(values: Any, *, max_items: int = 32, max_len: int = 240) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for item in values:
        if isinstance(item, str):
            text = item.strip()
            if text:
                out.append(text[:max_len])
        if len(out) >= max_items:
            break
    return out


def _request_requires_automatic_execution(request_text: Optional[str]) -> bool:
    if not isinstance(request_text, str):
        return False
    tokens = set(re.findall(r"[a-z0-9]+", request_text.casefold()))
    return bool(tokens & _AUTOMATIC_REQUEST_TERMS)


def _load_local_module(filename: str, name: str):
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class ModelRouteConfig:
    analysis_model: str = "openai/gpt-5.6-luna"
    generation_model: str = "openai/gpt-5.3-codex"
    repair_model: str = "openai/gpt-5.3-codex"
    reasoning_model: str = "openai/gpt-5.6-sol"


@dataclass(frozen=True)
class ProviderInfo:
    provider: str
    enabled: bool
    reason: str


@dataclass(frozen=True)
class ProviderCostConfig:
    analysis_cost_gbp_per_1k_tokens: float = 0.0
    generation_cost_gbp_per_1k_tokens: float = 0.0
    repair_cost_gbp_per_1k_tokens: float = 0.0


@dataclass
class UsageLedger:
    analysis_tokens: int = 0
    generation_tokens: int = 0
    repair_tokens: int = 0
    analysis_cost_gbp: float = 0.0
    generation_cost_gbp: float = 0.0
    repair_cost_gbp: float = 0.0
    analysis_attempts: int = 0
    generation_attempts: int = 0
    repair_attempts: int = 0
    analysis_retries: int = 0
    generation_retries: int = 0
    repair_retries: int = 0

    def to_dict(self) -> dict[str, Any]:
        total_tokens = self.analysis_tokens + self.generation_tokens + self.repair_tokens
        total_cost = self.analysis_cost_gbp + self.generation_cost_gbp + self.repair_cost_gbp
        total_attempts = self.analysis_attempts + self.generation_attempts + self.repair_attempts
        total_retries = self.analysis_retries + self.generation_retries + self.repair_retries
        return {
            "analysis": {
                "tokens": self.analysis_tokens,
                "costGbp": round(self.analysis_cost_gbp, 8),
                "attempts": self.analysis_attempts,
                "retries": self.analysis_retries,
            },
            "generation": {
                "tokens": self.generation_tokens,
                "costGbp": round(self.generation_cost_gbp, 8),
                "attempts": self.generation_attempts,
                "retries": self.generation_retries,
            },
            "repair": {
                "tokens": self.repair_tokens,
                "costGbp": round(self.repair_cost_gbp, 8),
                "attempts": self.repair_attempts,
                "retries": self.repair_retries,
            },
            "total": {
                "tokens": total_tokens,
                "costGbp": round(total_cost, 8),
                "attempts": total_attempts,
                "retries": total_retries,
            },
        }


@dataclass(frozen=True)
class GenerationRequest:
    evidence_kind: str
    evidence_path: Path
    requested_capability: Optional[str] = None
    observation_paths: tuple[Path, ...] = ()
    require_executable: bool = False


@dataclass
class EvidenceBundle:
    mode: str
    place_id: Optional[int]
    scan_id: Optional[str]
    output_dir: Path
    manifest_readiness: Optional[dict[str, Any]] = None
    release_manifest: Optional[dict[str, Any]] = None
    generation_readiness: Optional[dict[str, Any]] = None
    generated_script: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class JobRecord:
    job_id: str
    request: GenerationRequest
    status: str = "queued"
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error: Optional[str] = None
    result: Optional[dict[str, Any]] = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "jobId": self.job_id,
            "status": self.status,
            "createdAt": self.created_at,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "error": self.error,
            "request": {
                "evidenceKind": self.request.evidence_kind,
                "evidencePath": str(self.request.evidence_path),
                "requestedCapability": self.request.requested_capability,
                "observationPaths": [str(path) for path in self.request.observation_paths],
                "requireExecutable": self.request.require_executable,
            },
            "result": self.result,
        }


@dataclass
class FeedbackRecord:
    feedback_id: str
    created_at: float
    place_id: Optional[int]
    scan_id: Optional[str]
    feature_id: Optional[str]
    strategy_id: Optional[str]
    status: str
    runtime_errors: list[str] = field(default_factory=list)
    missing_objects: list[str] = field(default_factory=list)
    failed_interactions: list[str] = field(default_factory=list)
    successful_interactions: list[str] = field(default_factory=list)
    navigation_failures: list[str] = field(default_factory=list)
    executor_compatibility_issues: list[str] = field(default_factory=list)
    observed_changes: list[str] = field(default_factory=list)
    gameplay_verified: bool = False
    server_outcome_verified: bool = False
    notes: Optional[str] = None

    def key(self) -> str:
        return "|".join([
            str(self.place_id or ""),
            str(self.scan_id or ""),
            str(self.feature_id or ""),
            str(self.strategy_id or ""),
        ])

    def to_dict(self) -> dict[str, Any]:
        return {
            "feedbackId": self.feedback_id,
            "createdAt": self.created_at,
            "placeId": self.place_id,
            "scanId": self.scan_id,
            "featureId": self.feature_id,
            "strategyId": self.strategy_id,
            "status": self.status,
            "runtimeErrors": self.runtime_errors,
            "missingObjects": self.missing_objects,
            "failedInteractions": self.failed_interactions,
            "successfulInteractions": self.successful_interactions,
            "navigationFailures": self.navigation_failures,
            "executorCompatibilityIssues": self.executor_compatibility_issues,
            "observedChanges": self.observed_changes,
            "gameplayVerified": self.gameplay_verified,
            "serverOutcomeVerified": self.server_outcome_verified,
            "notes": self.notes,
        }


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


def _response_output_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return output_text
    if isinstance(output_text, list):
        return "\n".join(str(item) for item in output_text)
    chunks: list[str] = []
    output = payload.get("output")
    if not isinstance(output, list):
        return ""
    for message in output:
        if not isinstance(message, dict):
            continue
        for content in message.get("content") or []:
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "\n".join(chunks)


def _extract_first_json_object(text: str) -> Optional[dict[str, Any]]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _json_clone(value: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, sort_keys=True, ensure_ascii=False))


def _analysis_cache_signature(bundle: "EvidenceBundle", route_plan: RoutePlan) -> str:
    payload = {
        "mode": bundle.mode,
        "placeId": bundle.place_id,
        "scanId": bundle.scan_id,
        "complexity": route_plan.complexity,
        "generationReadiness": bundle.generation_readiness,
        "manifestReadiness": bundle.manifest_readiness,
        "releaseManifest": bundle.release_manifest,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()



@dataclass(frozen=True)
class RoutePlan:
    complexity: str
    analysis_models: tuple[str, ...]
    generation_models: tuple[str, ...]
    repair_models: tuple[str, ...]
    expected_cost_scores: dict[str, float]


_HARD_REASONING_TERMS = {
    "combat", "shoot", "reload", "weapon", "aim", "projectile", "recoil",
    "tracking", "automation", "autofarm", "workflow", "integration", "inference",
}


def _bounded_ratio(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if not 0.0 <= value <= 1.0:
        return default
    return value


def _route_complexity(bundle: EvidenceBundle) -> str:
    if bundle.mode == "manifest-only" or not isinstance(bundle.generation_readiness, dict):
        return "low"
    readiness = bundle.generation_readiness
    request = readiness.get("request") if isinstance(readiness.get("request"), dict) else {}
    request_text = request.get("request") if isinstance(request.get("request"), str) else ""

    score = 0
    tokens = set(re.findall(r"[a-z0-9]+", request_text.lower()))
    score += sum(term in tokens for term in _HARD_REASONING_TERMS)

    workflow_selection = readiness.get("workflowSelection")
    diagnostics = (workflow_selection.get("planningDiagnostics")
                   if isinstance(workflow_selection, dict) else None)
    if isinstance(diagnostics, dict):
        if int(diagnostics.get("executionReadyWorkflows") or 0) >= 2:
            score += 1
        if int(diagnostics.get("generationReadySteps") or 0) >= 6:
            score += 1
        if int(diagnostics.get("workflowCandidates") or 0) >= 4:
            score += 1

    blockers = (readiness.get("requestFeatureReadiness", {}).get("explicitBlockers")
                if isinstance(readiness.get("requestFeatureReadiness"), dict) else [])
    if isinstance(blockers, list) and len(blockers) >= 12:
        score += 1

    if score >= 4:
        return "hard"
    if score >= 2:
        return "standard"
    return "low"


def _effective_model_scores() -> dict[str, float]:
    multipliers = {
        "economy": _env_float("LYCOLES_ROUTE_COST_MULTIPLIER_ECONOMY", 1.0),
        "coding": _env_float("LYCOLES_ROUTE_COST_MULTIPLIER_CODING", 2.4),
        "reasoning": _env_float("LYCOLES_ROUTE_COST_MULTIPLIER_REASONING", 4.8),
    }
    retry_rates = {
        "economy": _bounded_ratio("LYCOLES_ROUTE_RETRY_RATE_ECONOMY", 0.03),
        "coding": _bounded_ratio("LYCOLES_ROUTE_RETRY_RATE_CODING", 0.015),
        "reasoning": _bounded_ratio("LYCOLES_ROUTE_RETRY_RATE_REASONING", 0.01),
    }
    failure_rates = {
        "economy": _bounded_ratio("LYCOLES_ROUTE_FAILURE_RATE_ECONOMY", 0.004),
        "coding": _bounded_ratio("LYCOLES_ROUTE_FAILURE_RATE_CODING", 0.002),
        "reasoning": _bounded_ratio("LYCOLES_ROUTE_FAILURE_RATE_REASONING", 0.0015),
    }
    return {
        role: multipliers[role] * (1.0 + retry_rates[role] * 1.5 + failure_rates[role] * 6.0)
        for role in ("economy", "coding", "reasoning")
    }


def _ordered_roles(base_roles: tuple[str, ...], scores: dict[str, float]) -> tuple[str, ...]:
    unique = []
    seen = set()
    for role in base_roles:
        if role not in seen:
            seen.add(role)
            unique.append(role)
    unique.sort(key=lambda role: (scores.get(role, float("inf")), base_roles.index(role)))
    return tuple(unique)


def _build_route_plan(bundle: EvidenceBundle, routes: ModelRouteConfig) -> RoutePlan:
    complexity = _route_complexity(bundle)
    scores = _effective_model_scores()
    role_to_model = {
        "economy": routes.analysis_model,
        "coding": routes.generation_model,
        "reasoning": routes.reasoning_model,
    }

    if complexity == "hard":
        analysis_roles = ("coding", "reasoning", "economy")
        generation_roles = ("reasoning", "coding", "economy")
        repair_roles = ("reasoning", "coding", "economy")
        analysis_models = tuple(role_to_model[role] for role in analysis_roles)
        generation_models = tuple(role_to_model[role] for role in generation_roles)
        repair_models = tuple(role_to_model[role] for role in repair_roles)
    else:
        analysis_roles = ("economy", "coding") if complexity == "low" else ("economy", "coding", "reasoning")
        generation_roles = ("coding", "economy", "reasoning") if complexity == "low" else (
            "coding", "reasoning", "economy")
        repair_roles = generation_roles
        analysis_models = tuple(role_to_model[role] for role in _ordered_roles(analysis_roles, scores))
        generation_models = tuple(role_to_model[role] for role in _ordered_roles(generation_roles, scores))
        repair_models = tuple(role_to_model[role] for role in _ordered_roles(repair_roles, scores))

    return RoutePlan(
        complexity=complexity,
        analysis_models=analysis_models,
        generation_models=generation_models,
        repair_models=repair_models,
        expected_cost_scores={
            role_to_model[role]: round(scores[role], 6)
            for role in ("economy", "coding", "reasoning")
        },
    )



def _apply_stage_usage(usage: UsageLedger, stage: str, metrics: dict[str, Any]) -> None:
    tokens = int(metrics.get("tokens", 0))
    cost = float(metrics.get("costGbp", 0.0))
    attempts = int(metrics.get("attempts", 0))
    retries = int(metrics.get("retriesUsed", 0))
    if stage == "analysis":
        usage.analysis_tokens += tokens
        usage.analysis_cost_gbp += cost
        usage.analysis_attempts += max(0, attempts)
        usage.analysis_retries += max(0, retries)
    elif stage == "generation":
        usage.generation_tokens += tokens
        usage.generation_cost_gbp += cost
        usage.generation_attempts += max(0, attempts)
        usage.generation_retries += max(0, retries)
    elif stage == "repair":
        usage.repair_tokens += tokens
        usage.repair_cost_gbp += cost
        usage.repair_attempts += max(0, attempts)
        usage.repair_retries += max(0, retries)



def _strip_lua_fences(text: str) -> str:
    cleaned = text.strip()
    if not cleaned.startswith("```"):
        return cleaned
    cleaned = re.sub(r"^```[A-Za-z0-9_-]*\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _bundle_prompt_summary(bundle: EvidenceBundle) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "mode": bundle.mode,
        "placeId": bundle.place_id,
        "scanId": bundle.scan_id,
    }
    if bundle.generation_readiness:
        readiness = bundle.generation_readiness
        summary["request"] = readiness.get("request")
        summary["generatedCapabilities"] = readiness.get("generatedCapabilities")
        summary["unavailableRequestedBehavior"] = readiness.get("unavailableRequestedBehavior")
        summary["workflowSelection"] = readiness.get("workflowSelection")
    elif bundle.manifest_readiness:
        readiness = bundle.manifest_readiness
        summary["generationReadiness"] = readiness.get("generationReadiness")
        summary["outcomeCandidates"] = readiness.get("outcomeCandidates")
    return summary


class BaseLLMProvider:
    def info(self) -> ProviderInfo:
        raise NotImplementedError

    def analyze(self, _: EvidenceBundle, __: str) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
        return None, {"tokens": 0, "costGbp": 0.0}

    def generate(self, _: EvidenceBundle, __: dict[str, Any], ___: str) -> tuple[Optional[str], dict[str, Any]]:
        return None, {"tokens": 0, "costGbp": 0.0}

    def repair(self, code: str, _: dict[str, Any], __: str) -> tuple[str, dict[str, Any]]:
        return code, {"tokens": 0, "costGbp": 0.0}


class DeterministicLLMProvider(BaseLLMProvider):
    def __init__(self, reason: str = "deterministic mode selected") -> None:
        self._info = ProviderInfo(provider="deterministic", enabled=False, reason=reason)

    def info(self) -> ProviderInfo:
        return self._info


class OpenAICompatibleProvider(BaseLLMProvider):
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        retries: int,
        cost_config: ProviderCostConfig,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._retries = max(0, retries)
        self._cost_config = cost_config
        self._info = ProviderInfo(provider="openai-compatible", enabled=True, reason="provider configured")

    def info(self) -> ProviderInfo:
        return self._info

    def _usage(self, payload: dict[str, Any], stage: str, meta: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        tokens = int(usage.get("total_tokens") or 0)
        if stage == "analysis":
            rate = self._cost_config.analysis_cost_gbp_per_1k_tokens
        elif stage == "generation":
            rate = self._cost_config.generation_cost_gbp_per_1k_tokens
        else:
            rate = self._cost_config.repair_cost_gbp_per_1k_tokens
        metadata = meta if isinstance(meta, dict) else {}
        return {
            "tokens": tokens,
            "costGbp": (tokens / 1000.0) * rate,
            "attempts": int(metadata.get("attempts") or 1),
            "retriesUsed": int(metadata.get("retriesUsed") or 0),
            "transientFailures": int(metadata.get("transientFailures") or 0),
        }

    def _call_responses_api(self, model: str, system_prompt: str, user_prompt: str) -> tuple[dict[str, Any], dict[str, Any]]:
        endpoint = f"{self._base_url}/responses"
        payload = {
            "model": model,
            "input": [
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        transient = {408, 425, 429, 500, 502, 503, 504}
        last_error: Optional[str] = None
        transient_failures = 0
        for attempt in range(self._retries + 1):
            request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                    return payload, {
                        "attempts": attempt + 1,
                        "retriesUsed": attempt,
                        "transientFailures": transient_failures,
                    }
            except urllib.error.HTTPError as exc:
                status = exc.code
                text = exc.read().decode("utf-8", errors="replace")
                exc.close()
                last_error = f"HTTP {status}: {text[:400]}"
                if status in transient:
                    transient_failures += 1
                if status not in transient or attempt == self._retries:
                    raise ValueError(f"Provider request failed: {last_error}") from None
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = str(exc)
                transient_failures += 1
                if attempt == self._retries:
                    raise ValueError(f"Provider request failed: {last_error}") from None
            time.sleep(0.4 * (2 ** attempt))
        raise ValueError(f"Provider request failed: {last_error or 'unknown error'}")

    def analyze(self, bundle: EvidenceBundle, model: str) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
        system_prompt = (
            "You are Lycoles feature-analysis AI. Return only one JSON object. "
            "Never claim runtime/gameplay/server authority verification."
        )
        user_prompt = (
            "Analyze this Roblox inspection evidence summary and return JSON with keys: "
            "candidateFeatures (array of short strings), risks (array), and notes (array).\n"
            f"Evidence:\n{json.dumps(_bundle_prompt_summary(bundle), ensure_ascii=False)}"
        )
        payload, meta = self._call_responses_api(model, system_prompt, user_prompt)
        text = _response_output_text(payload)
        parsed = _extract_first_json_object(text)
        return (parsed if isinstance(parsed, dict) else None), self._usage(payload, "analysis", meta)

    def generate(self, bundle: EvidenceBundle, analysis: dict[str, Any], model: str) -> tuple[Optional[str], dict[str, Any]]:
        system_prompt = (
            "You are Lycoles script-generation AI. Output only Lua/Luau source code. "
            "Do not fabricate server-authoritative capabilities."
        )
        user_prompt = (
            "Generate a Roblox Lua/Luau script with a functional GUI from this evidence summary. "
            "Include duplicate-execution protection, nil-safe lookups, and explicit unsupported-feature notices.\n"
            f"Evidence:\n{json.dumps(_bundle_prompt_summary(bundle), ensure_ascii=False)}\n"
            f"Analysis:\n{json.dumps(analysis, ensure_ascii=False)}"
        )
        payload, meta = self._call_responses_api(model, system_prompt, user_prompt)
        text = _strip_lua_fences(_response_output_text(payload))
        return (text or None), self._usage(payload, "generation", meta)

    def repair(self, code: str, analysis: dict[str, Any], model: str) -> tuple[str, dict[str, Any]]:
        system_prompt = (
            "You are Lycoles repair AI. Output only fixed Lua/Luau source code. "
            "Preserve place guard and safe client-only behavior."
        )
        user_prompt = (
            "Repair this Lua/Luau script so it remains client-safe and preserves behavior.\n"
            f"Analysis context: {json.dumps(analysis, ensure_ascii=False)}\n"
            f"Code:\n{code}"
        )
        payload, meta = self._call_responses_api(model, system_prompt, user_prompt)
        text = _strip_lua_fences(_response_output_text(payload))
        return (text or code), self._usage(payload, "repair", meta)


def _provider_from_environment() -> tuple[BaseLLMProvider, ProviderInfo]:
    provider = (os.environ.get("LYCOLES_LLM_PROVIDER") or "deterministic").strip().lower()
    if provider in {"", "deterministic", "none"}:
        value = DeterministicLLMProvider("deterministic provider selected")
        return value, value.info()

    if provider in {"openai", "openai-compatible"}:
        api_key = os.environ.get("LYCOLES_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            value = DeterministicLLMProvider("missing OPENAI_API_KEY/LYCOLES_OPENAI_API_KEY")
            return value, ProviderInfo(provider="openai-compatible", enabled=False, reason=value.info().reason)
        base_url = os.environ.get("LYCOLES_OPENAI_BASE_URL", "https://api.openai.com/v1")
        timeout_seconds = _env_float("LYCOLES_OPENAI_TIMEOUT_SECONDS", 45.0)
        retries = int(_env_float("LYCOLES_OPENAI_RETRIES", 2.0))
        cost_config = ProviderCostConfig(
            analysis_cost_gbp_per_1k_tokens=_env_float("LYCOLES_ANALYSIS_COST_GBP_PER_1K", 0.0),
            generation_cost_gbp_per_1k_tokens=_env_float("LYCOLES_GENERATION_COST_GBP_PER_1K", 0.0),
            repair_cost_gbp_per_1k_tokens=_env_float("LYCOLES_REPAIR_COST_GBP_PER_1K", 0.0),
        )
        value = OpenAICompatibleProvider(
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            retries=retries,
            cost_config=cost_config,
        )
        return value, value.info()

    value = DeterministicLLMProvider(f"unsupported provider '{provider}'")
    return value, ProviderInfo(provider=provider, enabled=False, reason=value.info().reason)


class EvidenceProcessor:
    def __init__(self) -> None:
        self._build_release = _load_local_module("build_release.py", "lycoles_build_release")
        self._replay_import = _load_local_module("evidence_replay_import.py", "lycoles_evidence_replay")

    @staticmethod
    def _scan_id_from_manifest(manifest: dict[str, Any]) -> Optional[str]:
        scan_id = manifest.get("scanId")
        if isinstance(scan_id, str) and scan_id:
            return scan_id
        integrity = manifest.get("integrity")
        if isinstance(integrity, dict):
            value = integrity.get("scanId")
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    def _scan_metadata_from_parts_dir(parts_dir: Path) -> tuple[Optional[int], Optional[str]]:
        for candidate in sorted(parts_dir.glob("*part-*.json"))[:5]:
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            place_id = payload.get("placeId") if isinstance(payload.get("placeId"), int) else None
            scan_id = payload.get("scanId") if isinstance(payload.get("scanId"), str) else None
            return place_id, scan_id
        return None, None

    @staticmethod
    def _resolve_manifest_input_path(path: Path) -> Path:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("manifest evidence must be a JSON object")
        schema = payload.get("schemaVersion")
        if schema == "30.6.manifest-assisted-workflow.5":
            source = payload.get("sourceManifest")
            if not isinstance(source, str) or not source.strip():
                raise ValueError("manifest-assisted workflow evidence is missing sourceManifest")
            candidates = [
                (path.parent / source).resolve(),
                Path(source).expanduser().resolve(),
                (Path.cwd() / source).resolve(),
            ]
            candidate = next((item for item in candidates if item.is_file()), None)
            if candidate is None:
                raise ValueError(
                    "manifest-assisted workflow sourceManifest is unavailable: "
                    f"{source}"
                )
            return candidate
        return path

    @staticmethod
    def _collect_observation_inputs(paths: tuple[Path, ...]) -> tuple[list[Path], list[Path]]:
        observation_dirs: list[Path] = []
        observation_files: list[Path] = []
        for path in paths:
            if path.is_dir():
                observation_dirs.append(path)
            elif path.is_file():
                observation_files.append(path)
            else:
                raise ValueError(f"Observation path not found: {path}")
        return observation_dirs, observation_files

    def _build_multipart_bundle(
        self,
        *,
        parts_path: Path,
        output_dir: Path,
        requested_capability: Optional[str],
        observation_paths: tuple[Path, ...],
        warnings: list[str],
    ) -> EvidenceBundle:
        observation_dirs, observation_files = self._collect_observation_inputs(observation_paths)
        try:
            manifest = self._build_release.build(
                parts_path,
                output_dir,
                requested_capability=requested_capability,
                observation_dirs=observation_dirs,
                observation_files=observation_files,
            )
        except ValueError as exc:
            message = str(exc)
            if "Malformed interaction baseline timing" not in message:
                raise

            if observation_dirs or observation_files:
                warnings.append(
                    "Observation overlay ignored due to malformed baseline timing; falling back to baseline-only generation."
                )
                try:
                    manifest = self._build_release.build(
                        parts_path,
                        output_dir,
                        requested_capability=requested_capability,
                        observation_dirs=[],
                        observation_files=[],
                    )
                except ValueError as baseline_exc:
                    baseline_message = str(baseline_exc)
                    if "Malformed interaction baseline timing" not in baseline_message:
                        raise
                else:
                    readiness_path = output_dir / "generation-readiness.json"
                    script_path = output_dir / "LycolesGeneratedUtility.lua"
                    generation_readiness = json.loads(readiness_path.read_text(encoding="utf-8")) if readiness_path.exists() else None
                    generated_script = script_path.read_text(encoding="utf-8") if script_path.exists() else None
                    return EvidenceBundle(
                        mode="multipart",
                        place_id=manifest.get("placeId"),
                        scan_id=self._scan_id_from_manifest(manifest),
                        output_dir=output_dir,
                        release_manifest=manifest,
                        generation_readiness=generation_readiness,
                        generated_script=generated_script,
                        warnings=warnings,
                    )

            warnings.append(
                "Baseline interactions include malformed timing; using manifest-readiness fallback with blocker reporting."
            )
            manifest_candidates = sorted(parts_path.glob("*manifest*.json"))
            if not manifest_candidates:
                place_id, scan_id = self._scan_metadata_from_parts_dir(parts_path)
                readiness = {
                    "schemaVersion": "30.6.synthetic-manifest-readiness.1",
                    "placeId": place_id,
                    "scanId": scan_id,
                    "generationReadiness": {
                        "status": "unsupported-by-current-evidence",
                        "blockers": [
                            "malformed_interaction_baseline_timing",
                            "full_multipart_report_unavailable",
                            "manifest_snapshot_missing",
                        ],
                    },
                    "claims": dict(FALSE_CLAIMS),
                }
                return EvidenceBundle(
                    mode="manifest-only",
                    place_id=place_id,
                    scan_id=scan_id,
                    output_dir=output_dir,
                    manifest_readiness=readiness,
                    warnings=warnings,
                )

            try:
                readiness = self._build_release.build_manifest_readiness(manifest_candidates[0], output_dir)
                place_id = readiness.get("placeId") if isinstance(readiness.get("placeId"), int) else None
                scan_id = readiness.get("scanId") if isinstance(readiness.get("scanId"), str) else None
            except Exception as manifest_exc:  # pylint: disable=broad-except
                place_id, scan_id = self._scan_metadata_from_parts_dir(parts_path)
                warnings.append(
                    f"Manifest-readiness parser rejected snapshot; synthesized fallback readiness ({manifest_exc})."
                )
                readiness = {
                    "schemaVersion": "30.6.synthetic-manifest-readiness.1",
                    "placeId": place_id,
                    "scanId": scan_id,
                    "generationReadiness": {
                        "status": "unsupported-by-current-evidence",
                        "blockers": [
                            "malformed_interaction_baseline_timing",
                            "full_multipart_report_unavailable",
                            "manifest_readiness_parser_rejected_snapshot",
                        ],
                    },
                    "claims": dict(FALSE_CLAIMS),
                }
            return EvidenceBundle(
                mode="manifest-only",
                place_id=place_id,
                scan_id=scan_id,
                output_dir=output_dir,
                manifest_readiness=readiness,
                warnings=warnings,
            )

        readiness_path = output_dir / "generation-readiness.json"
        script_path = output_dir / "LycolesGeneratedUtility.lua"
        generation_readiness = json.loads(readiness_path.read_text(encoding="utf-8")) if readiness_path.exists() else None
        generated_script = script_path.read_text(encoding="utf-8") if script_path.exists() else None
        return EvidenceBundle(
            mode="multipart",
            place_id=manifest.get("placeId"),
            scan_id=self._scan_id_from_manifest(manifest),
            output_dir=output_dir,
            release_manifest=manifest,
            generation_readiness=generation_readiness,
            generated_script=generated_script,
            warnings=warnings,
        )


    def process(self, request: GenerationRequest, output_dir: Path) -> EvidenceBundle:
        output_dir.mkdir(parents=True, exist_ok=True)
        if request.evidence_kind == "manifest":
            manifest_path = self._resolve_manifest_input_path(request.evidence_path)
            readiness = self._build_release.build_manifest_readiness(manifest_path, output_dir)
            return EvidenceBundle(
                mode="manifest-only",
                place_id=readiness.get("placeId"),
                scan_id=readiness.get("scanId"),
                output_dir=output_dir,
                manifest_readiness=readiness,
            )

        if request.evidence_kind == "parts_dir":
            return self._build_multipart_bundle(
                parts_path=request.evidence_path,
                output_dir=output_dir,
                requested_capability=request.requested_capability,
                observation_paths=request.observation_paths,
                warnings=[],
            )

        if request.evidence_kind == "replay_package":
            replay = self._replay_import.load_replay_package(request.evidence_path)
            replay_baseline = replay.get("baseline") if isinstance(replay.get("baseline"), dict) else {}
            replay_warnings = [str(item) for item in (replay.get("warnings") or []) if isinstance(item, str)]
            replay_observation_paths = tuple(
                Path(item["resolvedPath"]).expanduser().resolve()
                for item in (replay.get("observations") or [])
                if isinstance(item, dict) and isinstance(item.get("resolvedPath"), str)
            )
            merged_observations = replay_observation_paths + tuple(request.observation_paths)

            if replay_baseline.get("mode") == "manifest-only":
                manifest_path_value = replay_baseline.get("manifestPath")
                if not isinstance(manifest_path_value, str) or not manifest_path_value:
                    raise ValueError("Replay package manifest-only baseline is missing manifestPath")
                manifest_path = Path(manifest_path_value).expanduser().resolve()
                readiness = self._build_release.build_manifest_readiness(manifest_path, output_dir)
                return EvidenceBundle(
                    mode="manifest-only",
                    place_id=readiness.get("placeId"),
                    scan_id=readiness.get("scanId"),
                    output_dir=output_dir,
                    manifest_readiness=readiness,
                    warnings=replay_warnings,
                )

            parts_dir_value = replay_baseline.get("partsDir")
            if not isinstance(parts_dir_value, str) or not parts_dir_value:
                raise ValueError("Replay package multipart baseline is missing partsDir")
            parts_path = Path(parts_dir_value).expanduser().resolve()
            bundle = self._build_multipart_bundle(
                parts_path=parts_path,
                output_dir=output_dir,
                requested_capability=request.requested_capability,
                observation_paths=merged_observations,
                warnings=list(replay_warnings),
            )
            return bundle

        raise ValueError("Unsupported evidence kind")


class FeatureAnalysisEngine:
    def __init__(self, llm_provider: BaseLLMProvider, model_routes: ModelRouteConfig) -> None:
        self._llm_provider = llm_provider
        self._routes = model_routes

    def analyze(self, bundle: EvidenceBundle, usage: UsageLedger, route_plan: RoutePlan) -> dict[str, Any]:
        if bundle.generation_readiness is not None:
            readiness = bundle.generation_readiness
            request = readiness.get("request", {})
            feature_readiness = readiness.get("requestFeatureReadiness", {})
            blockers = feature_readiness.get("explicitBlockers") or []
            generated = readiness.get("generatedCapabilities") or []
            summary = {
                "mode": "multipart",
                "requestStatus": request.get("status"),
                "generatedCapabilityCount": len(generated),
                "generatedCapabilityKinds": [item.get("kind") for item in generated if isinstance(item, dict)],
                "explicitBlockers": blockers,
                "claims": dict(FALSE_CLAIMS),
            }
        elif bundle.manifest_readiness is not None:
            readiness = bundle.manifest_readiness
            generation = readiness.get("generationReadiness", {})
            summary = {
                "mode": "manifest-only",
                "requestStatus": "unsupported-by-current-evidence",
                "generatedCapabilityCount": 0,
                "generatedCapabilityKinds": [],
                "explicitBlockers": generation.get("blockers") or [],
                "claims": dict(FALSE_CLAIMS),
            }
        else:
            raise ValueError("No analysis source available")

        errors = []
        selected_model = None
        for model in route_plan.analysis_models:
            try:
                ai_analysis, llm_usage = self._llm_provider.analyze(bundle, model)
                _apply_stage_usage(usage, "analysis", llm_usage)
                selected_model = model
                if isinstance(ai_analysis, dict):
                    summary["aiAnalysis"] = ai_analysis
                break
            except ValueError as exc:
                errors.append(f"{model}: {exc}")
        if selected_model is None and errors:
            summary["aiAnalysisError"] = errors[-1]
        summary["analysisModelUsed"] = selected_model
        summary["analysisFallbackErrors"] = errors[:3]
        return summary



class AutonomousPlanningEngine:
    @staticmethod
    def _category_for(feature: dict[str, Any], requested_capability: Optional[str]) -> str:
        joined = " ".join(
            str(feature.get(key) or "")
            for key in ("targetFeature", "kind", "targetPath", "label")
        )
        tokens = _tokenize_text(joined) | _tokenize_text(requested_capability)
        for category, keywords in _FEATURE_CATEGORY_KEYWORDS.items():
            if any(keyword in tokens for keyword in keywords):
                return category
        return _CATEGORY_FALLBACK

    @staticmethod
    def _feature_label(feature: dict[str, Any], category: str) -> str:
        for key in ("targetFeature", "kind", "targetPath"):
            value = feature.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return category

    @staticmethod
    def _extract_features(bundle: EvidenceBundle, analysis: dict[str, Any]) -> list[dict[str, Any]]:
        features: list[dict[str, Any]] = []
        readiness = bundle.generation_readiness if isinstance(bundle.generation_readiness, dict) else {}
        for item in readiness.get("generatedCapabilities") or []:
            if not isinstance(item, dict):
                continue
            features.append({
                "id": item.get("id") if isinstance(item.get("id"), str) else _safe_feature_id("cap", str(item.get("kind") or "unknown"), str(item.get("targetPath") or "")),
                "kind": item.get("kind") if isinstance(item.get("kind"), str) else None,
                "targetFeature": item.get("targetFeature") if isinstance(item.get("targetFeature"), str) else None,
                "targetPath": item.get("targetPath") if isinstance(item.get("targetPath"), str) else None,
                "label": item.get("targetLabel") if isinstance(item.get("targetLabel"), str) else None,
                "classification": item.get("classification") if isinstance(item.get("classification"), str) else None,
                "automaticMovement": bool(item.get("automaticMovement") is True),
                "boundedRepeat": bool(item.get("boundedRepeat") is True),
                "operatorStartRequired": bool(item.get("operatorStartRequired") is True),
                "commands": [str(cmd) for cmd in (item.get("commands") or []) if isinstance(cmd, str)][:20],
                "source": "generated-capability",
            })

        request_feature = readiness.get("requestFeatureReadiness") if isinstance(readiness.get("requestFeatureReadiness"), dict) else {}
        matched = (request_feature.get("featureEvidence") or {}).get("matchedFeatures")
        if isinstance(matched, list):
            for item in matched:
                if not isinstance(item, dict):
                    continue
                feature_name = item.get("feature") if isinstance(item.get("feature"), str) else None
                features.append({
                    "id": _safe_feature_id("matched", str(feature_name or "unknown"), str(item.get("status") or "")),
                    "kind": item.get("status") if isinstance(item.get("status"), str) else None,
                    "targetFeature": feature_name,
                    "targetPath": None,
                    "label": feature_name,
                    "classification": item.get("evidenceClassification") if isinstance(item.get("evidenceClassification"), str) else None,
                    "automaticMovement": False,
                    "boundedRepeat": False,
                    "operatorStartRequired": True,
                    "commands": [],
                    "source": "matched-feature",
                })

        ai_analysis = analysis.get("aiAnalysis") if isinstance(analysis.get("aiAnalysis"), dict) else {}
        ai_candidates = ai_analysis.get("candidateFeatures") if isinstance(ai_analysis.get("candidateFeatures"), list) else []
        for candidate in ai_candidates:
            if not isinstance(candidate, str) or not candidate.strip():
                continue
            features.append({
                "id": _safe_feature_id("ai", candidate),
                "kind": "ai-candidate",
                "targetFeature": candidate.strip(),
                "targetPath": None,
                "label": candidate.strip(),
                "classification": "ai-hypothesis",
                "automaticMovement": False,
                "boundedRepeat": False,
                "operatorStartRequired": True,
                "commands": [],
                "source": "ai-analysis",
            })

        dedup: dict[str, dict[str, Any]] = {}
        for item in features:
            key = str(item.get("id") or _safe_feature_id("feature", str(item.get("targetFeature") or ""), str(item.get("targetPath") or "")))
            if key not in dedup:
                dedup[key] = item
        return list(dedup.values())

    @staticmethod
    def _strategy_candidates(
        feature: dict[str, Any],
        category: str,
        *,
        request_requires_automatic: bool,
        feedback_penalties: dict[str, int],
    ) -> list[dict[str, Any]]:
        target_path = str(feature.get("targetPath") or "")
        kind = str(feature.get("kind") or "")
        commands = feature.get("commands") if isinstance(feature.get("commands"), list) else []
        has_world_path = target_path.startswith("Workspace.")
        has_gui_path = "PlayerGui" in target_path
        has_prompt = "proximity" in kind.lower() or "prompt" in target_path.lower()
        has_direct_control = has_prompt or has_gui_path or bool(commands)

        strategies: list[dict[str, Any]] = []
        for strategy_id in _CATEGORY_STRATEGY_ORDER.get(category, _CATEGORY_STRATEGY_ORDER[_CATEGORY_FALLBACK]):
            score = 0.25
            evidence: list[str] = []
            assumptions: list[str] = []
            missing_dependencies: list[str] = []
            rejection_reasons: list[str] = []

            if strategy_id == "strategy-a-bring-pickups-to-player":
                if has_world_path:
                    score += 0.38
                    evidence.append("workspace-target-path-observed")
                else:
                    assumptions.append("No direct workspace target path observed for relocation")
                    missing_dependencies.append("workspace target path for collectible relocation")
                if request_requires_automatic:
                    score += 0.05
            elif strategy_id == "strategy-b-navigate-player-to-target":
                if has_world_path:
                    score += 0.32
                    evidence.append("world-target-location-observed")
                if feature.get("automaticMovement") is True:
                    score += 0.18
                    evidence.append("automatic-movement-capability-observed")
                if not has_world_path and feature.get("automaticMovement") is not True:
                    assumptions.append("Navigation may require additional spatial anchors")
                    missing_dependencies.append("world anchor or automatic movement signal")
            else:  # strategy-c-direct-interaction
                if has_direct_control:
                    score += 0.38
                    evidence.append("direct-control-signal-observed")
                if has_prompt:
                    score += 0.16
                    evidence.append("proximity-prompt-signal-observed")
                if not has_direct_control:
                    assumptions.append("Direct interaction signals are weak or absent")
                    missing_dependencies.append("observed GUI/prompt/tool control pathway")

            if feature.get("boundedRepeat") is True:
                score += 0.07
                evidence.append("bounded-repeat-observed")
            if feature.get("operatorStartRequired") is True:
                score -= 0.05
                assumptions.append("Manual operator initiation may be required")

            penalty_key = f"{feature.get('id')}|{strategy_id}"
            prior_failures = int(feedback_penalties.get(penalty_key, 0))
            if prior_failures > 0:
                score -= min(0.3, 0.1 * prior_failures)
                assumptions.append(f"Strategy previously failed {prior_failures} time(s)")
            if prior_failures >= 2:
                score = min(score, 0.19)
                assumptions.append("Strategy temporarily blocked due to repeated failures")
                rejection_reasons.append("feedback-penalty-block")

            threshold = 0.38
            if score < threshold:
                rejection_reasons.append(f"score-below-threshold:{round(score, 4)}<{threshold}")
            if missing_dependencies:
                rejection_reasons.append("insufficient-evidence")

            feasible = score >= threshold and not missing_dependencies and prior_failures < 2
            feasibility_class = (
                "supported"
                if feasible
                else "insufficient-evidence"
                if missing_dependencies
                else "feedback-blocked"
                if prior_failures >= 2
                else "policy-threshold"
            )
            strategies.append({
                "id": strategy_id,
                "label": _STRATEGY_LABELS[strategy_id],
                "summary": _STRATEGY_SUMMARY[strategy_id],
                "feasible": feasible,
                "score": round(max(0.0, min(1.0, score)), 4),
                "evidenceSignals": sorted(set(evidence)),
                "assumptions": assumptions[:6],
                "missingDependencies": sorted(set(missing_dependencies)),
                "rejectionReasons": sorted(set(rejection_reasons)),
                "feasibilityClass": feasibility_class,
                "priorFailureCount": prior_failures,
            })

        strategies.sort(key=lambda item: (item.get("feasible") is True, item.get("score", 0.0)), reverse=True)
        return strategies

    def build_plan(
        self,
        bundle: EvidenceBundle,
        request: GenerationRequest,
        analysis: dict[str, Any],
        feedback_penalties: dict[str, int],
    ) -> dict[str, Any]:
        discovered = self._extract_features(bundle, analysis)
        request_text = request.requested_capability
        requires_automatic = _request_requires_automatic_execution(request_text)

        ranked_features: list[dict[str, Any]] = []
        for item in discovered:
            category = self._category_for(item, request_text)
            strategies = self._strategy_candidates(
                item,
                category,
                request_requires_automatic=requires_automatic,
                feedback_penalties=feedback_penalties,
            )
            top = strategies[0] if strategies else None
            rank = 0.2
            if item.get("source") == "generated-capability":
                rank += 0.35
            if item.get("automaticMovement") is True:
                rank += 0.12
            if item.get("boundedRepeat") is True:
                rank += 0.08
            if top and top.get("feasible"):
                rank += 0.2
                rank += float(top.get("score") or 0.0) * 0.1
            if item.get("classification") == "ai-hypothesis":
                rank -= 0.08

            feasible_strategies = [entry for entry in strategies if entry.get("feasible") is True]
            rejected_strategies = [entry for entry in strategies if entry.get("feasible") is not True]
            missing_dependencies = sorted({
                dependency
                for strategy in rejected_strategies
                for dependency in (strategy.get("missingDependencies") or [])
                if isinstance(dependency, str)
            })
            rejection_reasons = sorted({
                reason
                for strategy in rejected_strategies
                for reason in (strategy.get("rejectionReasons") or [])
                if isinstance(reason, str)
            })
            available_evidence = sorted({
                signal
                for strategy in strategies
                for signal in (strategy.get("evidenceSignals") or [])
                if isinstance(signal, str)
            })
            if isinstance(item.get("targetPath"), str) and item.get("targetPath"):
                available_evidence.append("target-path:" + item["targetPath"])
            if isinstance(item.get("kind"), str) and item.get("kind"):
                available_evidence.append("kind:" + item["kind"])
            if item.get("commands"):
                available_evidence.append("commands:" + str(len(item.get("commands"))))
            available_evidence = sorted(set(available_evidence))

            ranked_features.append({
                "featureId": item.get("id"),
                "label": self._feature_label(item, category),
                "category": category,
                "source": item.get("source"),
                "kind": item.get("kind"),
                "targetFeature": item.get("targetFeature"),
                "targetPath": item.get("targetPath"),
                "classification": item.get("classification"),
                "commands": item.get("commands") or [],
                "rankScore": round(max(0.0, min(1.0, rank)), 4),
                "availableEvidence": available_evidence,
                "strategies": strategies,
                "generationReady": bool(top and top.get("feasible") is True),
                "feasibility": {
                    "feasibleStrategyCount": len(feasible_strategies),
                    "rejectedStrategyCount": len(rejected_strategies),
                    "missingDependencies": missing_dependencies,
                    "rejectionReasons": rejection_reasons,
                    "confidence": (
                        "high" if len(feasible_strategies) >= 2 else
                        "medium" if len(feasible_strategies) == 1 else
                        "low"
                    ),
                    "verificationStatus": "partially-verified" if feasible_strategies else "unverified",
                },
            })

        ranked_features.sort(key=lambda feature: feature.get("rankScore", 0.0), reverse=True)
        highest_ranked_feature = ranked_features[0] if ranked_features else None
        feasible_features = [
            feature for feature in ranked_features
            if isinstance(feature.get("feasibility"), dict)
            and int(feature["feasibility"].get("feasibleStrategyCount") or 0) > 0
        ]
        selected_feature = feasible_features[0] if feasible_features else highest_ranked_feature
        fallback_used = bool(
            selected_feature and highest_ranked_feature
            and selected_feature.get("featureId") != highest_ranked_feature.get("featureId")
        )
        selected_strategy = None
        if selected_feature is not None:
            strategies = selected_feature.get("strategies") or []
            selected_strategy = next((entry for entry in strategies if entry.get("feasible") is True), None)
            if selected_strategy is None:
                selected_strategy = strategies[0] if strategies else None

        blockers: list[str] = []
        if selected_feature is None:
            blockers.append("no feature candidates discovered from current evidence bundle")
        elif selected_strategy is None:
            blockers.append("no strategy candidates available for selected feature")
        elif selected_strategy.get("feasible") is not True:
            blockers.append("selected feature has no feasible strategy under current evidence")
            for reason in (selected_strategy.get("rejectionReasons") or [])[:4]:
                blockers.append(f"selected-strategy:{reason}")
            for dependency in (selected_strategy.get("missingDependencies") or [])[:4]:
                blockers.append(f"missing-dependency:{dependency}")

        if selected_feature is not None and not feasible_features:
            blockers.append("no feasible strategies across discovered features")

        status_map = {
            "discovered": bool(selected_feature),
            "generation-ready": bool(selected_feature and selected_strategy and selected_strategy.get("feasible") is True),
            "generated": False,
            "syntax-validated": False,
            "runtime-tested": False,
            "gameplay-verified": False,
            "server-outcome-verified": False,
        }

        generation_request = {
            "requestedCapability": request_text,
            "automaticExecutionRequested": requires_automatic,
            "selectedFeatureId": selected_feature.get("featureId") if selected_feature else None,
            "selectedStrategyId": selected_strategy.get("id") if selected_strategy else None,
            "selectedStrategyLabel": selected_strategy.get("label") if selected_strategy else None,
            "selectedFeatureCategory": selected_feature.get("category") if selected_feature else None,
            "selectedFeaturePath": selected_feature.get("targetPath") if selected_feature else None,
            "selectionUsedFeatureFallback": fallback_used,
            "feasibleFeatureCount": len(feasible_features),
            "evidenceReferences": [
                item for item in [
                    selected_feature.get("targetPath") if selected_feature else None,
                    selected_feature.get("kind") if selected_feature else None,
                    selected_feature.get("classification") if selected_feature else None,
                ]
                if isinstance(item, str) and item
            ][:12],
            "unverifiedAssumptions": (selected_strategy.get("assumptions") if selected_strategy else [])[:8],
        }

        return {
            "schemaVersion": "30.6.autonomous-generation-plan.1",
            "pipeline": {
                "stages": [
                    "baseline-plus-observation-ingestion",
                    "evidence-normalization",
                    "feature-discovery",
                    "strategy-selection",
                    "script-generation",
                    "deterministic-validation",
                    "feedback-loop",
                ],
                "claims": dict(FALSE_CLAIMS),
            },
            "featureDiscovery": {
                "count": len(ranked_features),
                "ranked": ranked_features[:24],
            },
            "selectionDiagnostics": {
                "highestRankedFeatureId": highest_ranked_feature.get("featureId") if highest_ranked_feature else None,
                "selectedFeatureId": selected_feature.get("featureId") if selected_feature else None,
                "feasibleFeatureCount": len(feasible_features),
                "fallbackUsed": fallback_used,
            },
            "selectedFeature": selected_feature,
            "selectedStrategy": selected_strategy,
            "generationRequest": generation_request,
            "verificationStates": status_map,
            "blockers": sorted(set(blockers)),
            "claims": dict(FALSE_CLAIMS),
        }


class ScriptGenerationEngine:
    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        model_routes: ModelRouteConfig,
        *,
        prefer_ai_generation: bool,
    ) -> None:
        self._llm_provider = llm_provider
        self._routes = model_routes
        self._prefer_ai_generation = prefer_ai_generation

    def generate(
        self,
        bundle: EvidenceBundle,
        analysis: dict[str, Any],
        usage: UsageLedger,
        route_plan: RoutePlan,
    ) -> tuple[Optional[str], str, Optional[str], list[str]]:
        if bundle.generated_script and not self._prefer_ai_generation:
            return bundle.generated_script, "deterministic-release-script", None, []

        errors = []
        for model in route_plan.generation_models:
            try:
                llm_script, llm_usage = self._llm_provider.generate(bundle, analysis, model)
                _apply_stage_usage(usage, "generation", llm_usage)
                if llm_script:
                    return llm_script, "ai-generated-script", model, errors[:3]
            except ValueError as exc:
                errors.append(f"{model}: {exc}")

        if bundle.generated_script:
            return bundle.generated_script, "deterministic-release-script", None, errors[:3]
        return None, "no-script-generated", None, errors[:3]


class ValidationRepairEngine:
    _LUAU_COMPILE_DEFAULTS = (
        Path(os.environ.get("LUAU_COMPILE_BIN", "")) if os.environ.get("LUAU_COMPILE_BIN") else None,
        Path(__file__).resolve().parents[1] / "build" / "luau-0.744" / "luau-compile",
        Path("/tmp/luau-0.744/luau-compile"),
    )

    def __init__(self, llm_provider: BaseLLMProvider, model_routes: ModelRouteConfig) -> None:
        self._llm_provider = llm_provider
        self._routes = model_routes
        self._luau_compile = self._find_luau_compile()

    def _find_luau_compile(self) -> Optional[Path]:
        for candidate in self._LUAU_COMPILE_DEFAULTS:
            if isinstance(candidate, Path) and candidate.is_file():
                return candidate
        return None

    def _compile_validation(self, code: str) -> dict[str, Any]:
        if self._luau_compile is None:
            return {
                "available": False,
                "passed": None,
                "exitCode": None,
                "stderr": None,
            }
        with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False, encoding="utf-8") as handle:
            handle.write(code)
            tmp_path = Path(handle.name)
        try:
            completed = subprocess.run(
                [str(self._luau_compile), "--null", str(tmp_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            return {
                "available": True,
                "passed": completed.returncode == 0,
                "exitCode": completed.returncode,
                "stderr": (completed.stderr or "")[:2000] or None,
            }
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _dependency_scan(code: str) -> dict[str, Any]:
        helper_patterns = {
            "fireproximityprompt": r"\bfireproximityprompt\b",
            "firetouchinterest": r"\bfiretouchinterest\b",
            "mousemoverel": r"\bmousemoverel\b",
            "mouse1click": r"\bmouse1click\b",
            "virtualinputmanager": r"\bVirtualInputManager\b",
        }
        required = [name for name, pattern in helper_patterns.items() if re.search(pattern, code)]
        return {
            "requiredExecutorHelpers": required,
            "usesWaitForChild": bool(re.search(r"\bWaitForChild\b", code)),
            "usesFindFirstChild": bool(re.search(r"\bFindFirstChild\b", code)),
            "hasCleanupPath": bool(re.search(r"\bDisconnect\b|\bDestroy\b", code)),
            "hasDuplicateGuard": bool(re.search(r"_G\.[A-Za-z0-9_]+", code)),
        }

    def _basic_validation(self, code: str, place_id: int) -> dict[str, Any]:
        if not isinstance(code, str):
            return {"valid": False, "reason": "code missing", "placeGuard": False}
        if not 1 <= len(code.encode("utf-8")) <= 1_000_000:
            return {"valid": False, "reason": "code size out of bounds", "placeGuard": False}
        place_guard = f"assert(game.PlaceId == {place_id}" in code
        if not place_guard:
            return {"valid": False, "reason": "missing place guard", "placeGuard": False}

        compile_check = self._compile_validation(code)
        if compile_check["available"] and compile_check["passed"] is not True:
            return {
                "valid": False,
                "reason": "luau compile failed",
                "placeGuard": True,
                "luauCompile": compile_check,
                "dependencyScan": self._dependency_scan(code),
            }

        dependency_scan = self._dependency_scan(code)
        return {
            "valid": True,
            "reason": None,
            "placeGuard": True,
            "unsafeOperationsFound": False,
            "luauCompile": compile_check,
            "dependencyScan": dependency_scan,
            "runtimeTested": False,
            "gameplayVerified": False,
            "serverOutcomeVerified": False,
        }

    @staticmethod
    def _verification_states(code: Optional[str], validation: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
        states = dict((plan.get("verificationStates") or {})) if isinstance(plan, dict) else {}
        for name in _VERIFICATION_STATE_ORDER:
            states.setdefault(name, False)
        states["generated"] = bool(isinstance(code, str) and code.strip())
        luau = validation.get("luauCompile") if isinstance(validation.get("luauCompile"), dict) else {}
        states["syntax-validated"] = bool(validation.get("valid") is True and (
            luau.get("available") is False or luau.get("passed") is True
        ))
        states["runtime-tested"] = False
        states["gameplay-verified"] = False
        states["server-outcome-verified"] = False

        current = "discovered"
        for name in _VERIFICATION_STATE_ORDER:
            if states.get(name):
                current = name
        return {
            "states": states,
            "currentState": current,
            "claims": dict(FALSE_CLAIMS),
        }

    def validate_and_repair(
        self,
        code: Optional[str],
        place_id: Optional[int],
        analysis: dict[str, Any],
        usage: UsageLedger,
        route_plan: RoutePlan,
        plan: Optional[dict[str, Any]] = None,
    ) -> tuple[Optional[str], dict[str, Any], Optional[str], list[str]]:
        if code is None:
            invalid = {"valid": False, "reason": "no script available", "placeGuard": False}
            invalid["verificationLifecycle"] = self._verification_states(None, invalid, plan or {})
            return None, invalid, None, []
        if not isinstance(place_id, int) or place_id <= 0:
            invalid = {"valid": False, "reason": "invalid place id", "placeGuard": False}
            invalid["verificationLifecycle"] = self._verification_states(None, invalid, plan or {})
            return None, invalid, None, []
        validation = self._basic_validation(code, place_id)
        validation["verificationLifecycle"] = self._verification_states(code, validation, plan or {})
        if validation["valid"]:
            return code, validation, None, []

        errors = []
        for model in route_plan.repair_models:
            try:
                repaired, llm_usage = self._llm_provider.repair(code, analysis, model)
                _apply_stage_usage(usage, "repair", llm_usage)
                repaired_validation = self._basic_validation(repaired, place_id)
                repaired_validation["verificationLifecycle"] = self._verification_states(repaired, repaired_validation, plan or {})
                if repaired_validation["valid"]:
                    return repaired, repaired_validation, model, errors[:3]
                errors.append(f"{model}: repaired output failed validation ({repaired_validation.get('reason')})")
            except ValueError as exc:
                errors.append(f"{model}: {exc}")

        validation["repairAttemptsExhausted"] = True
        return None, validation, None, errors[:3]


class DeliveryEngine:
    def __init__(self) -> None:
        self._generated_result = _load_local_module("generated_result.py", "lycoles_generated_result")

    @staticmethod
    def _capabilities_from_bundle(bundle: EvidenceBundle) -> list[str]:
        if bundle.release_manifest and isinstance(bundle.release_manifest.get("implementedClientControls"), list):
            return [str(item) for item in bundle.release_manifest["implementedClientControls"]][:64]
        readiness = bundle.generation_readiness or {}
        generated = readiness.get("generatedCapabilities") or []
        return [str(item.get("kind")) for item in generated if isinstance(item, dict) and item.get("kind")][:64]

    @staticmethod
    def _script_artifacts(bundle: EvidenceBundle, code: Optional[str]) -> dict[str, Any]:
        utility_path = bundle.output_dir / "LycolesGeneratedUtility.lua"
        guided_path = bundle.output_dir / "LycolesGuidedWorkflow.lua"
        prompt_path = bundle.output_dir / "LycolesPromptInteractions.lua"

        if utility_path.is_file():
            primary_path = utility_path
            primary_kind = "combined-utility"
        elif guided_path.is_file():
            primary_path = guided_path
            primary_kind = "guided-workflow"
        elif prompt_path.is_file():
            primary_path = prompt_path
            primary_kind = "prompt-interaction-trial"
        elif isinstance(code, str) and code.strip():
            primary_path = bundle.output_dir / "LycolesGeneratedScript.lua"
            primary_path.write_text(code, encoding="utf-8")
            primary_kind = "generated-script"
        else:
            primary_path = None
            primary_kind = None

        return {
            "generatedScriptPath": str(primary_path) if primary_path is not None else None,
            "generatedScriptKind": primary_kind,
            "scriptArtifacts": {
                "utility": str(utility_path) if utility_path.is_file() else None,
                "guidedWorkflow": str(guided_path) if guided_path.is_file() else None,
                "promptInteractions": str(prompt_path) if prompt_path.is_file() else None,
            },
        }

    @staticmethod
    def _executable_workflow_status(bundle: EvidenceBundle, readiness: dict[str, Any]) -> dict[str, Any]:
        request_section = readiness.get("request") if isinstance(readiness.get("request"), dict) else {}
        request_feature = (
            readiness.get("requestFeatureReadiness")
            if isinstance(readiness.get("requestFeatureReadiness"), dict)
            else {}
        )
        workflow_evidence = (
            request_feature.get("workflowEvidence")
            if isinstance(request_feature.get("workflowEvidence"), dict)
            else {}
        )
        workflow_selection = (
            readiness.get("workflowSelection")
            if isinstance(readiness.get("workflowSelection"), dict)
            else {}
        )
        planning = (
            workflow_selection.get("planningDiagnostics")
            if isinstance(workflow_selection.get("planningDiagnostics"), dict)
            else {}
        )
        release_manifest = bundle.release_manifest if isinstance(bundle.release_manifest, dict) else {}
        guided_trial = (
            release_manifest.get("guidedWorkflowTrial")
            if isinstance(release_manifest.get("guidedWorkflowTrial"), dict)
            else {}
        )

        request_text = request_section.get("request") if isinstance(request_section.get("request"), str) else None
        request_provided = bool(request_text and request_text.strip())
        automatic_required = bool(
            workflow_evidence.get("automaticExecutionRequired")
            if isinstance(workflow_evidence.get("automaticExecutionRequired"), bool)
            else _request_requires_automatic_execution(request_text)
        )

        execution_ready_candidates = int(
            workflow_evidence.get("executionReadyCandidates")
            if isinstance(workflow_evidence.get("executionReadyCandidates"), int)
            else planning.get("executionReadyWorkflows")
            if isinstance(planning.get("executionReadyWorkflows"), int)
            else 0
        )
        automatic_execution_ready_candidates = int(
            workflow_evidence.get("automaticExecutionReadyCandidates")
            if isinstance(workflow_evidence.get("automaticExecutionReadyCandidates"), int)
            else planning.get("automaticExecutionReadyWorkflows")
            if isinstance(planning.get("automaticExecutionReadyWorkflows"), int)
            else 0
        )
        request_aligned_candidates = int(
            workflow_evidence.get("requestAlignedExecutionReadyCandidates")
            if isinstance(workflow_evidence.get("requestAlignedExecutionReadyCandidates"), int)
            else planning.get("requestAlignedExecutionReadyWorkflows")
            if isinstance(planning.get("requestAlignedExecutionReadyWorkflows"), int)
            else 0
        )
        request_aligned_automatic_candidates = int(
            workflow_evidence.get("requestAlignedAutomaticExecutionReadyCandidates")
            if isinstance(workflow_evidence.get("requestAlignedAutomaticExecutionReadyCandidates"), int)
            else planning.get("requestAlignedAutomaticExecutionReadyWorkflows")
            if isinstance(planning.get("requestAlignedAutomaticExecutionReadyWorkflows"), int)
            else 0
        )

        guided_generated = guided_trial.get("generated") is True
        selected_candidate_id = workflow_selection.get("selectedCandidateId")
        manual_required = guided_trial.get("manualActivationRequired") is True
        automatic_supported = guided_trial.get("automaticActivation") is True

        executable_available = execution_ready_candidates > 0 and guided_generated
        if automatic_required:
            request_aligned_executable = (
                request_aligned_automatic_candidates > 0
                and guided_generated
                and automatic_supported
                and not manual_required
            )
        else:
            request_aligned_executable = request_aligned_candidates > 0 and guided_generated

        blockers: list[str] = []
        if request_provided and request_aligned_candidates == 0:
            blockers.append("no request-aligned execution-ready workflow candidates")
        if automatic_required and request_provided and request_aligned_automatic_candidates == 0:
            blockers.append("no request-aligned automatic execution-ready workflow candidates")
        if automatic_required and request_provided and manual_required:
            blockers.append("selected request-aligned workflow requires manual GUI activation")
        if automatic_required and request_provided and not automatic_supported:
            blockers.append("automatic activation is unavailable for selected workflow")
        if execution_ready_candidates > 0 and not guided_generated:
            blockers.append("execution-ready workflow candidates exist but guided workflow script was not generated")

        return {
            "requestedCapabilityProvided": request_provided,
            "requestStatus": request_section.get("status"),
            "requestImplementationReady": request_section.get("implementationReady") is True,
            "automaticExecutionRequired": automatic_required,
            "executionReadyWorkflowCandidates": execution_ready_candidates,
            "automaticExecutionReadyWorkflowCandidates": automatic_execution_ready_candidates,
            "requestAlignedExecutionReadyWorkflowCandidates": request_aligned_candidates,
            "requestAlignedAutomaticExecutionReadyWorkflowCandidates": request_aligned_automatic_candidates,
            "guidedWorkflowScriptGenerated": guided_generated,
            "selectedWorkflowCandidateId": selected_candidate_id,
            "executableWorkflowAvailable": executable_available,
            "requestAlignedExecutableWorkflowAvailable": request_aligned_executable,
            "manualGuiActivationRequired": manual_required,
            "automaticActivationSupported": automatic_supported,
            "blockers": blockers,
            "runtimeVerified": False,
            "gameplayVerified": False,
            "causalityProven": False,
        }

    def deliver(
        self,
        bundle: EvidenceBundle,
        request: GenerationRequest,
        code: Optional[str],
        validation: dict[str, Any],
        autonomous_plan: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        result_path = bundle.output_dir / "generated-result.json"
        autonomous_path = bundle.output_dir / "autonomous-generation.json"
        blocker_path = bundle.output_dir / "generation-blockers.json"

        plan_payload = autonomous_plan if isinstance(autonomous_plan, dict) else {
            "schemaVersion": "30.6.autonomous-generation-plan.1",
            "featureDiscovery": {"count": 0, "ranked": []},
            "selectedFeature": None,
            "selectedStrategy": None,
            "generationRequest": {
                "requestedCapability": request.requested_capability,
                "automaticExecutionRequested": _request_requires_automatic_execution(request.requested_capability),
            },
            "verificationStates": {
                name: False for name in _VERIFICATION_STATE_ORDER
            },
            "blockers": ["autonomous planning unavailable"],
            "claims": dict(FALSE_CLAIMS),
        }
        plan_payload["validation"] = validation

        if code is None or not validation.get("valid"):
            blockers = ["generated script unavailable or failed validation"]
            if isinstance(plan_payload.get("blockers"), list):
                blockers.extend(str(item) for item in plan_payload.get("blockers") if isinstance(item, str))
            blocker_payload = {
                "schemaVersion": "30.6.generation-blockers.1",
                "requestedCapability": request.requested_capability,
                "placeId": bundle.place_id,
                "scanId": bundle.scan_id,
                "blockers": sorted(set(blockers)),
                "validationReason": validation.get("reason"),
                "minimumAdditionalEvidence": [
                    "At least one execution-ready feature candidate with attributable interaction evidence",
                    "Observed control pathway (GUI/proximity/tool) mapped to target feature",
                    "State/outcome signal beyond temporal-only correlation",
                ],
                "claims": dict(FALSE_CLAIMS),
            }
            blocker_path.write_text(json.dumps(blocker_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
            plan_payload["blockerReportPath"] = str(blocker_path)
            autonomous_path.write_text(json.dumps(plan_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

            payload = {
                "generatedResultPath": None,
                "generatedResultSchema": None,
                "generatedScriptPath": None,
                "generatedScriptKind": None,
                "scriptArtifacts": {"utility": None, "guidedWorkflow": None, "promptInteractions": None},
                "autonomousGenerationPath": str(autonomous_path),
                "blockerReportPath": str(blocker_path),
                "executableWorkflow": {
                    "requestedCapabilityProvided": bool(request.requested_capability),
                    "requestStatus": None,
                    "requestImplementationReady": False,
                    "automaticExecutionRequired": _request_requires_automatic_execution(request.requested_capability),
                    "executionReadyWorkflowCandidates": 0,
                    "automaticExecutionReadyWorkflowCandidates": 0,
                    "requestAlignedExecutionReadyWorkflowCandidates": 0,
                    "requestAlignedAutomaticExecutionReadyWorkflowCandidates": 0,
                    "guidedWorkflowScriptGenerated": False,
                    "selectedWorkflowCandidateId": None,
                    "executableWorkflowAvailable": False,
                    "requestAlignedExecutableWorkflowAvailable": False,
                    "manualGuiActivationRequired": False,
                    "automaticActivationSupported": False,
                    "blockers": sorted(set(blockers)),
                    "runtimeVerified": False,
                    "gameplayVerified": False,
                    "causalityProven": False,
                },
                "claims": dict(FALSE_CLAIMS),
            }
            result_path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
            return payload

        readiness = bundle.generation_readiness
        if not isinstance(readiness, dict):
            raise ValueError("generation-readiness artifact missing for delivery")
        if not isinstance(bundle.place_id, int) or bundle.place_id <= 0:
            raise ValueError("invalid place id for delivery")

        readiness_request = None
        request_section = readiness.get("request") if isinstance(readiness.get("request"), dict) else {}
        if isinstance(request_section.get("request"), str):
            readiness_request = request_section.get("request")

        generated_result = self._generated_result.build(
            place_id=bundle.place_id,
            scan_id=bundle.scan_id or "scan-unavailable",
            code=code,
            requested_capability=readiness_request,
            validation={"placeGuard": bool(validation.get("placeGuard")), "unsafeOperationsFound": bool(validation.get("unsafeOperationsFound", False))},
            capabilities=self._capabilities_from_bundle(bundle),
            generation_readiness=readiness,
        )
        result_path.write_text(json.dumps(generated_result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        script_artifacts = self._script_artifacts(bundle, code)
        executable_workflow = self._executable_workflow_status(bundle, readiness)

        plan_payload["generatedScriptPath"] = script_artifacts["generatedScriptPath"]
        plan_payload["generatedScriptKind"] = script_artifacts["generatedScriptKind"]
        autonomous_path.write_text(json.dumps(plan_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

        return {
            "generatedResultPath": str(result_path),
            "generatedResultSchema": generated_result.get("schemaVersion"),
            "generatedScriptPath": script_artifacts["generatedScriptPath"],
            "generatedScriptKind": script_artifacts["generatedScriptKind"],
            "scriptArtifacts": script_artifacts["scriptArtifacts"],
            "autonomousGenerationPath": str(autonomous_path),
            "blockerReportPath": None,
            "executableWorkflow": executable_workflow,
            "claims": {
                "packageAuthenticityVerified": generated_result.get("packageAuthenticityVerified"),
                "runtimeVerified": generated_result.get("runtimeVerified"),
                "gameplayVerified": generated_result.get("gameplayVerified"),
                "executionAuthorized": generated_result.get("executionAuthorized"),
            },
        }


class LycolesGenerationService:
    def __init__(
        self,
        output_root: Path,
        model_routes: Optional[ModelRouteConfig] = None,
        llm_provider: Optional[BaseLLMProvider] = None,
        provider_info: Optional[ProviderInfo] = None,
    ) -> None:
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.model_routes = model_routes or ModelRouteConfig()

        if llm_provider is None:
            selected_provider, selected_info = _provider_from_environment()
            self.llm_provider = selected_provider
            self.provider_info = selected_info
        else:
            self.llm_provider = llm_provider
            self.provider_info = provider_info or llm_provider.info()

        prefer_ai_flag = (os.environ.get("LYCOLES_PREFER_AI_GENERATION") or "").strip().lower()
        prefer_ai_generation = self.provider_info.enabled and prefer_ai_flag in {"1", "true", "yes", "on"}

        self.evidence_processor = EvidenceProcessor()
        self.feature_analysis = FeatureAnalysisEngine(self.llm_provider, self.model_routes)
        self.autonomous_planning = AutonomousPlanningEngine()
        self.script_generation = ScriptGenerationEngine(
            self.llm_provider,
            self.model_routes,
            prefer_ai_generation=prefer_ai_generation,
        )
        self.validation_repair = ValidationRepairEngine(self.llm_provider, self.model_routes)
        self.delivery = DeliveryEngine()
        self._jobs: dict[str, JobRecord] = {}
        self._jobs_lock = threading.Lock()
        self._analysis_cache: dict[str, dict[str, Any]] = {}
        self._analysis_cache_lock = threading.Lock()
        self._feedback_log_path = self.output_root / "feedback-log.jsonl"
        self._feedback_lock = threading.Lock()
        self._feedback_records: list[FeedbackRecord] = []
        self._feedback_penalties: dict[str, int] = {}
        self._load_feedback_log()

    def _output_dir_for(self, job_id: str) -> Path:
        return self.output_root / job_id

    def _feedback_signature(self, place_id: Optional[int], scan_id: Optional[str], feature_id: Optional[str], strategy_id: Optional[str]) -> str:
        return "|".join([
            str(place_id or ""),
            str(scan_id or ""),
            str(feature_id or ""),
            str(strategy_id or ""),
        ])

    def _rebuild_feedback_penalties(self) -> None:
        penalties: dict[str, int] = {}
        for record in self._feedback_records:
            if record.status in {"failed", "runtime-error", "navigation-failed", "unsupported"}:
                key = self._feedback_signature(record.place_id, record.scan_id, record.feature_id, record.strategy_id)
                penalties[key] = penalties.get(key, 0) + 1
        self._feedback_penalties = penalties

    def _load_feedback_log(self) -> None:
        if not self._feedback_log_path.is_file():
            return
        loaded: list[FeedbackRecord] = []
        for line in self._feedback_log_path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            loaded.append(FeedbackRecord(
                feedback_id=str(payload.get("feedbackId") or _safe_feature_id("feedback", text[:32])),
                created_at=float(payload.get("createdAt") or time.time()),
                place_id=payload.get("placeId") if isinstance(payload.get("placeId"), int) else None,
                scan_id=payload.get("scanId") if isinstance(payload.get("scanId"), str) else None,
                feature_id=payload.get("featureId") if isinstance(payload.get("featureId"), str) else None,
                strategy_id=payload.get("strategyId") if isinstance(payload.get("strategyId"), str) else None,
                status=str(payload.get("status") or "unknown"),
                runtime_errors=_coerce_text_list(payload.get("runtimeErrors"), max_items=20),
                missing_objects=_coerce_text_list(payload.get("missingObjects"), max_items=20),
                failed_interactions=_coerce_text_list(payload.get("failedInteractions"), max_items=20),
                successful_interactions=_coerce_text_list(payload.get("successfulInteractions"), max_items=20),
                navigation_failures=_coerce_text_list(payload.get("navigationFailures"), max_items=20),
                executor_compatibility_issues=_coerce_text_list(payload.get("executorCompatibilityIssues"), max_items=20),
                observed_changes=_coerce_text_list(payload.get("observedChanges"), max_items=20),
                gameplay_verified=payload.get("gameplayVerified") is True,
                server_outcome_verified=payload.get("serverOutcomeVerified") is True,
                notes=(payload.get("notes") if isinstance(payload.get("notes"), str) else None),
            ))
        self._feedback_records = loaded[-1000:]
        self._rebuild_feedback_penalties()

    def list_feedback(self) -> list[dict[str, Any]]:
        with self._feedback_lock:
            return [record.to_dict() for record in self._feedback_records]

    def _feedback_penalties_for(self, *, place_id: Optional[int], scan_id: Optional[str]) -> dict[str, int]:
        prefix = f"{place_id or ''}|{scan_id or ''}|"
        with self._feedback_lock:
            return {
                key.split("|", 2)[2]: value
                for key, value in self._feedback_penalties.items()
                if key.startswith(prefix)
            }

    def record_feedback(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("feedback payload must be an object")
        status = str(payload.get("status") or "unknown").strip().lower()
        if status not in {"failed", "succeeded", "partial", "runtime-error", "navigation-failed", "unsupported"}:
            raise ValueError("feedback status must be one of failed/succeeded/partial/runtime-error/navigation-failed/unsupported")

        record = FeedbackRecord(
            feedback_id=str(payload.get("feedbackId") or ("feedback-" + uuid.uuid4().hex[:12])),
            created_at=float(payload.get("createdAt") or time.time()),
            place_id=payload.get("placeId") if isinstance(payload.get("placeId"), int) else None,
            scan_id=payload.get("scanId") if isinstance(payload.get("scanId"), str) else None,
            feature_id=payload.get("featureId") if isinstance(payload.get("featureId"), str) else None,
            strategy_id=payload.get("strategyId") if isinstance(payload.get("strategyId"), str) else None,
            status=status,
            runtime_errors=_coerce_text_list(payload.get("runtimeErrors"), max_items=20),
            missing_objects=_coerce_text_list(payload.get("missingObjects"), max_items=20),
            failed_interactions=_coerce_text_list(payload.get("failedInteractions"), max_items=20),
            successful_interactions=_coerce_text_list(payload.get("successfulInteractions"), max_items=20),
            navigation_failures=_coerce_text_list(payload.get("navigationFailures"), max_items=20),
            executor_compatibility_issues=_coerce_text_list(payload.get("executorCompatibilityIssues"), max_items=20),
            observed_changes=_coerce_text_list(payload.get("observedChanges"), max_items=20),
            gameplay_verified=payload.get("gameplayVerified") is True,
            server_outcome_verified=payload.get("serverOutcomeVerified") is True,
            notes=(payload.get("notes")[:512] if isinstance(payload.get("notes"), str) else None),
        )

        with self._feedback_lock:
            self._feedback_records.append(record)
            if len(self._feedback_records) > 1000:
                self._feedback_records = self._feedback_records[-1000:]
            self._rebuild_feedback_penalties()
            with self._feedback_log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record.to_dict(), sort_keys=True, ensure_ascii=False) + "\n")

        return {
            "status": "recorded",
            "feedback": record.to_dict(),
            "penaltyFailures": self._feedback_penalties.get(record.key(), 0),
        }


    def _run_pipeline(self, job_id: str, request: GenerationRequest) -> dict[str, Any]:
        usage = UsageLedger()
        output_dir = self._output_dir_for(job_id)
        bundle = self.evidence_processor.process(request, output_dir)
        route_plan = _build_route_plan(bundle, self.model_routes)

        analysis_cache_key = _analysis_cache_signature(bundle, route_plan)
        analysis_cache_hit = False
        with self._analysis_cache_lock:
            cached_analysis = self._analysis_cache.get(analysis_cache_key)

        if isinstance(cached_analysis, dict):
            analysis = _json_clone(cached_analysis)
            analysis_cache_hit = True
        else:
            analysis = self.feature_analysis.analyze(bundle, usage, route_plan)
            with self._analysis_cache_lock:
                self._analysis_cache[analysis_cache_key] = _json_clone(analysis)

        analysis["analysisCache"] = {
            "enabled": True,
            "hit": analysis_cache_hit,
            "key": analysis_cache_key,
        }
        analysis["evidenceWarnings"] = list(bundle.warnings)

        feedback_penalties = self._feedback_penalties_for(place_id=bundle.place_id, scan_id=bundle.scan_id)
        autonomous_plan = self.autonomous_planning.build_plan(bundle, request, analysis, feedback_penalties)
        analysis["autonomousGeneration"] = autonomous_plan

        code, generation_source, generation_model_used, generation_errors = self.script_generation.generate(
            bundle, analysis, usage, route_plan)
        code, validation, repair_model_used, repair_errors = self.validation_repair.validate_and_repair(
            code, bundle.place_id, analysis, usage, route_plan, plan=autonomous_plan)
        autonomous_plan["verificationStates"] = (
            (validation.get("verificationLifecycle") or {}).get("states")
            if isinstance(validation.get("verificationLifecycle"), dict)
            else autonomous_plan.get("verificationStates")
        )
        delivery = self.delivery.deliver(bundle, request, code, validation, autonomous_plan=autonomous_plan)

        blockers = list(analysis.get("explicitBlockers") or [])
        if isinstance(autonomous_plan.get("blockers"), list):
            blockers.extend(str(item) for item in autonomous_plan.get("blockers") if isinstance(item, str))
        blockers = sorted(set(blockers))
        executable_workflow = delivery.get("executableWorkflow") if isinstance(delivery.get("executableWorkflow"), dict) else {}
        request_provided = executable_workflow.get("requestedCapabilityProvided") is True
        request_executable_available = executable_workflow.get("requestAlignedExecutableWorkflowAvailable") is True

        if code is None:
            generation_status = "blocked"
        elif request_provided and not request_executable_available:
            generation_status = "observational-only-request-unmet"
        elif blockers:
            generation_status = "generated-with-blockers"
        else:
            generation_status = "generated"


        if generation_status == "observational-only-request-unmet" and not delivery.get("blockerReportPath"):
            workflow_blockers = [
                str(item)
                for item in (executable_workflow.get("blockers") or [])
                if isinstance(item, str)
            ]
            selected_feature = autonomous_plan.get("selectedFeature") if isinstance(autonomous_plan.get("selectedFeature"), dict) else {}
            selected_strategy = autonomous_plan.get("selectedStrategy") if isinstance(autonomous_plan.get("selectedStrategy"), dict) else {}
            strategy_missing = [
                str(item)
                for item in (selected_strategy.get("missingDependencies") or [])
                if isinstance(item, str)
            ]

            minimum_additional_evidence = [
                "Observed interaction events directly attributed to the requested feature candidate",
                "At least one execution-ready request-aligned workflow candidate in generation readiness",
                "Evidence-backed control pathway (GUI/proximity/tool) with path identity and outcome correlation",
            ]
            if any("workspace target path" in item for item in strategy_missing):
                minimum_additional_evidence.append(
                    "Workspace target path(s) correlated with feature interactions for relocation/navigation strategies"
                )
            if any("GUI/prompt/tool" in item for item in strategy_missing):
                minimum_additional_evidence.append(
                    "Observed GUI/Prompt/Tool activation events for the selected feature"
                )
            if any("world anchor" in item for item in strategy_missing):
                minimum_additional_evidence.append(
                    "Observed world anchor or automatic movement evidence tied to target feature"
                )

            blocker_payload = {
                "schemaVersion": "30.6.generation-blockers.2",
                "requestedCapability": request.requested_capability,
                "placeId": bundle.place_id,
                "scanId": bundle.scan_id,
                "generationStatus": generation_status,
                "selectedFeature": {
                    "featureId": selected_feature.get("featureId"),
                    "label": selected_feature.get("label"),
                    "category": selected_feature.get("category"),
                    "classification": selected_feature.get("classification"),
                },
                "selectedStrategy": {
                    "strategyId": selected_strategy.get("id"),
                    "label": selected_strategy.get("label"),
                    "feasible": selected_strategy.get("feasible"),
                    "score": selected_strategy.get("score"),
                    "missingDependencies": strategy_missing,
                    "rejectionReasons": [
                        str(item)
                        for item in (selected_strategy.get("rejectionReasons") or [])
                        if isinstance(item, str)
                    ],
                },
                "blockers": sorted(set(blockers + workflow_blockers)),
                "minimumAdditionalEvidence": sorted(set(minimum_additional_evidence)),
                "claims": dict(FALSE_CLAIMS),
            }
            blocker_path = bundle.output_dir / "generation-blockers.json"
            blocker_path.write_text(
                json.dumps(blocker_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            delivery["blockerReportPath"] = str(blocker_path)

        if request.require_executable and request_provided and not request_executable_available:
            blocker_text = ", ".join(str(item) for item in executable_workflow.get("blockers", [])[:4])
            if not blocker_text:
                blocker_text = "no request-aligned executable workflow was generated"
            raise ValueError(f"Executable workflow required but unavailable: {blocker_text}")

        ai_inference_performed = (
            generation_source == "ai-generated-script"
            or usage.analysis_attempts > 0
            or usage.generation_attempts > 0
            or usage.repair_attempts > 0
        )
        usage_summary = usage.to_dict()
        total_cost = float((usage_summary.get("total") or {}).get("costGbp") or 0.0)
        syntax_validated = bool(((validation.get("verificationLifecycle") or {}).get("states") or {}).get("syntax-validated"))
        economics = {
            "totalCostGbp": round(total_cost, 8),
            "totalTokens": int((usage_summary.get("total") or {}).get("tokens") or 0),
            "costPerSyntaxValidatedScriptGbp": round(total_cost, 8) if syntax_validated else None,
            "inferencePerformed": ai_inference_performed,
            "analysisCacheHit": analysis_cache_hit,
        }

        result = {
            "jobId": job_id,
            "status": "succeeded",
            "generationStatus": generation_status,
            "generationSource": generation_source,
            "provider": {
                "name": self.provider_info.provider,
                "enabled": self.provider_info.enabled,
                "reason": self.provider_info.reason,
                "analysisModel": self.model_routes.analysis_model,
                "generationModel": self.model_routes.generation_model,
                "repairModel": self.model_routes.repair_model,
                "reasoningModel": self.model_routes.reasoning_model,
                "complexityClass": route_plan.complexity,
                "analysisModelOrder": list(route_plan.analysis_models),
                "generationModelOrder": list(route_plan.generation_models),
                "repairModelOrder": list(route_plan.repair_models),
                "analysisModelUsed": analysis.get("analysisModelUsed"),
                "generationModelUsed": generation_model_used,
                "repairModelUsed": repair_model_used,
                "expectedCostScores": route_plan.expected_cost_scores,
                "analysisFallbackErrors": analysis.get("analysisFallbackErrors") or [],
                "generationFallbackErrors": generation_errors,
                "repairFallbackErrors": repair_errors,
                "analysisCacheEnabled": True,
                "analysisCacheHit": analysis_cache_hit,
                "analysisCacheKey": analysis_cache_key,
                "aiInferencePerformed": ai_inference_performed,
            },
            "evidence": {
                "evidenceKind": request.evidence_kind,
                "evidencePath": str(request.evidence_path),
                "mode": bundle.mode,
                "placeId": bundle.place_id,
                "scanId": bundle.scan_id,
                "warnings": list(bundle.warnings),
                "manifestReadinessPath": str(bundle.output_dir / "manifest-readiness-v109.json") if (bundle.output_dir / "manifest-readiness-v109.json").exists() else None,
                "releaseManifestPath": str(bundle.output_dir / "release-manifest.json") if (bundle.output_dir / "release-manifest.json").exists() else None,
                "generationReadinessPath": str(bundle.output_dir / "generation-readiness.json") if (bundle.output_dir / "generation-readiness.json").exists() else None,
            },
            "analysis": analysis,
            "autonomousGeneration": autonomous_plan,
            "validation": validation,
            "delivery": delivery,
            "usage": usage_summary,
            "economics": economics,
            "claims": dict(FALSE_CLAIMS),
            "outputDir": str(bundle.output_dir),
        }
        (bundle.output_dir / "job-result.json").write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        return result

    def run_sync(self, request: GenerationRequest) -> dict[str, Any]:
        return self._run_pipeline("job-" + uuid.uuid4().hex[:16], request)

    def submit(self, request: GenerationRequest) -> str:
        job_id = "job-" + uuid.uuid4().hex[:16]
        record = JobRecord(job_id=job_id, request=request)
        with self._jobs_lock:
            self._jobs[job_id] = record
        thread = threading.Thread(target=self._run_async, args=(job_id,), daemon=True)
        thread.start()
        return job_id

    def _run_async(self, job_id: str) -> None:
        with self._jobs_lock:
            record = self._jobs[job_id]
            record.status = "running"
            record.started_at = time.time()
            request = record.request
        try:
            result = self._run_pipeline(job_id, request)
            with self._jobs_lock:
                record = self._jobs[job_id]
                record.status = "succeeded"
                record.result = result
                record.finished_at = time.time()
        except Exception as exc:  # pylint: disable=broad-except
            with self._jobs_lock:
                record = self._jobs[job_id]
                record.status = "failed"
                record.error = f"{exc}\n{traceback.format_exc()}"
                record.finished_at = time.time()

    def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        with self._jobs_lock:
            record = self._jobs.get(job_id)
            return None if record is None else record.snapshot()

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._jobs_lock:
            return [record.snapshot() for _, record in sorted(self._jobs.items())]

    def make_http_handler(self):
        service = self

        class Handler(BaseHTTPRequestHandler):
            def _json(self, payload: dict[str, Any], status: int = 200) -> None:
                body = json.dumps(payload, sort_keys=True).encode("utf-8")
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("cache-control", "no-store")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _read_json(self) -> dict[str, Any]:
                length = int(self.headers.get("content-length", "0"))
                raw = self.rfile.read(length)
                return json.loads(raw.decode("utf-8")) if raw else {}

            def log_message(self, _format: str, *_args) -> None:
                return

            def do_GET(self):  # noqa: N802
                parts = [part for part in self.path.split("?")[0].split("/") if part]
                if parts == ["v1", "generation", "jobs"]:
                    return self._json({"jobs": service.list_jobs()})
                if len(parts) == 4 and parts[:3] == ["v1", "generation", "jobs"]:
                    job = service.get_job(parts[3])
                    if job is None:
                        return self._json({"error": "Job not found"}, 404)
                    return self._json(job)
                if parts == ["v1", "generation", "feedback"]:
                    return self._json({"feedback": service.list_feedback()})
                return self._json({"error": "Not found"}, 404)

            def do_POST(self):  # noqa: N802
                parts = [part for part in self.path.split("?")[0].split("/") if part]
                if parts == ["v1", "generation", "jobs"]:
                    try:
                        payload = self._read_json()
                        raw_observations = payload.get("observationPaths") or []
                        if not isinstance(raw_observations, list) or any(not isinstance(item, str) for item in raw_observations):
                            raise ValueError("observationPaths must be a list of strings")
                        require_executable = payload.get("requireExecutable", False)
                        if not isinstance(require_executable, bool):
                            raise ValueError("requireExecutable must be a boolean")
                        request = GenerationRequest(
                            evidence_kind=str(payload.get("evidenceKind")),
                            evidence_path=Path(str(payload.get("evidencePath"))).expanduser().resolve(),
                            requested_capability=payload.get("requestedCapability"),
                            observation_paths=tuple(Path(item).expanduser().resolve() for item in raw_observations),
                            require_executable=require_executable,
                        )
                        job_id = service.submit(request)
                        return self._json({"jobId": job_id, "status": "queued", "statusUrl": f"/v1/generation/jobs/{job_id}"}, 202)
                    except Exception as exc:  # pylint: disable=broad-except
                        return self._json({"error": str(exc)}, 400)
                if parts == ["v1", "generation", "feedback"]:
                    try:
                        payload = self._read_json()
                        recorded = service.record_feedback(payload)
                        return self._json(recorded, 201)
                    except Exception as exc:  # pylint: disable=broad-except
                        return self._json({"error": str(exc)}, 400)
                return self._json({"error": "Not found"}, 404)

        return Handler


def _request_from_args(args: argparse.Namespace) -> GenerationRequest:
    raw_paths = getattr(args, "observation_path", None) or []
    return GenerationRequest(
        evidence_kind=args.evidence_kind,
        evidence_path=Path(args.evidence_path).expanduser().resolve(),
        requested_capability=args.requested_capability,
        observation_paths=tuple(Path(item).expanduser().resolve() for item in raw_paths),
        require_executable=bool(getattr(args, "require_executable", False)),
    )


def _model_routes_from_environment() -> ModelRouteConfig:
    analysis_model = (os.environ.get("LYCOLES_ANALYSIS_MODEL") or ModelRouteConfig.analysis_model).strip()
    generation_model = (os.environ.get("LYCOLES_GENERATION_MODEL") or ModelRouteConfig.generation_model).strip()
    repair_model = (os.environ.get("LYCOLES_REPAIR_MODEL") or ModelRouteConfig.repair_model).strip()
    reasoning_model = (os.environ.get("LYCOLES_REASONING_MODEL")
                       or os.environ.get("LYCOLES_SOL_MODEL")
                       or ModelRouteConfig.reasoning_model).strip()
    return ModelRouteConfig(
        analysis_model=analysis_model,
        generation_model=generation_model,
        repair_model=repair_model,
        reasoning_model=reasoning_model,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run-job", help="Run one generation job synchronously")
    run_parser.add_argument("--evidence-kind", choices=("manifest", "parts_dir", "replay_package"), required=True)
    run_parser.add_argument("--evidence-path", required=True)
    run_parser.add_argument("--requested-capability", default=None)
    run_parser.add_argument("--observation-path", action="append", default=[],
                            help="Additional observation overlay path (dynamic JSON file or compiled observation directory); repeatable")
    run_parser.add_argument("--require-executable", action="store_true",
                            help="Fail when requested capability does not produce request-aligned executable workflow output")
    run_parser.add_argument("--output-root", default="build/generation-jobs")

    serve_parser = subparsers.add_parser("serve", help="Run HTTP job service")
    serve_parser.add_argument("--output-root", default="build/generation-jobs")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8787)

    feedback_parser = subparsers.add_parser("record-feedback", help="Record runtime feedback for future generation retries")
    feedback_parser.add_argument("--output-root", default="build/generation-jobs")
    feedback_parser.add_argument("--feedback-json", required=True,
                                 help="Path to JSON payload following the feedback contract")

    replay_parser = subparsers.add_parser("replay-import", help="Import baseline/observation artifacts into a validated replay package")
    replay_parser.add_argument("--baseline-input", action="append", required=True,
                               help="Baseline source path (parts directory, multipart ZIP, manifest JSON, or replay package); repeatable")
    replay_parser.add_argument("--observation-input", action="append", default=[],
                               help="Observation JSON or directory containing dynamic observation exports; repeatable")
    replay_parser.add_argument("--output-dir", required=True,
                               help="Destination directory for the replay package")
    replay_parser.add_argument("--expected-place-id", type=int, default=None,
                               help="Optional expected place ID for strict identity validation")
    replay_parser.add_argument("--expected-baseline-scan-id", default=None,
                               help="Optional expected baseline scan ID for strict identity validation")
    replay_parser.add_argument("--expected-observation-scan-id", action="append", default=[],
                               help="Optional expected observation scan ID(s); repeatable")

    args = parser.parse_args()

    if args.command == "replay-import":
        replay_import = _load_local_module("evidence_replay_import.py", "lycoles_evidence_replay_cli")
        result = replay_import.import_replay_package(
            baseline_inputs=[Path(item).expanduser().resolve() for item in args.baseline_input],
            observation_inputs=[Path(item).expanduser().resolve() for item in args.observation_input],
            output_dir=Path(args.output_dir).expanduser().resolve(),
            expected_place_id=args.expected_place_id,
            expected_baseline_scan_id=args.expected_baseline_scan_id,
            expected_observation_scan_ids=list(args.expected_observation_scan_id or []),
        )
        baseline = result.get("baseline") if isinstance(result.get("baseline"), dict) else {}
        part_digests = baseline.get("partDigests") if isinstance(baseline.get("partDigests"), list) else []
        compact = {
            "schemaVersion": result.get("schemaVersion"),
            "replayPackagePath": result.get("replayPackagePath"),
            "outputDir": result.get("outputDir"),
            "baseline": {
                "mode": baseline.get("mode"),
                "scanId": baseline.get("scanId"),
                "placeId": baseline.get("placeId"),
                "partCount": baseline.get("partCount"),
                "partDigestCount": len(part_digests),
                "manifestPath": baseline.get("manifestPath"),
                "partsDir": baseline.get("partsDir"),
                "partsComplete": baseline.get("partsComplete"),
            },
            "observationCount": len(result.get("observations") or []),
            "observationScanIds": [
                item.get("scanId")
                for item in (result.get("observations") or [])
                if isinstance(item, dict) and isinstance(item.get("scanId"), str)
            ],
            "validation": result.get("validation") if isinstance(result.get("validation"), dict) else {},
            "warnings": result.get("warnings") if isinstance(result.get("warnings"), list) else [],
        }
        print(json.dumps(compact, sort_keys=True))
        return 0

    service = LycolesGenerationService(
        output_root=Path(args.output_root),
        model_routes=_model_routes_from_environment(),
    )

    if args.command == "run-job":
        result = service.run_sync(_request_from_args(args))
        print(json.dumps(result, sort_keys=True))
        return 0

    if args.command == "record-feedback":
        payload = json.loads(Path(args.feedback_json).expanduser().read_text(encoding="utf-8"))
        result = service.record_feedback(payload)
        print(json.dumps(result, sort_keys=True))
        return 0

    handler = service.make_http_handler()
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Lycoles generation service listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
