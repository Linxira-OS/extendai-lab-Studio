import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

runtime_module = importlib.import_module("abris.orchestrator.opencode_runtime")
contract_module = importlib.import_module("abris.orchestrator.opencode_contract")

OpenCodeBridgeRuntime = runtime_module.OpenCodeBridgeRuntime
ManagedOpenCodeServer = runtime_module.ManagedOpenCodeServer
SubprocessBridgeTransport = runtime_module.SubprocessBridgeTransport
build_project_local_bridge_env = runtime_module.build_project_local_bridge_env
build_node_bridge_runtime = runtime_module.build_node_bridge_runtime
resolve_project_local_opencode_binary = (
    runtime_module.resolve_project_local_opencode_binary
)
StructuredSchemaRequest = contract_module.StructuredSchemaRequest


class RecordingTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def request(self, operation, payload):
        self.requests.append((operation, payload))
        return self.responses.pop(0)


class OpenCodeBridgeRuntimeTest(unittest.TestCase):
    def test_create_session_returns_session_identifier(self) -> None:
        transport = RecordingTransport([{"session_id": "ses_123"}])
        runtime = OpenCodeBridgeRuntime(
            transport=transport,
            session_defaults={"directory": "/workspace/abris"},
        )

        session_id = runtime.create_session("ABRIS Test")

        self.assertEqual(session_id, "ses_123")
        self.assertEqual(
            transport.requests,
            [
                (
                    "create_session",
                    {"title": "ABRIS Test", "directory": "/workspace/abris"},
                )
            ],
        )

    def test_create_session_accepts_nested_data_identifier(self) -> None:
        transport = RecordingTransport([{"data": {"id": "ses_nested"}}])
        runtime = OpenCodeBridgeRuntime(transport=transport)

        session_id = runtime.create_session("ABRIS Nested")

        self.assertEqual(session_id, "ses_nested")
        self.assertEqual(
            transport.requests,
            [("create_session", {"title": "ABRIS Nested"})],
        )

    def test_prompt_structured_sends_json_schema_format(self) -> None:
        transport = RecordingTransport(
            [{"structured_output": {"analysis_type": "RNA-seq", "goal": "de"}}]
        )
        runtime = OpenCodeBridgeRuntime(transport=transport)

        response = runtime.prompt_structured(
            "ses_123",
            StructuredSchemaRequest(
                prompt="Parse this request",
                schema={"type": "object"},
                retry_count=3,
            ),
        )

        self.assertEqual(response["structured_output"]["analysis_type"], "RNA-seq")
        operation, payload = transport.requests[0]
        self.assertEqual(operation, "prompt_structured")
        self.assertEqual(payload["session_id"], "ses_123")
        self.assertEqual(payload["format"]["type"], "json_schema")
        self.assertEqual(payload["format"]["retryCount"], 3)

    def test_runtime_exposes_session_list_and_usage_queries(self) -> None:
        transport = RecordingTransport(
            [
                {"sessions": [{"session_id": "ses_123", "title": "ABRIS"}]},
                {
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "total_tokens": 15,
                    }
                },
            ]
        )
        runtime = OpenCodeBridgeRuntime(transport=transport)

        sessions = runtime.list_sessions()
        usage = runtime.get_session_usage("ses_123")

        self.assertEqual(sessions[0]["session_id"], "ses_123")
        self.assertEqual(usage["total_tokens"], 15)
        self.assertEqual(
            transport.requests,
            [
                ("list_sessions", {}),
                ("get_session_usage", {"session_id": "ses_123"}),
            ],
        )

    def test_subscribe_events_normalizes_nested_payload_fields(self) -> None:
        transport = RecordingTransport(
            [
                {
                    "events": [
                        {
                            "id": "evt_1",
                            "type": "message.part.updated",
                            "payload": {
                                "sessionId": "ses_123",
                                "timestamp": "2026-03-19T10:00:02Z",
                                "part": {"type": "tool"},
                            },
                        }
                    ],
                    "completed": True,
                }
            ]
        )
        runtime = OpenCodeBridgeRuntime(transport=transport)

        snapshot = runtime.subscribe_events(limit=5, timeout_ms=250)

        self.assertTrue(snapshot["completed"])
        self.assertEqual(snapshot["events"][0]["session_id"], "ses_123")
        self.assertEqual(snapshot["events"][0]["timestamp"], "2026-03-19T10:00:02Z")
        self.assertEqual(snapshot["events"][0]["payload"]["part"]["type"], "tool")

    def test_runtime_exposes_async_lifecycle_methods(self) -> None:
        transport = RecordingTransport(
            [
                {"id": "ses_123", "title": "ABRIS"},
                {"status": {"sessionID": "ses_123", "status": {"type": "idle"}}},
                {"messages": [{"id": "msg_1", "role": "assistant"}]},
                {},
                {"events": [{"type": "server.connected"}]},
                {"ok": True},
                {"ok": True},
            ]
        )
        runtime = OpenCodeBridgeRuntime(transport=transport)

        session = runtime.get_session("ses_123")
        status = runtime.get_session_status()
        messages = runtime.get_messages("ses_123")
        async_result = runtime.prompt_async("ses_123", "hello")
        events = runtime.subscribe_events(limit=5, timeout_ms=250)
        abort_result = runtime.abort_session("ses_123")
        delete_result = runtime.delete_session("ses_123")

        self.assertEqual(session["id"], "ses_123")
        self.assertEqual(status["status"]["status"]["type"], "idle")
        self.assertEqual(messages[0]["id"], "msg_1")
        self.assertTrue(async_result["accepted"])
        self.assertEqual(events["events"][0]["type"], "server.connected")
        self.assertTrue(abort_result["ok"])
        self.assertTrue(delete_result["ok"])

        self.assertEqual(
            transport.requests,
            [
                ("get_session", {"session_id": "ses_123"}),
                ("get_session_status", {}),
                ("get_messages", {"session_id": "ses_123"}),
                ("prompt_async", {"session_id": "ses_123", "text": "hello"}),
                ("subscribe_events", {"limit": 5, "timeout_ms": 250}),
                ("abort_session", {"session_id": "ses_123"}),
                ("delete_session", {"session_id": "ses_123"}),
            ],
        )

    def test_subprocess_transport_round_trips_json(self) -> None:
        transport = SubprocessBridgeTransport(
            command=[
                sys.executable,
                "-c",
                (
                    "import json, sys; "
                    "payload = json.loads(sys.argv[2]); "
                    "print(json.dumps({'operation': sys.argv[1], 'payload': payload}))"
                ),
            ]
        )

        response = transport.request("create_session", {"title": "ABRIS"})

        self.assertEqual(response["operation"], "create_session")
        self.assertEqual(response["payload"]["title"], "ABRIS")

    def test_subprocess_transport_merges_default_payload(self) -> None:
        transport = SubprocessBridgeTransport(
            command=[
                sys.executable,
                "-c",
                (
                    "import json, sys; "
                    "payload = json.loads(sys.argv[2]); "
                    "print(json.dumps(payload))"
                ),
            ],
            default_payload={"startServer": False, "baseUrl": "http://localhost:4096"},
        )

        response = transport.request("health", {"title": "ABRIS"})

        self.assertEqual(response["startServer"], False)
        self.assertEqual(response["baseUrl"], "http://localhost:4096")
        self.assertEqual(response["title"], "ABRIS")

    def test_subprocess_transport_times_out_long_running_command(self) -> None:
        transport = SubprocessBridgeTransport(
            command=[
                sys.executable,
                "-c",
                "import time; time.sleep(5)",
            ],
            timeout_seconds=0.2,
        )

        with self.assertRaises(RuntimeError) as context:
            transport.request("list_sessions", {})

        self.assertIn("Bridge command timed out", str(context.exception))

    def test_build_node_bridge_runtime_requires_built_cli(self) -> None:
        with self.assertRaises(RuntimeError):
            build_node_bridge_runtime(Path("/nonexistent-abris-root"))

    def test_resolve_project_local_opencode_binary_requires_local_install(self) -> None:
        with self.assertRaises(RuntimeError):
            resolve_project_local_opencode_binary(Path("/nonexistent-abris-root"))

    def test_build_project_local_bridge_env_prefers_local_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bridge_bin = root / "packages" / "opencode-bridge" / "node_modules" / ".bin"
            bridge_bin.mkdir(parents=True, exist_ok=True)
            local_binary = bridge_bin / "opencode"
            local_binary.write_text("#!/usr/bin/env node\n", encoding="utf-8")

            env = build_project_local_bridge_env(root)

        self.assertEqual(env["OPENCODE_BIN"], str(local_binary))
        self.assertTrue(
            env["PATH"].split(runtime_module.os.pathsep)[0].endswith(".bin")
        )
        self.assertEqual(
            Path(env["XDG_CONFIG_HOME"]),
            root / ".abris-runtime" / "config",
        )

    def test_build_node_bridge_runtime_passes_runtime_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bridge_dist = root / "packages" / "opencode-bridge" / "dist"
            bridge_dist.mkdir(parents=True, exist_ok=True)
            (bridge_dist / "cli.js").write_text("// bridge", encoding="utf-8")
            bridge_bin = root / "packages" / "opencode-bridge" / "node_modules" / ".bin"
            bridge_bin.mkdir(parents=True, exist_ok=True)
            (bridge_bin / "opencode").write_text(
                "#!/usr/bin/env node\n", encoding="utf-8"
            )

            with mock.patch.object(
                runtime_module.shutil, "which", return_value="/usr/bin/node"
            ):
                runtime = build_node_bridge_runtime(
                    root,
                    runtime_config={"mcp": {"paper-search": {"enabled": True}}},
                    start_server=False,
                )

        self.assertEqual(
            runtime.transport.default_payload["config"],
            {"mcp": {"paper-search": {"enabled": True}}},
        )
        self.assertFalse(runtime.transport.default_payload["startServer"])

    def test_build_node_bridge_runtime_uses_managed_local_server_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            bridge_dist = root / "packages" / "opencode-bridge" / "dist"
            bridge_dist.mkdir(parents=True, exist_ok=True)
            (bridge_dist / "cli.js").write_text("// bridge", encoding="utf-8")
            bridge_bin = root / "packages" / "opencode-bridge" / "node_modules" / ".bin"
            bridge_bin.mkdir(parents=True, exist_ok=True)
            (bridge_bin / "opencode").write_text(
                "#!/usr/bin/env node\n", encoding="utf-8"
            )
            managed = ManagedOpenCodeServer(base_url="http://127.0.0.1:4096")

            with (
                mock.patch.object(
                    runtime_module.shutil, "which", return_value="/usr/bin/node"
                ),
                mock.patch.object(
                    runtime_module,
                    "start_managed_local_opencode_server",
                    return_value=managed,
                ) as starter,
            ):
                runtime = build_node_bridge_runtime(root)

        starter.assert_called_once()
        self.assertIs(runtime.managed_server, managed)
        self.assertEqual(
            runtime.transport.default_payload["baseUrl"],
            "http://127.0.0.1:4096",
        )
        self.assertFalse(runtime.transport.default_payload["startServer"])
        self.assertNotIn("config", runtime.transport.default_payload)


if __name__ == "__main__":
    unittest.main()
