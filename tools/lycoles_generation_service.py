"""Dedicated Lycoles generation service with async job orchestration."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
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

        if request.evidence_kind != "parts_dir":
            raise ValueError("Unsupported evidence kind")

        observation_dirs: list[Path] = []
        observation_files: list[Path] = []
        for path in request.observation_paths:
            if path.is_dir():
                observation_dirs.append(path)
            elif path.is_file():
                observation_files.append(path)
            else:
                raise ValueError(f"Observation path not found: {path}")

        manifest = self._build_release.build(
            request.evidence_path,
            output_dir,
            requested_capability=request.requested_capability,
            observation_dirs=observation_dirs,
            observation_files=observation_files,
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
        )


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
    def __init__(self, llm_provider: BaseLLMProvider, model_routes: ModelRouteConfig) -> None:
        self._llm_provider = llm_provider
        self._routes = model_routes

    @staticmethod
    def _basic_validation(code: str, place_id: int) -> dict[str, Any]:
        if not isinstance(code, str):
            return {"valid": False, "reason": "code missing", "placeGuard": False}
        if not 1 <= len(code.encode("utf-8")) <= 1_000_000:
            return {"valid": False, "reason": "code size out of bounds", "placeGuard": False}
        if f"assert(game.PlaceId == {place_id}" not in code:
            return {"valid": False, "reason": "missing place guard", "placeGuard": False}
        return {"valid": True, "reason": None, "placeGuard": True, "unsafeOperationsFound": False}

    def validate_and_repair(
        self,
        code: Optional[str],
        place_id: Optional[int],
        analysis: dict[str, Any],
        usage: UsageLedger,
        route_plan: RoutePlan,
    ) -> tuple[Optional[str], dict[str, Any], Optional[str], list[str]]:
        if code is None:
            return None, {"valid": False, "reason": "no script available", "placeGuard": False}, None, []
        if not isinstance(place_id, int) or place_id <= 0:
            return None, {"valid": False, "reason": "invalid place id", "placeGuard": False}, None, []
        validation = self._basic_validation(code, place_id)
        if validation["valid"]:
            return code, validation, None, []

        errors = []
        for model in route_plan.repair_models:
            try:
                repaired, llm_usage = self._llm_provider.repair(code, analysis, model)
                _apply_stage_usage(usage, "repair", llm_usage)
                repaired_validation = self._basic_validation(repaired, place_id)
                if repaired_validation["valid"]:
                    return repaired, repaired_validation, model, errors[:3]
                errors.append(f"{model}: repaired output failed validation ({repaired_validation.get('reason')})")
            except ValueError as exc:
                errors.append(f"{model}: {exc}")

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
    ) -> dict[str, Any]:
        result_path = bundle.output_dir / "generated-result.json"
        if code is None or not validation.get("valid"):
            payload = {
                "generatedResultPath": None,
                "generatedResultSchema": None,
                "generatedScriptPath": None,
                "generatedScriptKind": None,
                "scriptArtifacts": {"utility": None, "guidedWorkflow": None, "promptInteractions": None},
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
                    "blockers": ["generated script unavailable or failed validation"],
                    "runtimeVerified": False,
                    "gameplayVerified": False,
                    "causalityProven": False,
                },
                "claims": dict(FALSE_CLAIMS),
            }
            result_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        return {
            "generatedResultPath": str(result_path),
            "generatedResultSchema": generated_result.get("schemaVersion"),
            "generatedScriptPath": script_artifacts["generatedScriptPath"],
            "generatedScriptKind": script_artifacts["generatedScriptKind"],
            "scriptArtifacts": script_artifacts["scriptArtifacts"],
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

    def _output_dir_for(self, job_id: str) -> Path:
        return self.output_root / job_id

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
        code, generation_source, generation_model_used, generation_errors = self.script_generation.generate(
            bundle, analysis, usage, route_plan)
        code, validation, repair_model_used, repair_errors = self.validation_repair.validate_and_repair(
            code, bundle.place_id, analysis, usage, route_plan)
        delivery = self.delivery.deliver(bundle, request, code, validation)

        blockers = analysis.get("explicitBlockers") or []
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
                "mode": bundle.mode,
                "placeId": bundle.place_id,
                "scanId": bundle.scan_id,
                "manifestReadinessPath": str(bundle.output_dir / "manifest-readiness-v109.json") if (bundle.output_dir / "manifest-readiness-v109.json").exists() else None,
                "releaseManifestPath": str(bundle.output_dir / "release-manifest.json") if (bundle.output_dir / "release-manifest.json").exists() else None,
                "generationReadinessPath": str(bundle.output_dir / "generation-readiness.json") if (bundle.output_dir / "generation-readiness.json").exists() else None,
            },
            "analysis": analysis,
            "validation": validation,
            "delivery": delivery,
            "usage": usage.to_dict(),
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
    run_parser.add_argument("--evidence-kind", choices=("manifest", "parts_dir"), required=True)
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

    args = parser.parse_args()
    service = LycolesGenerationService(
        output_root=Path(args.output_root),
        model_routes=_model_routes_from_environment(),
    )

    if args.command == "run-job":
        result = service.run_sync(_request_from_args(args))
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
