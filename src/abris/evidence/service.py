from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from abris.models.schemas import EvidenceBundle, EvidenceRecord, TokenUsage
from abris.orchestrator.opencode_contract import (
    OpenCodeRuntime,
    StructuredSchemaRequest,
)
from abris.runlog.store import RunLedger


HIGH_TRUST_PROVIDERS = {
    "arxiv",
    "pubmed",
    "pmc",
    "europepmc",
    "crossref",
    "openalex",
    "dblp",
    "zenodo",
    "hal",
    "doaj",
}

MEDIUM_TRUST_PROVIDERS = {
    "semantic scholar",
    "semanticscholar",
    "core",
    "openaire",
    "unpaywall",
}

BLOCKED_PROVIDERS = {
    "sci-hub",
    "scihub",
    "google scholar",
    "googlescholar",
}


@dataclass(slots=True)
class EvidenceAcquisitionService:
    runtime: OpenCodeRuntime
    run_ledger: RunLedger | None = None

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        run_id: str | None = None,
        step_id: str | None = None,
    ) -> EvidenceBundle:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Evidence query must not be empty.")
        if limit < 1 or limit > 20:
            raise ValueError("Evidence search limit must be between 1 and 20.")

        owns_run = False
        active_run_id = run_id or ""
        active_step_id = step_id or "step_evidence_search"
        if self.run_ledger is not None:
            if not active_run_id:
                run = self.run_ledger.create_run(
                    run_type="evidence_search",
                    title=f"Evidence search: {normalized_query[:80]}",
                    initial_state="running",
                    owner="evidence_service",
                    metadata={"query": normalized_query, "limit": limit},
                )
                active_run_id = run.run_id
                owns_run = True
            self.run_ledger.start_step(
                active_run_id,
                step_id=active_step_id,
                step_type="evidence_search",
                title="Evidence Search",
                metadata={"query": normalized_query, "limit": limit},
                waiting_on="runtime_search",
                owner="evidence_service",
            )

        session_id = self.runtime.create_session("ABRIS Evidence Search")
        if self.run_ledger is not None and active_run_id:
            self.run_ledger.attach_runtime_session(
                active_run_id,
                step_id=active_step_id,
                session_id=session_id,
            )
        response = self.runtime.prompt_structured(
            session_id,
            StructuredSchemaRequest(
                prompt=(
                    "Use the configured paper-search MCP to search the literature. "
                    "Return only evidence records grounded in the MCP results. "
                    "Prefer high-trust open literature sources. "
                    f"Query: {normalized_query}. Limit: {limit}."
                ),
                schema={
                    "type": "object",
                    "properties": {
                        "records": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "source_class": {"type": "string"},
                                    "provider": {"type": "string"},
                                    "title": {"type": "string"},
                                    "authors": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "year": {"type": "integer"},
                                    "url": {"type": "string"},
                                    "doi": {"type": "string"},
                                    "pmid": {"type": "string"},
                                    "arxiv_id": {"type": "string"},
                                    "license": {"type": "string"},
                                    "snippet": {"type": "string"},
                                    "abstract": {"type": "string"},
                                    "confidence": {"type": "number"},
                                },
                                "required": [
                                    "source_class",
                                    "provider",
                                    "title",
                                ],
                            },
                        },
                        "warnings": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["records"],
                },
            ),
        )

        payload = response.get("structured_output", {})
        raw_records = payload.get("records", []) if isinstance(payload, dict) else []
        warnings = payload.get("warnings", []) if isinstance(payload, dict) else []
        records = self._normalize_records(normalized_query, raw_records)
        usage_payload = self.runtime.get_session_usage(session_id)
        usage = self._normalize_usage(session_id, usage_payload)
        retrieved_at = datetime.now(timezone.utc).isoformat()
        summary = {
            "record_count": len(records),
            "admissible_count": sum(
                1 for record in records if record.admissibility == "allowed"
            ),
            "downgraded_count": sum(
                1 for record in records if record.admissibility == "downgraded"
            ),
            "blocked_count": sum(
                1 for record in records if record.admissibility == "blocked"
            ),
            "providers": sorted(
                {record.provider for record in records if record.provider}
            ),
        }
        bundle = EvidenceBundle(
            bundle_id=f"evidence_{session_id}",
            query=normalized_query,
            session_id=session_id,
            retrieved_at=retrieved_at,
            run_id=active_run_id,
            step_id=active_step_id,
            records=records,
            usage=usage,
            summary=summary,
            warnings=[str(item) for item in warnings if str(item).strip()],
        )
        if self.run_ledger is not None and active_run_id:
            self.run_ledger.store_evidence_bundle(bundle)
            self.run_ledger.attach_evidence_bundle(
                active_run_id,
                step_id=active_step_id,
                bundle_id=bundle.bundle_id,
            )
            self.run_ledger.finish_step(
                active_run_id,
                step_id=active_step_id,
                final_state="completed",
                last_checkpoint=bundle.bundle_id,
                owner="evidence_service",
                metadata={"record_count": len(records), "bundle_id": bundle.bundle_id},
            )
            if owns_run:
                self.run_ledger.set_run_state(
                    active_run_id,
                    new_state="completed",
                    last_checkpoint=bundle.bundle_id,
                    owner="evidence_service",
                    metadata={
                        "bundle_id": bundle.bundle_id,
                        "record_count": len(records),
                    },
                )
        return bundle

    def _normalize_records(self, query: str, raw_records: Any) -> list[EvidenceRecord]:
        if not isinstance(raw_records, list):
            return []

        normalized: list[EvidenceRecord] = []
        for index, item in enumerate(raw_records, start=1):
            if not isinstance(item, dict):
                continue
            source_class = (
                str(item.get("source_class") or "public_registry").strip().lower()
            )
            provider = str(item.get("provider") or "unknown").strip().lower()
            title = str(item.get("title") or "").strip()
            if not title:
                continue
            admissibility, reason = self._classify_admissibility(source_class, provider)
            normalized.append(
                EvidenceRecord(
                    evidence_id=f"evidence_{index:03d}",
                    query=query,
                    source_class=source_class,
                    provider=provider,
                    title=title,
                    authors=self._normalize_authors(item.get("authors")),
                    year=self._normalize_year(item.get("year")),
                    url=str(item.get("url") or "").strip(),
                    doi=str(item.get("doi") or "").strip(),
                    pmid=str(item.get("pmid") or "").strip(),
                    arxiv_id=str(item.get("arxiv_id") or "").strip(),
                    license=str(item.get("license") or "").strip(),
                    retrieved_at=datetime.now(timezone.utc).isoformat(),
                    raw_snippet=str(item.get("snippet") or "").strip(),
                    normalized_abstract=str(item.get("abstract") or "").strip(),
                    confidence=self._normalize_confidence(item.get("confidence")),
                    admissibility=admissibility,
                    admissibility_reason=reason,
                )
            )
        return normalized

    def _classify_admissibility(
        self, source_class: str, provider: str
    ) -> tuple[str, str]:
        if source_class not in {"public_registry", "workspace_local"}:
            return "blocked", "Source class is not approved for evidence ingestion."
        if provider in BLOCKED_PROVIDERS:
            return "blocked", "Provider is blocked by default evidence policy."
        if provider in HIGH_TRUST_PROVIDERS:
            return "allowed", "Provider is in the high-trust literature set."
        if provider in MEDIUM_TRUST_PROVIDERS:
            return "downgraded", "Provider is medium-trust and should be reviewed."
        return "downgraded", "Provider is unknown and requires review."

    def _normalize_authors(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _normalize_year(self, value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        return None

    def _normalize_confidence(self, value: Any) -> float:
        if isinstance(value, bool):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        return 0.0

    def _normalize_usage(self, session_id: str, payload: dict[str, Any]) -> TokenUsage:
        if not isinstance(payload, dict):
            return TokenUsage(session_id=session_id)
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
        if usage.total_tokens == 0:
            usage.total_tokens = usage.input_tokens + usage.output_tokens
        return usage

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
