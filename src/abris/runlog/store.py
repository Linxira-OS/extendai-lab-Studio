from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from abris.config.settings import Settings
from abris.models.schemas import EvidenceBundle, RunEvent, RunRecord, RunStepState


class RunLedger:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.settings.run_dir.mkdir(parents=True, exist_ok=True)
        self._events_dir = self.settings.run_dir / "events"
        self._state_dir = self.settings.run_dir / "state"
        self._bundle_dir = self.settings.run_dir / "evidence"
        self._events_dir.mkdir(parents=True, exist_ok=True)
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._bundle_dir.mkdir(parents=True, exist_ok=True)

    def create_run(
        self,
        *,
        run_type: str,
        title: str,
        initial_state: str = "queued",
        owner: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> RunRecord:
        now = self._now()
        run = RunRecord(
            run_id=f"run_{uuid4().hex[:12]}",
            run_type=run_type,
            title=title,
            current_state=initial_state,
            created_at=now,
            updated_at=now,
            metadata=dict(metadata or {}),
        )
        setattr(run, "owner", owner)
        self._write_state(run)
        self._append_event(
            RunEvent(
                event_id=f"evt_{uuid4().hex[:12]}",
                run_id=run.run_id,
                event_type="run.created",
                state_to=initial_state,
                timestamp=now,
                payload={"run_type": run_type, "title": title, "owner": owner},
            )
        )
        return run

    def list_runs(self) -> list[RunRecord]:
        runs: list[RunRecord] = []
        for file_path in sorted(
            self._state_dir.glob("*.json"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        ):
            runs.append(self._load_state(file_path))
        return runs

    def get_run(self, run_id: str) -> RunRecord:
        return self._load_state(self._state_path(run_id))

    def get_run_events(self, run_id: str) -> list[RunEvent]:
        path = self._event_path(run_id)
        if not path.exists():
            return []
        events: list[RunEvent] = []
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip():
                continue
            payload = json.loads(raw_line)
            events.append(RunEvent(**payload))
        return events

    def set_run_state(
        self,
        run_id: str,
        *,
        new_state: str,
        reason: str = "",
        waiting_on: str = "",
        last_checkpoint: str = "",
        failure_reason: str = "",
        owner: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> RunRecord:
        run = self.get_run(run_id)
        state_from = run.current_state
        now = self._now()
        run.current_state = new_state
        run.updated_at = now
        run.waiting_on = waiting_on
        if owner:
            setattr(run, "owner", owner)
        run.failure_reason = (
            failure_reason or reason
            if new_state in {"failed", "blocked_policy", "aborted"}
            else ""
        )
        run.last_heartbeat = now
        if last_checkpoint:
            run.last_checkpoint = last_checkpoint
        elif new_state == "completed" and not run.last_checkpoint:
            run.last_checkpoint = "run_completed"
        if metadata:
            run.metadata.update(metadata)
        self._write_state(run)
        self._append_event(
            RunEvent(
                event_id=f"evt_{uuid4().hex[:12]}",
                run_id=run_id,
                event_type="run.state_changed",
                state_from=state_from,
                state_to=new_state,
                timestamp=now,
                reason=reason,
                payload={
                    "waiting_on": waiting_on,
                    "last_checkpoint": run.last_checkpoint,
                    "failure_reason": run.failure_reason,
                    "owner": getattr(run, "owner", ""),
                    "metadata": metadata or {},
                },
            )
        )
        return run

    def heartbeat(self, run_id: str, *, step_id: str = "", reason: str = "") -> None:
        run = self.get_run(run_id)
        now = self._now()
        run.last_heartbeat = now
        run.updated_at = now
        if step_id:
            step = self._ensure_step(run, step_id, step_type="unknown", title=step_id)
            step.last_heartbeat = now
            step.updated_at = now
        self._write_state(run)
        self._append_event(
            RunEvent(
                event_id=f"evt_{uuid4().hex[:12]}",
                run_id=run_id,
                step_id=step_id,
                event_type="heartbeat",
                state_to=run.current_state,
                timestamp=now,
                reason=reason,
            )
        )

    def start_step(
        self,
        run_id: str,
        *,
        step_id: str,
        step_type: str,
        title: str,
        metadata: dict[str, Any] | None = None,
        waiting_on: str = "",
        owner: str = "system",
    ) -> RunRecord:
        run = self.get_run(run_id)
        now = self._now()
        step = self._ensure_step(run, step_id, step_type=step_type, title=title)
        state_from = step.state
        step.state = "running"
        step.updated_at = now
        step.last_heartbeat = now
        step.waiting_on = waiting_on
        setattr(step, "owner", owner)
        step.failure_reason = ""
        if metadata:
            step.metadata.update(metadata)
        run.current_state = "running"
        run.waiting_on = waiting_on
        setattr(run, "owner", owner)
        run.failure_reason = ""
        run.updated_at = now
        run.last_heartbeat = now
        self._write_state(run)
        self._append_event(
            RunEvent(
                event_id=f"evt_{uuid4().hex[:12]}",
                run_id=run_id,
                step_id=step_id,
                event_type="step.started",
                state_from=state_from,
                state_to="running",
                timestamp=now,
                payload={
                    "step_type": step_type,
                    "title": title,
                    "owner": owner,
                    "metadata": metadata or {},
                },
            )
        )
        return run

    def finish_step(
        self,
        run_id: str,
        *,
        step_id: str,
        final_state: str,
        reason: str = "",
        waiting_on: str = "",
        failure_reason: str = "",
        last_checkpoint: str = "",
        owner: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> RunRecord:
        run = self.get_run(run_id)
        now = self._now()
        step = self._ensure_step(run, step_id, step_type="unknown", title=step_id)
        state_from = step.state
        step.state = final_state
        step.updated_at = now
        step.last_heartbeat = now
        step.waiting_on = waiting_on
        if owner:
            setattr(step, "owner", owner)
        if failure_reason:
            step.failure_reason = failure_reason
        elif final_state == "completed":
            step.failure_reason = ""
        if last_checkpoint:
            step.last_checkpoint = last_checkpoint
            run.last_checkpoint = last_checkpoint
        if metadata:
            step.metadata.update(metadata)
        if final_state == "completed":
            run.current_state = (
                "completed" if self._all_steps_terminal(run) else run.current_state
            )
            if not run.current_state == "completed":
                run.waiting_on = waiting_on
            elif not waiting_on:
                run.waiting_on = ""
            if not failure_reason:
                run.failure_reason = ""
        elif final_state in {"failed", "blocked_policy", "aborted"}:
            run.current_state = final_state
            run.failure_reason = failure_reason or reason
            run.waiting_on = waiting_on
        if owner:
            setattr(run, "owner", owner)
        run.updated_at = now
        run.last_heartbeat = now
        self._write_state(run)
        self._append_event(
            RunEvent(
                event_id=f"evt_{uuid4().hex[:12]}",
                run_id=run_id,
                step_id=step_id,
                event_type="step.finished",
                state_from=state_from,
                state_to=final_state,
                timestamp=now,
                reason=reason,
                payload={
                    "metadata": metadata or {},
                    "waiting_on": waiting_on,
                    "failure_reason": failure_reason,
                    "last_checkpoint": step.last_checkpoint,
                    "owner": getattr(step, "owner", ""),
                },
            )
        )
        return run

    def attach_runtime_session(
        self, run_id: str, *, step_id: str = "", session_id: str
    ) -> None:
        run = self.get_run(run_id)
        now = self._now()
        if session_id not in run.runtime_session_ids:
            run.runtime_session_ids.append(session_id)
        if step_id:
            step = self._ensure_step(run, step_id, step_type="unknown", title=step_id)
            step.runtime_session_id = session_id
            step.updated_at = now
            step.last_checkpoint = session_id
        run.updated_at = now
        run.last_checkpoint = session_id
        self._write_state(run)
        self._append_event(
            RunEvent(
                event_id=f"evt_{uuid4().hex[:12]}",
                run_id=run_id,
                step_id=step_id,
                event_type="runtime.attached",
                timestamp=now,
                payload={"session_id": session_id, "last_checkpoint": session_id},
            )
        )

    def attach_evidence_bundle(
        self, run_id: str, *, step_id: str, bundle_id: str
    ) -> None:
        run = self.get_run(run_id)
        now = self._now()
        if bundle_id not in run.evidence_bundle_ids:
            run.evidence_bundle_ids.append(bundle_id)
        step = self._ensure_step(run, step_id, step_type="evidence", title=step_id)
        step.evidence_bundle_id = bundle_id
        step.updated_at = now
        step.last_checkpoint = bundle_id
        run.updated_at = now
        run.last_checkpoint = bundle_id
        self._write_state(run)
        self._append_event(
            RunEvent(
                event_id=f"evt_{uuid4().hex[:12]}",
                run_id=run_id,
                step_id=step_id,
                event_type="evidence.attached",
                timestamp=now,
                payload={"bundle_id": bundle_id, "last_checkpoint": bundle_id},
            )
        )

    def store_evidence_bundle(self, bundle: EvidenceBundle) -> None:
        self._bundle_path(bundle.bundle_id).write_text(
            json.dumps(asdict(bundle), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_evidence_bundle(self, bundle_id: str) -> dict[str, Any] | None:
        path = self._bundle_path(bundle_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None

    def attach_artifact(self, run_id: str, *, step_id: str, artifact_path: str) -> None:
        run = self.get_run(run_id)
        now = self._now()
        if artifact_path not in run.artifact_paths:
            run.artifact_paths.append(artifact_path)
        step = self._ensure_step(run, step_id, step_type="artifact", title=step_id)
        if artifact_path not in step.artifact_paths:
            step.artifact_paths.append(artifact_path)
        step.updated_at = now
        step.last_checkpoint = artifact_path
        run.updated_at = now
        run.last_checkpoint = artifact_path
        self._write_state(run)
        self._append_event(
            RunEvent(
                event_id=f"evt_{uuid4().hex[:12]}",
                run_id=run_id,
                step_id=step_id,
                event_type="artifact.attached",
                timestamp=now,
                payload={
                    "artifact_path": artifact_path,
                    "last_checkpoint": artifact_path,
                },
            )
        )

    def _ensure_step(
        self, run: RunRecord, step_id: str, *, step_type: str, title: str
    ) -> RunStepState:
        for step in run.steps:
            if step.step_id == step_id:
                if step_type != "unknown" and step.step_type == "unknown":
                    step.step_type = step_type
                if title and step.title == step.step_id:
                    step.title = title
                return step
        now = self._now()
        step = RunStepState(
            step_id=step_id,
            step_type=step_type,
            title=title,
            state="queued",
            created_at=now,
            updated_at=now,
        )
        run.steps.append(step)
        return step

    def _all_steps_terminal(self, run: RunRecord) -> bool:
        if not run.steps:
            return False
        return all(
            step.state in {"completed", "failed", "blocked_policy", "aborted"}
            for step in run.steps
        )

    def _write_state(self, run: RunRecord) -> None:
        self._state_path(run.run_id).write_text(
            json.dumps(asdict(run), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_state(self, path: Path) -> RunRecord:
        payload = json.loads(path.read_text(encoding="utf-8"))
        steps = [RunStepState(**item) for item in payload.pop("steps", [])]
        run = RunRecord(**payload)
        run.steps = steps
        return run

    def _append_event(self, event: RunEvent) -> None:
        with self._event_path(event.run_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")

    def _state_path(self, run_id: str) -> Path:
        return self._state_dir / f"{run_id}.json"

    def _event_path(self, run_id: str) -> Path:
        return self._events_dir / f"{run_id}.jsonl"

    def _bundle_path(self, bundle_id: str) -> Path:
        return self._bundle_dir / f"{bundle_id}.json"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
