import importlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

schemas = importlib.import_module("abris.models.schemas")
auth_module = importlib.import_module("abris.control_plane.auth")
api_module = importlib.import_module("abris.control_plane.api")
service_module = importlib.import_module("abris.control_plane.service")
settings_module = importlib.import_module("abris.config.settings")

ControlPlaneService = service_module.ControlPlaneService
LocalAuthConfig = auth_module.LocalAuthConfig
LocalAuthService = auth_module.LocalAuthService
build_control_plane_api = api_module.build_control_plane_api
TokenUsage = schemas.TokenUsage
Settings = settings_module.Settings


class FakeRuntime:
    def __init__(self) -> None:
        self.aborted: list[str] = []

    def create_session(self, title: str) -> str:
        return "ses_new"

    def get_session(self, session_id: str) -> dict:
        return {"id": session_id, "title": "Demo Session", "status": "running"}

    def get_session_status(self) -> dict:
        return {
            "status": [
                {
                    "session_id": "ses_123",
                    "title": "Demo Session",
                    "status": "running",
                }
            ]
        }

    def list_sessions(self) -> list[dict]:
        return [
            {
                "session_id": "ses_123",
                "title": "Demo Session",
                "status": "running",
            }
        ]

    def get_messages(self, session_id: str) -> list[dict]:
        return [
            {
                "id": "msg_1",
                "role": "user",
                "createdAt": "2026-03-19T10:00:00Z",
                "usage": {"inputTokens": 12, "outputTokens": 0, "totalTokens": 12},
            },
            {
                "id": "msg_2",
                "role": "assistant",
                "createdAt": "2026-03-19T10:00:02Z",
                "usage": {
                    "inputTokens": 5,
                    "outputTokens": 17,
                    "totalTokens": 22,
                    "cost": 0.03,
                },
            },
        ]

    def get_session_usage(self, session_id: str) -> dict:
        return {
            "input_tokens": 17,
            "output_tokens": 17,
            "total_tokens": 34,
            "cost": 0.03,
            "message_count": 2,
            "prompt_count": 1,
        }

    def prompt_text(self, session_id: str, text: str) -> dict:
        return {"ok": True}

    def prompt_async(self, session_id: str, text: str) -> dict:
        return {"accepted": True}

    def prompt_structured(self, session_id: str, request) -> dict:
        return {
            "structured_output": {
                "records": [
                    {
                        "source_class": "public_registry",
                        "provider": "arxiv",
                        "title": "Batch correction in single-cell RNA-seq",
                        "authors": ["A. Author", "B. Author"],
                        "year": 2025,
                        "url": "https://arxiv.org/abs/1234.5678",
                        "arxiv_id": "1234.5678",
                        "license": "CC-BY",
                        "snippet": "Introduces a robust correction benchmark.",
                        "abstract": "A benchmark study for batch correction.",
                        "confidence": 0.92,
                    },
                    {
                        "source_class": "public_registry",
                        "provider": "semantic scholar",
                        "title": "Review of transcriptomics automation",
                        "authors": ["C. Author"],
                        "year": 2024,
                        "url": "https://example.org/review",
                        "confidence": 0.61,
                    },
                ],
                "warnings": ["One provider requires manual review."],
            }
        }

    def subscribe_events(self, limit: int = 10, timeout_ms: int = 1000) -> dict:
        return {
            "events": [
                {
                    "id": "evt_1",
                    "type": "session.message",
                    "payload": {
                        "sessionId": "ses_123",
                        "timestamp": "2026-03-19T10:00:02Z",
                        "detail": "hello",
                    },
                },
                {
                    "id": "evt_2",
                    "session_id": "ses_other",
                    "type": "session.message",
                },
            ]
        }

    def abort_session(self, session_id: str) -> dict:
        self.aborted.append(session_id)
        return {"ok": True, "session_id": session_id}

    def delete_session(self, session_id: str) -> dict:
        return {"ok": True}


