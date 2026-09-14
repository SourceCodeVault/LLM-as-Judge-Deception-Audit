#!/usr/bin/env python3
"""
generate_redundancy_tables.py — Deterministic generation of redundancy-analysis
tables for the supplementary document.

Reads Giorgi's rulebook-redundancy-analysis result CSVs (standard CSV with
header rows) and produces a markdown file containing:

  1. Alpha coefficients by compressed-rulebook spec
  2. Cluster flicker summary for the natural_tight spec

All statistics are verified against expected values from Giorgi's report
(rulebook-redundancy-analysis/README.md, §Step 6 and §Step 8).  If the
cross-checks disagree the script refuses to render (exit 2) unless --force.

Usage (from repo root):
    python paper/supplementary/redundancy_diagnostic_artifacts/generate_redundancy_tables.py

    # with explicit paths:
    python paper/supplementary/redundancy_diagnostic_artifacts/generate_redundancy_tables.py \\
        --alpha-csv rulebook-redundancy-analysis/results/compressed_rulebook/\\\
            compressed_rulebook_alpha_seed_and_reruns_available.csv \\
        --flicker-csv rulebook-redundancy-analysis/results/compressed_rulebook/\\\
            cluster_flicker_summary_reruns.csv

Then validate against source CSVs:
    python paper/supplementary/redundancy_diagnostic_artifacts/validate_redundancy_tables.py
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve default paths relative to this script
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[2]  # .../LLM-as-Judge-Deception-Audit/
assert (_REPO_ROOT / "rulebook-redundancy-analysis").is_dir(), (
    f"Expected repo root at {_REPO_ROOT}, but rulebook-redundancy-analysis/ not found"
)

_DEFAULT_ALPHA = (
    _REPO_ROOT / "rulebook-redundancy-analysis" / "results" / "compressed_rulebook"
    / "compressed_rulebook_alpha_seed_and_reruns_available.csv"
)
_DEFAULT_FLICKER = (
    _REPO_ROOT / "rulebook-redundancy-analysis" / "results" / "compressed_rulebook"
    / "cluster_flicker_summary_reruns.csv"
)
_DEFAULT_OUT = _SCRIPT_DIR / "redundancy_tables.md"

# ---------------------------------------------------------------------------
# Expected values from Giorgi's report — crosscheck anchors
# Source: rulebook-redundancy-analysis/README.md §Step 6 (alpha table)
# ---------------------------------------------------------------------------
EXPECT_ALPHA = {
    "original":       {"labels": 14, "alpha": 0.238},
    "j_only":         {"labels": 11, "alpha": 0.242},
    "natural_tight":  {"labels":  9, "alpha": 0.278},
    "j_all":          {"labels": 10, "alpha": 0.244},
    "broad_clusters": {"labels":  6, "alpha": 0.263},
}
EXPECT_JFAMILY_ALL_ALPHA = 0.128  # Giorgi's reported value (≈0.128)

# Source: rulebook-redundancy-analysis/README.md §Step 8 (flicker table)
EXPECT_FLICKER = {
    "F12":  {"cases_seen": 198, "flicker": 0.030},
    "S1":   {"cases_seen": 115, "flicker": 0.165},
    "J12":  {"cases_seen":  92, "flicker": 0.989},
    "J345": {"cases_seen":  59, "flicker": 0.983},
}

_TOL = 0.002  # absolute tolerance for 3dp comparison

# ---------------------------------------------------------------------------
# CSV parsing — standard CSV with header row (csv.DictReader)
# ---------------------------------------------------------------------------

def parse_csv_records(path: Path) -> list[dict[str, str]]:
    """Parse a standard CSV file with header row into list of dicts."""
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)

# Keep the old name as an alias so the validate script's import still works.
parse_kv_records = parse_csv_records

# ---------------------------------------------------------------------------
# Histogram helpers
# ---------------------------------------------------------------------------

def hist_fires_all_5(hist: str) -> int:
    """Return the '5' bucket from a hist_fired_passes value string."""
    for tok in hist.split():
        k, _, v = tok.partition(":")
        if k == "5":
            return int(v)
    return 0

def hist_sum(hist: str) -> int:
    """Sum of all non-zero histogram buckets."""
    total = 0
    for tok in hist.split():
        _, _, v = tok.partition(":")
        total += int(v)
    return total

# ---------------------------------------------------------------------------
# Cross-check recomputation against known-good values
# ---------------------------------------------------------------------------

def crosscheck_alpha(recs: list[dict[str, str]]) -> list[str]:
    """Verify alpha records against Giorgi's reported values."""
    problems: list[str] = []
    by_spec = {r["spec"]: r for r in recs}
    for spec, exp in EXPECT_ALPHA.items():
        r = by_spec.get(spec)
        if r is None:
            problems.append(f"[alpha] missing expected spec '{spec}'")
            continue
        if abs(float(r["alpha_masi"]) - exp["alpha"]) > _TOL:
            problems.append(
                f"[alpha/{spec}] α={float(r['alpha_masi']):.3f} "
                f"≠ expected {exp['alpha']:.3f}")
        if int(r["labels"]) != exp["labels"]:
            problems.append(
                f"[alpha/{spec}] labels={r['labels']} ≠ expected {exp['labels']}")
    # j_family_all anchor
    jfa = by_spec.get("j_family_all")
    if jfa:
        if abs(float(jfa["alpha_masi"]) - EXPECT_JFAMILY_ALL_ALPHA) > 0.004:
            problems.append(
                f"[alpha/j_family_all] α={float(jfa['alpha_masi']):.3f} "
                f"≠ expected ≈{EXPECT_JFAMILY_ALL_ALPHA:.3f}")
    else:
        problems.append("[alpha] missing spec 'j_family_all' (coarsening rebuttal centrepiece)")
    # All specs should have 297 cases, 6 runs
    for r in recs:
        if int(r.get("cases", 0)) != 297:
            problems.append(f"[alpha/{r['spec']}] cases={r['cases']}, expected 297")
        if int(r.get("runs", 0)) != 6:
            problems.append(f"[alpha/{r['spec']}] runs={r['runs']}, expected 6")
    return problems

