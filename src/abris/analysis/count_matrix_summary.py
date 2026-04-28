from __future__ import annotations

import csv
import math
import statistics
from pathlib import Path
from typing import Any


def summarize_count_matrix(
    counts_path: str | Path,
    sample_sheet_path: str | Path | None = None,
    *,
    top_n: int = 5,
    max_features: int = 5000,
    max_samples: int = 64,
) -> dict[str, Any]:
    counts_file = Path(counts_path)
    if not counts_file.exists():
        raise ValueError(f"Counts file does not exist: {counts_file}")

    delimiter = _detect_delimiter(counts_file)
    rows = _read_delimited_rows(counts_file, delimiter)
    if len(rows) < 2:
        raise ValueError(
            "Counts matrix must include a header and at least one feature row."
        )

    header = rows[0]
    if len(header) < 2:
        raise ValueError(
            "Counts matrix must include one feature column and at least one sample column."
        )

    sample_names = [cell.strip() for cell in header[1:] if cell.strip()]
    if not sample_names:
        raise ValueError("Counts matrix sample columns are empty.")
    if len(sample_names) > max_samples:
        raise ValueError(
            f"Counts matrix exceeds bounded compute limit: {len(sample_names)} samples > {max_samples}."
        )

    feature_rows = rows[1:]
    if len(feature_rows) > max_features:
        raise ValueError(
            f"Counts matrix exceeds bounded compute limit: {len(feature_rows)} features > {max_features}."
        )

    feature_values: list[tuple[str, list[float]]] = []
    sample_totals = {sample: 0.0 for sample in sample_names}
    for row in feature_rows:
        if len(row) != len(header):
            raise ValueError("Counts matrix rows must match header width.")
        feature_id = row[0].strip()
        if not feature_id:
            raise ValueError(
                "Counts matrix contains a feature row without an identifier."
            )
        values = [_parse_numeric(cell) for cell in row[1:]]
        feature_values.append((feature_id, values))
        for sample_name, value in zip(sample_names, values, strict=True):
            sample_totals[sample_name] += value

    group_map, group_summary = _load_group_summary(sample_names, sample_sheet_path)
    top_features = _rank_top_features(feature_values, key="mean", top_n=top_n)
    high_variance_features = _rank_top_features(
        feature_values, key="variance", top_n=top_n
    )
    comparison_summary = _build_comparison_summary(
        feature_values, sample_names, group_map, top_n
    )

    return {
        "analysis_type": "prototype_count_matrix_summary",
        "disclaimer": (
            "Prototype count-matrix summary only; this is not full RNA-seq alignment or DESeq2 execution."
        ),
        "validation_summary": {
            "delimiter": "tab" if delimiter == "\t" else "comma",
            "counts_file": str(counts_file),
            "sample_sheet": str(sample_sheet_path) if sample_sheet_path else None,
        },
        "sample_count": len(sample_names),
        "feature_count": len(feature_values),
        "group_summary": group_summary,
        "sample_totals": [
            {"sample": sample, "total_count": round(total, 4)}
            for sample, total in sorted(sample_totals.items())
        ],
        "top_features": top_features,
        "high_variance_features": high_variance_features,
        "comparison_summary": comparison_summary,
        "warnings": [],
    }


def _detect_delimiter(path: Path) -> str:
    first_line = path.read_text(encoding="utf-8").splitlines()[0]
    return "\t" if "\t" in first_line else ","


def _read_delimited_rows(path: Path, delimiter: str) -> list[list[str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle, delimiter=delimiter))


def _parse_numeric(raw: str) -> float:
    try:
        return float(raw.strip())
    except ValueError as exc:
        raise ValueError(
            f"Counts matrix contains a non-numeric value: {raw!r}"
        ) from exc


def _load_group_summary(
    sample_names: list[str], sample_sheet_path: str | Path | None
) -> tuple[dict[str, str], dict[str, int]]:
    if sample_sheet_path is None:
        return (
            {sample: "ungrouped" for sample in sample_names},
            {"ungrouped": len(sample_names)},
        )

    sample_sheet = Path(sample_sheet_path)
    if not sample_sheet.exists():
        raise ValueError(f"Sample sheet does not exist: {sample_sheet}")

    delimiter = _detect_delimiter(sample_sheet)
    with sample_sheet.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if reader.fieldnames is None:
            raise ValueError("Sample sheet is empty.")

        lowered = {name.lower(): name for name in reader.fieldnames}
        sample_key = lowered.get("sample") or lowered.get("sample_id")
        group_key = lowered.get("group") or lowered.get("condition")
        if sample_key is None or group_key is None:
            raise ValueError(
                "Sample sheet requires 'sample' and 'group' or 'condition' columns."
            )

        group_map: dict[str, str] = {}
        for row in reader:
            sample_name = str(row.get(sample_key, "")).strip()
            group_name = str(row.get(group_key, "")).strip()
            if sample_name:
                group_map[sample_name] = group_name or "ungrouped"

    missing_samples = [sample for sample in sample_names if sample not in group_map]
    if missing_samples:
        raise ValueError(
            "Sample sheet is missing group assignments for: "
            + ", ".join(missing_samples)
        )

    summary: dict[str, int] = {}
    for sample in sample_names:
        group_name = group_map[sample]
        summary[group_name] = summary.get(group_name, 0) + 1
    return group_map, summary


def _rank_top_features(
    feature_values: list[tuple[str, list[float]]], *, key: str, top_n: int
) -> list[dict[str, float | str]]:
    ranked: list[tuple[str, float]] = []
    for feature_id, values in feature_values:
        score = (
            statistics.fmean(values) if key == "mean" else statistics.pvariance(values)
        )
        ranked.append((feature_id, score))
    ranked.sort(key=lambda item: item[1], reverse=True)
    metric_name = "mean_abundance" if key == "mean" else "variance"
    return [
        {"feature": feature_id, metric_name: round(score, 6)}
        for feature_id, score in ranked[:top_n]
    ]


def _build_comparison_summary(
    feature_values: list[tuple[str, list[float]]],
    sample_names: list[str],
    group_map: dict[str, str],
    top_n: int,
) -> dict[str, Any]:
    distinct_groups = sorted({group_map[sample] for sample in sample_names})
    if len(distinct_groups) != 2:
        return {
            "status": "unavailable",
            "reason": "Comparison summary requires exactly two groups.",
            "groups": distinct_groups,
        }

    left_group, right_group = distinct_groups
    left_indices = [
        i for i, sample in enumerate(sample_names) if group_map[sample] == left_group
    ]
    right_indices = [
        i for i, sample in enumerate(sample_names) if group_map[sample] == right_group
    ]

    ranked: list[dict[str, float | str]] = []
    for feature_id, values in feature_values:
        left_mean = statistics.fmean(values[index] for index in left_indices)
        right_mean = statistics.fmean(values[index] for index in right_indices)
        log2_fold_change = math.log2((right_mean + 1.0) / (left_mean + 1.0))
        ranked.append(
            {
                "feature": feature_id,
                "left_group": left_group,
                "right_group": right_group,
                "left_mean": round(left_mean, 6),
                "right_mean": round(right_mean, 6),
                "log2_fold_change": round(log2_fold_change, 6),
                "abs_log2_fold_change": round(abs(log2_fold_change), 6),
            }
        )

    ranked.sort(key=lambda item: float(item["abs_log2_fold_change"]), reverse=True)
    for item in ranked:
        item.pop("abs_log2_fold_change", None)
    return {
        "status": "available",
        "groups": distinct_groups,
        "top_fold_change_features": ranked[:top_n],
    }