class ControlPlaneServiceTest(unittest.TestCase):
    def test_list_sessions_aggregates_usage(self) -> None:
        service = ControlPlaneService(runtime=FakeRuntime())

        sessions = service.list_sessions()

        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].session_id, "ses_123")
        self.assertEqual(sessions[0].message_count, 2)
        self.assertEqual(sessions[0].usage.total_tokens, 34)
        self.assertAlmostEqual(sessions[0].usage.cost, 0.03)

    def test_get_session_usage_prefers_runtime_usage_snapshot(self) -> None:
        service = ControlPlaneService(runtime=FakeRuntime())

        usage = service.get_session_usage("ses_123")

        self.assertIsInstance(usage, TokenUsage)
        self.assertEqual(usage.total_tokens, 34)
        self.assertEqual(usage.prompt_count, 1)

    def test_get_session_events_filters_other_sessions(self) -> None:
        service = ControlPlaneService(runtime=FakeRuntime())

        events = service.get_session_events("ses_123")

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_id, "evt_1")
        self.assertEqual(events[0].session_id, "ses_123")
        self.assertEqual(events[0].timestamp, "2026-03-19T10:00:02Z")
        self.assertEqual(events[0].payload["detail"], "hello")

    def test_browse_artifacts_returns_metadata_only(self) -> None:
        runtime = FakeRuntime()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "examples").mkdir()
            (root / "examples" / "notes.txt").write_text("hello", encoding="utf-8")
            service = ControlPlaneService(
                runtime=runtime,
                settings=Settings.from_root(root),
            )

            listing = service.browse_artifacts("examples")

        self.assertEqual(listing["path"], "examples")
        self.assertEqual(len(listing["entries"]), 1)
        entry = listing["entries"][0]
        self.assertEqual(entry.kind, "TEXT")
        self.assertEqual(entry.safe_action, "allow_direct_read")
        self.assertNotIn("content", entry.summary)

    def test_browse_artifacts_protects_large_fastq(self) -> None:
        runtime = FakeRuntime()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            data_dir.mkdir()
            fastq = data_dir / "sample_R1.fastq.gz"
            settings = Settings.from_root(root)
            fastq.write_bytes(b"0" * (settings.max_direct_read_bytes + 16))
            service = ControlPlaneService(runtime=runtime, settings=settings)

            listing = service.browse_artifacts("data")

        entry = listing["entries"][0]
        self.assertEqual(entry.kind, "FASTQ")
        self.assertEqual(entry.safe_action, "convert_to_metadata_only")

    def test_browse_artifacts_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = ControlPlaneService(
                runtime=FakeRuntime(),
                settings=Settings.from_root(root),
            )

            with self.assertRaises(ValueError):
                service.browse_artifacts("../outside")

    def test_live_activity_returns_sessions_and_events(self) -> None:
        service = ControlPlaneService(runtime=FakeRuntime())

        payload = service.get_live_activity(limit=10, timeout_ms=200)

        self.assertEqual(payload["totals"]["session_count"], 1)
        self.assertEqual(len(payload["sessions"]), 1)
        self.assertEqual(len(payload["events"]), 1)
        self.assertEqual(payload["events"][0].session_id, "ses_123")

    def test_search_evidence_returns_bundle_with_admissibility(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ControlPlaneService(
                runtime=FakeRuntime(),
                settings=Settings.from_root(Path(temp_dir)),
            )

            bundle = service.search_evidence("single-cell batch correction", limit=5)

            self.assertEqual(bundle.query, "single-cell batch correction")
            self.assertTrue(bundle.run_id)
            self.assertEqual(bundle.step_id, "step_evidence_search")
            self.assertEqual(len(bundle.records), 2)
            self.assertEqual(bundle.records[0].admissibility, "allowed")
            self.assertEqual(bundle.records[1].admissibility, "downgraded")
            self.assertEqual(bundle.summary["record_count"], 2)
            self.assertEqual(bundle.usage.total_tokens, 34)

            runs = service.list_runs()
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0].run_id, bundle.run_id)
            self.assertEqual(runs[0].current_state, "completed")

    def test_get_run_returns_authoritative_run_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ControlPlaneService(
                runtime=FakeRuntime(),
                settings=Settings.from_root(Path(temp_dir)),
            )
            bundle = service.search_evidence("single-cell batch correction", limit=5)

            payload = service.get_run(bundle.run_id)

            self.assertEqual(payload["run"].run_id, bundle.run_id)
            self.assertEqual(payload["run"].current_state, "completed")
            self.assertEqual(payload["run"].owner, "evidence_service")
            self.assertEqual(payload["run"].last_checkpoint, bundle.bundle_id)
            self.assertGreaterEqual(len(payload["events"]), 3)
            self.assertEqual(len(payload["steps"]), 1)
            self.assertEqual(payload["steps"][0].step_id, "step_evidence_search")
            self.assertEqual(payload["steps"][0].owner, "evidence_service")
            self.assertEqual(payload["steps"][0].last_checkpoint, bundle.bundle_id)
            self.assertGreaterEqual(len(payload["timeline"]), 3)
            self.assertEqual(payload["timeline"][0]["event_type"], "run.created")
            self.assertEqual(
                payload["current_step"]["step_id"],
                "step_evidence_search",
            )
            self.assertEqual(payload["current_step"]["owner"], "evidence_service")
            self.assertEqual(
                payload["current_step"]["last_checkpoint"], bundle.bundle_id
            )
            self.assertEqual(len(payload["linked"]["evidence_bundles"]), 1)
            self.assertEqual(
                payload["linked"]["evidence_bundles"][0]["bundle_id"],
                bundle.bundle_id,
            )

    def test_list_runs_marks_stalled_from_run_ledger_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = Settings.from_root(Path(temp_dir))
            settings.stall_timeout_seconds = 5
            service = ControlPlaneService(runtime=FakeRuntime(), settings=settings)
            run = service.run_ledger.create_run(
                run_type="analysis",
                title="Stalled analysis",
                initial_state="running",
                owner="orchestrator",
            )
            service.run_ledger.start_step(
                run.run_id,
                step_id="step_001_count_matrix_summary",
                step_type="pipeline_step",
                title="count_matrix_summary",
                owner="orchestrator",
            )
            stale_run = service.run_ledger.get_run(run.run_id)
            stale_timestamp = (
                datetime.now(timezone.utc) - timedelta(seconds=90)
            ).isoformat()
            stale_run.last_heartbeat = stale_timestamp
            stale_run.waiting_on = "runtime_search"
            stale_run.steps[0].last_heartbeat = stale_timestamp
            service.run_ledger._write_state(stale_run)

            runs = service.list_runs()
            payload = service.get_run(run.run_id)

            self.assertEqual(len(runs), 1)
            self.assertTrue(runs[0].stalled)
            self.assertIn("No run heartbeat", runs[0].stalled_reason)
            self.assertTrue(payload["run"].stalled)
            self.assertTrue(payload["steps"][0].stalled)
            self.assertIn("No step heartbeat", payload["steps"][0].stalled_reason)