def crosscheck_flicker(recs: list[dict[str, str]]) -> list[str]:
    """Verify flicker records against Giorgi's reported values."""
    problems: list[str] = []
    nt = {r["cluster"]: r for r in recs if r["spec"] == "natural_tight"}
    if len(nt) < 8:
        problems.append(
            f"[flicker] natural_tight has {len(nt)} clusters (expected ≥ 8)")
    for cluster, exp in EXPECT_FLICKER.items():
        r = nt.get(cluster)
        if r is None:
            problems.append(f"[flicker] missing expected cluster '{cluster}'")
            continue
        if int(r["cases_seen"]) != exp["cases_seen"]:
            problems.append(
                f"[flicker/{cluster}] cases_seen={r['cases_seen']} "
                f"≠ expected {exp['cases_seen']}")
        if abs(float(r["flicker_given_seen"]) - exp["flicker"]) > _TOL:
            problems.append(
                f"[flicker/{cluster}] flicker={float(r['flicker_given_seen']):.3f} "
                f"≠ expected {exp['flicker']:.3f}")
    # Internal consistency
    for cluster, r in nt.items():
        hsum = hist_sum(r["hist_fired_passes"])
        seen = int(r["cases_seen"])
        if hsum != seen:
            problems.append(
                f"[flicker/{cluster}] histogram sum {hsum} ≠ cases_seen {seen}")
        fa5 = hist_fires_all_5(r["hist_fired_passes"])
        ua = int(r["unanimous_cases"])
        if fa5 != ua:
            problems.append(
                f"[flicker/{cluster}] fires-all-5={fa5} ≠ unanimous_cases={ua}")
    return problems

# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def fmt3(x: float) -> str:
    """Three-decimal-place string for fractions."""
    return f"{x:.3f}"

# ---------------------------------------------------------------------------
# Table renderers
# ---------------------------------------------------------------------------

ALPHA_HEADER = (
    "| Spec | Labels | Cases | Runs | α (MASI) | Obs. Disagreement | Exp. Disagreement |"
)
ALPHA_SEP = (
    "|------|--------|-------|------|----------|-------------------|-------------------|"
)

FLICKER_HEADER = (
    "| Cluster | Members | Cases Seen | Fires All 5 | Flicker Rate | "
    "Mean Fire Rate When Seen |"
)
FLICKER_SEP = (
    "|---------|---------|------------|-------------|--------------|"
    "--------------------------|"
)

_ALPHA_BOLD = {"natural_tight", "j_family_all"}

