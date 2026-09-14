#!/usr/bin/env python3
"""
Evaluate whether natural rule clustering improves rerun reproducibility.

Input is the pass-level rule incidence matrix. Each compression map converts
the original binary rule columns into a smaller binary codebook by OR-ing rules
inside a cluster. Reproducibility is then measured within each case over reruns.
"""

from __future__ import annotations

import argparse
import csv
import itertools
from collections import defaultdict
from pathlib import Path


META_COLUMNS = {"case_id", "pass_id", "ground_truth", "verdict", "quadrant", "source_path"}


COMPRESSION_SPECS: dict[str, dict[str, list[str]]] = {
    "original": {
        "F1": ["F1"],
        "F2": ["F2"],
        "F3": ["F3"],
        "H1": ["H1"],
        "J1": ["J1"],
        "J2": ["J2"],
        "J3": ["J3"],
        "J4": ["J4"],
        "J5": ["J5"],
        "S1": ["S1"],
        "U1": ["U1"],
        "U2": ["U2"],
        "U3": ["U3"],
        "U4": ["U4"],
    },
    "natural_tight": {
        "F12": ["F1", "F2"],
        "F3": ["F3"],
        "H1": ["H1"],
        "J12": ["J1", "J2"],
        "J345": ["J3", "J4", "J5"],
        "S1": ["S1"],
        "U13": ["U1", "U3"],
        "U2": ["U2"],
        "U4": ["U4"],
    },
    "j_only": {
        "F1": ["F1"],
        "F2": ["F2"],
        "F3": ["F3"],
        "H1": ["H1"],
        "J12": ["J1", "J2"],
        "J345": ["J3", "J4", "J5"],
        "S1": ["S1"],
        "U1": ["U1"],
        "U2": ["U2"],
        "U3": ["U3"],
        "U4": ["U4"],
    },
    "j_all": {
        "F1": ["F1"],
        "F2": ["F2"],
        "F3": ["F3"],
        "H1": ["H1"],
        "J_ALL": ["J1", "J2", "J3", "J4", "J5"],
        "S1": ["S1"],
        "U1": ["U1"],
        "U2": ["U2"],
        "U3": ["U3"],
        "U4": ["U4"],
    },
    "broad_clusters": {
        "F123_U13": ["F1", "F2", "F3", "U1", "U3"],
        "H1": ["H1"],
        "J_ALL": ["J1", "J2", "J3", "J4", "J5"],
        "S1": ["S1"],
        "U2": ["U2"],
        "U4": ["U4"],
    },
    "j_family_original": {
        "J1": ["J1"],
        "J2": ["J2"],
        "J3": ["J3"],
        "J4": ["J4"],
        "J5": ["J5"],
    },
    "j_family_tight": {
        "J12": ["J1", "J2"],
        "J345": ["J3", "J4", "J5"],
    },
    "j_family_all": {
        "J_ALL": ["J1", "J2", "J3", "J4", "J5"],
    },
}