class LocalAuthServiceTest(unittest.TestCase):
    def test_login_and_authenticate(self) -> None:
        service = LocalAuthService(LocalAuthConfig(username="admin", password="pw"))

        context = service.login("admin", "pw")
        authenticated = service.authenticate(context.session_token)

        self.assertEqual(authenticated.username, "admin")
        self.assertEqual(authenticated.role, "admin")


class ControlPlaneApiTest(unittest.TestCase):
    def _request_raw(
        self,
        app,
        method: str,
        path: str,
        body=None,
        token: str | None = None,
        query_string: str = "",
    ):
        raw_body = json.dumps(body).encode("utf-8") if body is not None else b""
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": query_string,
            "CONTENT_LENGTH": str(len(raw_body)),
            "wsgi.input": BytesIO(raw_body),
        }
        if token is not None:
            environ["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        captured = {}

        def start_response(status, headers):
            captured["status"] = status
            captured["headers"] = headers

        response = b"".join(app(environ, start_response))
        return captured["status"], captured["headers"], response

    def _request(
        self,
        app,
        method: str,
        path: str,
        body=None,
        token: str | None = None,
        query_string: str = "",
    ):
        status, _, response = self._request_raw(
            app,
            method,
            path,
            body=body,
            token=token,
            query_string=query_string,
        )
        return status, json.loads(response.decode("utf-8"))

    def test_api_requires_auth_for_session_listing(self) -> None:
        app = build_control_plane_api(
            ControlPlaneService(runtime=FakeRuntime()),
            username="admin",
            password="pw",
        )

        status, payload = self._request(app, "GET", "/api/sessions")

        self.assertTrue(status.startswith("403"))
        self.assertIn("Authentication required", payload["error"])

    def test_root_serves_web_shell(self) -> None:
        app = build_control_plane_api(
            ControlPlaneService(runtime=FakeRuntime()),
            username="admin",
            password="pw",
        )

        status, headers, body = self._request_raw(app, "GET", "/")

        self.assertTrue(status.startswith("200"))
        self.assertEqual(dict(headers).get("Cache-Control"), "no-store")
        self.assertIn("ABRIS Control Plane", body.decode("utf-8"))

    def test_static_asset_serving_returns_javascript(self) -> None:
        app = build_control_plane_api(
            ControlPlaneService(runtime=FakeRuntime()),
            username="admin",
            password="pw",
        )

        status, headers, body = self._request_raw(app, "GET", "/static/app.js")

        self.assertTrue(status.startswith("200"))
        self.assertIn("javascript", dict(headers).get("Content-Type", ""))
        self.assertIn("requestJson", body.decode("utf-8"))

    def test_api_evidence_search_returns_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = build_control_plane_api(
                ControlPlaneService(
                    runtime=FakeRuntime(), settings=Settings.from_root(Path(temp_dir))
                ),
                username="admin",
                password="pw",
            )
            _, login_payload = self._request(
                app,
                "POST",
                "/api/auth/login",
                {"username": "admin", "password": "pw"},
            )

            status, payload = self._request(
                app,
                "POST",
                "/api/evidence/search",
                body={"query": "single-cell batch correction", "limit": 5},
                token=login_payload["session_token"],
            )

            self.assertTrue(status.startswith("200"))
            self.assertEqual(payload["query"], "single-cell batch correction")
            self.assertTrue(payload["run_id"])
            self.assertEqual(payload["summary"]["record_count"], 2)
            self.assertEqual(payload["records"][0]["provider"], "arxiv")

            run_status, run_payload = self._request(
                app,
                "GET",
                f"/api/runs/{payload['run_id']}",
                token=login_payload["session_token"],
            )

            self.assertTrue(run_status.startswith("200"))
            self.assertEqual(run_payload["run"]["run_id"], payload["run_id"])
            self.assertEqual(run_payload["run"]["current_state"], "completed")
            self.assertEqual(run_payload["run"]["owner"], "evidence_service")
            self.assertEqual(
                run_payload["run"]["last_checkpoint"], payload["bundle_id"]
            )
            self.assertEqual(len(run_payload["steps"]), 1)
            self.assertGreaterEqual(len(run_payload["timeline"]), 3)
            self.assertEqual(
                run_payload["current_step"]["step_id"],
                "step_evidence_search",
            )
            self.assertEqual(run_payload["current_step"]["owner"], "evidence_service")

    def test_api_runs_lists_authoritative_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            app = build_control_plane_api(
                ControlPlaneService(
                    runtime=FakeRuntime(), settings=Settings.from_root(Path(temp_dir))
                ),
                username="admin",
                password="pw",
            )
            _, login_payload = self._request(
                app,
                "POST",
                "/api/auth/login",
                {"username": "admin", "password": "pw"},
            )
            _, search_payload = self._request(
                app,
                "POST",
                "/api/evidence/search",
                body={"query": "single-cell batch correction", "limit": 5},
                token=login_payload["session_token"],
            )

            status, payload = self._request(
                app,
                "GET",
                "/api/runs",
                token=login_payload["session_token"],
            )

            self.assertTrue(status.startswith("200"))
            self.assertEqual(len(payload["runs"]), 1)
            self.assertEqual(payload["runs"][0]["run_id"], search_payload["run_id"])

    def test_api_login_and_list_sessions(self) -> None:
        app = build_control_plane_api(
            ControlPlaneService(runtime=FakeRuntime()),
            username="admin",
            password="pw",
        )

        login_status, login_payload = self._request(
            app,
            "POST",
            "/api/auth/login",
            {"username": "admin", "password": "pw"},
        )
        status, payload = self._request(
            app,
            "GET",
            "/api/sessions",
            token=login_payload["session_token"],
        )

        self.assertTrue(login_status.startswith("200"))
        self.assertTrue(status.startswith("200"))
        self.assertEqual(payload["sessions"][0]["session_id"], "ses_123")
        self.assertEqual(payload["sessions"][0]["usage"]["total_tokens"], 34)

    def test_api_abort_requires_operator_role(self) -> None:
        app = build_control_plane_api(
            ControlPlaneService(runtime=FakeRuntime()),
            username="viewer",
            password="pw",
            role="viewer",
        )
        _, login_payload = self._request(
            app,
            "POST",
            "/api/auth/login",
            {"username": "viewer", "password": "pw"},
        )

        status, payload = self._request(
            app,
            "POST",
            "/api/sessions/ses_123/abort",
            token=login_payload["session_token"],
        )

        self.assertTrue(status.startswith("403"))
        self.assertIn("Insufficient permissions", payload["error"])

    def test_api_abort_allowed_for_admin(self) -> None:
        runtime = FakeRuntime()
        app = build_control_plane_api(
            ControlPlaneService(runtime=runtime),
            username="admin",
            password="pw",
            role="admin",
        )
        _, login_payload = self._request(
            app,
            "POST",
            "/api/auth/login",
            {"username": "admin", "password": "pw"},
        )

        status, payload = self._request(
            app,
            "POST",
            "/api/sessions/ses_123/abort",
            token=login_payload["session_token"],
        )

        self.assertTrue(status.startswith("202"))
        self.assertTrue(payload["ok"])
        self.assertEqual(runtime.aborted, ["ses_123"])

    def test_api_artifacts_returns_metadata_listing(self) -> None:
        runtime = FakeRuntime()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            examples_dir = root / "examples"
            examples_dir.mkdir()
            (examples_dir / "counts.tsv").write_text(
                "gene\ts1\nA\t1\n", encoding="utf-8"
            )
            service = ControlPlaneService(
                runtime=runtime,
                settings=Settings.from_root(root),
            )
            app = build_control_plane_api(service, username="admin", password="pw")
            _, login_payload = self._request(
                app,
                "POST",
                "/api/auth/login",
                {"username": "admin", "password": "pw"},
            )

            status, payload = self._request(
                app,
                "GET",
                "/api/artifacts",
                token=login_payload["session_token"],
                query_string="path=examples",
            )

        self.assertTrue(status.startswith("200"))
        self.assertEqual(payload["path"], "examples")
        self.assertEqual(payload["entries"][0]["kind"], "TEXT")
        self.assertNotIn("content", payload["entries"][0]["summary"])

    def test_api_dashboard_activity_returns_snapshot(self) -> None:
        app = build_control_plane_api(
            ControlPlaneService(runtime=FakeRuntime()),
            username="admin",
            password="pw",
        )
        _, login_payload = self._request(
            app,
            "POST",
            "/api/auth/login",
            {"username": "admin", "password": "pw"},
        )

        status, payload = self._request(
            app,
            "GET",
            "/api/dashboard/activity",
            token=login_payload["session_token"],
            query_string="limit=10&timeout_ms=200",
        )

        self.assertTrue(status.startswith("200"))
        self.assertEqual(payload["totals"]["session_count"], 1)
        self.assertEqual(payload["events"][0]["session_id"], "ses_123")

    def test_api_artifacts_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = ControlPlaneService(
                runtime=FakeRuntime(),
                settings=Settings.from_root(root),
            )
            app = build_control_plane_api(service, username="admin", password="pw")
            _, login_payload = self._request(
                app,
                "POST",
                "/api/auth/login",
                {"username": "admin", "password": "pw"},
            )

            status, payload = self._request(
                app,
                "GET",
                "/api/artifacts",
                token=login_payload["session_token"],
                query_string="path=..%2Foutside",
            )

        self.assertTrue(status.startswith("400"))
        self.assertIn("project root", payload["error"])


if __name__ == "__main__":
    unittest.main()
