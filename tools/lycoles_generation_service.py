"""Dedicated Lycoles generation service with async job orchestration."""

from __future__ import annotations

import argparse
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


def _load_local_module(filename: str, name: str):
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class ModelRouteConfig:
    analysis_model: str = "gpt-4.1-mini"
    generation_model: str = "gpt-4.1"
    repair_model: str = "gpt-4.1-mini"


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

    def to_dict(self) -> dict[str, Any]:
        total_tokens = self.analysis_tokens + self.generation_tokens + self.repair_tokens
        total_cost = self.analysis_cost_gbp + self.generation_cost_gbp + self.repair_cost_gbp
        return {
            "analysis": {"tokens": self.analysis_tokens, "costGbp": round(self.analysis_cost_gbp, 8)},
            "generation": {"tokens": self.generation_tokens, "costGbp": round(self.generation_cost_gbp, 8)},
            "repair": {"tokens": self.repair_tokens, "costGbp": round(self.repair_cost_gbp, 8)},
            "total": {"tokens": total_tokens, "costGbp": round(total_cost, 8)},
        }


@dataclass(frozen=True)
class GenerationRequest:
    evidence_kind: str
    evidence_path: Path
    requested_capability: Optional[str] = None


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

    def _usage(self, payload: dict[str, Any], stage: str) -> dict[str, Any]:
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        tokens = int(usage.get("total_tokens") or 0)
        if stage == "analysis":
            rate = self._cost_config.analysis_cost_gbp_per_1k_tokens
        elif stage == "generation":
            rate = self._cost_config.generation_cost_gbp_per_1k_tokens
        else:
            rate = self._cost_config.repair_cost_gbp_per_1k_tokens
        return {"tokens": tokens, "costGbp": (tokens / 1000.0) * rate}

    def _call_responses_api(self, model: str, system_prompt: str, user_prompt: str) -> dict[str, Any]:
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
        for attempt in range(self._retries + 1):
            request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                status = exc.code
                text = exc.read().decode("utf-8", errors="replace")
                exc.close()
                last_error = f"HTTP {status}: {text[:400]}"
                if status not in transient or attempt == self._retries:
                    raise ValueError(f"Provider request failed: {last_error}") from None
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = str(exc)
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
        payload = self._call_responses_api(model, system_prompt, user_prompt)
        text = _response_output_text(payload)
        parsed = _extract_first_json_object(text)
        return (parsed if isinstance(parsed, dict) else None), self._usage(payload, "analysis")

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
        payload = self._call_responses_api(model, system_prompt, user_prompt)
        text = _strip_lua_fences(_response_output_text(payload))
        return (text or None), self._usage(payload, "generation")

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
        payload = self._call_responses_api(model, system_prompt, user_prompt)
        text = _strip_lua_fences(_response_output_text(payload))
        return (text or code), self._usage(payload, "repair")


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

    def process(self, request: GenerationRequest, output_dir: Path) -> EvidenceBundle:
        output_dir.mkdir(parents=True, exist_ok=True)
        if request.evidence_kind == "manifest":
            readiness = self._build_release.build_manifest_readiness(request.evidence_path, output_dir)
            return EvidenceBundle(
                mode="manifest-only",
                place_id=readiness.get("placeId"),
                scan_id=readiness.get("scanId"),
                output_dir=output_dir,
                manifest_readiness=readiness,
            )

        if request.evidence_kind != "parts_dir":
            raise ValueError("Unsupported evidence kind")

        manifest = self._build_release.build(request.evidence_path, output_dir)
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

    def analyze(self, bundle: EvidenceBundle, usage: UsageLedger) -> dict[str, Any]:
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

        ai_analysis, llm_usage = self._llm_provider.analyze(bundle, self._routes.analysis_model)
        usage.analysis_tokens += int(llm_usage.get("tokens", 0))
        usage.analysis_cost_gbp += float(llm_usage.get("costGbp", 0.0))
        if isinstance(ai_analysis, dict):
            summary["aiAnalysis"] = ai_analysis
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

    def generate(self, bundle: EvidenceBundle, analysis: dict[str, Any], usage: UsageLedger) -> tuple[Optional[str], str]:
        if bundle.generated_script and not self._prefer_ai_generation:
            return bundle.generated_script, "deterministic-release-script"

        llm_script, llm_usage = self._llm_provider.generate(bundle, analysis, self._routes.generation_model)
        usage.generation_tokens += int(llm_usage.get("tokens", 0))
        usage.generation_cost_gbp += float(llm_usage.get("costGbp", 0.0))
        if llm_script:
            return llm_script, "ai-generated-script"
        if bundle.generated_script:
            return bundle.generated_script, "deterministic-release-script"
        return None, "no-script-generated"


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
    ) -> tuple[Optional[str], dict[str, Any]]:
        if code is None:
            return None, {"valid": False, "reason": "no script available", "placeGuard": False}
        if not isinstance(place_id, int) or place_id <= 0:
            return None, {"valid": False, "reason": "invalid place id", "placeGuard": False}
        validation = self._basic_validation(code, place_id)
        if validation["valid"]:
            return code, validation
        repaired, llm_usage = self._llm_provider.repair(code, analysis, self._routes.repair_model)
        usage.repair_tokens += int(llm_usage.get("tokens", 0))
        usage.repair_cost_gbp += float(llm_usage.get("costGbp", 0.0))
        repaired_validation = self._basic_validation(repaired, place_id)
        return (repaired if repaired_validation["valid"] else None), repaired_validation


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

    def deliver(
        self,
        bundle: EvidenceBundle,
        request: GenerationRequest,
        code: Optional[str],
        validation: dict[str, Any],
    ) -> dict[str, Any]:
        result_path = bundle.output_dir / "generated-result.json"
        if code is None or not validation.get("valid"):
            payload = {"generatedResultPath": None, "generatedResultSchema": None, "claims": dict(FALSE_CLAIMS)}
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
        return {
            "generatedResultPath": str(result_path),
            "generatedResultSchema": generated_result.get("schemaVersion"),
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

    def _output_dir_for(self, job_id: str) -> Path:
        return self.output_root / job_id

    def _run_pipeline(self, job_id: str, request: GenerationRequest) -> dict[str, Any]:
        usage = UsageLedger()
        output_dir = self._output_dir_for(job_id)
        bundle = self.evidence_processor.process(request, output_dir)
        analysis = self.feature_analysis.analyze(bundle, usage)
        code, generation_source = self.script_generation.generate(bundle, analysis, usage)
        code, validation = self.validation_repair.validate_and_repair(code, bundle.place_id, analysis, usage)
        delivery = self.delivery.deliver(bundle, request, code, validation)

        blockers = analysis.get("explicitBlockers") or []
        generation_status = "blocked" if code is None else ("generated-with-blockers" if blockers else "generated")
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
                "aiInferencePerformed": generation_source == "ai-generated-script" or usage.analysis_tokens > 0 or usage.repair_tokens > 0,
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
                        request = GenerationRequest(
                            evidence_kind=str(payload.get("evidenceKind")),
                            evidence_path=Path(str(payload.get("evidencePath"))).expanduser().resolve(),
                            requested_capability=payload.get("requestedCapability"),
                        )
                        job_id = service.submit(request)
                        return self._json({"jobId": job_id, "status": "queued", "statusUrl": f"/v1/generation/jobs/{job_id}"}, 202)
                    except Exception as exc:  # pylint: disable=broad-except
                        return self._json({"error": str(exc)}, 400)
                return self._json({"error": "Not found"}, 404)

        return Handler


def _request_from_args(args: argparse.Namespace) -> GenerationRequest:
    return GenerationRequest(
        evidence_kind=args.evidence_kind,
        evidence_path=Path(args.evidence_path).expanduser().resolve(),
        requested_capability=args.requested_capability,
    )


def _model_routes_from_environment() -> ModelRouteConfig:
    return ModelRouteConfig(
        analysis_model=(os.environ.get("LYCOLES_ANALYSIS_MODEL") or ModelRouteConfig.analysis_model).strip(),
        generation_model=(os.environ.get("LYCOLES_GENERATION_MODEL") or ModelRouteConfig.generation_model).strip(),
        repair_model=(os.environ.get("LYCOLES_REPAIR_MODEL") or ModelRouteConfig.repair_model).strip(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run-job", help="Run one generation job synchronously")
    run_parser.add_argument("--evidence-kind", choices=("manifest", "parts_dir"), required=True)
    run_parser.add_argument("--evidence-path", required=True)
    run_parser.add_argument("--requested-capability", default=None)
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
