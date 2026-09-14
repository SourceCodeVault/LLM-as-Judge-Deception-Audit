#!/usr/bin/env python3
"""
Compare rules by case-level stability profiles.

Input is a pass-level incidence CSV, usually rule_incidence_reruns.csv.
For each case and rule:

    fire_rate(rule, case) = fired_passes / observed_passes

Then each rule is represented as a continuous vector across cases and compared
with other rules by correlation and distance.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import numpy as np


META_COLUMNS = {"case_id", "pass_id", "ground_truth", "verdict", "quadrant", "source_path"}


def load_incidence(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    rules = [name for name in fieldnames if name not in META_COLUMNS]
    return rows, rules


def average_ranks(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    sorted_values = values[order]
    i = 0
    while i < len(values):
        j = i + 1
        while j < len(values) and sorted_values[j] == sorted_values[i]:
            j += 1
        avg_rank = (i + j - 1) / 2.0 + 1.0
        ranks[order[i:j]] = avg_rank
        i = j
    return ranks


def corr(x: np.ndarray, y: np.ndarray) -> float:
    sx = float(np.std(x))
    sy = float(np.std(y))
    if sx < 1e-12 or sy < 1e-12:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def cosine(x: np.ndarray, y: np.ndarray) -> float:
    denom = float(np.linalg.norm(x) * np.linalg.norm(y))
    return float(np.dot(x, y) / denom) if denom else 0.0


def profile_score(pearson: float, mae: float) -> float:
    # Heuristic screen: high positive correlation and small absolute difference.
    return pearson * (1.0 - mae)


def build_fire_rates(rows: list[dict[str, str]], rules: list[str]) -> tuple[list[str], dict[str, dict[str, float]], dict[str, int]]:
    totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    pass_counts: dict[str, int] = defaultdict(int)
    for row in rows:
        case_id = row["case_id"]
        pass_counts[case_id] += 1
        for rule in rules:
            totals[case_id][rule] += int(row[rule])

    case_ids = sorted(pass_counts)
    rates = {
        case_id: {rule: totals[case_id][rule] / pass_counts[case_id] for rule in rules}
        for case_id in case_ids
    }
    return case_ids, rates, dict(pass_counts)


def write_fire_rates(
    path: Path,
    case_ids: list[str],
    rates: dict[str, dict[str, float]],
    pass_counts: dict[str, int],
    rules: list[str],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case_id", "observed_passes", *rules])
        for case_id in case_ids:
            writer.writerow([case_id, pass_counts[case_id], *[f"{rates[case_id][rule]:.10g}" for rule in rules]])


def write_dicts(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def pairwise_profiles(case_ids: list[str], rates: dict[str, dict[str, float]], rules: list[str]) -> list[dict]:
    vectors = {rule: np.array([rates[case_id][rule] for case_id in case_ids], dtype=float) for rule in rules}
    rows = []
    for i, rule_a in enumerate(rules):
        for rule_b in rules[i + 1:]:
            a = vectors[rule_a]
            b = vectors[rule_b]
            diff = a - b
            pearson = corr(a, b)
            spearman = corr(average_ranks(a), average_ranks(b))
            mae = float(np.mean(np.abs(diff)))
            rmse = float(math.sqrt(np.mean(diff * diff)))
            max_abs = float(np.max(np.abs(diff)))
            exact_cases = int(np.sum(np.abs(diff) < 1e-12))
            near_20pp = int(np.sum(np.abs(diff) <= 0.2))
            near_40pp = int(np.sum(np.abs(diff) <= 0.4))
            both_variable = int(np.sum((a > 0) & (a < 1) & (b > 0) & (b < 1)))
            active_a = int(np.sum(a > 0))
            active_b = int(np.sum(b > 0))
            both_active = int(np.sum((a > 0) & (b > 0)))
            rows.append({
                "rule_a": rule_a,
                "rule_b": rule_b,
                "cases": len(case_ids),
                "active_cases_a": active_a,
                "active_cases_b": active_b,
                "both_active_cases": both_active,
                "mean_a": float(np.mean(a)),
                "mean_b": float(np.mean(b)),
                "prevalence_gap": abs(float(np.mean(a) - np.mean(b))),
                "pearson": pearson,
                "spearman": spearman,
                "cosine": cosine(a, b),
                "mae": mae,
                "rmse": rmse,
                "max_abs_diff": max_abs,
                "exact_same_cases": exact_cases,
                "exact_same_rate": exact_cases / len(case_ids),
                "within_20pp_cases": near_20pp,
                "within_20pp_rate": near_20pp / len(case_ids),
                "within_40pp_cases": near_40pp,
                "within_40pp_rate": near_40pp / len(case_ids),
                "both_variable_cases": both_variable,
                "profile_score": profile_score(pearson, mae),
            })
    return sorted(rows, key=lambda r: (r["profile_score"], r["pearson"], -r["mae"]), reverse=True)


def directional_profiles(case_ids: list[str], rates: dict[str, dict[str, float]], rules: list[str]) -> list[dict]:
    vectors = {rule: np.array([rates[case_id][rule] for case_id in case_ids], dtype=float) for rule in rules}
    rows = []
    for antecedent in rules:
        a = vectors[antecedent]
        active = a > 0
        active_count = int(np.sum(active))
        if active_count == 0:
            continue
        for consequent in rules:
            if consequent == antecedent:
                continue
            b = vectors[consequent]
            rows.append({
                "antecedent": antecedent,
                "consequent": consequent,
                "antecedent_active_cases": active_count,
                "case_support_confidence": float(np.mean(b[active] > 0)),
                "mean_consequent_rate_when_active": float(np.mean(b[active])),
                "mean_rate_gap_when_active": float(np.mean(np.maximum(a[active] - b[active], 0.0))),
                "cases_with_a_rate_gt_b_rate": int(np.sum(a[active] > b[active])),
                "cases_with_a_rate_le_b_rate": int(np.sum(a[active] <= b[active])),
            })
    return sorted(
        rows,
        key=lambda r: (
            r["case_support_confidence"],
            -r["mean_rate_gap_when_active"],
            r["antecedent_active_cases"],
        ),
        reverse=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    # Start from the pass-level incidence matrix and collapse repeated passes
    # to one fire-rate vector per case.
    parser.add_argument("--incidence", default="data/rule_incidence_reruns.csv")
    parser.add_argument("--out-dir", default="results")
    parser.add_argument("--suffix", default="reruns")
    parser.add_argument("--top", type=int, default=25)
    args = parser.parse_args()

    rows, rules = load_incidence(Path(args.incidence))
    case_ids, rates, pass_counts = build_fire_rates(rows, rules)
    pairwise = pairwise_profiles(case_ids, rates, rules)
    directional = directional_profiles(case_ids, rates, rules)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fire_rate_path = out_dir / f"case_rule_fire_rates_{args.suffix}.csv"
    pairwise_path = out_dir / f"stability_profile_pairs_{args.suffix}.csv"
    directional_path = out_dir / f"stability_profile_implications_{args.suffix}.csv"
    write_fire_rates(fire_rate_path, case_ids, rates, pass_counts, rules)
    write_dicts(pairwise_path, pairwise)
    write_dicts(directional_path, directional)

    print(f"Incidence: {args.incidence}")
    print(f"Cases: {len(case_ids)}")
    print(f"Pass rows: {len(rows)}")
    print(f"Observed passes per case: {dict(sorted({count: list(pass_counts.values()).count(count) for count in set(pass_counts.values())}.items()))}")
    print(f"Rules: {', '.join(rules)}")

    print("\nTop stability-profile matches:")
    for row in pairwise[: args.top]:
        print(
            f"  {row['rule_a']:>3}-{row['rule_b']:<3} "
            f"score={row['profile_score']:.3f} pearson={row['pearson']:.3f} "
            f"spearman={row['spearman']:.3f} mae={row['mae']:.3f} rmse={row['rmse']:.3f} "
            f"same={row['exact_same_rate']:.3f} within20pp={row['within_20pp_rate']:.3f} "
            f"means=({row['mean_a']:.3f},{row['mean_b']:.3f})"
        )

    print("\nTop case-level directional implications:")
    shown = 0
    for row in directional:
        if row["antecedent_active_cases"] < 10:
            continue
        print(
            f"  {row['antecedent']:>3} => {row['consequent']:<3} "
            f"active_cases={row['antecedent_active_cases']} "
            f"case_conf={row['case_support_confidence']:.3f} "
            f"mean_conseq_rate={row['mean_consequent_rate_when_active']:.3f} "
            f"A>B_cases={row['cases_with_a_rate_gt_b_rate']}"
        )
        shown += 1
        if shown >= args.top:
            break

    print("\nWrote:")
    print(f"  {fire_rate_path}")
    print(f"  {pairwise_path}")
    print(f"  {directional_path}")


if __name__ == "__main__":
    main()
