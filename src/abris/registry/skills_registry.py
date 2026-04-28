from __future__ import annotations

from dataclasses import asdict

from abris.models.schemas import SkillSpec


class SkillsRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, SkillSpec] = {}

    def register(self, skill: SkillSpec) -> None:
        self._skills[skill.skill_id] = skill

    def get(self, skill_id: str) -> SkillSpec:
        return self._skills[skill_id]

    def has(self, skill_id: str) -> bool:
        return skill_id in self._skills

    def list_all(self) -> list[SkillSpec]:
        return list(self._skills.values())

    def find_by_category(self, category: str) -> list[SkillSpec]:
        return [skill for skill in self._skills.values() if skill.category == category]

    def export(self) -> list[dict[str, object]]:
        return [asdict(skill) for skill in self._skills.values()]


def build_default_registry() -> SkillsRegistry:
    registry = SkillsRegistry()
    registry.register(
        SkillSpec(
            skill_id="count_matrix_summary",
            name="Count Matrix Summary",
            layer="atomic",
            category="prototype-analysis",
            description="Lightweight local summary for small count matrices.",
            requirements=[],
        )
    )
    registry.register(
        SkillSpec(
            skill_id="fastqc",
            name="FastQC",
            layer="atomic",
            category="quality-control",
            description="Quality control for sequencing reads.",
            requirements=["fastqc"],
        )
    )
    registry.register(
        SkillSpec(
            skill_id="trim_galore",
            name="Trim Galore",
            layer="atomic",
            category="preprocessing",
            description="Adapter trimming and read preprocessing.",
            requirements=["trim_galore"],
        )
    )
    registry.register(
        SkillSpec(
            skill_id="star_alignment",
            name="STAR Alignment",
            layer="atomic",
            category="alignment",
            description="Spliced read alignment for RNA-seq.",
            requirements=["STAR"],
        )
    )
    registry.register(
        SkillSpec(
            skill_id="featurecounts",
            name="featureCounts",
            layer="atomic",
            category="quantification",
            description="Gene-level read counting from alignments.",
            requirements=["featureCounts"],
        )
    )
    registry.register(
        SkillSpec(
            skill_id="deseq2",
            name="DESeq2",
            layer="atomic",
            category="differential-analysis",
            description="Differential expression analysis.",
            requirements=["Rscript", "DESeq2"],
        )
    )
    registry.register(
        SkillSpec(
            skill_id="go_enrichment",
            name="GO Enrichment",
            layer="atomic",
            category="enrichment",
            description="Functional enrichment analysis for differential hits.",
            requirements=["Rscript"],
        )
    )
    return registry
