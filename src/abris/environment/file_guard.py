from __future__ import annotations

from pathlib import Path

from abris.config.settings import Settings
from abris.models.schemas import FileAccessDecision, FileReadRequest, InputAsset


class FileGuard:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def evaluate(
        self, request: FileReadRequest, asset: InputAsset | None = None
    ) -> FileAccessDecision:
        size_bytes = (
            asset.size_bytes if asset is not None else Path(request.path).stat().st_size
        )
        file_type = asset.file_type if asset is not None else "UNKNOWN"
        summary = (
            asset.metadata_summary
            if asset is not None
            else {
                "path": str(request.path),
                "size_bytes": size_bytes,
            }
        )

        if (
            asset is not None
            and asset.protected
            and size_bytes > self.settings.max_direct_read_bytes
        ):
            return FileAccessDecision(
                action="convert_to_metadata_only",
                allowed=False,
                reason="Protected sequencing file exceeds direct-read threshold.",
                warnings=[
                    "Raw content was blocked from direct prompt-oriented access.",
                ],
                policy_rule="protected_large_file",
                safe_summary=summary,
                redirect_tool=self._redirect_tool(file_type),
            )

        if asset is not None and asset.protected and request.embed_in_prompt:
            return FileAccessDecision(
                action="allow_bounded_preview",
                allowed=True,
                reason="Protected sequencing file may only be previewed in bounded form.",
                warnings=["Prompt embedding downgraded to bounded preview."],
                policy_rule="protected_prompt_embed",
                safe_summary=summary,
                redirect_tool=self._redirect_tool(file_type),
            )

        if file_type == "UNKNOWN_BINARY" and request.embed_in_prompt:
            return FileAccessDecision(
                action="deny",
                allowed=False,
                reason="Unknown binary input cannot be embedded into prompt context.",
                warnings=["Safe metadata probe only."],
                policy_rule="unknown_binary_prompt_embed",
                safe_summary=summary,
            )

        if size_bytes <= self.settings.max_direct_read_bytes:
            return FileAccessDecision(
                action="allow_direct_read",
                allowed=True,
                reason="File is within direct-read threshold.",
                policy_rule="small_safe_file",
                safe_summary=summary,
            )

        return FileAccessDecision(
            action="allow_bounded_preview",
            allowed=True,
            reason="File exceeds direct-read threshold; bounded preview recommended.",
            warnings=["Large file downgraded to preview mode."],
            policy_rule="large_non_protected_file",
            safe_summary=summary,
        )

    def _redirect_tool(self, file_type: str) -> str | None:
        if file_type == "FASTQ":
            return "fastqc"
        if file_type in {"BAM", "CRAM"}:
            return "samtools"
        if file_type == "VCF":
            return "bcftools"
        return None