def load_incidence(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        rules = [field for field in (reader.fieldnames or []) if field not in META_COLUMNS]
    return rows, rules


def compress_row(row: dict[str, str], spec: dict[str, list[str]]) -> frozenset[str]:
    compressed = set()
    for label, members in spec.items():
        if any(int(row.get(member, "0")) for member in members):
            compressed.add(label)
    return frozenset(compressed)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    union = len(a | b)
    return len(a & b) / union if union else 1.0


def evaluate_case_sets(case_sets: list[frozenset[str]], labels: list[str]) -> dict:
    pairs = list(itertools.combinations(range(len(case_sets)), 2))
    pair_jaccards = [jaccard(case_sets[i], case_sets[j]) for i, j in pairs]
    exact_all = 1 if len(set(case_sets)) == 1 else 0
    unique_sets = len(set(case_sets))
    union_size = len(set().union(*case_sets)) if case_sets else 0
    intersection_size = len(set.intersection(*map(set, case_sets))) if case_sets else 0

    label_pair_agreements = []
    for label in labels:
        values = [1 if label in rule_set else 0 for rule_set in case_sets]
        agreements = [1 if values[i] == values[j] else 0 for i, j in pairs]
        label_pair_agreements.extend(agreements)

    return {
        "pairwise_jaccard": sum(pair_jaccards) / len(pair_jaccards) if pair_jaccards else 1.0,
        "exact_all": exact_all,
        "unique_sets": unique_sets,
        "union_size": union_size,
        "intersection_size": intersection_size,
        "label_pair_agreement": sum(label_pair_agreements) / len(label_pair_agreements) if label_pair_agreements else 1.0,
    }


def evaluate(rows: list[dict[str, str]], spec_name: str, spec: dict[str, list[str]]) -> tuple[dict, list[dict], list[dict]]:
    labels = list(spec)
    by_case: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_case[row["case_id"]].append(row)

    case_rows = []
    label_counts = {label: 0 for label in labels}
    label_active_cases = {label: 0 for label in labels}
    for case_id, case_obs in sorted(by_case.items()):
        case_obs.sort(key=lambda row: row["pass_id"])
        compressed_sets = [compress_row(row, spec) for row in case_obs]
        for rule_set in compressed_sets:
            for label in rule_set:
                label_counts[label] += 1
        for label in labels:
            if any(label in rule_set for rule_set in compressed_sets):
                label_active_cases[label] += 1
        metrics = evaluate_case_sets(compressed_sets, labels)
        case_rows.append({
            "spec": spec_name,
            "case_id": case_id,
            "passes": len(case_obs),
            **metrics,
            "sets": " | ".join(" ".join(sorted(rule_set)) for rule_set in compressed_sets),
        })

    n_cases = len(case_rows)
    summary = {
        "spec": spec_name,
        "labels": len(labels),
        "cases": n_cases,
        "pass_rows": sum(len(v) for v in by_case.values()),
        "exact_all_cases": sum(row["exact_all"] for row in case_rows),
        "exact_all_case_rate": sum(row["exact_all"] for row in case_rows) / n_cases if n_cases else 0.0,
        "mean_pairwise_jaccard": sum(row["pairwise_jaccard"] for row in case_rows) / n_cases if n_cases else 0.0,
        "mean_unique_sets_per_case": sum(row["unique_sets"] for row in case_rows) / n_cases if n_cases else 0.0,
        "mean_union_size": sum(row["union_size"] for row in case_rows) / n_cases if n_cases else 0.0,
        "mean_intersection_size": sum(row["intersection_size"] for row in case_rows) / n_cases if n_cases else 0.0,
        "mean_label_pair_agreement": sum(row["label_pair_agreement"] for row in case_rows) / n_cases if n_cases else 0.0,
    }

    label_rows = []
    total_passes = summary["pass_rows"]
    for label in labels:
        label_rows.append({
            "spec": spec_name,
            "label": label,
            "members": " ".join(spec[label]),
            "pass_support": label_counts[label],
            "pass_prevalence": label_counts[label] / total_passes if total_passes else 0.0,
            "active_cases": label_active_cases[label],
            "active_case_rate": label_active_cases[label] / n_cases if n_cases else 0.0,
        })
    return summary, case_rows, label_rows


def write_dicts(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    # Compression maps OR together original rules, then reproducibility is
    # measured over the compressed citation sets for each case.
    parser.add_argument("--incidence", default="data/rule_incidence_reruns.csv")
    parser.add_argument("--out-dir", default="results/compressed_rulebook")
    parser.add_argument("--suffix", default="reruns")
    parser.add_argument("--top-worst", type=int, default=10)
    args = parser.parse_args()

    rows, original_rules = load_incidence(Path(args.incidence))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summaries = []
    all_case_rows = []
    all_label_rows = []
    for spec_name, spec in COMPRESSION_SPECS.items():
        missing = sorted({member for members in spec.values() for member in members} - set(original_rules))
        if missing:
            raise ValueError(f"{spec_name} references missing original rules: {missing}")
        summary, case_rows, label_rows = evaluate(rows, spec_name, spec)
        summaries.append(summary)
        all_case_rows.extend(case_rows)
        all_label_rows.extend(label_rows)

    write_dicts(out_dir / f"compressed_rulebook_reproducibility_{args.suffix}.csv", summaries)
    write_dicts(out_dir / f"compressed_rulebook_case_metrics_{args.suffix}.csv", all_case_rows)
    write_dicts(out_dir / f"compressed_rulebook_label_summary_{args.suffix}.csv", all_label_rows)

    original = next(row for row in summaries if row["spec"] == "original")
    print(f"Incidence: {args.incidence}")
    print(f"Cases: {original['cases']}; pass rows: {original['pass_rows']}")
    print("\nReproducibility by codebook:")
    for row in summaries:
        print(
            f"  {row['spec']:<15} labels={row['labels']:>2} "
            f"exact_all={row['exact_all_case_rate']:.3f} "
            f"pairJ={row['mean_pairwise_jaccard']:.3f} "
            f"unique_sets={row['mean_unique_sets_per_case']:.3f} "
            f"label_agree={row['mean_label_pair_agreement']:.3f}"
        )

    print("\nGain versus original:")
    for row in summaries:
        if row["spec"] == "original":
            continue
        print(
            f"  {row['spec']:<15} "
            f"Δexact={row['exact_all_case_rate'] - original['exact_all_case_rate']:+.3f} "
            f"ΔpairJ={row['mean_pairwise_jaccard'] - original['mean_pairwise_jaccard']:+.3f} "
            f"Δunique={row['mean_unique_sets_per_case'] - original['mean_unique_sets_per_case']:+.3f} "
            f"Δlabel_agree={row['mean_label_pair_agreement'] - original['mean_label_pair_agreement']:+.3f}"
        )

    print("\nWorst original cases by pairwise Jaccard:")
    original_cases = [row for row in all_case_rows if row["spec"] == "original"]
    for row in sorted(original_cases, key=lambda r: (r["pairwise_jaccard"], -r["unique_sets"]))[: args.top_worst]:
        print(
            f"  {row['case_id']} pairJ={row['pairwise_jaccard']:.3f} "
            f"unique_sets={row['unique_sets']} sets={row['sets']}"
        )

    print("\nWrote:")
    print(f"  {out_dir / f'compressed_rulebook_reproducibility_{args.suffix}.csv'}")
    print(f"  {out_dir / f'compressed_rulebook_case_metrics_{args.suffix}.csv'}")
    print(f"  {out_dir / f'compressed_rulebook_label_summary_{args.suffix}.csv'}")


if __name__ == "__main__":
    main()
