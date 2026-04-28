import sys
import importlib
import unittest
from dataclasses import dataclass
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

BioAnalysisOrchestrator = importlib.import_module(
    "abris.orchestrator.bio_orchestrator"
).BioAnalysisOrchestrator
EnvironmentSnapshot = importlib.import_module(
    "abris.models.schemas"
).EnvironmentSnapshot
AutonomyPolicy = importlib.import_module("abris.models.schemas").AutonomyPolicy
AcquisitionRequest = importlib.import_module("abris.models.schemas").AcquisitionRequest
PipelineStep = importlib.import_module("abris.models.schemas").PipelineStep
SkillSpec = importlib.import_module("abris.models.schemas").SkillSpec
SkillsRegistry = importlib.import_module(
    "abris.registry.skills_registry"
).SkillsRegistry


@dataclass
class StaticDetector:
    snapshot: object

    def detect(self):
        return self.snapshot


class BioAnalysisOrchestratorTest(unittest.TestCase):
    def test_orchestrator_builds_rna_seq_plan(self) -> None:
        orchestrator = BioAnalysisOrchestrator(
            detector=StaticDetector(
                EnvironmentSnapshot(
                    os_name="test-os",
                    python_version="3.12",
                    cpu_count=8,
                    available_tools=[
                        "fastqc",
                        "trim_galore",
                        "STAR",
                        "featureCounts",
                        "Rscript",
                    ],
                    available_python_modules=[],
                    available_r_packages=["DESeq2"],
                    notes=[],
                )
            ),
            autonomy_policy=AutonomyPolicy(
                mode="acquire_bounded",
                approval_required=False,
                allowed_source_classes=["workspace_local"],
            ),
        )
        report = orchestrator.analyze("Please run RNA-seq differential analysis")

        self.assertEqual(report.intent.analysis_type, "RNA-seq")
        self.assertEqual(
            [step.skill_id for step in report.plan],
            [
                "fastqc",
                "trim_galore",
                "star_alignment",
                "featurecounts",
                "deseq2",
                "go_enrichment",
            ],
        )
        self.assertTrue(all(result.status == "success" for result in report.results))

    def test_orchestrator_blocks_when_requirements_are_missing(self) -> None:
        orchestrator = BioAnalysisOrchestrator(
            detector=StaticDetector(
                EnvironmentSnapshot(
                    os_name="test-os",
                    python_version="3.12",
                    cpu_count=8,
                    available_tools=["fastqc"],
                    available_python_modules=[],
                    available_r_packages=[],
                    notes=[
                        "Rscript not found; R package execution is not available yet."
                    ],
                )
            ),
            autonomy_policy=AutonomyPolicy(
                mode="acquire_bounded",
                approval_required=False,
                allowed_source_classes=["workspace_local"],
            ),
        )

        report = orchestrator.analyze("Please run RNA-seq differential analysis")

        self.assertTrue(all(result.status == "blocked" for result in report.results))
        self.assertIn("trim_galore", report.results[0].outputs["missing_requirements"])
        self.assertEqual(report.results[-1].step, "go_enrichment")

    def test_environment_validation_supports_python_module_requirements(self) -> None:
        registry = SkillsRegistry()
        registry.register(
            SkillSpec(
                skill_id="scanpy_qc",
                name="Scanpy QC",
                layer="atomic",
                category="single-cell",
                description="Quality control with Scanpy.",
                requirements=["scanpy"],
            )
        )
        orchestrator = BioAnalysisOrchestrator(
            detector=StaticDetector(
                EnvironmentSnapshot(
                    os_name="test-os",
                    python_version="3.12",
                    cpu_count=8,
                    available_tools=[],
                    available_python_modules=[],
                    available_r_packages=[],
                    notes=[],
                )
            ),
            registry=registry,
            autonomy_policy=AutonomyPolicy(
                mode="acquire_bounded",
                approval_required=False,
                allowed_source_classes=["workspace_local"],
            ),
        )

        results = orchestrator._validate_environment_for_plan(
            [PipelineStep(skill_id="scanpy_qc")],
            EnvironmentSnapshot(
                os_name="test-os",
                python_version="3.12",
                cpu_count=8,
                available_tools=[],
                available_python_modules=[],
                available_r_packages=[],
                notes=[],
            ),
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "blocked")
        self.assertEqual(results[0].outputs["missing_requirements"], ["scanpy"])

    def test_orchestrator_uses_runtime_for_structured_intent(self) -> None:
        class FakeRuntime:
            def create_session(self, title: str) -> str:
                self.title = title
                return "ses_runtime"

            def prompt_text(self, session_id: str, text: str):
                return {"text": text}

            def prompt_structured(self, session_id: str, request):
                self.prompt = request.prompt
                return {
                    "structured_output": {
                        "analysis_type": "SingleCell",
                        "goal": "cluster_cells",
                        "expected_outputs": ["umap", "cluster_markers"],
                        "acquisition_requests": [
                            {
                                "source_class": "public_registry",
                                "locator": "geo:GSE123",
                            }
                        ],
                        "requests_codegen": True,
                    }
                }

        runtime = FakeRuntime()
        orchestrator = BioAnalysisOrchestrator(
            detector=StaticDetector(
                EnvironmentSnapshot(
                    os_name="test-os",
                    python_version="3.12",
                    cpu_count=8,
                    available_tools=["fastqc"],
                    available_python_modules=[],
                    available_r_packages=[],
                    notes=[],
                )
            ),
            runtime=runtime,
            autonomy_policy=AutonomyPolicy(
                mode="generate_bounded",
                approval_required=False,
                codegen_scope=["src/abris"],
            ),
        )

        intent = orchestrator.understand_intent("cluster this data", {})

        self.assertEqual(runtime.title, "ABRIS Intent Parsing")
        self.assertIn('"autonomy_mode": "generate_bounded"', runtime.prompt)
        self.assertEqual(intent.analysis_type, "SingleCell")
        self.assertEqual(intent.goal, "cluster_cells")
        self.assertEqual(intent.expected_outputs, ["umap", "cluster_markers"])
        self.assertEqual(len(intent.acquisition_requests), 1)
        self.assertEqual(intent.acquisition_requests[0].source_class, "public_registry")
        self.assertTrue(intent.requests_codegen)

    def test_plan_only_mode_blocks_execution_even_when_environment_is_ready(
        self,
    ) -> None:
        orchestrator = BioAnalysisOrchestrator(
            detector=StaticDetector(
                EnvironmentSnapshot(
                    os_name="test-os",
                    python_version="3.12",
                    cpu_count=8,
                    available_tools=[
                        "fastqc",
                        "trim_galore",
                        "STAR",
                        "featureCounts",
                        "Rscript",
                    ],
                    available_python_modules=[],
                    available_r_packages=["DESeq2"],
                    notes=[],
                )
            )
        )

        report = orchestrator.analyze("Please run RNA-seq differential analysis")

        self.assertEqual(report.results[0].step, "policy_gate")
        self.assertEqual(report.results[0].status, "blocked")
        self.assertEqual(report.autonomy_policy.mode, "plan_only")

    def test_acquisition_request_requires_allowed_mode_and_approval(self) -> None:
        orchestrator = BioAnalysisOrchestrator(
            detector=StaticDetector(
                EnvironmentSnapshot(
                    os_name="test-os",
                    python_version="3.12",
                    cpu_count=8,
                    available_tools=["fastqc"],
                    available_python_modules=[],
                    available_r_packages=[],
                    notes=[],
                )
            ),
            autonomy_policy=AutonomyPolicy(
                mode="acquire_bounded",
                approval_required=True,
                allowed_source_classes=["public_registry"],
            ),
        )

        report = orchestrator.analyze(
            "Fetch GEO data and run analysis",
            {
                "acquisition_requests": [
                    {"source_class": "public_registry", "locator": "geo:GSE123"}
                ]
            },
        )

        self.assertEqual(report.results[0].step, "policy_gate")
        self.assertIn("requires approval", report.results[0].message)
        self.assertTrue(report.results[0].outputs["requires_acquisition"])

    def test_acquisition_request_requires_structured_entries(self) -> None:
        orchestrator = BioAnalysisOrchestrator(
            detector=StaticDetector(
                EnvironmentSnapshot(
                    os_name="test-os",
                    python_version="3.12",
                    cpu_count=8,
                    available_tools=["fastqc"],
                    available_python_modules=[],
                    available_r_packages=[],
                    notes=[],
                )
            ),
            autonomy_policy=AutonomyPolicy(
                mode="acquire_bounded",
                approval_required=False,
                allowed_source_classes=["public_registry"],
            ),
        )

        report = orchestrator.analyze(
            "Fetch GEO data and run analysis",
            {"acquisition_requests": ["geo:GSE123"]},
        )

        self.assertEqual(report.results[0].step, "policy_gate")
        self.assertIn("structured acquisition_requests", report.results[0].message)

    def test_acquisition_request_requires_locator(self) -> None:
        orchestrator = BioAnalysisOrchestrator(
            detector=StaticDetector(
                EnvironmentSnapshot(
                    os_name="test-os",
                    python_version="3.12",
                    cpu_count=8,
                    available_tools=["fastqc"],
                    available_python_modules=[],
                    available_r_packages=[],
                    notes=[],
                )
            ),
            autonomy_policy=AutonomyPolicy(
                mode="acquire_bounded",
                approval_required=False,
                allowed_source_classes=["public_registry"],
            ),
        )

        intent = importlib.import_module("abris.models.schemas").AnalysisIntent(
            analysis_type="generic",
            goal="exploratory_analysis",
            requires_acquisition=True,
            acquisition_requests=[
                AcquisitionRequest(source_class="public_registry", locator="")
            ],
        )

        results = orchestrator._enforce_autonomy_policy(intent)
        self.assertEqual(results[0].step, "policy_gate")
        self.assertIn("missing source_class or locator", results[0].message)

    def test_acquisition_request_requires_allowed_source_class(self) -> None:
        orchestrator = BioAnalysisOrchestrator(
            detector=StaticDetector(
                EnvironmentSnapshot(
                    os_name="test-os",
                    python_version="3.12",
                    cpu_count=8,
                    available_tools=["fastqc"],
                    available_python_modules=[],
                    available_r_packages=[],
                    notes=[],
                )
            ),
            autonomy_policy=AutonomyPolicy(
                mode="acquire_bounded",
                approval_required=False,
                allowed_source_classes=["workspace_local"],
            ),
        )

        report = orchestrator.analyze(
            "Fetch GEO data and run analysis",
            {
                "acquisition_requests": [
                    {"source_class": "public_registry", "locator": "geo:GSE123"}
                ]
            },
        )

        self.assertEqual(report.results[0].step, "policy_gate")
        self.assertIn("disallowed source class", report.results[0].message)

    def test_codegen_request_requires_scope(self) -> None:
        orchestrator = BioAnalysisOrchestrator(
            detector=StaticDetector(
                EnvironmentSnapshot(
                    os_name="test-os",
                    python_version="3.12",
                    cpu_count=8,
                    available_tools=["fastqc"],
                    available_python_modules=[],
                    available_r_packages=[],
                    notes=[],
                )
            ),
            autonomy_policy=AutonomyPolicy(
                mode="generate_bounded",
                approval_required=False,
            ),
        )

        report = orchestrator.analyze(
            "Generate code for a new pipeline adapter",
            {"codegen_scope": ["src/abris"]},
        )

        self.assertEqual(report.results[0].step, "policy_gate")
        self.assertIn("scope is empty", report.results[0].message)

    def test_optimization_request_requires_optimize_mode(self) -> None:
        orchestrator = BioAnalysisOrchestrator(
            detector=StaticDetector(
                EnvironmentSnapshot(
                    os_name="test-os",
                    python_version="3.12",
                    cpu_count=8,
                    available_tools=["fastqc"],
                    available_python_modules=[],
                    available_r_packages=[],
                    notes=[],
                )
            ),
            autonomy_policy=AutonomyPolicy(
                mode="generate_bounded",
                approval_required=False,
                optimization_scope=["skill:fastqc-v2"],
            ),
        )

        report = orchestrator.analyze(
            "Optimize the analysis skill for faster execution",
            {"optimization_scope": ["skill:fastqc-v2"]},
        )

        self.assertEqual(report.results[0].step, "policy_gate")
        self.assertIn("optimize_proposed", report.results[0].message)


if __name__ == "__main__":
    unittest.main()
