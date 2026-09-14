#!/usr/bin/env python3
"""
Cluster rules from rule-rule distance matrices.

Two distances are supported:
  1. Pass-level Jaccard distance: 1 - Jaccard(binary fired rows)
  2. Case-level profile distance: 1 - corr(case fire-rate vectors)

The clustering is average-linkage agglomerative clustering implemented directly
to avoid extra dependencies.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import numpy as np


INCIDENCE_META = {"case_id", "pass_id", "ground_truth", "verdict", "quadrant", "source_path"}
FIRE_RATE_META = {"case_id", "observed_passes"}


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = reader.fieldnames or []
    return rows, fields


def load_binary_matrix(path: Path) -> tuple[list[str], np.ndarray]:
    rows, fields = read_csv(path)
    rules = [field for field in fields if field not in INCIDENCE_META]
    matrix = np.array([[int(row[rule]) for rule in rules] for row in rows], dtype=float)
    return rules, matrix


def load_fire_rate_matrix(path: Path) -> tuple[list[str], np.ndarray]:
    rows, fields = read_csv(path)
    rules = [field for field in fields if field not in FIRE_RATE_META]
    matrix = np.array([[float(row[rule]) for rule in rules] for row in rows], dtype=float)
    return rules, matrix


def jaccard_distance_matrix(rules: list[str], matrix: np.ndarray) -> np.ndarray:
    n_rules = len(rules)
    distances = np.zeros((n_rules, n_rules), dtype=float)
    for i in range(n_rules):
        a = matrix[:, i] > 0
        for j in range(i + 1, n_rules):
            b = matrix[:, j] > 0
            union = int(np.sum(a | b))
            inter = int(np.sum(a & b))
            distance = 1.0 - (inter / union if union else 1.0)
            distances[i, j] = distance
            distances[j, i] = distance
    return distances


def corr_distance_matrix(rules: list[str], matrix: np.ndarray) -> np.ndarray:
    n_rules = len(rules)
    distances = np.zeros((n_rules, n_rules), dtype=float)
    for i in range(n_rules):
        a = matrix[:, i]
        for j in range(i + 1, n_rules):
            b = matrix[:, j]
            if float(np.std(a)) < 1e-12 or float(np.std(b)) < 1e-12:
                corr = 0.0
            else:
                corr = float(np.corrcoef(a, b)[0, 1])
            distance = 1.0 - corr
            distances[i, j] = distance
            distances[j, i] = distance
    return distances


def write_matrix(path: Path, labels: list[str], matrix: np.ndarray) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["rule", *labels])
        for label, row in zip(labels, matrix):
            writer.writerow([label, *[f"{value:.10g}" for value in row]])


def write_long_distances(path: Path, labels: list[str], matrix: np.ndarray) -> None:
    rows = []
    for i, a in enumerate(labels):
        for j in range(i + 1, len(labels)):
            b = labels[j]
            distance = float(matrix[i, j])
            rows.append({
                "rule_a": a,
                "rule_b": b,
                "distance": distance,
                "similarity": 1.0 - distance,
            })
    rows.sort(key=lambda row: row["distance"])
    write_dicts(path, rows)


def average_linkage(labels: list[str], matrix: np.ndarray) -> list[dict]:
    clusters: dict[str, set[int]] = {label: {i} for i, label in enumerate(labels)}
    merge_rows = []
    next_id = 1

    while len(clusters) > 1:
        names = sorted(clusters)
        best_pair: tuple[str, str] | None = None
        best_distance = float("inf")
        for i, left in enumerate(names):
            for right in names[i + 1:]:
                distances = [
                    float(matrix[a, b])
                    for a in clusters[left]
                    for b in clusters[right]
                ]
                distance = sum(distances) / len(distances)
                if distance < best_distance - 1e-12:
                    best_distance = distance
                    best_pair = (left, right)

        if best_pair is None:
            break
        left, right = best_pair
        members = clusters[left] | clusters[right]
        new_name = f"C{next_id:02d}"
        next_id += 1
        merge_rows.append({
            "step": len(merge_rows) + 1,
            "cluster": new_name,
            "left": left,
            "right": right,
            "distance": best_distance,
            "similarity": 1.0 - best_distance,
            "size": len(members),
            "members": " ".join(labels[i] for i in sorted(members)),
        })
        del clusters[left]
        del clusters[right]
        clusters[new_name] = members

    return merge_rows


def cut_average_linkage(labels: list[str], matrix: np.ndarray, threshold: float) -> list[list[str]]:
    clusters: dict[str, set[int]] = {label: {i} for i, label in enumerate(labels)}
    next_id = 1

    while True:
        names = sorted(clusters)
        best_pair: tuple[str, str] | None = None
        best_distance = float("inf")
        for i, left in enumerate(names):
            for right in names[i + 1:]:
                distances = [
                    float(matrix[a, b])
                    for a in clusters[left]
                    for b in clusters[right]
                ]
                distance = sum(distances) / len(distances)
                if distance < best_distance - 1e-12:
                    best_distance = distance
                    best_pair = (left, right)
        if best_pair is None or best_distance > threshold:
            break
        left, right = best_pair
        members = clusters[left] | clusters[right]
        del clusters[left]
        del clusters[right]
        clusters[f"C{next_id:02d}"] = members
        next_id += 1

    result = [[" ".join(labels[i] for i in sorted(members)), len(members)] for members in clusters.values()]
    result.sort(key=lambda item: (-item[1], item[0]))
    return [item[0].split() for item in result]


def write_dicts(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_clusters(path: Path, metric: str, labels: list[str], matrix: np.ndarray, thresholds: list[float]) -> list[dict]:
    rows = []
    for threshold in thresholds:
        clusters = cut_average_linkage(labels, matrix, threshold)
        for idx, members in enumerate(clusters, start=1):
            rows.append({
                "metric": metric,
                "threshold": threshold,
                "cluster_id": idx,
                "size": len(members),
                "members": " ".join(members),
            })
    write_dicts(path, rows)
    return rows


def support_summary(rules: list[str], binary_matrix: np.ndarray, fire_rate_matrix: np.ndarray) -> list[dict]:
    rows = []
    for idx, rule in enumerate(rules):
        rows.append({
            "rule": rule,
            "pass_support": int(np.sum(binary_matrix[:, idx])),
            "pass_prevalence": float(np.mean(binary_matrix[:, idx])),
            "active_cases": int(np.sum(fire_rate_matrix[:, idx] > 0)),
            "mean_case_fire_rate": float(np.mean(fire_rate_matrix[:, idx])),
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    # Jaccard distances use pass-level binary rows; correlation distances use
    # case-level fire rates generated by analyze_rule_stability_profiles.py.
    parser.add_argument("--incidence", default="data/rule_incidence_reruns.csv")
    parser.add_argument("--fire-rates", default="results/case_rule_fire_rates_reruns.csv")
    parser.add_argument("--out-dir", default="results/clusters")
    parser.add_argument("--suffix", default="reruns")
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    incidence_rules, binary = load_binary_matrix(Path(args.incidence))
    rate_rules, fire_rates = load_fire_rate_matrix(Path(args.fire_rates))
    if incidence_rules != rate_rules:
        raise ValueError("Rule columns differ between incidence and fire-rate files")

    rules = incidence_rules
    jaccard = jaccard_distance_matrix(rules, binary)
    corr_dist = corr_distance_matrix(rules, fire_rates)
    jaccard_linkage = average_linkage(rules, jaccard)
    corr_linkage = average_linkage(rules, corr_dist)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    write_matrix(out_dir / f"rule_distance_jaccard_{args.suffix}.csv", rules, jaccard)
    write_matrix(out_dir / f"rule_distance_fire_rate_corr_{args.suffix}.csv", rules, corr_dist)
    write_long_distances(out_dir / f"rule_distance_jaccard_long_{args.suffix}.csv", rules, jaccard)
    write_long_distances(out_dir / f"rule_distance_fire_rate_corr_long_{args.suffix}.csv", rules, corr_dist)
    write_dicts(out_dir / f"rule_cluster_linkage_jaccard_{args.suffix}.csv", jaccard_linkage)
    write_dicts(out_dir / f"rule_cluster_linkage_fire_rate_corr_{args.suffix}.csv", corr_linkage)
    write_clusters(
        out_dir / f"rule_clusters_jaccard_{args.suffix}.csv",
        "jaccard",
        rules,
        jaccard,
        [0.15, 0.25, 0.35, 0.50, 0.70],
    )
    write_clusters(
        out_dir / f"rule_clusters_fire_rate_corr_{args.suffix}.csv",
        "fire_rate_corr",
        rules,
        corr_dist,
        [0.05, 0.10, 0.20, 0.35, 0.50],
    )
    write_dicts(out_dir / f"rule_cluster_support_{args.suffix}.csv", support_summary(rules, binary, fire_rates))

    print(f"Incidence: {args.incidence}")
    print(f"Fire rates: {args.fire_rates}")
    print(f"Rules: {', '.join(rules)}")

    print("\nClosest pass-level Jaccard pairs:")
    long_j = []
    for i, a in enumerate(rules):
        for j in range(i + 1, len(rules)):
            long_j.append((float(jaccard[i, j]), a, rules[j]))
    for distance, a, b in sorted(long_j)[: args.top]:
        print(f"  {a:>3}-{b:<3} distance={distance:.3f} jaccard={1 - distance:.3f}")

    print("\nClosest case-level fire-rate correlation pairs:")
    long_c = []
    for i, a in enumerate(rules):
        for j in range(i + 1, len(rules)):
            long_c.append((float(corr_dist[i, j]), a, rules[j]))
    for distance, a, b in sorted(long_c)[: args.top]:
        print(f"  {a:>3}-{b:<3} distance={distance:.3f} corr={1 - distance:.3f}")

    print("\nAverage-linkage merge order, Jaccard:")
    for row in jaccard_linkage[: args.top]:
        print(
            f"  step {row['step']:>2}: {row['cluster']} = ({row['left']}) + ({row['right']}) "
            f"distance={row['distance']:.3f} members={row['members']}"
        )

    print("\nAverage-linkage merge order, fire-rate corr:")
    for row in corr_linkage[: args.top]:
        print(
            f"  step {row['step']:>2}: {row['cluster']} = ({row['left']}) + ({row['right']}) "
            f"distance={row['distance']:.3f} members={row['members']}"
        )

    print("\nWrote files under:")
    print(f"  {out_dir}")


if __name__ == "__main__":
    main()
