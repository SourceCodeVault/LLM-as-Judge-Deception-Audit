#!/usr/bin/env python3
"""
Conditional stability-aware redundancy by verdict, ground truth, and quadrant.

For each stratum, first collapse repeated pass rows to case-level fire rates
within that stratum, then compare rule vectors across cases in the stratum.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from analyze_rule_stability_profiles import (
    META_COLUMNS,
    build_fire_rates,
    directional_profiles,
    pairwise_profiles,
    write_dicts,
    write_fire_rates,
)


def load_incidence(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    rules = [field for field in fieldnames if field not in META_COLUMNS]
    return rows, rules


def safe_name(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in value.strip())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "blank"


def summarize_fire_rates(case_ids: list[str], rates: dict[str, dict[str, float]], rules: list[str]) -> list[dict]:
    rows = []
    for rule in rules:
        values = [rates[case_id][rule] for case_id in case_ids]
        active = [value for value in values if value > 0]
        rows.append({
            "rule": rule,
            "cases": len(case_ids),
            "active_cases": len(active),
            "active_case_rate": len(active) / len(case_ids) if case_ids else 0.0,
            "mean_fire_rate": sum(values) / len(values) if values else 0.0,
            "mean_active_fire_rate": sum(active) / len(active) if active else 0.0,
        })
    return rows


def write_combined(path: Path, rows: list[dict]) -> None:
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


def stratum_values(rows: list[dict[str, str]], column: str) -> list[str]:
    return sorted({row[column] for row in rows if row.get(column)})


def analyze_stratum(
    rows: list[dict[str, str]],
    rules: list[str],
    stratum_type: str,
    stratum_value: str,
    out_dir: Path,
    suffix: str,
    min_cases: int,
) -> tuple[dict | None, list[dict], list[dict]]:
    selected = [row for row in rows if row.get(stratum_type) == stratum_value]
    if not selected:
        return None, [], []

    case_ids, rates, pass_counts = build_fire_rates(selected, rules)
    if len(case_ids) < min_cases:
        return {
            "stratum_type": stratum_type,
            "stratum": stratum_value,
            "cases": len(case_ids),
            "pass_rows": len(selected),
            "status": "skipped_min_cases",
        }, [], []

    pairwise = pairwise_profiles(case_ids, rates, rules)
    directional = directional_profiles(case_ids, rates, rules)
    rule_summary = summarize_fire_rates(case_ids, rates, rules)

    prefix = f"{suffix}_{stratum_type}_{safe_name(stratum_value)}"
    write_fire_rates(out_dir / f"case_rule_fire_rates_{prefix}.csv", case_ids, rates, pass_counts, rules)
    write_dicts(out_dir / f"stability_profile_pairs_{prefix}.csv", pairwise)
    write_dicts(out_dir / f"stability_profile_implications_{prefix}.csv", directional)
    write_dicts(out_dir / f"rule_fire_rate_summary_{prefix}.csv", rule_summary)

    top = pairwise[0] if pairwise else {}
    summary = {
        "stratum_type": stratum_type,
        "stratum": stratum_value,
        "cases": len(case_ids),
        "pass_rows": len(selected),
        "observed_pass_count_pattern": "; ".join(
            f"{count}:{list(pass_counts.values()).count(count)}"
            for count in sorted(set(pass_counts.values()))
        ),
        "status": "ok",
        "top_pair": f"{top.get('rule_a', '')}-{top.get('rule_b', '')}" if top else "",
        "top_profile_score": top.get("profile_score", ""),
        "top_pearson": top.get("pearson", ""),
        "top_spearman": top.get("spearman", ""),
        "top_mae": top.get("mae", ""),
        "top_exact_same_rate": top.get("exact_same_rate", ""),
        "top_within_20pp_rate": top.get("within_20pp_rate", ""),
    }

    pairwise_with_stratum = [
        {"stratum_type": stratum_type, "stratum": stratum_value, **row}
        for row in pairwise
    ]
    directional_with_stratum = [
        {"stratum_type": stratum_type, "stratum": stratum_value, **row}
        for row in directional
    ]
    return summary, pairwise_with_stratum, directional_with_stratum


def main() -> None:
    parser = argparse.ArgumentParser()
    # Each stratum is analyzed from the same incidence matrix, then collapsed
    # to case-level fire rates within that stratum.
    parser.add_argument("--incidence", default="data/rule_incidence_reruns.csv")
    parser.add_argument("--out-dir", default="results/conditional")
    parser.add_argument("--suffix", default="reruns")
    parser.add_argument("--min-cases", type=int, default=20)
    parser.add_argument("--top", type=int, default=8)
    args = parser.parse_args()

    rows, rules = load_incidence(Path(args.incidence))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    strata = []
    for column in ["verdict", "ground_truth", "quadrant"]:
        for value in stratum_values(rows, column):
            strata.append((column, value))

    summaries = []
    all_pairwise = []
    all_directional = []
    for stratum_type, value in strata:
        summary, pairwise, directional = analyze_stratum(
            rows,
            rules,
            stratum_type,
            value,
            out_dir,
            args.suffix,
            args.min_cases,
        )
        if summary:
            summaries.append(summary)
        all_pairwise.extend(pairwise)
        all_directional.extend(directional)

    summary_path = out_dir / f"conditional_redundancy_summary_{args.suffix}.csv"
    pairwise_path = out_dir / f"conditional_stability_profile_pairs_{args.suffix}.csv"
    directional_path = out_dir / f"conditional_stability_profile_implications_{args.suffix}.csv"
    write_combined(summary_path, summaries)
    write_combined(pairwise_path, sorted(all_pairwise, key=lambda r: (r["profile_score"], r["pearson"], -r["mae"]), reverse=True))
    write_combined(
        directional_path,
        sorted(
            all_directional,
            key=lambda r: (
                r["case_support_confidence"],
                -r["mean_rate_gap_when_active"],
                r["antecedent_active_cases"],
            ),
            reverse=True,
        ),
    )

    print(f"Incidence: {args.incidence}")
    print(f"Rows: {len(rows)}")
    print(f"Rules: {', '.join(rules)}")
    print(f"Strata analyzed: {sum(1 for row in summaries if row.get('status') == 'ok')}")
    skipped = [row for row in summaries if row.get("status") != "ok"]
    if skipped:
        print(f"Skipped strata: {len(skipped)} under min_cases={args.min_cases}")

    print("\nTop pair by stratum:")
    for row in summaries:
        if row.get("status") != "ok":
            print(f"  {row['stratum_type']}={row['stratum']}: skipped cases={row['cases']}")
            continue
        print(
            f"  {row['stratum_type']}={row['stratum']:<20} "
            f"cases={row['cases']:>3} rows={row['pass_rows']:>4} "
            f"top={row['top_pair']:<7} pearson={float(row['top_pearson']):.3f} "
            f"mae={float(row['top_mae']):.3f} same={float(row['top_exact_same_rate']):.3f}"
        )

    print("\nTop conditional stability-profile matches overall:")
    for row in sorted(all_pairwise, key=lambda r: (r["profile_score"], r["pearson"], -r["mae"]), reverse=True)[: args.top]:
        print(
            f"  {row['stratum_type']}={row['stratum']:<20} "
            f"{row['rule_a']:>3}-{row['rule_b']:<3} "
            f"score={row['profile_score']:.3f} pearson={row['pearson']:.3f} "
            f"mae={row['mae']:.3f} same={row['exact_same_rate']:.3f} "
            f"within20pp={row['within_20pp_rate']:.3f}"
        )

    print("\nWrote:")
    print(f"  {summary_path}")
    print(f"  {pairwise_path}")
    print(f"  {directional_path}")
    print(f"  per-stratum fire-rate/profile files in {out_dir}")


if __name__ == "__main__":
    main()
