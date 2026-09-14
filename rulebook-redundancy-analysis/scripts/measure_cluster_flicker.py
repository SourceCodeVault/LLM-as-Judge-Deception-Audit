#!/usr/bin/env python3
"""
Measure cluster-level presence/absence flicker across reruns.

Question:
  When any member of a cluster fires in a case, how often does the compressed
  cluster fire in all reruns?

This diagnoses whether clustering solves label-substitution instability or
whether the whole concept-family still flickers on/off.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

from evaluate_compressed_rulebook import COMPRESSION_SPECS, compress_row, load_incidence


def build_case_cluster_counts(
    rows: list[dict[str, str]],
    spec: dict[str, list[str]],
) -> tuple[dict[str, Counter], dict[str, int]]:
    counts: dict[str, Counter] = defaultdict(Counter)
    pass_counts: dict[str, int] = Counter()
    for row in rows:
        case_id = row["case_id"]
        pass_counts[case_id] += 1
        fired = compress_row(row, spec)
        for label in fired:
            counts[case_id][label] += 1
    return counts, pass_counts


def summarize_cluster_flicker(
    rows: list[dict[str, str]],
    spec_name: str,
    spec: dict[str, list[str]],
) -> tuple[list[dict], list[dict]]:
    counts, pass_counts = build_case_cluster_counts(rows, spec)
    labels = list(spec)
    summary_rows = []
    case_rows = []

    for label in labels:
        seen_cases = 0
        unanimous_cases = 0
        flicker_cases = 0
        count_hist = Counter()
        active_rates = []

        for case_id in sorted(pass_counts):
            n_passes = pass_counts[case_id]
            fired_count = counts[case_id][label]
            if fired_count == 0:
                continue
            seen_cases += 1
            count_hist[fired_count] += 1
            active_rates.append(fired_count / n_passes)
            if fired_count == n_passes:
                unanimous_cases += 1
                status = "unanimous"
            else:
                flicker_cases += 1
                status = "flickering"
            case_rows.append({
                "spec": spec_name,
                "cluster": label,
                "members": " ".join(spec[label]),
                "case_id": case_id,
                "passes": n_passes,
                "fired_passes": fired_count,
                "fire_rate": fired_count / n_passes,
                "status": status,
            })

        summary_rows.append({
            "spec": spec_name,
            "cluster": label,
            "members": " ".join(spec[label]),
            "cases_seen": seen_cases,
            "unanimous_cases": unanimous_cases,
            "flicker_cases": flicker_cases,
            "unanimous_given_seen": unanimous_cases / seen_cases if seen_cases else 0.0,
            "flicker_given_seen": flicker_cases / seen_cases if seen_cases else 0.0,
            "mean_fire_rate_given_seen": sum(active_rates) / len(active_rates) if active_rates else 0.0,
            "hist_fired_passes": " ".join(f"{count}:{count_hist[count]}" for count in sorted(count_hist)),
        })

    return summary_rows, case_rows


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
    # Counts whether each compressed cluster appears in 1, 2, ..., all reruns
    # after appearing at least once for a case.
    parser.add_argument("--incidence", default="data/rule_incidence_reruns.csv")
    parser.add_argument("--out-dir", default="results/compressed_rulebook")
    parser.add_argument("--suffix", default="reruns")
    parser.add_argument("--specs", nargs="*", default=["natural_tight", "j_only", "j_all", "broad_clusters"])
    parser.add_argument("--top-cases", type=int, default=8)
    args = parser.parse_args()

    rows, rules = load_incidence(Path(args.incidence))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_summary = []
    all_cases = []
    for spec_name in args.specs:
        spec = COMPRESSION_SPECS[spec_name]
        missing = sorted({member for members in spec.values() for member in members} - set(rules))
        if missing:
            raise ValueError(f"{spec_name} references missing rules: {missing}")
        summary, case_rows = summarize_cluster_flicker(rows, spec_name, spec)
        all_summary.extend(summary)
        all_cases.extend(case_rows)

    summary_path = out_dir / f"cluster_flicker_summary_{args.suffix}.csv"
    cases_path = out_dir / f"cluster_flicker_cases_{args.suffix}.csv"
    write_dicts(summary_path, all_summary)
    write_dicts(cases_path, all_cases)

    print(f"Incidence: {args.incidence}")
    print(f"Rows: {len(rows)}")
    print("\nCluster-level on/off stability, conditional on cluster appearing at least once:")
    for row in sorted(all_summary, key=lambda r: (r["spec"], -r["cases_seen"], r["cluster"])):
        if row["cases_seen"] == 0:
            continue
        print(
            f"  {row['spec']:<15} {row['cluster']:<10} "
            f"seen={row['cases_seen']:>3} "
            f"all_passes={row['unanimous_cases']:>3} ({row['unanimous_given_seen']:.3f}) "
            f"flicker={row['flicker_cases']:>3} ({row['flicker_given_seen']:.3f}) "
            f"mean_rate={row['mean_fire_rate_given_seen']:.3f} "
            f"hist={row['hist_fired_passes']}"
        )

    print("\nMost unstable cluster-case examples:")
    flickers = [row for row in all_cases if row["status"] == "flickering"]
    flickers.sort(key=lambda r: (r["fire_rate"], r["spec"], r["cluster"], r["case_id"]))
    for row in flickers[: args.top_cases]:
        print(
            f"  {row['spec']:<15} {row['cluster']:<10} "
            f"case={row['case_id']} fired={row['fired_passes']}/{row['passes']} "
            f"members={row['members']}"
        )

    print("\nWrote:")
    print(f"  {summary_path}")
    print(f"  {cases_path}")


if __name__ == "__main__":
    main()
