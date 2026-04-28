import importlib
import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

Settings = importlib.import_module("abris.config.settings").Settings
SequencingGateway = importlib.import_module(
    "abris.data.sequencing_gateway"
).SequencingGateway
FileGuard = importlib.import_module("abris.environment.file_guard").FileGuard
FileReadRequest = importlib.import_module("abris.models.schemas").FileReadRequest
BioAnalysisOrchestrator = importlib.import_module(
    "abris.orchestrator.bio_orchestrator"
).BioAnalysisOrchestrator


class FileIntakeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        pipeline_dir = self.root / "configs" / "pipelines"
        pipeline_dir.mkdir(parents=True, exist_ok=True)
        (pipeline_dir / "rna_seq_standard.yaml").write_text(
            "\n".join(
                [
                    "id: rna-seq-standard",
                    "name: RNA-seq Standard Pipeline",
                    "steps:",
                    "  - skill: fastqc",
                    "  - skill: trim_galore",
                    "  - skill: star_alignment",
                    "  - skill: featurecounts",
                    "  - skill: deseq2",
                    "  - skill: go_enrichment",
                    "outputs:",
                    "  - differential_expression_results",
                    "  - volcano_plot",
                    "  - heatmap",
                    "  - enrichment_report",
                ]
            ),
            encoding="utf-8",
        )
        self.settings = Settings.from_root(self.root)
        self.gateway = SequencingGateway()
        self.guard = FileGuard(self.settings)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_large_protected_fastq_is_metadata_only(self) -> None:
        fastq_path = self.root / "sample_R1.fastq.gz"
        fastq_path.write_bytes(b"0" * (self.settings.max_direct_read_bytes + 128))

        asset = self.gateway.inspect_path(fastq_path)
        decision = self.guard.evaluate(
            FileReadRequest(
                path=fastq_path,
                operation="prompt_embed",
                caller="test",
                embed_in_prompt=True,
            ),
            asset,
        )

        self.assertEqual(asset.file_type, "FASTQ")
        self.assertTrue(asset.protected)
        self.assertEqual(decision.action, "convert_to_metadata_only")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.redirect_tool, "fastqc")

    def test_small_text_file_is_allowed_for_direct_read(self) -> None:
        text_path = self.root / "notes.txt"
        text_path.write_text("hello\nworld\n", encoding="utf-8")

        asset = self.gateway.inspect_path(text_path)
        decision = self.guard.evaluate(
            FileReadRequest(
                path=text_path,
                operation="direct_read",
                caller="test",
            ),
            asset,
        )

        self.assertEqual(asset.file_type, "TEXT")
        self.assertEqual(decision.action, "allow_direct_read")
        self.assertTrue(decision.allowed)

    def test_unknown_binary_denies_prompt_embedding(self) -> None:
        binary_path = self.root / "blob.bin"
        binary_path.write_bytes(b"\x00\x01\x02\x03")

        asset = self.gateway.inspect_path(binary_path)
        decision = self.guard.evaluate(
            FileReadRequest(
                path=binary_path,
                operation="prompt_embed",
                caller="test",
                embed_in_prompt=True,
            ),
            asset,
        )

        self.assertEqual(asset.file_type, "UNKNOWN_BINARY")
        self.assertEqual(decision.action, "deny")
        self.assertFalse(decision.allowed)

    def test_orchestrator_reports_assets_and_access_decisions(self) -> None:
        fastq_path = self.root / "reads_R1.fastq.gz"
        fastq_path.write_bytes(b"0" * (self.settings.max_direct_read_bytes + 64))

        orchestrator = BioAnalysisOrchestrator(settings=self.settings)
        report = orchestrator.analyze(
            "Please run RNA-seq differential analysis",
            parameters={"input_files": [str(fastq_path)]},
        )

        self.assertEqual(len(report.assets), 1)
        self.assertEqual(len(report.file_access_decisions), 1)
        self.assertEqual(report.assets[0].file_type, "FASTQ")
        self.assertEqual(
            report.file_access_decisions[0].action,
            "convert_to_metadata_only",
        )


if __name__ == "__main__":
    unittest.main()
