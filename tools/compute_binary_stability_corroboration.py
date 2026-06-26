#!/usr/bin/env python3
"""
compute_binary_stability_corroboration.py — Supplementary corroboration for the
ICC(2,1) test-retest stability result, for the case where the rated quantity is
a *binary* verdict (APPROVE / BLOCK).

WHY THIS EXISTS
---------------
ICC(2,1) on a binary outcome is an unconventional (though conservative)
parameterisation. To corroborate it, this script computes two model-free
agreement statistics over the same k reruns per case:

  * Raw percent agreement, reported two ways:
      - unanimity rate: fraction of cases whose k reruns ALL produced the same
        verdict (the most intuitive "stability under non-determinism" number);
      - mean pairwise agreement: averaged over cases, the fraction of rerun
        PAIRS that agree (this is the observed-agreement term of Fleiss' kappa).
  * Fleiss' kappa: chance-corrected agreement for n >= 2 interchangeable raters
    (reruns are interchangeable — there is no meaningful identity to "rerun 3"
    vs "rerun 5" — so Fleiss is the right generalisation, not an average of
    pairwise Cohen's kappa).

IMPORTANT STATISTICAL CAVEAT (read before writing any paper sentence)
---------------------------------------------------------------------
Kappa suffers the well-known "high agreement, low kappa" paradox
(Feinstein & Cicchetti 1990): when one verdict dominates the marginal, the
chance-agreement term approaches 1 and kappa is deflated or even undefined
(0/0) EVEN WHEN observed agreement is ~100%. If you computed ICC on *correctness*
(~0.99 base rate) rather than the raw verdict (~0.66), expect this. The script
detects the skew and tells you. Do NOT assert that Fleiss' kappa "tightly aligns
with the ICC" until this script prints numbers that actually show it; if the
marginal is skewed, lead with unanimity / percent agreement instead and report
kappa with the paradox noted. --emit-note chooses the wording for you from the
computed result.

INPUT
-----
Point this at the SAME directories you passed to compute_stability.py, so the
verdict set is identical to the one the ICC was computed on. Verdicts are read
via build_dashboard.parse_logs (the canonical pipeline encoding), and reruns of
one case are grouped by their stable source id (provenance_file by default).

Usage (run from tools/, next to build_dashboard.py):
  python tools/compute_binary_stability_corroboration.py \
      --rerun-dir output/<test_retest_rerun_dir> \
      --seed-dir  output/<test_retest_seed_dir> \
      --raters 6 --icc 0.979 --emit-note \
      --out-json stability_corroboration.json

      e.g.
    python tools/compute_binary_stability_corroboration.py \
      --rerun-dir output/run_20260525_234223_arm04b_testretest_reruns_x5_300 \
      --seed-dir  output/run_20260525_205154_arm04a_testretest_seed_300 \
      --raters 6 --icc 0.979 --emit-note \
      --out-json stability_corroboration.json    
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from build_dashboard import parse_logs  # canonical verdict encoding
except ImportError as e:  # pragma: no cover
    sys.stderr.write(
        "ERROR: could not import build_dashboard. Run from the tools/ directory "
        f"that contains build_dashboard.py. ({e})\n"
    )
    raise


# ---------------------------------------------------------------------------
# Metrics  (pure functions, independently testable)
# ---------------------------------------------------------------------------

def fleiss_counts(matrix: list[list[int]]) -> tuple[float, float, float]:
    """Given an N x K matrix of per-case category counts (each row summing to
    the same n raters), return (P_bar, P_e, kappa).

    P_bar = mean observed agreement (mean fraction of agreeing rater pairs)
    P_e   = expected agreement by chance = sum_j p_j^2
    kappa = (P_bar - P_e) / (1 - P_e)   [NaN if P_e == 1]
    """
    N = len(matrix)
    if N == 0:
        return (float("nan"), float("nan"), float("nan"))
    n = sum(matrix[0])
    if n < 2:
        return (float("nan"), float("nan"), float("nan"))

    # Per-case agreement P_i = (sum_j n_ij^2 - n) / (n(n-1))
    P_i = [(sum(c * c for c in row) - n) / (n * (n - 1)) for row in matrix]
    P_bar = sum(P_i) / N

    total = N * n
    col_tot = [sum(row[j] for row in matrix) for j in range(len(matrix[0]))]
    p_j = [c / total for c in col_tot]
    P_e = sum(p * p for p in p_j)

    if math.isclose(P_e, 1.0):
        kappa = float("nan")  # no variance to chance-correct against (paradox)
    else:
        kappa = (P_bar - P_e) / (1 - P_e)
    return (P_bar, P_e, kappa)


def marginals(matrix: list[list[int]], categories: list[str]) -> dict[str, float]:
    total = sum(sum(row) for row in matrix)
    if total == 0:
        return {c: float("nan") for c in categories}
    col_tot = [sum(row[j] for row in matrix) for j in range(len(categories))]
    return {categories[j]: col_tot[j] / total for j in range(len(categories))}


def unanimity_rate(verdicts_by_case: dict[str, list[str]]) -> tuple[int, int]:
    """(n_unanimous, n_cases): cases where every available rerun agreed."""
    n_unan = sum(1 for vs in verdicts_by_case.values() if len(set(vs)) == 1)
    return (n_unan, len(verdicts_by_case))


# ---------------------------------------------------------------------------
# Data assembly  (reuses the pipeline's own parser)
# ---------------------------------------------------------------------------

def gather_audit_files(dirs: list[Path]) -> list[Path]:
    out: set[Path] = set()
    for d in dirs:
        if d is None or not d.exists():
            continue
        for pat in ("audit_*.json", "audit_*.error.json"):
            for f in d.rglob(pat):
                # mirror build_dashboard: skip any folder starting with "_"
                if not any(part.startswith("_")
                           for part in f.relative_to(d).parts[:-1]):
                    out.add(f)
    return sorted(out, key=str)


def build_verdicts(records: list[dict], id_field: str) -> dict[str, list[str]]:
    by_case: dict[str, list[str]] = defaultdict(list)
    for r in records:
        cid = r.get(id_field) or ""
        if not cid:
            continue
        by_case[cid].append(r["l3"])
    return dict(by_case)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run(rerun_dir: Path, seed_dir: Path | None, id_field: str,
        raters: int | None, icc: float | None) -> dict:
    files = gather_audit_files([d for d in (seed_dir, rerun_dir) if d])
    if not files:
        raise SystemExit("No audit_*.json files found under the given directories.")
    records_clean, drops, all_records = parse_logs(files)
    by_case = build_verdicts(records_clean, id_field)

    # Diagnostics: ratings-per-case distribution. For a k=6 test-retest over 300
    # cases this should read ~300 cases at 6 ratings each. Anything like
    # "1800 cases at 1 rating" means the grouping id is per-run, not per-case —
    # rerun with a different --id-field.
    per_case_counts = Counter(len(v) for v in by_case.values())
    variants_seen = Counter(r.get("variant") for r in records_clean)

    # Choose the rater count to lock Fleiss to (equal-n form).
    target_n = raters
    if target_n is None:
        target_n = per_case_counts.most_common(1)[0][0] if per_case_counts else 0

    complete = {c: v for c, v in by_case.items() if len(v) == target_n}
    excluded = {c: v for c, v in by_case.items() if len(v) != target_n}

    categories = sorted({v for vs in by_case.values() for v in vs})
    # Build N x K count matrix on the complete (equal-n) cases.
    cat_index = {c: i for i, c in enumerate(categories)}
    matrix: list[list[int]] = []
    for c, vs in complete.items():
        row = [0] * len(categories)
        for v in vs:
            row[cat_index[v]] += 1
        matrix.append(row)

    P_bar, P_e, kappa = fleiss_counts(matrix) if matrix else (math.nan,) * 3
    marg = marginals(matrix, categories) if matrix else {}
    n_unan_all, n_cases_all = unanimity_rate(by_case)
    n_unan_cmp, n_cases_cmp = unanimity_rate(complete)
    max_marginal = max(marg.values()) if marg else float("nan")

    result = {
        "id_field": id_field,
        "n_audit_files": len(files),
        "n_clean_records": len(records_clean),
        "drops": drops,
        "variants_seen": dict(variants_seen),
        "ratings_per_case_distribution": dict(sorted(per_case_counts.items())),
        "raters_locked_to": target_n,
        "categories": categories,
        "n_cases_total": n_cases_all,
        "n_cases_in_kappa": len(matrix),
        "n_cases_excluded_unequal_n": len(excluded),
        "marginals": marg,
        "max_marginal": max_marginal,
        "skew_warning": bool(marg) and max_marginal > 0.90,
        "fleiss_kappa": kappa,
        "observed_agreement_P_bar": P_bar,
        "expected_agreement_P_e": P_e,
        "unanimity_all_cases": [n_unan_all, n_cases_all],
        "unanimity_all_pct": (100.0 * n_unan_all / n_cases_all) if n_cases_all else float("nan"),
        "unanimity_complete_cases": [n_unan_cmp, n_cases_cmp],
        "icc_reference": icc,
    }
    return result


def emit_note(res: dict) -> str:
    """Paper-ready sentence generated from the result. Wording is chosen by the
    data: it never asserts alignment that was not computed, and it routes around
    the kappa paradox when the marginal is skewed."""
    k = res["fleiss_kappa"]
    pbar = res["observed_agreement_P_bar"]
    n_un, n_tot = res["unanimity_all_cases"]
    pct = res["unanimity_all_pct"]
    icc = res["icc_reference"]
    n_cmp = res["n_cases_in_kappa"]
    raters = res["raters_locked_to"]

    unan = (f"{n_un} of {n_tot} cases ({pct:.1f}%) returned an identical verdict "
            f"across all {raters} passes")
    agree = (f"mean pairwise agreement {pbar:.3f}" if not math.isnan(pbar) else
             "mean pairwise agreement undefined")

    head = ("Supplementary note on binary verdict stability. Because applying "
            "ICC(2,1) to a binary outcome is an unconventional (though "
            "conservative) parameterisation, we additionally report two "
            "model-free agreement statistics over the same reruns: ")

    if math.isnan(k):
        body = (
            f"{unan}, and {agree}. Fleiss' kappa is undefined here because the "
            f"verdict marginal is degenerate (all assignments fall in one "
            f"category), the limiting form of the high-agreement/low-kappa "
            f"paradox; we therefore report observed agreement directly. The "
            f"near-perfect raw agreement corroborates the high verdict stability "
            f"indicated by the ICC.")
    elif res["skew_warning"]:
        body = (
            f"{unan}, and {agree}. The verdict marginal is skewed "
            f"(largest class {res['max_marginal']:.3f}), which deflates "
            f"chance-corrected agreement via the well-documented "
            f"high-agreement/low-kappa paradox; Fleiss' kappa over the "
            f"{n_cmp} complete-rerun cases is {k:.3f}. We therefore read the raw "
            f"agreement as the primary corroboration of the ICC"
            + (f" ({icc:.3f})." if icc is not None else "."))
    else:
        aligns = (icc is not None and not math.isnan(k) and abs(k - icc) <= 0.10)
        if aligns:
            body = (
                f"{unan}; mean pairwise agreement is {pbar:.3f}; and Fleiss' "
                f"kappa over the {n_cmp} complete-rerun cases is {k:.3f}, closely "
                f"matching the ICC of {icc:.3f}. These corroborate the high "
                f"verdict stability under LLM non-determinism.")
        else:
            ref = f" against an ICC of {icc:.3f}" if icc is not None else ""
            body = (
                f"{unan}; mean pairwise agreement is {pbar:.3f}; and Fleiss' "
                f"kappa over the {n_cmp} complete-rerun cases is {k:.3f}{ref}. "
                f"We report all three and discuss any divergence in text rather "
                f"than asserting exact agreement.")
    return head + body


def render_console(res: dict) -> str:
    lines = ["# Binary verdict stability — supplementary corroboration", ""]
    lines.append(f"Audit files read: {res['n_audit_files']}  ·  "
                 f"clean records: {res['n_clean_records']}")
    lines.append(f"Variants present: {res['variants_seen']}")
    lines.append(f"Ratings-per-case distribution: "
                 f"{res['ratings_per_case_distribution']}  "
                 f"(locked Fleiss to n={res['raters_locked_to']} raters)")
    if res["ratings_per_case_distribution"] and \
       res["raters_locked_to"] not in res["ratings_per_case_distribution"]:
        lines.append("  [!] no case has the locked rater count — check --raters")
    if len(res["ratings_per_case_distribution"]) > 1:
        lines.append(f"  note: {res['n_cases_excluded_unequal_n']} case(s) "
                     f"excluded from kappa for having != {res['raters_locked_to']} "
                     f"ratings (unanimity below still uses all cases)")
    # Sanity tripwire for a wrong grouping id.
    if res["n_cases_total"] and res["raters_locked_to"] <= 1:
        lines.append("  [!!] every case has <=1 rating — the grouping id is "
                     "almost certainly per-run, not per-case. Try a different "
                     "--id-field (e.g. case_id).")
    lines.append("")
    lines.append(f"Categories: {res['categories']}")
    lines.append(f"Marginals: " + ", ".join(
        f"{c}={p:.3f}" for c, p in res["marginals"].items()))
    if res["skew_warning"]:
        lines.append(f"  [!] marginal skewed (max {res['max_marginal']:.3f} > 0.90): "
                     "kappa is subject to the high-agreement/low-kappa paradox; "
                     "lead with percent agreement.")
    lines.append("")
    n_un, n_tot = res["unanimity_all_cases"]
    lines.append(f"Unanimity (all cases):      {n_un}/{n_tot} "
                 f"({res['unanimity_all_pct']:.1f}%) cases identical across all passes")
    lines.append(f"Mean pairwise agreement:    "
                 f"{res['observed_agreement_P_bar']:.4f}  (P_bar)")
    lines.append(f"Expected chance agreement:  "
                 f"{res['expected_agreement_P_e']:.4f}  (P_e)")
    k = res["fleiss_kappa"]
    lines.append(f"Fleiss' kappa:              "
                 + ("undefined (degenerate marginal)" if math.isnan(k) else f"{k:.4f}")
                 + f"   [on {res['n_cases_in_kappa']} complete-rerun cases]")
    if res["icc_reference"] is not None:
        lines.append(f"ICC reference (given):      {res['icc_reference']:.4f}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Fleiss' kappa + percent agreement corroboration for binary "
                    "verdict ICC.")
    ap.add_argument("--rerun-dir", type=Path, required=True,
                    help="test-retest rerun directory (same as compute_stability)")
    ap.add_argument("--seed-dir", type=Path, default=None,
                    help="test-retest seed-pass directory (the t=0 baseline)")
    ap.add_argument("--id-field", default="provenance_file",
                    help="record field that is stable across reruns of one case "
                         "(default provenance_file; try case_id if populated)")
    ap.add_argument("--raters", type=int, default=None,
                    help="expected reruns per case for the equal-n Fleiss form "
                         "(default: inferred mode, e.g. 6)")
    ap.add_argument("--icc", type=float, default=None,
                    help="ICC value to state alongside (e.g. 0.979) — used only "
                         "to phrase the note, never to alter a metric")
    ap.add_argument("--emit-note", action="store_true",
                    help="print a paper-ready sentence generated from the result")
    ap.add_argument("--out-json", type=Path, default=None)
    args = ap.parse_args()

    res = run(args.rerun_dir, args.seed_dir, args.id_field, args.raters, args.icc)
    print(render_console(res))
    if args.emit_note:
        print("\n=== Supplementary note (generated from the result above) ===\n")
        print(emit_note(res))
    if args.out_json:
        args.out_json.write_text(json.dumps(res, indent=2, default=float),
                                 encoding="utf-8")
        print(f"\nWrote {args.out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
