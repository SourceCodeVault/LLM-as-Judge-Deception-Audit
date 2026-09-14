#!/usr/bin/env python3
"""
Measure entropy of rule citations across reruns.

Per case:
  entropy of the full citation-set state across passes.

Per rule/cluster:
  binary entropy of fired/not-fired across passes within each case, summarized
  over cases. This identifies sensors whose presence/absence flickers.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path

from evaluate_compressed_rulebook import COMPRESSION_SPECS, compress_row, load_incidence


def entropy_from_counts(counts: Counter, normalize_by: float | None = None) -> float:
    total = sum(counts.values())
    if total == 0:
        return 0.0
    h = 0.0
    for count in counts.values():
        if count == 0:
            continue
        p = count / total
        h -= p * math.log2(p)
    if normalize_by and normalize_by > 0:
        return h / normalize_by
    return h


def binary_entropy(k: int, n: int) -> float:
    if n == 0 or k == 0 or k == n:
        return 0.0
    p = k / n
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def set_label(rule_set: frozenset[str]) -> str:
    return " ".join(sorted(rule_set)) if rule_set else "(empty)"


def build_by_case(rows: list[dict[str, str]], spec: dict[str, list[str]]) -> dict[str, list[tuple[str, frozenset[str]]]]:
    by_case: dict[str, list[tuple[str, frozenset[str]]]] = defaultdict(list)
    for row in rows:
        by_case[row["case_id"]].append((row["pass_id"], compress_row(row, spec)))
    for case_id in by_case:
        by_case[case_id].sort(key=lambda item: item[0])
    return dict(sorted(by_case.items()))


def case_entropy_rows(spec_name: str, by_case: dict[str, list[tuple[str, frozenset[str]]]]) -> list[dict]:
    rows = []
    for case_id, observations in by_case.items():
        labels = [rule_set for _, rule_set in observations]
        counts = Counter(labels)
        n = len(labels)
        max_h = math.log2(n) if n > 1 else 0.0
        h = entropy_from_counts(counts)
        rows.append({
            "spec": spec_name,
            "case_id": case_id,
            "passes": n,
            "entropy_bits": h,
            "normalized_entropy": h / max_h if max_h else 0.0,
            "unique_sets": len(counts),
            "modal_count": max(counts.values()) if counts else 0,
            "modal_rate": max(counts.values()) / n if counts else 0.0,
            "state_counts": " | ".join(f"{set_label(state)}:{count}" for state, count in counts.most_common()),
        })
    return rows


def label_entropy_rows(spec_name: str, spec: dict[str, list[str]], by_case: dict[str, list[tuple[str, frozenset[str]]]]) -> list[dict]:
    rows = []
    for label in spec:
        entropies_all = []
        entropies_seen = []
        seen_cases = 0
        unanimous_seen = 0
        flicker_seen = 0
        count_hist = Counter()
        for _, observations in by_case.items():
            n = len(observations)
            fired = sum(1 for _, rule_set in observations if label in rule_set)
            h = binary_entropy(fired, n)
            entropies_all.append(h)
            if fired > 0:
                seen_cases += 1
                count_hist[fired] += 1
                entropies_seen.append(h)
                if fired == n:
                    unanimous_seen += 1
                else:
                    flicker_seen += 1
        rows.append({
            "spec": spec_name,
            "label": label,
            "members": " ".join(spec[label]),
            "cases": len(by_case),
            "seen_cases": seen_cases,
            "seen_case_rate": seen_cases / len(by_case) if by_case else 0.0,
            "mean_entropy_all_cases": sum(entropies_all) / len(entropies_all) if entropies_all else 0.0,
            "mean_entropy_seen_cases": sum(entropies_seen) / len(entropies_seen) if entropies_seen else 0.0,
            "unanimous_given_seen": unanimous_seen / seen_cases if seen_cases else 0.0,
            "flicker_given_seen": flicker_seen / seen_cases if seen_cases else 0.0,
            "hist_fired_passes": " ".join(f"{count}:{count_hist[count]}" for count in sorted(count_hist)),
        })
    return rows


def summarize_case_entropy(case_rows: list[dict]) -> list[dict]:
    by_spec: dict[str, list[dict]] = defaultdict(list)
    for row in case_rows:
        by_spec[row["spec"]].append(row)
    summaries = []
    for spec, rows in sorted(by_spec.items()):
        ent = [float(row["entropy_bits"]) for row in rows]
        norm = [float(row["normalized_entropy"]) for row in rows]
        uniq = [int(row["unique_sets"]) for row in rows]
        summaries.append({
            "spec": spec,
            "cases": len(rows),
            "mean_entropy_bits": sum(ent) / len(ent) if ent else 0.0,
            "median_entropy_bits": sorted(ent)[len(ent) // 2] if ent else 0.0,
            "mean_normalized_entropy": sum(norm) / len(norm) if norm else 0.0,
            "mean_unique_sets": sum(uniq) / len(uniq) if uniq else 0.0,
            "zero_entropy_cases": sum(1 for value in ent if value == 0.0),
            "zero_entropy_case_rate": sum(1 for value in ent if value == 0.0) / len(ent) if ent else 0.0,
            "max_entropy_bits": max(ent) if ent else 0.0,
        })
    return summaries


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
    # Case entropy treats each full citation set as a state; label entropy
    # treats each rule/cluster as a binary sensor across reruns.
    parser.add_argument("--incidence", default="data/rule_incidence_reruns.csv")
    parser.add_argument("--out-dir", default="results/entropy")
    parser.add_argument("--suffix", default="reruns")
    parser.add_argument("--specs", nargs="*", default=["original", "natural_tight", "j_only", "j_all", "broad_clusters"])
    parser.add_argument("--top", type=int, default=12)
    args = parser.parse_args()

    rows, rules = load_incidence(Path(args.incidence))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_case_rows = []
    all_label_rows = []
    for spec_name in args.specs:
        spec = COMPRESSION_SPECS[spec_name]
        missing = sorted({member for members in spec.values() for member in members} - set(rules))
        if missing:
            raise ValueError(f"{spec_name} references missing rules: {missing}")
        by_case = build_by_case(rows, spec)
        all_case_rows.extend(case_entropy_rows(spec_name, by_case))
        all_label_rows.extend(label_entropy_rows(spec_name, spec, by_case))

    case_summary = summarize_case_entropy(all_case_rows)
    write_dicts(out_dir / f"case_entropy_summary_{args.suffix}.csv", case_summary)
    write_dicts(out_dir / f"case_entropy_{args.suffix}.csv", all_case_rows)
    write_dicts(out_dir / f"label_entropy_{args.suffix}.csv", all_label_rows)

    print(f"Incidence: {args.incidence}")
    print(f"Rows: {len(rows)}")
    print("\nCase citation-set entropy summary:")
    for row in case_summary:
        print(
            f"  {row['spec']:<15} mean_H={row['mean_entropy_bits']:.3f} bits "
            f"norm_H={row['mean_normalized_entropy']:.3f} "
            f"unique_sets={row['mean_unique_sets']:.3f} "
            f"zero_cases={row['zero_entropy_cases']}/{row['cases']} ({row['zero_entropy_case_rate']:.3f})"
        )

    print("\nHighest mean binary entropy among labels/clusters, conditional on being seen:")
    seen_rows = [row for row in all_label_rows if row["seen_cases"] > 0]
    seen_rows.sort(key=lambda row: (row["mean_entropy_seen_cases"], row["seen_cases"]), reverse=True)
    for row in seen_rows[: args.top]:
        print(
            f"  {row['spec']:<15} {row['label']:<10} "
            f"seen={row['seen_cases']:>3} "
            f"H_seen={row['mean_entropy_seen_cases']:.3f} "
            f"H_all={row['mean_entropy_all_cases']:.3f} "
            f"flicker={row['flicker_given_seen']:.3f} "
            f"hist={row['hist_fired_passes']}"
        )

    print("\nHighest-entropy cases under original rulebook:")
    original_cases = [row for row in all_case_rows if row["spec"] == "original"]
    original_cases.sort(key=lambda row: (row["entropy_bits"], row["unique_sets"]), reverse=True)
    for row in original_cases[: args.top]:
        print(
            f"  {row['case_id']} H={row['entropy_bits']:.3f} "
            f"norm={row['normalized_entropy']:.3f} unique={row['unique_sets']} "
            f"states={row['state_counts']}"
        )

    print("\nWrote:")
    print(f"  {out_dir / f'case_entropy_summary_{args.suffix}.csv'}")
    print(f"  {out_dir / f'case_entropy_{args.suffix}.csv'}")
    print(f"  {out_dir / f'label_entropy_{args.suffix}.csv'}")


if __name__ == "__main__":
    main()
