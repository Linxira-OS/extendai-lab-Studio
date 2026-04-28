from __future__ import annotations

import atexit
import json
import socket
import subprocess
from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
import time
from typing import Any, Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request

from abris.orchestrator.opencode_contract import (
    OpenCodeRuntime,
    StructuredSchemaRequest,
)


class BridgeTransport(Protocol):
    def request(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(slots=True)
class ManagedOpenCodeServer:
    base_url: str
    process: subprocess.Popen[str] | None = None

    def close(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=3)


@dataclass(slots=True)
class SubprocessBridgeTransport:
    command: list[str]
    workdir: Path | None = None
    env: dict[str, str] | None = None
    default_payload: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 10.0

    def request(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        merged_payload = {**self.default_payload, **payload}
        timeout_seconds = self.timeout_seconds
        if operation == "subscribe_events":
            requested_ms = merged_payload.get("timeout_ms")
            if isinstance(requested_ms, (int, float)):
                timeout_seconds = max(2.0, (float(requested_ms) / 1000.0) + 1.5)
            else:
                timeout_seconds = max(2.0, timeout_seconds)
        try:
            process = subprocess.run(
                [*self.command, operation, json.dumps(merged_payload)],
                cwd=self.workdir,
                env=self.env,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(
                f"Bridge command timed out after {timeout_seconds:.1f}s: {operation}"
            ) from error
        if process.returncode != 0:
            raise RuntimeError(process.stderr.strip() or process.stdout.strip())

        stdout = process.stdout.strip()
        if not stdout:
            return {}
        decoded = json.loads(stdout)
        if not isinstance(decoded, dict):
            raise RuntimeError("Bridge transport returned non-object JSON response.")
        return decoded


def resolve_project_local_opencode_binary(project_root: Path) -> Path:
    bridge_root = project_root / "packages" / "opencode-bridge"
    bin_dir = bridge_root / "node_modules" / ".bin"
    candidates = [bin_dir / "opencode.cmd", bin_dir / "opencode"]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise RuntimeError(
        "Project-local OpenCode runtime not installed. Expected local npm dependency under "
        f"{bin_dir} and will not fall back to host-global opencode."
    )


def build_project_local_bridge_env(project_root: Path) -> dict[str, str]:
    bridge_root = project_root / "packages" / "opencode-bridge"
    local_opencode = resolve_project_local_opencode_binary(project_root)
    existing_path = os.environ.get("PATH", "")
    path_entries = [str(local_opencode.parent)]
    if existing_path:
        path_entries.append(existing_path)

    isolated_root = project_root / ".abris-runtime"
    config_root = isolated_root / "config"
    cache_root = isolated_root / "cache"
    data_root = isolated_root / "data"

    return {
        **os.environ,
        "PATH": os.pathsep.join(path_entries),
        "ABRIS_PROJECT_LOCAL_OPENCODE": str(local_opencode),
        "OPENCODE_BIN": str(local_opencode),
        "XDG_CONFIG_HOME": str(config_root),
        "XDG_CACHE_HOME": str(cache_root),
        "XDG_DATA_HOME": str(data_root),
        "ABRIS_OPENCODE_BRIDGE_ROOT": str(bridge_root),
    }


@dataclass(slots=True)
class OpenCodeBridgeRuntime(OpenCodeRuntime):
    transport: BridgeTransport
    session_defaults: dict[str, Any] = field(default_factory=dict)
    managed_server: ManagedOpenCodeServer | None = None

    def create_session(self, title: str) -> str:
        payload = {"title": title, **self.session_defaults}
        response = self.transport.request("create_session", payload)
        data = response.get("data")
        nested = data if isinstance(data, dict) else {}
        session_id = (
            response.get("session_id")
            or response.get("id")
            or nested.get("session_id")
            or nested.get("id")
        )
        if not isinstance(session_id, str) or not session_id:
            raise RuntimeError("Bridge response did not include a valid session id.")
        return session_id

    def list_sessions(self) -> list[dict[str, Any]]:
        response = self.transport.request("list_sessions", {})
        sessions = response.get("sessions", [])
        if not isinstance(sessions, list):
            raise RuntimeError("Bridge response did not include a valid sessions list.")
        return [session for session in sessions if isinstance(session, dict)]

    def get_session(self, session_id: str) -> dict[str, Any]:
        return self.transport.request("get_session", {"session_id": session_id})

    def get_session_status(self) -> dict[str, Any]:
        return self.transport.request("get_session_status", {})

    def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        response = self.transport.request("get_messages", {"session_id": session_id})
        messages = response.get("messages", [])
        if not isinstance(messages, list):
            raise RuntimeError("Bridge response did not include a valid messages list.")
        return [message for message in messages if isinstance(message, dict)]

    def get_session_usage(self, session_id: str) -> dict[str, Any]:
        response = self.transport.request(
            "get_session_usage", {"session_id": session_id}
        )
        usage = response.get("usage", response)
        if not isinstance(usage, dict):
            raise RuntimeError("Bridge response did not include a valid usage object.")
        return usage

    def prompt_text(self, session_id: str, text: str) -> dict[str, Any]:
        return self.transport.request(
            "prompt_text",
            {
                "session_id": session_id,
                "text": text,
            },
        )

    def prompt_async(self, session_id: str, text: str) -> dict[str, Any]:
        response = self.transport.request(
            "prompt_async",
            {
                "session_id": session_id,
                "text": text,
            },
        )
        if not response:
            return {"accepted": True}
        return response

    def prompt_structured(
        self, session_id: str, request: StructuredSchemaRequest
    ) -> dict[str, Any]:
        return self.transport.request(
            "prompt_structured",
            {
                "session_id": session_id,
                "text": request.prompt,
                "format": {
                    "type": "json_schema",
                    "schema": request.schema,
                    "retryCount": request.retry_count,
                },
            },
        )

    def subscribe_events(
        self, limit: int = 10, timeout_ms: int = 1_000
    ) -> dict[str, Any]:
        response = self.transport.request(
            "subscribe_events",
            {"limit": limit, "timeout_ms": timeout_ms},
        )
        raw_events = response.get("events", [])
        if not isinstance(raw_events, list):
            raise RuntimeError("Bridge response did not include a valid events list.")

        normalized_events: list[dict[str, Any]] = []
        for event in raw_events:
            if not isinstance(event, dict):
                continue
            raw_payload = event.get("payload")
            payload = raw_payload if isinstance(raw_payload, dict) else event
            normalized_events.append(
                {
                    "id": event.get("id") or event.get("event_id"),
                    "session_id": event.get("session_id")
                    or event.get("sessionID")
                    or event.get("sessionId")
                    or payload.get("session_id")
                    or payload.get("sessionID")
                    or payload.get("sessionId"),
                    "type": event.get("type")
                    or event.get("event_type")
                    or event.get("eventType")
                    or event.get("name"),
                    "timestamp": event.get("timestamp")
                    or event.get("createdAt")
                    or event.get("time")
                    or payload.get("timestamp")
                    or payload.get("createdAt")
                    or payload.get("time"),
                    "payload": payload,
                }
            )

        return {
            **response,
            "events": normalized_events,
        }

    def abort_session(self, session_id: str) -> dict[str, Any]:
        return self.transport.request("abort_session", {"session_id": session_id})

    def delete_session(self, session_id: str) -> dict[str, Any]:
        return self.transport.request("delete_session", {"session_id": session_id})


def _opencode_healthcheck(base_url: str, timeout_seconds: float = 0.35) -> bool:
    try:
        with urllib_request.urlopen(
            f"{base_url}/global/health", timeout=timeout_seconds
        ) as response:
            return 200 <= response.status < 300
    except urllib_error.HTTPError:
        return True
    except (urllib_error.URLError, TimeoutError, OSError):
        return False


def start_managed_local_opencode_server(
    project_root: Path,
    *,
    bridge_env: dict[str, str],
    runtime_config: dict[str, Any] | None,
    hostname: str = "127.0.0.1",
    port: int = 4096,
    timeout_ms: int = 5_000,
) -> ManagedOpenCodeServer:
    base_url = f"http://{hostname}:{port}"
    if _opencode_healthcheck(base_url):
        return ManagedOpenCodeServer(base_url=base_url, process=None)

    local_opencode = resolve_project_local_opencode_binary(project_root)
    args = [str(local_opencode), "serve", f"--hostname={hostname}", f"--port={port}"]
    env = {
        **bridge_env,
        "OPENCODE_CONFIG_CONTENT": json.dumps(runtime_config or {}),
    }

    popen_kwargs: dict[str, Any] = {
        "cwd": project_root,
        "env": env,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "text": True,
    }

    if os.name == "nt":
        popen_kwargs["shell"] = True
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        command: str | list[str] = subprocess.list2cmdline(args)
    else:
        popen_kwargs["shell"] = False
        command = args

    process = subprocess.Popen(command, **popen_kwargs)
    deadline = time.monotonic() + (timeout_ms / 1000)

    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"Managed OpenCode server exited with code {process.returncode}."
            )
        if _opencode_healthcheck(base_url):
            server = ManagedOpenCodeServer(base_url=base_url, process=process)
            atexit.register(server.close)
            return server
        try:
            with socket.create_connection((hostname, port), timeout=0.2):
                pass
        except OSError:
            time.sleep(0.1)
            continue
        if _opencode_healthcheck(base_url, timeout_seconds=0.6):
            server = ManagedOpenCodeServer(base_url=base_url, process=process)
            atexit.register(server.close)
            return server
        time.sleep(0.1)

    process.terminate()
    raise RuntimeError(f"Timed out waiting for managed OpenCode server at {base_url}.")


def build_node_bridge_runtime(
    project_root: Path,
    *,
    base_url: str | None = None,
    runtime_config: dict[str, Any] | None = None,
    start_server: bool | None = None,
    directory: Path | None = None,
    workspace_id: str | None = None,
    node_binary: str = "node",
) -> OpenCodeBridgeRuntime:
    if shutil.which(node_binary) is None:
        raise RuntimeError(f"Node executable not found: {node_binary}")

    bridge_cli = project_root / "packages" / "opencode-bridge" / "dist" / "cli.js"
    if not bridge_cli.exists():
        raise RuntimeError(f"OpenCode bridge CLI not built: {bridge_cli}")

    bridge_env = build_project_local_bridge_env(project_root)

    default_payload: dict[str, Any] = {}
    managed_server: ManagedOpenCodeServer | None = None
    should_manage_local_server = base_url is None and (
        start_server is None or start_server
    )

    if should_manage_local_server:
        managed_server = start_managed_local_opencode_server(
            project_root,
            bridge_env=bridge_env,
            runtime_config=runtime_config,
        )
        default_payload["baseUrl"] = managed_server.base_url
        default_payload["startServer"] = False
    else:
        if base_url is not None:
            default_payload["baseUrl"] = base_url
        if runtime_config is not None:
            default_payload["config"] = runtime_config
        if start_server is not None:
            default_payload["startServer"] = start_server

    transport = SubprocessBridgeTransport(
        command=[node_binary, str(bridge_cli)],
        workdir=project_root,
        env=bridge_env,
        default_payload=default_payload,
    )
    session_defaults: dict[str, Any] = {}
    if directory is not None:
        session_defaults["directory"] = str(directory)
    if workspace_id is not None:
        session_defaults["workspaceId"] = workspace_id
    return OpenCodeBridgeRuntime(
        transport=transport,
        session_defaults=session_defaults,
        managed_server=managed_server,
    )
