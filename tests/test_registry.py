import sys
import importlib
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

SkillSpec = importlib.import_module("abris.models.schemas").SkillSpec
registry_module = importlib.import_module("abris.registry.skills_registry")
SkillsRegistry = registry_module.SkillsRegistry
build_default_registry = registry_module.build_default_registry


class SkillsRegistryTest(unittest.TestCase):
    def test_registry_can_register_and_query(self) -> None:
        registry = SkillsRegistry()
        registry.register(
            SkillSpec(
                skill_id="demo",
                name="Demo",
                layer="atomic",
                category="testing",
                description="demo skill",
            )
        )

        self.assertEqual(registry.get("demo").name, "Demo")
        self.assertEqual(len(registry.find_by_category("testing")), 1)

    def test_default_registry_supports_rna_seq_pipeline(self) -> None:
        registry = build_default_registry()

        for skill_id in [
            "fastqc",
            "trim_galore",
            "star_alignment",
            "featurecounts",
            "deseq2",
            "go_enrichment",
        ]:
            self.assertTrue(registry.has(skill_id), skill_id)


if __name__ == "__main__":
    unittest.main()
