import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

BioAnalysisOrchestrator = importlib.import_module(
    "abris.orchestrator.bio_orchestrator"
).BioAnalysisOrchestrator
AutonomyPolicy = importlib.import_module("abris.models.schemas").AutonomyPolicy
Settings = importlib.import_module("abris.config.settings").Settings
RunLedger = importlib.import_module("abris.runlog.store").RunLedger


class PrototypeAnalysisTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        pipelines_dir = self.root / "configs" / "pipelines"
        pipelines_dir.mkdir(parents=True, exist_ok=True)
        repo_root = Path(__file__).resolve().parents[1]
        source_pipeline = (
            repo_root / "configs" / "pipelines" / "count_matrix_prototype.yaml"
        )
        (pipelines_dir / "count_matrix_prototype.yaml").write_text(
            source_pipeline.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        self.counts_path = self.root / "counts.tsv"
        self.counts_path.write_text(
            "\n".join(
                [
                    "feature\tctrl_1\tctrl_2\ttreat_1\ttreat_2",
                    "GeneA\t100\t110\t240\t230",
                    "GeneB\t80\t85\t82\t79",
                    "GeneC\t15\t18\t60\t55",
                    "GeneD\t300\t290\t310\t305",
                    "GeneE\t40\t45\t20\t18",
                ]
            ),
            encoding="utf-8",
        )
        self.sample_sheet = self.root / "samples.csv"
        self.sample_sheet.write_text(
            "\n".join(
                [
                    "sample,group",
                    "ctrl_1,control",
                    "ctrl_2,control",
                    "treat_1,treatment",
                    "treat_2,treatment",
                ]
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_prototype_count_matrix_pipeline_runs_real_summary(self) -> None:
        settings = Settings.from_root(self.root)
        orchestrator = BioAnalysisOrchestrator(
            settings=settings,
            autonomy_policy=AutonomyPolicy(
                mode="acquire_bounded",
                approval_required=False,
                allowed_source_classes=["workspace_local"],
            ),
        )

        report = orchestrator.analyze(
            "Analyze this local count matrix",
            {
                "pipeline_profile": "prototype_counts",
                "counts_file": str(self.counts_path),
                "sample_sheet": str(self.sample_sheet),
                "input_files": [str(self.counts_path), str(self.sample_sheet)],
            },
        )

        self.assertEqual(
            [step.skill_id for step in report.plan], ["count_matrix_summary"]
        )
        self.assertEqual(report.results[0].status, "success")
        self.assertEqual(report.results[0].outputs["sample_count"], 4)
        self.assertEqual(report.results[0].outputs["feature_count"], 5)
        self.assertEqual(
            report.results[0].outputs["comparison_summary"]["status"], "available"
        )
        self.assertEqual(
            report.results[0].outputs["top_features"][0]["feature"], "GeneD"
        )
        self.assertEqual(len(report.results[0].outputs["artifact_paths"]), 3)

        ledger = RunLedger(settings)
        run = ledger.get_run(report.run_id)
        self.assertEqual(len(run.artifact_paths), 3)
        self.assertTrue(any(path.endswith("counts.tsv") for path in run.artifact_paths))
        self.assertTrue(
            any(path.endswith("samples.csv") for path in run.artifact_paths)
        )
        summary_paths = [
            path for path in run.artifact_paths if path.endswith("_summary.json")
        ]
        self.assertEqual(len(summary_paths), 1)
        summary_payload = json.loads(Path(summary_paths[0]).read_text(encoding="utf-8"))
        self.assertEqual(
            summary_payload["analysis_type"], "prototype_count_matrix_summary"
        )

    def test_prototype_count_matrix_rejects_missing_group_column(self) -> None:
        bad_sheet = self.root / "bad_samples.csv"
        bad_sheet.write_text(
            "\n".join(
                [
                    "sample,batch",
                    "ctrl_1,a",
                    "ctrl_2,a",
                    "treat_1,b",
                    "treat_2,b",
                ]
            ),
            encoding="utf-8",
        )
        orchestrator = BioAnalysisOrchestrator(
            autonomy_policy=AutonomyPolicy(
                mode="acquire_bounded",
                approval_required=False,
                allowed_source_classes=["workspace_local"],
            )
        )

        report = orchestrator.analyze(
            "Analyze this local count matrix",
            {
                "pipeline_profile": "prototype_counts",
                "counts_file": str(self.counts_path),
                "sample_sheet": str(bad_sheet),
            },
        )

        self.assertEqual(report.results[0].status, "blocked")
        self.assertIn("Sample sheet requires", report.results[0].message)


if __name__ == "__main__":
    unittest.main()
