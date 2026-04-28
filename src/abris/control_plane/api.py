from __future__ import annotations

import argparse
import json
import mimetypes
import os
from urllib.parse import parse_qs
from dataclasses import fields, is_dataclass
from importlib import resources
from pathlib import Path
from typing import Any
from wsgiref.simple_server import make_server

from abris.control_plane.auth import LocalAuthConfig, LocalAuthService
from abris.control_plane.service import ControlPlaneService


class ControlPlaneApi:
    def __init__(
        self,
        service: ControlPlaneService,
        auth_service: LocalAuthService,
    ) -> None:
        self.service = service
        self.auth_service = auth_service

    def __call__(self, environ: dict[str, Any], start_response: Any) -> list[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))

        try:
            if path == "/" and method == "GET":
                if self._has_react_frontend():
                    return self._react_static_response(start_response, "index.html")
                return self._static_response(start_response, "index.html")
            if path == "/favicon.ico" and method == "GET":
                start_response("204 No Content", [("Content-Length", "0")])
                return [b""]
            if path.startswith("/assets/") and method == "GET":
                asset_name = path.removeprefix("/").strip()
                if self._has_react_frontend():
                    return self._react_static_response(start_response, asset_name)
                return self._json_response(
                    start_response, 404, {"error": "Static asset not found."}
                )
            if path.startswith("/static/") and method == "GET":
                asset_name = path.removeprefix("/static/").strip()
                if not asset_name or "/" in asset_name or "\\" in asset_name:
                    return self._json_response(
                        start_response, 404, {"error": "Static asset not found."}
                    )
                return self._static_response(start_response, asset_name)

            if path == "/api/auth/login" and method == "POST":
                payload = self._read_json_body(environ)
                context = self.auth_service.login(
                    str(payload.get("username", "")),
                    str(payload.get("password", "")),
                )
                return self._json_response(
                    start_response, 200, self._to_jsonable(context)
                )

            auth_context = self._require_auth(environ)

            if path == "/api/sessions" and method == "GET":
                return self._json_response(
                    start_response,
                    200,
                    {"sessions": self._to_jsonable(self.service.list_sessions())},
                )

            if path == "/api/runs" and method == "GET":
                return self._json_response(
                    start_response,
                    200,
                    {"runs": self._to_jsonable(self.service.list_runs())},
                )

            if path == "/api/artifacts" and method == "GET":
                query = self._parse_query(environ)
                requested_path = query.get("path", ".")
                return self._json_response(
                    start_response,
                    200,
                    self._to_jsonable(
                        self.service.browse_artifacts(str(requested_path))
                    ),
                )

            if path == "/api/dashboard/activity" and method == "GET":
                query = self._parse_query(environ)
                limit = self._parse_int_query(query.get("limit"), default=25)
                timeout_ms = self._parse_int_query(query.get("timeout_ms"), default=250)
                return self._json_response(
                    start_response,
                    200,
                    self._to_jsonable(
                        self.service.get_live_activity(
                            limit=limit,
                            timeout_ms=timeout_ms,
                        )
                    ),
                )

            if path == "/api/evidence/search" and method == "POST":
                payload = self._read_json_body(environ)
                query = str(payload.get("query", "")).strip()
                limit = payload.get("limit", 5)
                run_id = payload.get("run_id")
                if isinstance(limit, bool):
                    raise ValueError("Evidence limit must be an integer.")
                if isinstance(limit, float):
                    limit = int(limit)
                if not isinstance(limit, int):
                    raise ValueError("Evidence limit must be an integer.")
                return self._json_response(
                    start_response,
                    200,
                    self._to_jsonable(
                        self.service.search_evidence(
                            query,
                            limit=limit,
                            run_id=str(run_id).strip() if run_id else None,
                        )
                    ),
                )

            if path.startswith("/api/runs/") and method == "GET":
                parts = [part for part in path.split("/") if part]
                if len(parts) == 3:
                    return self._json_response(
                        start_response,
                        200,
                        self._to_jsonable(self.service.get_run(parts[2])),
                    )

            if path.startswith("/api/sessions/"):
                parts = [part for part in path.split("/") if part]
                if len(parts) >= 3:
                    session_id = parts[2]
                    if len(parts) == 3 and method == "GET":
                        return self._json_response(
                            start_response,
                            200,
                            self._to_jsonable(self.service.get_session(session_id)),
                        )
                    if len(parts) == 4 and parts[3] == "messages" and method == "GET":
                        return self._json_response(
                            start_response,
                            200,
                            {
                                "messages": self._to_jsonable(
                                    self.service.get_session_messages(session_id)
                                )
                            },
                        )
                    if len(parts) == 4 and parts[3] == "usage" and method == "GET":
                        return self._json_response(
                            start_response,
                            200,
                            self._to_jsonable(
                                self.service.get_session_usage(session_id)
                            ),
                        )
                    if len(parts) == 4 and parts[3] == "events" and method == "GET":
                        return self._json_response(
                            start_response,
                            200,
                            {
                                "events": self._to_jsonable(
                                    self.service.get_session_events(session_id)
                                )
                            },
                        )
                    if len(parts) == 4 and parts[3] == "abort" and method == "POST":
                        self.auth_service.authorize(auth_context, {"operator", "admin"})
                        return self._json_response(
                            start_response,
                            202,
                            self._to_jsonable(self.service.abort_session(session_id)),
                        )

            return self._json_response(start_response, 404, {"error": "Not found."})
        except PermissionError as error:
            return self._json_response(start_response, 403, {"error": str(error)})
        except ValueError as error:
            return self._json_response(start_response, 400, {"error": str(error)})

    def _static_response(self, start_response: Any, asset_name: str) -> list[bytes]:
        try:
            asset = resources.files("abris.control_plane.web").joinpath(asset_name)
            body = asset.read_bytes()
        except FileNotFoundError:
            return self._json_response(
                start_response, 404, {"error": "Static asset not found."}
            )

        content_type, _ = mimetypes.guess_type(asset_name)
        start_response(
            "200 OK",
            [
                (
                    "Content-Type",
                    f"{content_type or 'application/octet-stream'}; charset=utf-8",
                ),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
            ],
        )
        return [body]

    def _has_react_frontend(self) -> bool:
        try:
            asset = resources.files("abris.control_plane.webapp").joinpath(
                "dist/index.html"
            )
            return asset.is_file()
        except Exception:
            return False

    def _react_static_response(
        self, start_response: Any, asset_name: str
    ) -> list[bytes]:
        try:
            asset = resources.files("abris.control_plane.webapp").joinpath(
                f"dist/{asset_name}"
            )
            body = asset.read_bytes()
        except FileNotFoundError:
            if asset_name != "index.html":
                return self._react_static_response(start_response, "index.html")
            return self._json_response(
                start_response, 404, {"error": "React frontend asset not found."}
            )

        content_type, _ = mimetypes.guess_type(asset_name)
        start_response(
            "200 OK",
            [
                (
                    "Content-Type",
                    f"{content_type or 'application/octet-stream'}; charset=utf-8",
                ),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
            ],
        )
        return [body]

    def _require_auth(self, environ: dict[str, Any]):
        header = str(environ.get("HTTP_AUTHORIZATION", ""))
        if not header.startswith("Bearer "):
            raise PermissionError("Authentication required.")
        token = header.removeprefix("Bearer ").strip()
        return self.auth_service.authenticate(token)

    def _read_json_body(self, environ: dict[str, Any]) -> dict[str, Any]:
        try:
            content_length = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            content_length = 0

        body = environ.get("wsgi.input")
        if body is None:
            return {}
        raw_bytes = body.read(content_length) if content_length > 0 else body.read()
        if not raw_bytes:
            return {}
        decoded = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("Expected JSON object body.")
        return decoded

    def _parse_query(self, environ: dict[str, Any]) -> dict[str, str]:
        raw_query = str(environ.get("QUERY_STRING", ""))
        parsed = parse_qs(raw_query, keep_blank_values=True)
        return {key: values[-1] if values else "" for key, values in parsed.items()}

    def _parse_int_query(self, raw_value: str | None, *, default: int) -> int:
        if raw_value is None or raw_value == "":
            return default
        try:
            return int(raw_value)
        except ValueError as error:
            raise ValueError("Expected integer query parameter.") from error

    def _json_response(
        self,
        start_response: Any,
        status_code: int,
        payload: Any,
    ) -> list[bytes]:
        body = json.dumps(payload).encode("utf-8")
        start_response(
            f"{status_code} {'OK' if status_code < 400 else 'ERROR'}",
            [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]

    def _to_jsonable(self, value: Any) -> Any:
        if is_dataclass(value) and not isinstance(value, type):
            return {
                field.name: self._to_jsonable(getattr(value, field.name))
                for field in fields(value)
            }
        if isinstance(value, dict):
            return {str(key): self._to_jsonable(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._to_jsonable(item) for item in value]
        if isinstance(value, tuple):
            return [self._to_jsonable(item) for item in value]
        if isinstance(value, Path):
            return str(value)
        return value


def build_control_plane_api(
    service: ControlPlaneService,
    *,
    username: str = "admin",
    password: str = "abris-admin",
    role: str = "admin",
) -> ControlPlaneApi:
    return ControlPlaneApi(
        service=service,
        auth_service=LocalAuthService(
            LocalAuthConfig(username=username, password=password, role=role)
        ),
    )


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the ABRIS control-plane web UI.")
    parser.add_argument(
        "--host", default=os.environ.get("ABRIS_CONTROL_PLANE_HOST", "127.0.0.1")
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("ABRIS_CONTROL_PLANE_PORT", "8000")),
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("ABRIS_CONTROL_PLANE_USERNAME", "admin"),
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("ABRIS_CONTROL_PLANE_PASSWORD", "abris-admin"),
    )
    parser.add_argument(
        "--role",
        default=os.environ.get("ABRIS_CONTROL_PLANE_ROLE", "admin"),
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_argument_parser()
    args = parser.parse_args(argv)

    orchestrator_module = __import__(
        "abris.cli", fromlist=["build_orchestrator_from_env"]
    )
    orchestrator = orchestrator_module.build_orchestrator_from_env()
    if orchestrator.runtime is None:
        raise SystemExit(
            "Control-plane server requires OpenCode runtime. Set ABRIS_USE_OPENCODE=1 before startup."
        )

    app = build_control_plane_api(
        ControlPlaneService(
            runtime=orchestrator.runtime, settings=orchestrator.settings
        ),
        username=args.username,
        password=args.password,
        role=args.role,
    )
    with make_server(args.host, args.port, app) as server:
        print(f"ABRIS control plane listening on http://{args.host}:{args.port}")
        server.serve_forever()


if __name__ == "__main__":
    main()