def render_alpha_table(recs: list[dict[str, str]]) -> str:
    """Emit the alpha coefficients table as GFM markdown."""
    lines = [ALPHA_HEADER, ALPHA_SEP]
    for r in recs:
        spec = r["spec"]
        lab = int(r["labels"])
        cas = int(r["cases"])
        run = int(r["runs"])
        a = float(r["alpha_masi"])
        od = float(r["observed_disagreement"])
        ed = float(r["expected_disagreement"])
        if spec in _ALPHA_BOLD:
            lines.append(
                f"| **{spec}** | **{lab}** | {cas} | {run} | "
                f"**{fmt3(a)}** | **{fmt3(od)}** | **{fmt3(ed)}** |"
            )
        else:
            lines.append(
                f"| {spec} | {lab} | {cas} | {run} | "
                f"{fmt3(a)} | {fmt3(od)} | {fmt3(ed)} |"
            )
    return "\n".join(lines)

def render_flicker_table(recs: list[dict[str, str]]) -> str:
    """Emit the cluster flicker table as GFM markdown (natural_tight only)."""
    nt = [r for r in recs if r["spec"] == "natural_tight"]
    lines = [FLICKER_HEADER, FLICKER_SEP]
    for r in nt:
        cluster = r["cluster"]
        members = r["members"]
        seen = int(r["cases_seen"])
        fa5 = hist_fires_all_5(r["hist_fired_passes"])
        fr = float(r["flicker_given_seen"])
        mf = float(r["mean_fire_rate_given_seen"])
        lines.append(
            f"| {cluster} | {members} | {seen} | {fa5} | "
            f"{fmt3(fr)} | {fmt3(mf)} |"
        )
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument(
        "--alpha-csv", type=Path, default=_DEFAULT_ALPHA,
        help="Path to compressed_rulebook_alpha_seed_and_reruns_available.csv",
    )
    ap.add_argument(
        "--flicker-csv", type=Path, default=_DEFAULT_FLICKER,
        help="Path to cluster_flicker_summary_reruns.csv",
    )
    ap.add_argument(
        "--out", type=Path, default=_DEFAULT_OUT,
        help="Output .md path (default: sibling redundancy_tables.md)",
    )
    ap.add_argument(
        "--force", action="store_true",
        help="Render even if cross-checks fail",
    )
    args = ap.parse_args()

    # ── Parse ──────────────────────────────────────────────────────────
    alpha_recs = parse_csv_records(args.alpha_csv)
    flicker_recs = parse_csv_records(args.flicker_csv)

    print(f"  parsed {len(alpha_recs)} alpha records from {args.alpha_csv.name}")
    print(f"  parsed {len(flicker_recs)} flicker records from {args.flicker_csv.name}")

    # ── Cross-check ────────────────────────────────────────────────────
    problems = crosscheck_alpha(alpha_recs) + crosscheck_flicker(flicker_recs)
    if problems:
        print("✗ Cross-check failures:", file=sys.stderr)
        for p in problems:
            print(f"   - {p}", file=sys.stderr)
        if not args.force:
            print("Refusing to render (use --force to override).", file=sys.stderr)
            return 2

    # ── Render ─────────────────────────────────────────────────────────
    src = [args.alpha_csv.name, args.flicker_csv.name]
    parts = [
        f"<!-- GENERATED by paper/supplementary/redundancy_diagnostic_artifacts/"
        f"generate_redundancy_tables.py from {', '.join(src)}. "
        f"Do not hand-edit numeric cells. -->",
        "",
        "## Table 1: Alpha Coefficients by Compressed Rulebook Spec",
        "",
        render_alpha_table(alpha_recs),
        "",
        "*Computed on the k=6 frame (297 cases: seed + 5 reruns).*",
        "",
        "## Table 2: Cluster Flicker Summary (natural_tight spec)",
        "",
        render_flicker_table(flicker_recs),
        "",
        "*Computed on the k=5 frame (296 complete cases: reruns only).*",
        "",
    ]
    text = "\n".join(parts)

    # ── Write ──────────────────────────────────────────────────────────
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"✅ Tables written: {args.out}")

    # ── Spot values ────────────────────────────────────────────────────
    by_spec_alpha = {r["spec"]: r for r in alpha_recs}
    nt_a = by_spec_alpha.get("natural_tight", {})
    jfa = by_spec_alpha.get("j_family_all", {})
    nt_flicker = [r for r in flicker_recs if r["spec"] == "natural_tight"]
    if nt_a:
        print(f"  natural_tight  α = {float(nt_a['alpha_masi']):.6f}  (Giorgi: 0.278)")
    if jfa:
        print(f"  j_family_all   α = {float(jfa['alpha_masi']):.6f}  (Giorgi: ≈0.128)")
    print(f"  flicker rows     = {len(nt_flicker)} clusters (natural_tight)")

    if problems:
        print(
            "⚠️  Rendered with --force despite cross-check failures.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())