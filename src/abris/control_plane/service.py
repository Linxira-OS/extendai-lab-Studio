from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any

from abris.config.settings import Settings
from abris.data.sequencing_gateway import SequencingGateway
from abris.evidence.service import EvidenceAcquisitionService
from abris.environment.file_guard import FileGuard
from abris.models.schemas import (
    ArtifactRef,
    ControlPlaneSession,
    EvidenceBundle,
    FileReadRequest,
    RunRecord,
    SessionEvent,
    TokenUsage,
)
from abris.orchestrator.opencode_contract import OpenCodeRuntime
from abris.runlog.store import RunLedger


@dataclass(slots=True)
class ControlPlaneService:
    runtime: OpenCodeRuntime
    settings: Settings | None = None
    gateway: SequencingGateway = field(init=False)
    file_guard: FileGuard = field(init=False)
    evidence_service: EvidenceAcquisitionService = field(init=False)
    run_ledger: RunLedger = field(init=False)

    def __post_init__(self) -> None:
        self.settings = self.settings or Settings.from_root(
            Path(__file__).resolve().parents[3]
        )
        self.gateway = SequencingGateway()
        self.file_guard = FileGuard(self.settings)
        self.run_ledger = RunLedger(self._settings())
        self.evidence_service = EvidenceAcquisitionService(
            self.runtime, self.run_ledger
        )

    def list_sessions(self) -> list[ControlPlaneSession]:
        session_items = self._safe_list_sessions()
        if not session_items:
            session_items = self._safe_status_snapshot_items()
        sessions: list[ControlPlaneSession] = []

        for item in session_items:
            session_id = str(item.get("session_id") or item.get("sessionID") or "")
            if not session_id:
                continue
            title = str(item.get("title") or session_id)
            status = str(
                item.get("status") or item.get("type") or item.get("state") or "unknown"
            )
            messages = self._safe_get_messages(session_id)
            usage = self._safe_get_session_usage(session_id, messages)
            sessions.append(
                ControlPlaneSession(
                    session_id=session_id,
                    title=title,
                    status=status,
                    message_count=len(messages),
                    last_message_at=self._extract_last_timestamp(messages),
                    stalled=status in {"waiting", "blocked", "stalled"},
                    usage=usage,
                )
            )

        return sessions

    def get_session(self, session_id: str) -> dict[str, Any]:
        payload = self.runtime.get_session(session_id)
        messages = self.runtime.get_messages(session_id)
        usage = self._safe_get_session_usage(session_id, messages)
        return {
            "session": payload,
            "usage": usage,
            "message_count": len(messages),
        }

    def get_session_messages(self, session_id: str) -> list[dict[str, Any]]:
        return self.runtime.get_messages(session_id)

    def get_session_usage(self, session_id: str) -> TokenUsage:
        messages = self.runtime.get_messages(session_id)
        return self._safe_get_session_usage(session_id, messages)

    def get_session_events(
        self, session_id: str, *, limit: int = 25, timeout_ms: int = 250
    ) -> list[SessionEvent]:
        return self._collect_events(
            session_id=session_id,
            limit=limit,
            timeout_ms=timeout_ms,
        )

    def browse_artifacts(self, relative_path: str = ".") -> dict[str, Any]:
        settings = self._settings()
        base_path = self._resolve_artifact_path(relative_path)
        entries: list[ArtifactRef] = []

        for index, child in enumerate(sorted(base_path.iterdir()), start=1):
            entries.append(self._build_artifact_ref(child, index))

        return {
            "path": os.path.relpath(
                base_path.resolve(), settings.project_root.resolve()
            ),
            "entries": entries,
        }

    def get_live_activity(
        self, *, limit: int = 25, timeout_ms: int = 250
    ) -> dict[str, Any]:
        sessions = self.list_sessions()
        runs = self.list_runs()
        known_session_ids = {session.session_id for session in sessions}
        events = [
            event
            for event in self._collect_events(
                session_id=None,
                limit=limit,
                timeout_ms=timeout_ms,
            )
            if not event.session_id or event.session_id in known_session_ids
        ]
        return {
            "sessions": sessions,
            "runs": runs,
            "events": events,
            "totals": {
                "session_count": len(sessions),
                "stalled_count": sum(1 for session in sessions if session.stalled),
                "run_count": len(runs),
                "blocked_run_count": sum(
                    1 for run in runs if run.current_state == "blocked_policy"
                ),
                "stalled_run_count": sum(
                    1 for run in runs if getattr(run, "stalled", False)
                ),
            },
        }

    def search_evidence(
        self, query: str, *, limit: int = 5, run_id: str | None = None
    ) -> EvidenceBundle:
        return self.evidence_service.search(query, limit=limit, run_id=run_id)

    def list_runs(self) -> list[RunRecord]:
        return [
            self._materialize_run_health(run) for run in self.run_ledger.list_runs()
        ]

    def get_run(self, run_id: str) -> dict[str, Any]:
        run = self._materialize_run_health(self.run_ledger.get_run(run_id))
        events = self.run_ledger.get_run_events(run_id)
        return {
            "run": run,
            "steps": run.steps,
            "timeline": self._build_run_timeline(events),
            "current_step": self._select_current_step(run),
            "linked": {
                "runtime_session_ids": run.runtime_session_ids,
                "evidence_bundle_ids": run.evidence_bundle_ids,
                "artifact_paths": run.artifact_paths,
                "evidence_bundles": self._load_linked_evidence_bundles(run),
                "artifacts": self._load_linked_artifacts(run),
            },
            "events": events,
        }

    def _collect_events(
        self,
        *,
        session_id: str | None,
        limit: int,
        timeout_ms: int,
    ) -> list[SessionEvent]:
        try:
            snapshot = self.runtime.subscribe_events(limit=limit, timeout_ms=timeout_ms)
        except Exception:
            return []
        raw_events = snapshot.get("events", [])
        events: list[SessionEvent] = []

        if not isinstance(raw_events, list):
            return events

        for index, event in enumerate(raw_events, start=1):
            if not isinstance(event, dict):
                continue
            raw_payload = event.get("payload")
            payload: dict[str, Any]
            if isinstance(raw_payload, dict):
                payload = {str(key): value for key, value in raw_payload.items()}
            else:
                payload = {str(key): value for key, value in event.items()}
            event_session_id = str(
                event.get("session_id")
                or event.get("sessionID")
                or event.get("sessionId")
                or payload.get("session_id")
                or payload.get("sessionID")
                or payload.get("sessionId")
                or ""
            )
            if session_id and event_session_id and event_session_id != session_id:
                continue
            events.append(
                SessionEvent(
                    event_id=str(event.get("id") or f"evt_{index:03d}"),
                    session_id=event_session_id or session_id or "",
                    event_type=str(event.get("type") or "unknown"),
                    timestamp=str(
                        event.get("timestamp")
                        or event.get("createdAt")
                        or payload.get("timestamp")
                        or payload.get("createdAt")
                        or ""
                    ),
                    payload=payload,
                )
            )

        return events

    def _build_run_timeline(self, events: list[Any]) -> list[dict[str, Any]]:
        timeline: list[dict[str, Any]] = []
        for index, event in enumerate(events, start=1):
            if not hasattr(event, "event_id"):
                continue
            payload = getattr(event, "payload", {})
            timeline.append(
                {
                    "index": index,
                    "event_id": getattr(event, "event_id", f"evt_{index:03d}"),
                    "step_id": getattr(event, "step_id", ""),
                    "event_type": getattr(event, "event_type", ""),
                    "state_from": getattr(event, "state_from", ""),
                    "state_to": getattr(event, "state_to", ""),
                    "timestamp": getattr(event, "timestamp", ""),
                    "reason": getattr(event, "reason", ""),
                    "payload": payload if isinstance(payload, dict) else {},
                }
            )
        return timeline

    def _materialize_run_health(self, run: RunRecord) -> RunRecord:
        timeout_seconds = self._settings().stall_timeout_seconds
        now = datetime.now(timezone.utc)
        terminal_states = {"completed", "failed", "blocked_policy", "aborted"}

        run.stalled = False
        run.stalled_reason = ""
        for step in run.steps:
            step.stalled = False
            step.stalled_reason = ""
            if step.state in terminal_states:
                continue
            heartbeat_age = self._heartbeat_age_seconds(step.last_heartbeat, now)
            if heartbeat_age is not None and heartbeat_age > timeout_seconds:
                step.stalled = True
                step.stalled_reason = f"No step heartbeat for {heartbeat_age}s while state remains {step.state}."

        if run.current_state not in terminal_states:
            heartbeat_age = self._heartbeat_age_seconds(run.last_heartbeat, now)
            if heartbeat_age is not None and heartbeat_age > timeout_seconds:
                run.stalled = True
                waiting_on = run.waiting_on or "unknown"
                run.stalled_reason = f"No run heartbeat for {heartbeat_age}s while waiting_on={waiting_on}."
        return run

    def _heartbeat_age_seconds(self, timestamp: str, now: datetime) -> int | None:
        if not timestamp:
            return None
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0, int((now - parsed).total_seconds()))

    def _select_current_step(self, run: RunRecord) -> dict[str, Any] | None:
        for step in run.steps:
            if step.state not in {"completed", "failed", "blocked_policy", "aborted"}:
                return {
                    "step_id": step.step_id,
                    "title": step.title,
                    "state": step.state,
                    "owner": getattr(step, "owner", ""),
                    "stalled": step.stalled,
                    "stalled_reason": step.stalled_reason,
                    "waiting_on": step.waiting_on,
                    "last_checkpoint": step.last_checkpoint,
                    "last_heartbeat": step.last_heartbeat,
                    "failure_reason": step.failure_reason,
                }
        if run.steps:
            step = run.steps[-1]
            return {
                "step_id": step.step_id,
                "title": step.title,
                "state": step.state,
                "owner": getattr(step, "owner", ""),
                "stalled": step.stalled,
                "stalled_reason": step.stalled_reason,
                "waiting_on": step.waiting_on,
                "last_checkpoint": step.last_checkpoint,
                "last_heartbeat": step.last_heartbeat,
                "failure_reason": step.failure_reason,
            }
        return None

    def _resolve_artifact_path(self, relative_path: str) -> Path:
        settings = self._settings()
        requested = relative_path.strip() or "."
        candidate = (settings.project_root / requested).resolve()
        root = settings.project_root.resolve()
        try:
            candidate.relative_to(root)
        except ValueError as error:
            raise ValueError("Artifact path must stay within project root.") from error
        if not candidate.exists():
            raise ValueError("Artifact path does not exist.")
        if not candidate.is_dir():
            raise ValueError("Artifact path must be a directory.")
        return candidate

    def _load_linked_evidence_bundles(self, run: RunRecord) -> list[dict[str, Any]]:
        bundles: list[dict[str, Any]] = []
        for bundle_id in run.evidence_bundle_ids:
            bundle = self.run_ledger.get_evidence_bundle(bundle_id)
            if bundle is not None:
                bundles.append(bundle)
        return bundles

    def _load_linked_artifacts(self, run: RunRecord) -> list[dict[str, Any]]:
        artifacts: list[dict[str, Any]] = []
        for index, artifact_path in enumerate(run.artifact_paths, start=1):
            candidate = Path(artifact_path)
            if not candidate.exists() or not candidate.is_file():
                continue
            artifact = self._build_artifact_ref(candidate, index)
            artifacts.append(
                {
                    "artifact_id": artifact.artifact_id,
                    "path": artifact.path,
                    "kind": artifact.kind,
                    "safe_action": artifact.safe_action,
                    "summary": artifact.summary,
                }
            )
        return artifacts

    def _build_artifact_ref(self, file_path: Path, index: int) -> ArtifactRef:
        settings = self._settings()
        relative_path = os.path.relpath(
            file_path.resolve(),
            settings.project_root.resolve(),
        )
        if file_path.is_dir():
            return ArtifactRef(
                artifact_id=f"artifact_{index:03d}",
                path=relative_path,
                kind="DIRECTORY",
                safe_action="browse_directory",
                summary={
                    "file_name": file_path.name,
                    "entry_type": "directory",
                },
            )

        asset = self.gateway.inspect_path(file_path, index=index)
        decision = self.file_guard.evaluate(
            FileReadRequest(
                path=file_path,
                operation="artifact_browse",
                caller="control_plane",
                embed_in_prompt=False,
            ),
            asset,
        )
        return ArtifactRef(
            artifact_id=asset.asset_id,
            path=relative_path,
            kind=asset.file_type,
            safe_action=decision.action,
            summary={
                "file_name": file_path.name,
                "size_bytes": asset.size_bytes,
                "size_class": asset.size_class,
                "detected_format": asset.detected_format,
                "protected": asset.protected,
                "warnings": asset.warnings,
                "recommended_actions": asset.recommended_actions,
                "policy_rule": decision.policy_rule,
                "redirect_tool": decision.redirect_tool,
                "safe_summary": decision.safe_summary,
            },
        )

    def _settings(self) -> Settings:
        settings = self.settings
        if settings is None:
            raise RuntimeError("ControlPlaneService settings are not initialized.")
        return settings

    def abort_session(self, session_id: str) -> dict[str, Any]:
        return self.runtime.abort_session(session_id)

    def _normalize_status_items(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        if isinstance(payload.get("sessions"), list):
            return [item for item in payload["sessions"] if isinstance(item, dict)]

        status_field = payload.get("status")
        if isinstance(status_field, list):
            return [item for item in status_field if isinstance(item, dict)]

        if isinstance(status_field, dict):
            if isinstance(status_field.get("sessions"), list):
                return [
                    item for item in status_field["sessions"] if isinstance(item, dict)
                ]
            session_id = status_field.get("session_id") or status_field.get("sessionID")
            nested_status = status_field.get("status")
            if session_id:
                normalized = {
                    "session_id": session_id,
                    "title": status_field.get("title") or session_id,
                }
                if isinstance(nested_status, dict):
                    normalized["status"] = nested_status.get(
                        "type"
                    ) or nested_status.get("status")
                elif nested_status is not None:
                    normalized["status"] = nested_status
                return [normalized]

        return []

    def _safe_list_sessions(self) -> list[dict[str, Any]]:
        try:
            sessions = self.runtime.list_sessions()
        except Exception:
            return []
        return [item for item in sessions if isinstance(item, dict)]

    def _safe_status_snapshot_items(self) -> list[dict[str, Any]]:
        try:
            status_snapshot = self.runtime.get_session_status()
        except Exception:
            return []
        return self._normalize_status_items(status_snapshot)

    def _safe_get_messages(self, session_id: str) -> list[dict[str, Any]]:
        try:
            messages = self.runtime.get_messages(session_id)
        except Exception:
            return []
        return [message for message in messages if isinstance(message, dict)]

    def _safe_get_session_usage(
        self, session_id: str, messages: list[dict[str, Any]]
    ) -> TokenUsage:
        try:
            payload = self.runtime.get_session_usage(session_id)
        except Exception:
            return self._aggregate_usage(session_id, messages)

        if not isinstance(payload, dict):
            return self._aggregate_usage(session_id, messages)

        usage = TokenUsage(session_id=session_id)
        usage.input_tokens = self._read_int(
            payload,
            "input_tokens",
            "inputTokens",
            "prompt_tokens",
            "promptTokens",
        )
        usage.output_tokens = self._read_int(
            payload,
            "output_tokens",
            "outputTokens",
            "completion_tokens",
            "completionTokens",
        )
        usage.total_tokens = self._read_int(payload, "total_tokens", "totalTokens")
        usage.cost = self._read_float(payload, "cost", "estimatedCost")
        usage.message_count = self._read_int(payload, "message_count", "messageCount")
        usage.prompt_count = self._read_int(payload, "prompt_count", "promptCount")

        if usage.message_count == 0:
            usage.message_count = len(messages)
        if usage.prompt_count == 0:
            usage.prompt_count = sum(
                1
                for message in messages
                if isinstance(message, dict) and message.get("role") == "user"
            )
        if usage.total_tokens == 0:
            usage.total_tokens = usage.input_tokens + usage.output_tokens
        return usage

    def _aggregate_usage(
        self, session_id: str, messages: list[dict[str, Any]]
    ) -> TokenUsage:
        usage = TokenUsage(session_id=session_id)

        for message in messages:
            usage.message_count += 1
            if message.get("role") == "user":
                usage.prompt_count += 1

            raw_usage = message.get("usage") if isinstance(message, dict) else None
            if not isinstance(raw_usage, dict):
                continue

            usage.input_tokens += self._read_int(
                raw_usage,
                "input_tokens",
                "inputTokens",
                "prompt_tokens",
                "promptTokens",
            )
            usage.output_tokens += self._read_int(
                raw_usage,
                "output_tokens",
                "outputTokens",
                "completion_tokens",
                "completionTokens",
            )
            usage.total_tokens += self._read_int(
                raw_usage,
                "total_tokens",
                "totalTokens",
            )
            usage.cost += self._read_float(raw_usage, "cost", "estimatedCost")

        if usage.total_tokens == 0:
            usage.total_tokens = usage.input_tokens + usage.output_tokens
        return usage

    def _extract_last_timestamp(self, messages: list[dict[str, Any]]) -> str:
        for message in reversed(messages):
            for key in ("createdAt", "timestamp", "time"):
                value = message.get(key)
                if isinstance(value, str) and value:
                    return value
        return ""

    def _read_int(self, payload: dict[str, Any], *keys: str) -> int:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
        return 0

    def _read_float(self, payload: dict[str, Any], *keys: str) -> float:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                return float(value)
        return 0.0
