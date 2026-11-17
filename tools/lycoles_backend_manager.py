#!/usr/bin/env python3
"""Managed lifecycle operations for Lycoles generation backend.

This utility provides supervised startup, health checks, deployment smoke
verification, and bounded restart behavior for the deterministic
`lycoles_generation_service.py` HTTP backend.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICE_SCRIPT = REPO_ROOT / "tools" / "lycoles_generation_service.py"
INSPECTOR_SCRIPT = REPO_ROOT / "LycolesUniversalInspector.lua"

DEFAULT_OUTPUT_ROOT = REPO_ROOT / "build" / "generation-jobs"
DEFAULT_RUNTIME_DIR = REPO_ROOT / "build" / "runtime" / "lycoles-backend"

DEFAULT_HOST = os.environ.get("LYCOLES_BACKEND_HOST", "0.0.0.0")
DEFAULT_PORT = int(os.environ.get("LYCOLES_BACKEND_PORT", "8787"))
DEFAULT_STARTUP_TIMEOUT = float(os.environ.get("LYCOLES_BACKEND_STARTUP_TIMEOUT", "20"))
DEFAULT_HEALTH_TIMEOUT = float(os.environ.get("LYCOLES_BACKEND_HEALTH_TIMEOUT", "2.5"))
DEFAULT_POLL_INTERVAL = float(os.environ.get("LYCOLES_BACKEND_POLL_INTERVAL", "0.25"))
DEFAULT_MAX_RESTARTS = int(os.environ.get("LYCOLES_BACKEND_MAX_RESTARTS", "5"))
DEFAULT_RESTART_WINDOW = float(os.environ.get("LYCOLES_BACKEND_RESTART_WINDOW", "300"))
DEFAULT_RESTART_BACKOFF = float(os.environ.get("LYCOLES_BACKEND_RESTART_BACKOFF", "1.0"))
DEFAULT_RESTART_BACKOFF_MAX = float(os.environ.get("LYCOLES_BACKEND_RESTART_BACKOFF_MAX", "12.0"))


@dataclass(frozen=True)
class RuntimePaths:
    runtime_dir: Path
    supervisor_pid: Path
    service_pid: Path
    supervisor_log: Path
    service_log: Path
    state_json: Path


@dataclass(frozen=True)
class BackendConfig:
    host: str
    port: int
    output_root: Path
    runtime_dir: Path
    startup_timeout: float
    health_timeout: float
    poll_interval: float
    max_restarts: int
    restart_window_seconds: float
    restart_backoff_seconds: float
    restart_backoff_max_seconds: float

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


def _runtime_paths(runtime_dir: Path) -> RuntimePaths:
    return RuntimePaths(
        runtime_dir=runtime_dir,
        supervisor_pid=runtime_dir / "supervisor.pid",
        service_pid=runtime_dir / "service.pid",
        supervisor_log=runtime_dir / "supervisor.log",
        service_log=runtime_dir / "service.log",
        state_json=runtime_dir / "state.json",
    )


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_pid(path: Path) -> Optional[int]:
    try:
        value = path.read_text(encoding="utf-8").strip()
        pid = int(value)
    except (OSError, ValueError):
        return None
    return pid if pid > 0 else None


def _write_pid(path: Path, pid: int) -> None:
    path.write_text(f"{pid}\n", encoding="utf-8")


def _clear_file(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        return


def _pid_alive(pid: Optional[int]) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _read_json(path: Path) -> Optional[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _json_request(url: str, *, method: str = "GET", payload: Optional[dict[str, Any]] = None, timeout: float = 2.5) -> tuple[int, dict[str, Any]]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"content-type": "application/json", "accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            raw = response.read().decode("utf-8")
            decoded = json.loads(raw) if raw else {}
            if not isinstance(decoded, dict):
                decoded = {"raw": decoded}
            return status, decoded
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        decoded = json.loads(raw) if raw else {}
        if not isinstance(decoded, dict):
            decoded = {"raw": decoded}
        return int(exc.code), decoded


def _health_probe(config: BackendConfig) -> dict[str, Any]:
    result: dict[str, Any] = {
        "reachable": False,
        "healthy": False,
        "baseUrl": config.base_url,
        "checkedAt": _now_iso(),
    }
    try:
        health_status, health_payload = _json_request(
            f"{config.base_url}/v1/generation/health",
            timeout=config.health_timeout,
        )
        result["healthStatusCode"] = health_status
        result["healthPayload"] = health_payload
    except Exception as exc:  # pylint: disable=broad-except
        result["error"] = str(exc)
        return result

    try:
        contract_status, contract_payload = _json_request(
            f"{config.base_url}/v1/generation/provider-contract",
            timeout=config.health_timeout,
        )
    except Exception as exc:  # pylint: disable=broad-except
        result["error"] = str(exc)
        return result

    provider = contract_payload.get("provider") if isinstance(contract_payload, dict) else None
    result.update(
        {
            "reachable": True,
            "contractStatusCode": contract_status,
            "providerContract": contract_payload,
            "provider": provider,
            "healthy": (health_status == 200 and contract_status == 200 and isinstance(provider, dict)),
        }
    )
    return result


def _service_command(config: BackendConfig) -> list[str]:
    return [
        sys.executable,
        str(SERVICE_SCRIPT),
        "serve",
        "--output-root",
        str(config.output_root),
        "--host",
        config.host,
        "--port",
        str(config.port),
    ]


def _supervisor_command(config: BackendConfig) -> list[str]:
    return [
        sys.executable,
        str(Path(__file__).resolve()),
        "_supervise",
        "--host",
        config.host,
        "--port",
        str(config.port),
        "--output-root",
        str(config.output_root),
        "--runtime-dir",
        str(config.runtime_dir),
        "--startup-timeout",
        str(config.startup_timeout),
        "--health-timeout",
        str(config.health_timeout),
        "--poll-interval",
        str(config.poll_interval),
        "--max-restarts",
        str(config.max_restarts),
        "--restart-window-seconds",
        str(config.restart_window_seconds),
        "--restart-backoff-seconds",
        str(config.restart_backoff_seconds),
        "--restart-backoff-max-seconds",
        str(config.restart_backoff_max_seconds),
    ]


def _set_deterministic_env(base_env: dict[str, str]) -> dict[str, str]:
    env = dict(base_env)
    env.setdefault("LYCOLES_ENABLE_PAID_LLM", "false")
    env.setdefault("LYCOLES_LLM_PROVIDER", "deterministic")
    return env


def _ensure_runtime_dirs(paths: RuntimePaths, output_root: Path) -> None:
    paths.runtime_dir.mkdir(parents=True, exist_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)


def _status(config: BackendConfig) -> dict[str, Any]:
    paths = _runtime_paths(config.runtime_dir)
    _ensure_runtime_dirs(paths, config.output_root)
    supervisor_pid = _read_pid(paths.supervisor_pid)
    service_pid = _read_pid(paths.service_pid)
    state = _read_json(paths.state_json)
    health = _health_probe(config)
    return {
        "schemaVersion": "30.6.backend-manager-status.1",
        "checkedAt": _now_iso(),
        "host": config.host,
        "port": config.port,
        "baseUrl": config.base_url,
        "paths": {
            "runtimeDir": str(paths.runtime_dir),
            "outputRoot": str(config.output_root),
            "supervisorLog": str(paths.supervisor_log),
            "serviceLog": str(paths.service_log),
            "state": str(paths.state_json),
        },
        "supervisor": {
            "pid": supervisor_pid,
            "running": _pid_alive(supervisor_pid),
        },
        "service": {
            "pid": service_pid,
            "running": _pid_alive(service_pid),
        },
        "health": health,
        "state": state,
    }


def _wait_for_health(config: BackendConfig, timeout_seconds: float) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last = _health_probe(config)
    while time.time() < deadline:
        last = _health_probe(config)
        if last.get("healthy") is True:
            return last
        time.sleep(max(0.05, config.poll_interval))
    return last


def _start(config: BackendConfig, *, dry_run: bool = False) -> dict[str, Any]:
    paths = _runtime_paths(config.runtime_dir)
    _ensure_runtime_dirs(paths, config.output_root)
    current = _status(config)
    if current["supervisor"]["running"] and current["health"].get("healthy") is True:
        return {
            "action": "start",
            "result": "already-running",
            "status": current,
        }

    if dry_run:
        return {
            "action": "start",
            "result": "dry-run",
            "command": _supervisor_command(config),
        }

    with paths.supervisor_log.open("a", encoding="utf-8") as stream:
        stream.write(f"[{_now_iso()}] manager start invoked\n")
        kwargs: dict[str, Any] = {
            "cwd": str(REPO_ROOT),
            "stdin": subprocess.DEVNULL,
            "stdout": stream,
            "stderr": subprocess.STDOUT,
            "start_new_session": True,
            "env": _set_deterministic_env(os.environ),
        }
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        process = subprocess.Popen(_supervisor_command(config), **kwargs)

    _write_pid(paths.supervisor_pid, process.pid)
    health = _wait_for_health(config, config.startup_timeout)
    return {
        "action": "start",
        "result": "started" if health.get("healthy") else "started-unhealthy",
        "supervisorPid": process.pid,
        "health": health,
    }


def _terminate_pid(pid: int, *, grace_seconds: float = 5.0) -> bool:
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return True
    deadline = time.time() + grace_seconds
    while time.time() < deadline:
        if not _pid_alive(pid):
            return True
        time.sleep(0.1)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        return not _pid_alive(pid)
    return not _pid_alive(pid)


def _stop(config: BackendConfig) -> dict[str, Any]:
    paths = _runtime_paths(config.runtime_dir)
    _ensure_runtime_dirs(paths, config.output_root)

    supervisor_pid = _read_pid(paths.supervisor_pid)
    service_pid = _read_pid(paths.service_pid)
    supervisor_was_running = _pid_alive(supervisor_pid)
    service_was_running = _pid_alive(service_pid)

    stopped_supervisor = True
    stopped_service = True

    if supervisor_was_running:
        stopped_supervisor = _terminate_pid(supervisor_pid or 0)
    if service_was_running:
        stopped_service = _terminate_pid(service_pid or 0)

    _clear_file(paths.supervisor_pid)
    _clear_file(paths.service_pid)
    _write_json(
        paths.state_json,
        {
            "updatedAt": _now_iso(),
            "stopped": True,
            "stoppedByManager": True,
            "supervisorPid": None,
            "servicePid": None,
            "supervisorWasRunning": supervisor_was_running,
            "serviceWasRunning": service_was_running,
        },
    )

    if supervisor_pid:
        stopped_supervisor = stopped_supervisor or not _pid_alive(supervisor_pid)
    if service_pid:
        stopped_service = stopped_service or not _pid_alive(service_pid)

    return {
        "action": "stop",
        "stoppedSupervisor": stopped_supervisor,
        "stoppedService": stopped_service,
        "status": _status(config),
    }


def _minimal_snapshot() -> dict[str, Any]:
    return {
        "gameName": "LycolesBackendSmokeGame",
        "placeId": 286090429,
        "scanId": "SMOKE-" + str(int(time.time() * 1000)),
        "partCount": 1,
        "featureEvidence": {
            "movement": {
                "interactionEvents": 6,
                "observedEvents": 6,
                "evidenceLevel": "observed",
            },
            "combat": {
                "interactionEvents": 4,
                "observedEvents": 4,
                "evidenceLevel": "observed",
            },
        },
        "featureReadiness": {
            "summary": {
                "available": 2,
                "blocked": 0,
            }
        },
        "interactionDiagnostics": {
            "requestedCapabilityAssessment": {
                "status": "review-only-candidates",
                "blockers": [],
            }
        },
        "scanStats": {
            "complete": True,
            "profile": "smoke-test",
        },
        "inspectedAt": _now_iso(),
    }


def _smoke_session_lifecycle(config: BackendConfig, *, timeout_seconds: float = 20.0) -> dict[str, Any]:
    snapshot = _minimal_snapshot()
    session_status, created = _json_request(
        f"{config.base_url}/v1/generation/sessions",
        method="POST",
        payload={"inspectionSnapshot": snapshot},
        timeout=config.health_timeout,
    )
    if session_status != 201:
        raise RuntimeError(f"session creation failed: HTTP {session_status} {created}")

    session_id = str((created.get("session") or {}).get("sessionId") or "")
    if not session_id:
        raise RuntimeError("session creation missing sessionId")

    recommendations = (created.get("recommendations") or {}).get("items") or []
    if not recommendations:
        raise RuntimeError("session creation missing recommendations")
    recommendation_id = str((recommendations[0] or {}).get("id") or "")
    if not recommendation_id:
        raise RuntimeError("first recommendation missing id")

    queued_status, queued = _json_request(
        f"{config.base_url}/v1/generation/sessions/{session_id}/jobs",
        method="POST",
        payload={"selectedFeatureIds": [recommendation_id], "customRequest": "smoke run"},
        timeout=config.health_timeout,
    )
    if queued_status != 202:
        raise RuntimeError(f"job queue failed: HTTP {queued_status} {queued}")

    job_id = str(queued.get("jobId") or "")
    if not job_id:
        raise RuntimeError("queued job missing jobId")

    deadline = time.time() + timeout_seconds
    final_job: Optional[dict[str, Any]] = None
    while time.time() < deadline:
        poll_status, job_payload = _json_request(
            f"{config.base_url}/v1/generation/session-jobs/{job_id}",
            timeout=config.health_timeout,
        )
        if poll_status != 200:
            raise RuntimeError(f"job poll failed: HTTP {poll_status} {job_payload}")
        final_job = job_payload
        if str(job_payload.get("status")) in {"completed", "failed"}:
            break
        time.sleep(max(0.05, config.poll_interval))

    if not final_job or str(final_job.get("status")) != "completed":
        raise RuntimeError(f"job did not complete in time: {final_job}")

    result_status, result_payload = _json_request(
        f"{config.base_url}/v1/generation/session-jobs/{job_id}/result",
        timeout=config.health_timeout,
    )
    if result_status != 200:
        raise RuntimeError(f"job result failed: HTTP {result_status} {result_payload}")
    if not isinstance(result_payload.get("script"), str) or not result_payload.get("script"):
        raise RuntimeError("job result missing script")

    return {
        "sessionId": session_id,
        "jobId": job_id,
        "status": "completed",
        "provider": result_payload.get("provider"),
        "versionId": result_payload.get("versionId"),
    }


def _deploy(config: BackendConfig) -> dict[str, Any]:
    started = _start(config)
    health = _wait_for_health(config, config.startup_timeout)
    smoke = _smoke_session_lifecycle(config, timeout_seconds=max(10.0, config.startup_timeout))
    return {
        "action": "deploy",
        "started": started,
        "health": health,
        "smoke": smoke,
    }


def _setup_check(config: BackendConfig) -> dict[str, Any]:
    paths = _runtime_paths(config.runtime_dir)
    _ensure_runtime_dirs(paths, config.output_root)
    return {
        "schemaVersion": "30.6.backend-manager-setup-check.1",
        "checkedAt": _now_iso(),
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
        },
        "node": {
            "path": shutil.which("node"),
        },
        "requiredFiles": {
            "serviceScript": str(SERVICE_SCRIPT),
            "serviceScriptExists": SERVICE_SCRIPT.is_file(),
            "inspectorScript": str(INSPECTOR_SCRIPT),
            "inspectorScriptExists": INSPECTOR_SCRIPT.is_file(),
        },
        "defaults": {
            "paidLlmEnabledDefault": _set_deterministic_env({}).get("LYCOLES_ENABLE_PAID_LLM"),
            "providerDefault": _set_deterministic_env({}).get("LYCOLES_LLM_PROVIDER"),
            "host": config.host,
            "port": config.port,
        },
        "paths": {
            "runtimeDir": str(paths.runtime_dir),
            "outputRoot": str(config.output_root),
        },
    }


def _supervise(config: BackendConfig) -> int:
    paths = _runtime_paths(config.runtime_dir)
    _ensure_runtime_dirs(paths, config.output_root)

    stop_flag = {"stop": False}

    def _handle_stop(_signum: int, _frame: Any) -> None:
        stop_flag["stop"] = True

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    _write_pid(paths.supervisor_pid, os.getpid())
    restart_times: list[float] = []
    restart_count = 0
    child: Optional[subprocess.Popen[Any]] = None

    try:
        while not stop_flag["stop"]:
            env = _set_deterministic_env(os.environ)
            with paths.service_log.open("a", encoding="utf-8") as service_log:
                service_log.write(f"[{_now_iso()}] starting service process\n")
                child = subprocess.Popen(
                    _service_command(config),
                    cwd=str(REPO_ROOT),
                    stdin=subprocess.DEVNULL,
                    stdout=service_log,
                    stderr=subprocess.STDOUT,
                    env=env,
                )
            _write_pid(paths.service_pid, child.pid)
            _write_json(
                paths.state_json,
                {
                    "updatedAt": _now_iso(),
                    "supervisorPid": os.getpid(),
                    "servicePid": child.pid,
                    "serviceCommand": _service_command(config),
                    "restartCount": restart_count,
                },
            )

            while not stop_flag["stop"]:
                code = child.poll()
                if code is None:
                    time.sleep(0.2)
                    continue
                break

            if stop_flag["stop"]:
                break

            exit_code = child.returncode
            restart_count += 1
            now = time.time()
            restart_times.append(now)
            restart_times = [stamp for stamp in restart_times if now - stamp <= config.restart_window_seconds]

            _write_json(
                paths.state_json,
                {
                    "updatedAt": _now_iso(),
                    "supervisorPid": os.getpid(),
                    "lastExitCode": exit_code,
                    "restartCount": restart_count,
                    "restartsInWindow": len(restart_times),
                    "windowSeconds": config.restart_window_seconds,
                },
            )

            if len(restart_times) > config.max_restarts:
                with paths.supervisor_log.open("a", encoding="utf-8") as stream:
                    stream.write(
                        f"[{_now_iso()}] restart limit exceeded; exiting supervisor."
                        f" count={len(restart_times)} window={config.restart_window_seconds}s\n"
                    )
                break

            backoff = min(
                config.restart_backoff_max_seconds,
                config.restart_backoff_seconds * (2 ** max(0, restart_count - 1)),
            )
            with paths.supervisor_log.open("a", encoding="utf-8") as stream:
                stream.write(
                    f"[{_now_iso()}] service exited code={exit_code}; "
                    f"restarting in {backoff:.2f}s\n"
                )
            time.sleep(max(0.1, backoff))

    except Exception:  # pylint: disable=broad-except
        with paths.supervisor_log.open("a", encoding="utf-8") as stream:
            stream.write(f"[{_now_iso()}] supervisor failure\n{traceback.format_exc()}\n")
        return 1
    finally:
        if child and child.poll() is None:
            _terminate_pid(child.pid, grace_seconds=5.0)
        _clear_file(paths.service_pid)
        _clear_file(paths.supervisor_pid)
        _write_json(
            paths.state_json,
            {
                "updatedAt": _now_iso(),
                "supervisorPid": None,
                "servicePid": None,
                "stopped": True,
            },
        )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--host", default=DEFAULT_HOST)
        sub.add_argument("--port", type=int, default=DEFAULT_PORT)
        sub.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
        sub.add_argument("--runtime-dir", default=str(DEFAULT_RUNTIME_DIR))
        sub.add_argument("--startup-timeout", type=float, default=DEFAULT_STARTUP_TIMEOUT)
        sub.add_argument("--health-timeout", type=float, default=DEFAULT_HEALTH_TIMEOUT)
        sub.add_argument("--poll-interval", type=float, default=DEFAULT_POLL_INTERVAL)
        sub.add_argument("--max-restarts", type=int, default=DEFAULT_MAX_RESTARTS)
        sub.add_argument("--restart-window-seconds", type=float, default=DEFAULT_RESTART_WINDOW)
        sub.add_argument("--restart-backoff-seconds", type=float, default=DEFAULT_RESTART_BACKOFF)
        sub.add_argument("--restart-backoff-max-seconds", type=float, default=DEFAULT_RESTART_BACKOFF_MAX)

    for name in ("setup-check", "start", "stop", "status", "health", "ensure", "deploy", "smoke", "_supervise"):
        command_parser = subparsers.add_parser(name)
        add_common(command_parser)
        if name == "start":
            command_parser.add_argument("--dry-run", action="store_true")

    return parser


def _config_from_args(args: argparse.Namespace) -> BackendConfig:
    return BackendConfig(
        host=str(args.host),
        port=max(1, int(args.port)),
        output_root=Path(args.output_root).expanduser().resolve(),
        runtime_dir=Path(args.runtime_dir).expanduser().resolve(),
        startup_timeout=max(1.0, float(args.startup_timeout)),
        health_timeout=max(0.25, float(args.health_timeout)),
        poll_interval=max(0.05, float(args.poll_interval)),
        max_restarts=max(0, int(args.max_restarts)),
        restart_window_seconds=max(1.0, float(args.restart_window_seconds)),
        restart_backoff_seconds=max(0.1, float(args.restart_backoff_seconds)),
        restart_backoff_max_seconds=max(0.2, float(args.restart_backoff_max_seconds)),
    )


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    config = _config_from_args(args)

    if args.command == "_supervise":
        return _supervise(config)

    if args.command == "setup-check":
        print(json.dumps(_setup_check(config), indent=2, sort_keys=True))
        return 0

    if args.command == "status":
        print(json.dumps(_status(config), indent=2, sort_keys=True))
        return 0

    if args.command == "health":
        print(json.dumps(_health_probe(config), indent=2, sort_keys=True))
        return 0

    if args.command == "start":
        print(json.dumps(_start(config, dry_run=bool(args.dry_run)), indent=2, sort_keys=True))
        return 0

    if args.command == "stop":
        print(json.dumps(_stop(config), indent=2, sort_keys=True))
        return 0

    if args.command == "ensure":
        status = _status(config)
        if status.get("health", {}).get("healthy") is True:
            result = {"action": "ensure", "result": "already-healthy", "status": status}
        else:
            started = _start(config)
            result = {
                "action": "ensure",
                "result": "restarted" if started.get("result") != "already-running" else "reused-running",
                "start": started,
                "status": _status(config),
            }
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    if args.command == "smoke":
        print(json.dumps(_smoke_session_lifecycle(config), indent=2, sort_keys=True))
        return 0

    if args.command == "deploy":
        print(json.dumps(_deploy(config), indent=2, sort_keys=True))
        return 0

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
