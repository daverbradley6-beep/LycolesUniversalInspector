"""Dedicated Lycoles generation service with async job orchestration."""

from __future__ import annotations

import argparse
import importlib.util
import json
import threading
import time
import traceback
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
    analysis_model: str = "deterministic-analysis"
    generation_model: str = "deterministic-generation"
    repair_model: str = "deterministic-repair"


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


class DeterministicLLMProvider:
    def analyze(self, _: EvidenceBundle, __: str) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
        return None, {"tokens": 0, "costGbp": 0.0}

    def generate(self, _: EvidenceBundle, __: dict[str, Any], ___: str) -> tuple[Optional[str], dict[str, Any]]:
        return None, {"tokens": 0, "costGbp": 0.0}

    def repair(self, code: str, _: dict[str, Any], __: str) -> tuple[str, dict[str, Any]]:
        return code, {"tokens": 0, "costGbp": 0.0}


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
    def __init__(self, llm_provider: DeterministicLLMProvider, model_routes: ModelRouteConfig) -> None:
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

        _analysis, llm_usage = self._llm_provider.analyze(bundle, self._routes.analysis_model)
        usage.analysis_tokens += int(llm_usage.get("tokens", 0))
        usage.analysis_cost_gbp += float(llm_usage.get("costGbp", 0.0))
        return summary


class ScriptGenerationEngine:
    def __init__(self, llm_provider: DeterministicLLMProvider, model_routes: ModelRouteConfig) -> None:
        self._llm_provider = llm_provider
        self._routes = model_routes

    def generate(self, bundle: EvidenceBundle, analysis: dict[str, Any], usage: UsageLedger) -> tuple[Optional[str], str]:
        if bundle.generated_script:
            return bundle.generated_script, "deterministic-release-script"
        llm_script, llm_usage = self._llm_provider.generate(bundle, analysis, self._routes.generation_model)
        usage.generation_tokens += int(llm_usage.get("tokens", 0))
        usage.generation_cost_gbp += float(llm_usage.get("costGbp", 0.0))
        if llm_script:
            return llm_script, "llm-generated-script"
        return None, "no-script-generated"


class ValidationRepairEngine:
    def __init__(self, llm_provider: DeterministicLLMProvider, model_routes: ModelRouteConfig) -> None:
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

        generated_result = self._generated_result.build(
            place_id=bundle.place_id,
            scan_id=bundle.scan_id or "scan-unavailable",
            code=code,
            requested_capability=request.requested_capability,
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
    def __init__(self, output_root: Path, model_routes: Optional[ModelRouteConfig] = None) -> None:
        self.output_root = Path(output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.model_routes = model_routes or ModelRouteConfig()
        self.llm_provider = DeterministicLLMProvider()
        self.evidence_processor = EvidenceProcessor()
        self.feature_analysis = FeatureAnalysisEngine(self.llm_provider, self.model_routes)
        self.script_generation = ScriptGenerationEngine(self.llm_provider, self.model_routes)
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
    service = LycolesGenerationService(output_root=Path(args.output_root))

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
