#!/usr/bin/env python3
"""
Build a case-pass rule incidence matrix and run first-pass redundancy checks.

Optional provenance input: the v2 preprint zip containing the seed pass and
5 reruns. The reproducible repo starts from the CSV matrices in data/, so this
script is only needed if you want to rebuild those matrices from raw audit JSON.
Output:
  rule_analysis/rule_incidence.csv
  rule_analysis/pairwise_cofiring.csv
  rule_analysis/rule_implications.csv
  rule_analysis/combination_equivalence.csv

The matrix is binary because current telemetry records citation presence/absence:
case x pass x rule -> fired / not fired.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ZIP = "LLM-as-Judge-Deception-Audit-v2.0-preprint.zip"
ROOT_PREFIX_RE = re.compile(r"^[^/]+/")
RULE_ORDER = ["F1", "F2", "F3", "H1", "J1", "J2", "J3", "J4", "J5", "S1", "U1", "U2", "U3", "U4"]

SEED_DIR = "output/run_20260525_205154_arm04a_testretest_seed_300/"
RERUN_DIR = "output/run_20260525_234223_arm04b_testretest_reruns_x5_300/"


@dataclass(frozen=True)
class Observation:
    case_id: str
    pass_id: str
    source_path: str
    verdict: str
    quadrant: str
    ground_truth: str
    rules: frozenset[str]


def strip_root(path: str) -> str:
    return ROOT_PREFIX_RE.sub("", path, count=1)


def pass_id_from_path(path: str) -> str | None:
    clean = strip_root(path)
    name = Path(path).name
    if clean.startswith(SEED_DIR):
        return "seed_00"
    if clean.startswith(RERUN_DIR):
        match = re.search(r"__rerun_(\d+)\.json$", name)
        if match:
            return f"rerun_{int(match.group(1)):02d}"
    return None


def is_candidate_audit(path: str) -> bool:
    clean = strip_root(path)
    if not path.endswith(".json") or "/audit_" not in path:
        return False
    return clean.startswith(SEED_DIR) or clean.startswith(RERUN_DIR)


def load_observations(zip_path: Path) -> list[Observation]:
    observations: list[Observation] = []
    with zipfile.ZipFile(zip_path) as archive:
        for path in archive.namelist():
            if not is_candidate_audit(path):
                continue
            pass_id = pass_id_from_path(path)
            if pass_id is None:
                continue
            try:
                data = json.loads(archive.read(path))
            except Exception:
                continue

            if data.get("pipeline_status") != "OK":
                continue
            meta = data.get("metadata") or {}
            if meta.get("arm") != "ABLATION_NOISE":
                continue
            gap = data.get("compliance_gap") or {}
            labels = meta.get("apollo_labels") or {}
            is_misaligned = labels.get("is_misaligned")
            ground_truth = "ROGUE" if is_misaligned is True else ("CLEAN" if is_misaligned is False else "UNKNOWN")

            rules = frozenset(r for r in (meta.get("rules_fired") or []) if re.fullmatch(r"[A-Z]\d+", str(r)))
            observations.append(
                Observation(
                    case_id=str(data.get("case_id") or ""),
                    pass_id=pass_id,
                    source_path=strip_root(path),
                    verdict=str(gap.get("auditor_recommended_action") or meta.get("auditor_recommended_action") or ""),
                    quadrant=str(gap.get("quadrant") or ""),
                    ground_truth=ground_truth,
                    rules=rules,
                )
            )
    return observations


def keep_complete_cases(observations: list[Observation], required: set[str]) -> list[Observation]:
    by_case: dict[str, dict[str, Observation]] = defaultdict(dict)
    for obs in observations:
        by_case[obs.case_id][obs.pass_id] = obs
    keep = {case_id for case_id, passes in by_case.items() if required.issubset(set(passes))}
    return sorted(
        (obs for obs in observations if obs.case_id in keep and obs.pass_id in required),
        key=lambda o: (o.case_id, o.pass_id),
    )


def select_passes(observations: list[Observation], required: set[str]) -> list[Observation]:
    return sorted(
        (obs for obs in observations if obs.pass_id in required),
        key=lambda o: (o.case_id, o.pass_id),
    )


def missing_passes(observations: list[Observation], required: set[str]) -> list[tuple[str, list[str], list[str]]]:
    by_case: dict[str, set[str]] = defaultdict(set)
    for obs in observations:
        if obs.pass_id in required:
            by_case[obs.case_id].add(obs.pass_id)
    return [
        (case_id, sorted(required - passes), sorted(passes))
        for case_id, passes in sorted(by_case.items())
        if not required.issubset(passes)
    ]


def write_incidence(observations: list[Observation], rules: list[str], out_path: Path) -> None:
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case_id", "pass_id", "ground_truth", "verdict", "quadrant", "source_path", *rules])
        for obs in observations:
            writer.writerow([
                obs.case_id,
                obs.pass_id,
                obs.ground_truth,
                obs.verdict,
                obs.quadrant,
                obs.source_path,
                *[1 if rule in obs.rules else 0 for rule in rules],
            ])


def phi(n11: int, n10: int, n01: int, n00: int) -> float:
    denom = math.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
    return (n11 * n00 - n10 * n01) / denom if denom else 0.0


def pairwise_stats(observations: list[Observation], rules: list[str]) -> list[dict]:
    rows = []
    n = len(observations)
    rule_sets = {rule: {i for i, obs in enumerate(observations) if rule in obs.rules} for rule in rules}
    for a, b in itertools.combinations(rules, 2):
        set_a, set_b = rule_sets[a], rule_sets[b]
        n11 = len(set_a & set_b)
        n10 = len(set_a - set_b)
        n01 = len(set_b - set_a)
        n00 = n - n11 - n10 - n01
        support_a = len(set_a)
        support_b = len(set_b)
        union = len(set_a | set_b)
        rows.append({
            "rule_a": a,
            "rule_b": b,
            "n": n,
            "n11": n11,
            "support_a": support_a,
            "support_b": support_b,
            "p_a": support_a / n if n else 0.0,
            "p_b": support_b / n if n else 0.0,
            "p_a_given_b": n11 / support_b if support_b else 0.0,
            "p_b_given_a": n11 / support_a if support_a else 0.0,
            "jaccard": n11 / union if union else 0.0,
            "phi": phi(n11, n10, n01, n00),
        })
    return rows


def implication_rows(pairwise: list[dict], min_antecedent: int, threshold: float) -> list[dict]:
    rows = []
    for row in pairwise:
        a, b = row["rule_a"], row["rule_b"]
        if row["support_a"] >= min_antecedent:
            rows.append({
                "antecedent": a,
                "consequent": b,
                "antecedent_support": row["support_a"],
                "cofire": row["n11"],
                "confidence": row["p_b_given_a"],
                "misses": row["support_a"] - row["n11"],
                "meets_threshold": row["p_b_given_a"] >= threshold,
            })
        if row["support_b"] >= min_antecedent:
            rows.append({
                "antecedent": b,
                "consequent": a,
                "antecedent_support": row["support_b"],
                "cofire": row["n11"],
                "confidence": row["p_a_given_b"],
                "misses": row["support_b"] - row["n11"],
                "meets_threshold": row["p_a_given_b"] >= threshold,
            })
    return sorted(rows, key=lambda r: (r["meets_threshold"], r["confidence"], r["antecedent_support"]), reverse=True)


def score_prediction(y: list[int], pred: list[int]) -> dict:
    tp = sum(1 for a, b in zip(y, pred) if a == 1 and b == 1)
    tn = sum(1 for a, b in zip(y, pred) if a == 0 and b == 0)
    fp = sum(1 for a, b in zip(y, pred) if a == 0 and b == 1)
    fn = sum(1 for a, b in zip(y, pred) if a == 1 and b == 0)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracy = (tp + tn) / len(y) if y else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": accuracy,
        "mismatches": fp + fn,
    }


def combination_equivalence(observations: list[Observation], rules: list[str], min_target: int) -> list[dict]:
    vectors = {rule: [1 if rule in obs.rules else 0 for obs in observations] for rule in rules}
    rows = []
    expressions = [
        ("AND", lambda a, b: [x & y for x, y in zip(a, b)]),
        ("OR", lambda a, b: [x | y for x, y in zip(a, b)]),
        ("A_AND_NOT_B", lambda a, b: [x & (1 - y) for x, y in zip(a, b)]),
        ("B_AND_NOT_A", lambda a, b: [y & (1 - x) for x, y in zip(a, b)]),
        ("XOR", lambda a, b: [x ^ y for x, y in zip(a, b)]),
    ]

    for target in rules:
        y = vectors[target]
        target_support = sum(y)
        if target_support < min_target:
            continue
        for a, b in itertools.combinations([r for r in rules if r != target], 2):
            va, vb = vectors[a], vectors[b]
            for op_name, op in expressions:
                pred = op(va, vb)
                pred_support = sum(pred)
                if pred_support == 0:
                    continue
                metrics = score_prediction(y, pred)
                rows.append({
                    "target": target,
                    "expression": f"{a} {op_name} {b}",
                    "target_support": target_support,
                    "predicted_support": pred_support,
                    **metrics,
                })
    return sorted(rows, key=lambda r: (r["f1"], r["accuracy"], -r["mismatches"]), reverse=True)


def write_dicts(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def fmt_pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", default=DEFAULT_ZIP, help="Path to v2 preprint zip")
    parser.add_argument("--out-dir", default="rule_analysis")
    parser.add_argument("--implication-threshold", type=float, default=0.95)
    parser.add_argument("--min-antecedent", type=int, default=30)
    parser.add_argument("--min-target", type=int, default=30)
    parser.add_argument(
        "--passes",
        choices=["reruns", "seed-and-reruns"],
        default="reruns",
        help="Analyze the 5 reruns only, or the common seed+5-rerun panel.",
    )
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    zip_path = Path(args.zip)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    required = {"rerun_01", "rerun_02", "rerun_03", "rerun_04", "rerun_05"}
    if args.passes == "seed-and-reruns":
        required = {"seed_00", *required}
    all_observations = load_observations(zip_path)
    selected_observations = select_passes(all_observations, required)
    observations = keep_complete_cases(all_observations, required)
    observed_rules = sorted({rule for obs in selected_observations for rule in obs.rules}, key=lambda s: (s[0], int(s[1:])))
    rules = [rule for rule in RULE_ORDER if rule in observed_rules] + [rule for rule in observed_rules if rule not in RULE_ORDER]

    suffix = "reruns" if args.passes == "reruns" else "seed_and_reruns"
    incidence_path = out_dir / f"rule_incidence_{suffix}.csv"
    available_incidence_path = out_dir / f"rule_incidence_{suffix}_available.csv"
    pairwise_path = out_dir / f"pairwise_cofiring_{suffix}.csv"
    implications_path = out_dir / f"rule_implications_{suffix}.csv"
    combinations_path = out_dir / f"combination_equivalence_{suffix}.csv"

    write_incidence(selected_observations, rules, available_incidence_path)
    write_incidence(observations, rules, incidence_path)
    pairwise = pairwise_stats(observations, rules)
    implications = implication_rows(pairwise, args.min_antecedent, args.implication_threshold)
    combinations = combination_equivalence(observations, rules, args.min_target)

    write_dicts(pairwise_path, sorted(pairwise, key=lambda r: (r["jaccard"], r["phi"]), reverse=True))
    write_dicts(implications_path, implications)
    write_dicts(combinations_path, combinations)

    case_count = len({obs.case_id for obs in observations})
    available_case_count = len({obs.case_id for obs in selected_observations})
    selected_pass_counts = Counter(obs.pass_id for obs in selected_observations)
    pass_counts = Counter(obs.pass_id for obs in observations)
    rule_counts = Counter(rule for obs in observations for rule in obs.rules)
    missing = missing_passes(selected_observations, required)

    print(f"Panel: {args.passes}")
    print(f"Available cases: {available_case_count}")
    print(f"Available observations: {len(selected_observations)} ({dict(sorted(selected_pass_counts.items()))})")
    print(f"Complete cases: {case_count}")
    print(f"Observations: {len(observations)} ({dict(sorted(pass_counts.items()))})")
    if missing:
        print("Incomplete selected cases:")
        for case_id, missing_pass_ids, present_pass_ids in missing[:10]:
            print(f"  {case_id}: missing {missing_pass_ids}; present {present_pass_ids}")
    print(f"Rules ({len(rules)}): {', '.join(rules)}")
    print("\nRule firing counts:")
    for rule in rules:
        print(f"  {rule:>3}: {rule_counts[rule]:4d} / {len(observations)} = {fmt_pct(rule_counts[rule] / len(observations))}")

    print("\nTop pairwise co-firing by Jaccard (min support >= 30 each):")
    shown = 0
    for row in sorted(pairwise, key=lambda r: (r["jaccard"], r["phi"]), reverse=True):
        if min(row["support_a"], row["support_b"]) < args.min_antecedent:
            continue
        print(
            f"  {row['rule_a']:>3}-{row['rule_b']:<3} "
            f"J={row['jaccard']:.3f} phi={row['phi']:.3f} "
            f"P({row['rule_b']}|{row['rule_a']})={row['p_b_given_a']:.3f} "
            f"P({row['rule_a']}|{row['rule_b']})={row['p_a_given_b']:.3f} "
            f"cofire={row['n11']}"
        )
        shown += 1
        if shown >= args.top:
            break

    print(f"\nRule implications with confidence >= {args.implication_threshold:.2f}:")
    hits = [r for r in implications if r["meets_threshold"]]
    for row in hits[: args.top]:
        print(
            f"  {row['antecedent']:>3} => {row['consequent']:<3} "
            f"confidence={row['confidence']:.3f} "
            f"support={row['antecedent_support']} misses={row['misses']}"
        )
    if not hits:
        print("  none")

    print("\nTop combination equivalence candidates (pairwise Boolean expressions):")
    for row in combinations[: args.top]:
        print(
            f"  {row['target']:>3} ~= {row['expression']:<18} "
            f"F1={row['f1']:.3f} acc={row['accuracy']:.3f} "
            f"precision={row['precision']:.3f} recall={row['recall']:.3f} "
            f"mismatches={row['mismatches']}"
        )

    print("\nWrote:")
    for path in [available_incidence_path, incidence_path, pairwise_path, implications_path, combinations_path]:
        print(f"  {path}")


if __name__ == "__main__":
    main()
