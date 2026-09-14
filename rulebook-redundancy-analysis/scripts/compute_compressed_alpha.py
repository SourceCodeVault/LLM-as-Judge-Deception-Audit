#!/usr/bin/env python3
"""
Recompute Krippendorff's alpha for compressed rulebooks.

Mirrors the repository's reported rule-citation metric:
  - labels are frozenset-style rule citation sets
  - set distance is MASI
  - empty-empty labels have distance 0
  - rows are arranged as runs/coders by cases/items

This script implements alpha directly to avoid requiring NLTK at runtime.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path

from evaluate_compressed_rulebook import COMPRESSION_SPECS, META_COLUMNS, compress_row, load_incidence


def masi_distance(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 0.0
    if a == b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    if union == 0:
        return 0.0
    jaccard_similarity = inter / union
    if inter == min(len(a), len(b)):
        m = 2.0 / 3.0
    elif inter > 0:
        m = 1.0 / 3.0
    else:
        m = 1.0
    return 1.0 - m * jaccard_similarity


def krippendorff_alpha_masi(items: list[list[frozenset[str]]]) -> tuple[float, float, float]:
    """
    Compute alpha = 1 - Do/De for fixed-cardinality item annotations.

    items: list of cases; each case is a list of run labels.
    """
    observed_num = 0.0
    observed_den = 0
    label_counts: Counter[frozenset[str]] = Counter()

    for labels in items:
        valid = [label for label in labels if label is not None]
        for label in valid:
            label_counts[label] += 1
        m = len(valid)
        if m < 2:
            continue
        for i in range(m):
            for j in range(m):
                if i == j:
                    continue
                observed_num += masi_distance(valid[i], valid[j])
                observed_den += 1

    total = sum(label_counts.values())
    if observed_den == 0 or total < 2:
        return math.nan, math.nan, math.nan
    observed = observed_num / observed_den

    expected_num = 0.0
    expected_den = total * (total - 1)
    labels = list(label_counts)
    for a in labels:
        ca = label_counts[a]
        for b in labels:
            cb = label_counts[b]
            if a == b:
                expected_num += ca * (cb - 1) * masi_distance(a, b)
            else:
                expected_num += ca * cb * masi_distance(a, b)
    expected = expected_num / expected_den if expected_den else math.nan
    alpha = 1.0 - observed / expected if expected and not math.isnan(expected) else math.nan
    return alpha, observed, expected


def build_items(
    rows: list[dict[str, str]],
    spec: dict[str, list[str]],
    include_incomplete: bool,
) -> tuple[list[list[frozenset[str] | None]], int, int]:
    by_case: dict[str, dict[str, frozenset[str]]] = defaultdict(dict)
    pass_ids = sorted({row["pass_id"] for row in rows})
    for row in rows:
        by_case[row["case_id"]][row["pass_id"]] = compress_row(row, spec)

    if include_incomplete:
        case_ids = sorted(by_case)
        items = [[by_case[case_id].get(pass_id) for pass_id in pass_ids] for case_id in case_ids]
    else:
        case_ids = [
            case_id for case_id, passes in sorted(by_case.items())
            if set(pass_ids).issubset(passes)
        ]
        items = [[by_case[case_id][pass_id] for pass_id in pass_ids] for case_id in case_ids]
    return items, len(case_ids), len(pass_ids)


def set_summary(items: list[list[frozenset[str]]]) -> dict:
    flat = [label for item in items for label in item if label is not None]
    empty = sum(1 for label in flat if not label)
    unique_labels = len(set(flat))
    exact_cases = sum(1 for item in items if len(set(label for label in item if label is not None)) == 1)
    all_empty_cases = sum(1 for item in items if all((label is None or not label) for label in item))
    missing_annotations = sum(1 for item in items for label in item if label is None)
    return {
        "annotations": len(flat),
        "missing_annotations": missing_annotations,
        "unique_label_sets": unique_labels,
        "empty_annotations": empty,
        "empty_annotation_rate": empty / len(flat) if flat else 0.0,
        "exact_case_sets": exact_cases,
        "exact_case_set_rate": exact_cases / len(items) if items else 0.0,
        "all_empty_cases": all_empty_cases,
        "all_empty_case_rate": all_empty_cases / len(items) if items else 0.0,
    }


def write_dicts(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    # The available k=6 matrix keeps all 297 cases and represents the one
    # missing rerun as a missing annotation, matching compute_stability.py.
    parser.add_argument("--incidence", default="data/rule_incidence_seed_and_reruns_available.csv")
    parser.add_argument("--out-dir", default="results/compressed_rulebook")
    parser.add_argument("--suffix", default="seed_and_reruns")
    parser.add_argument("--reported-alpha", type=float, default=0.23833564424581033)
    parser.add_argument("--complete-only", action="store_true", help="Drop cases missing any run instead of keeping missing annotations as None.")
    args = parser.parse_args()

    rows, original_rules = load_incidence(Path(args.incidence))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for spec_name, spec in COMPRESSION_SPECS.items():
        missing = sorted({member for members in spec.values() for member in members} - set(original_rules))
        if missing:
            raise ValueError(f"{spec_name} references missing original rules: {missing}")
        items, n_cases, n_runs = build_items(rows, spec, include_incomplete=not args.complete_only)
        alpha, observed, expected = krippendorff_alpha_masi(items)
        summary = set_summary(items)
        results.append({
            "spec": spec_name,
            "labels": len(spec),
            "cases": n_cases,
            "runs": n_runs,
            "alpha_masi": alpha,
            "observed_disagreement": observed,
            "expected_disagreement": expected,
            "delta_vs_reported_original": alpha - args.reported_alpha if not math.isnan(alpha) else math.nan,
            **summary,
        })

    path = out_dir / f"compressed_rulebook_alpha_{args.suffix}.csv"
    write_dicts(path, results)

    print(f"Incidence: {args.incidence}")
    print("Krippendorff alpha using MASI set distance")
    for row in results:
        print(
            f"  {row['spec']:<18} labels={row['labels']:>2} "
            f"k={row['runs']} n={row['cases']} "
            f"alpha={row['alpha_masi']:.6f} "
            f"Do={row['observed_disagreement']:.6f} De={row['expected_disagreement']:.6f} "
            f"empty_ann={row['empty_annotation_rate']:.3f}"
        )
    print("\nWrote:")
    print(f"  {path}")


if __name__ == "__main__":
    main()
