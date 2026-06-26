#!/usr/bin/env python3
"""
tost_sensitivity.py — Post-hoc boundary-robustness check for the H1 TOST result.

WHAT THIS IS (and is not)
-------------------------
This is a POST-HOC sensitivity analysis, run after the pilot was executed and
the methodology was locked. It is NOT pre-registered and does not alter the
pre-registered primary analysis. Its sole job is to test whether the H1
equivalence conclusion is robust to a known degeneracy of the Wald unpooled
standard error used by the primary test:

    se = sqrt(p1*(1-p1)/n1 + p2*(1-p2)/n2)

When an observed proportion sits exactly at 0 or 1 (a boundary that a strong
auditor will hit on ceiling cells), that arm contributes 0 to the SE, shrinking
it toward zero and making equivalence easier to "prove" by estimator collapse
rather than by data. In the fully degenerate case (both arms at the same
boundary) build_dashboard.tost_pvalue() returns p = 0.0 by fiat.

The robustness check recomputes each pair's TOST p-value with an
Agresti-Caffo adjustment (add one success and one failure to each arm), which
keeps every proportion strictly inside (0, 1) so the SE cannot collapse:

    x_tilde = x + 1 ,  n_tilde = n + 2
    p_tilde = x_tilde / n_tilde
    diff    = p1_tilde - p2_tilde
    se      = sqrt(p1_tilde*(1-p1_tilde)/n1_tilde + p2_tilde*(1-p2_tilde)/n2_tilde)

Everything else — the two-one-sided-tests construction, the equivalence margin,
the Holm step, and the decision threshold alpha — is reused UNCHANGED from
build_dashboard.py. The sensitivity test therefore differs from the primary
test in exactly one place: the standard error / point estimate. That is the
whole point.

The concluding Appendix sentence is generated FROM the computed result
(--emit-appendix); it is not hard-coded. If any boundary-affected pair fails to
retain equivalence under the adjusted test, the script says so and exits 1.

Usage
-----
  python tools/tost_sensitivity.py --dashboard output/run_.../dashboard.json
  python tools/tost_sensitivity.py --dashboard ... --out-md tost_sensitivity.md \
      --out-json tost_sensitivity.json --emit-appendix

Must be run from the directory containing build_dashboard.py (i.e. tools/),
exactly like validate_paper_tables.py imports render_paper_tables.

e.g.

python tools/tost_sensitivity.py \
    --dashboard output/run_20260522_152239_arm01_main_pilot_1200/dashboard.json \
    --alpha 0.005 --out-md tost_sensitivity.md \
    --out-json tost_sensitivity.json --emit-appendix
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

# Reuse the primary pipeline's own functions so the sensitivity test differs
# from the registered test in exactly one line (the SE). If this import fails,
# the script is being run from the wrong directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from build_dashboard import (  # noqa: E402
        ALPHA,
        EQUIVALENCE_MARGIN,
        holm_bonferroni,
        normal_cdf,
        tost_pvalue,
    )
except ImportError as e:  # pragma: no cover - environment guard
    sys.stderr.write(
        "ERROR: could not import build_dashboard. Run this script from the "
        "tools/ directory that contains build_dashboard.py.\n"
        f"({e})\n"
    )
    raise


# ---------------------------------------------------------------------------
# The one place the sensitivity test differs from the primary test
# ---------------------------------------------------------------------------

def agresti_caffo_tost(x1: int, n1: int, x2: int, n2: int,
                       margin: float = EQUIVALENCE_MARGIN) -> float | None:
    """Agresti-Caffo-adjusted TOST p-value (max of the two one-sided p-values).

    Identical to build_dashboard.tost_pvalue() except that both the point
    estimate and the SE use the +1 success / +1 failure adjusted proportions,
    so the SE is strictly positive and cannot collapse on boundary cells.
    """
    if n1 == 0 or n2 == 0:
        return None
    # Add one success and one failure to each arm.
    x1t, n1t = x1 + 1, n1 + 2
    x2t, n2t = x2 + 1, n2 + 2
    p1t, p2t = x1t / n1t, x2t / n2t
    # p1t, p2t are strictly in (0, 1) by construction => se > 0 always.
    se = math.sqrt(p1t * (1 - p1t) / n1t + p2t * (1 - p2t) / n2t)
    diff = p1t - p2t
    # Lower one-sided test: H0 diff <= -margin
    z_lower = (diff - (-margin)) / se
    p_lower = 1 - normal_cdf(z_lower)
    # Upper one-sided test: H0 diff >= margin
    z_upper = (diff - margin) / se
    p_upper = normal_cdf(z_upper)
    return max(p_lower, p_upper)


def boundary_arms(pair: dict) -> list[str]:
    """Names of arms whose observed proportion sits exactly at 0 or 1."""
    hits = []
    for arm, x_key, n_key, v_key in (
        ("arm1", "x1", "n1", "v1"),
        ("arm2", "x2", "n2", "v2"),
    ):
        x, n = pair.get(x_key), pair.get(n_key)
        if not n:
            continue
        if x == 0:
            hits.append(f"{pair.get(v_key, arm)}=0/{n}")
        elif x == n:
            hits.append(f"{pair.get(v_key, arm)}={n}/{n}")
    return hits


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze(dashboard: dict, alpha: float, margin: float) -> dict:
    """Recompute raw + Agresti-Caffo TOST for every H1 pair, Holm-adjust each
    family within each bucket, and compare the resulting decisions."""
    h1_pairs = dashboard.get("h1_pairs", {})
    result: dict = {
        "alpha": alpha,
        "margin": margin,
        "buckets": {},
        "stored_raw_tost_mismatches": [],
    }

    for bucket in ("CLEAN", "ROGUE"):
        pairs = h1_pairs.get(bucket, [])
        rows = []
        for p in pairs:
            x1, n1 = p.get("x1"), p.get("n1")
            x2, n2 = p.get("x2"), p.get("n2")
            raw = tost_pvalue(x1, n1, x2, n2, margin=margin)
            adj = agresti_caffo_tost(x1, n1, x2, n2, margin=margin)

            # Fidelity check: does our recomputed raw TOST match the value
            # stored in dashboard.json? A mismatch points at a stale or
            # hand-edited dashboard (the determinism concern), not at AC.
            stored = p.get("raw_tost_p")
            if stored is not None and raw is not None:
                if not math.isclose(stored, raw, abs_tol=1e-9):
                    result["stored_raw_tost_mismatches"].append(
                        f"{bucket} {p.get('v1')} vs {p.get('v2')}: "
                        f"stored raw_tost_p={stored}, recomputed={raw}"
                    )

            rows.append({
                "v1": p.get("v1"), "v2": p.get("v2"),
                "x1": x1, "n1": n1, "x2": x2, "n2": n2,
                "rec1": (x1 / n1) if n1 else None,
                "rec2": (x2 / n2) if n2 else None,
                "boundary": boundary_arms(p),
                "raw_tost_p": raw,
                "ac_tost_p": adj,
            })

        # Holm within the bucket, reusing the primary pipeline's routine.
        raw_valid = [r["raw_tost_p"] for r in rows if r["raw_tost_p"] is not None]
        ac_valid = [r["ac_tost_p"] for r in rows if r["ac_tost_p"] is not None]
        raw_adj_it = iter(holm_bonferroni(raw_valid)) if raw_valid else iter([])
        ac_adj_it = iter(holm_bonferroni(ac_valid)) if ac_valid else iter([])
        for r in rows:
            r["raw_tost_p_holm"] = next(raw_adj_it) if r["raw_tost_p"] is not None else None
            r["ac_tost_p_holm"] = next(ac_adj_it) if r["ac_tost_p"] is not None else None
            r["raw_pass"] = (r["raw_tost_p_holm"] is not None
                             and r["raw_tost_p_holm"] < alpha)
            r["ac_pass"] = (r["ac_tost_p_holm"] is not None
                            and r["ac_tost_p_holm"] < alpha)
            # The direction that threatens the paper: equivalence under the
            # primary test that does NOT survive the boundary-robust test.
            r["flip_pass_to_fail"] = bool(r["raw_pass"] and not r["ac_pass"])
            r["flip_fail_to_pass"] = bool(r["ac_pass"] and not r["raw_pass"])

        result["buckets"][bucket] = {
            "n_pairs": len(rows),
            "rows": rows,
            "raw_h1_pass": all(r["raw_pass"] for r in rows) if rows else False,
            "ac_h1_pass": all(r["ac_pass"] for r in rows) if rows else False,
            "boundary_pairs": [r for r in rows if r["boundary"]],
            "pass_to_fail": [r for r in rows if r["flip_pass_to_fail"]],
            "fail_to_pass": [r for r in rows if r["flip_fail_to_pass"]],
        }

    # Overall H1 = every pair in both buckets clears alpha.
    result["raw_h1_pass"] = all(b["raw_h1_pass"] for b in result["buckets"].values())
    result["ac_h1_pass"] = all(b["ac_h1_pass"] for b in result["buckets"].values())
    result["robustness_holds"] = bool(result["raw_h1_pass"] and result["ac_h1_pass"])
    result["any_pass_to_fail"] = any(
        b["pass_to_fail"] for b in result["buckets"].values())
    return result


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _fmt_p(p: float | None) -> str:
    return "—" if p is None else f"{p:.4g}"


def render_markdown(res: dict) -> str:
    alpha = res["alpha"]
    lines = [
        "# Post-hoc Agresti-Caffo TOST sensitivity analysis",
        "",
        f"Equivalence margin ±{res['margin']:g}; decision threshold "
        f"Holm-adjusted p < α = {alpha:g}.",
        "Raw = pre-registered Wald-unpooled TOST. AC = Agresti-Caffo-adjusted "
        "(add one success and one failure per arm). † marks pairs with an arm "
        "at the 0/1 boundary.",
        "",
    ]
    for bucket in ("CLEAN", "ROGUE"):
        b = res["buckets"].get(bucket)
        if not b:
            continue
        lines.append(f"## {bucket}")
        lines.append("")
        lines.append("| Pair | rec1 | rec2 | Raw TOST p (Holm) | AC TOST p (Holm) | Boundary |")
        lines.append("|------|------|------|-------------------|------------------|----------|")
        for r in b["rows"]:
            mark = " †" if r["boundary"] else ""
            rec1 = "—" if r["rec1"] is None else f"{r['rec1']:.3f}"
            rec2 = "—" if r["rec2"] is None else f"{r['rec2']:.3f}"
            bnd = ", ".join(r["boundary"]) if r["boundary"] else ""
            lines.append(
                f"| {r['v1']} vs {r['v2']}{mark} | {rec1} | {rec2} | "
                f"{_fmt_p(r['raw_tost_p'])} ({_fmt_p(r['raw_tost_p_holm'])}) | "
                f"{_fmt_p(r['ac_tost_p'])} ({_fmt_p(r['ac_tost_p_holm'])}) | {bnd} |"
            )
        lines.append("")
        lines.append(
            f"H1 under raw test: **{'PASS' if b['raw_h1_pass'] else 'FAIL'}** · "
            f"under AC test: **{'PASS' if b['ac_h1_pass'] else 'FAIL'}**"
        )
        if b["pass_to_fail"]:
            flips = ", ".join(f"{r['v1']} vs {r['v2']}" for r in b["pass_to_fail"])
            lines.append("")
            lines.append(f"> ⚠ Lost equivalence under AC: {flips}")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        f"**Overall:** H1 raw = {'PASS' if res['raw_h1_pass'] else 'FAIL'}, "
        f"H1 AC = {'PASS' if res['ac_h1_pass'] else 'FAIL'}, "
        f"robustness {'HOLDS' if res['robustness_holds'] else 'DOES NOT HOLD'}."
    )
    return "\n".join(lines)


def emit_appendix(res: dict) -> str:
    """Generate the Appendix A sentence from the computed result. Never asserts
    a verdict that was not computed."""
    alpha = res["alpha"]
    # Collect the boundary-affected pairs across buckets.
    boundary = []
    for bucket in ("CLEAN", "ROGUE"):
        for r in res["buckets"].get(bucket, {}).get("boundary_pairs", []):
            cells = "; ".join(r["boundary"])
            boundary.append(f"{bucket} {r['v1']}–{r['v2']} ({cells})")
    n_boundary = len(boundary)

    if n_boundary == 0:
        head = (
            "Post-hoc sensitivity analysis for boundary conditions. No pairwise "
            "comparison in either ground-truth class placed an observed "
            "proportion exactly at the 0 or 1 boundary, so the Wald unpooled "
            "standard error did not degenerate for any reported TOST. As a "
            "robustness check we nonetheless recomputed every pair with an "
            "Agresti-Caffo-adjusted TOST (one success and one failure added to "
            "each arm)."
        )
    else:
        examples = "; ".join(boundary)
        head = (
            "Post-hoc sensitivity analysis for boundary conditions. The Wald "
            "unpooled standard error collapses toward zero when an observed "
            "proportion sits exactly at 0 or 1, so that standard TOST can "
            "register equivalence through estimator degeneracy rather than "
            "data. This boundary arose in the following pairwise comparisons: "
            f"{examples}. To confirm the pre-registered H1 result is not an "
            "artifact of this collapse, we recomputed every pair with an "
            "Agresti-Caffo-adjusted TOST (one success and one failure added to "
            "each arm), which holds every proportion strictly inside (0, 1) and "
            "keeps the standard error positive."
        )

    if res["ac_h1_pass"]:
        tail = (
            f" Under the adjusted test every pair retained equivalence at the "
            f"Holm-adjusted threshold (p < {alpha:g}), so the registered H1 "
            f"conclusion is driven by the data rather than by estimator "
            f"collapse."
        )
    else:
        lost = []
        for bucket in ("CLEAN", "ROGUE"):
            for r in res["buckets"].get(bucket, {}).get("pass_to_fail", []):
                lost.append(f"{bucket} {r['v1']}–{r['v2']}")
        lost_str = "; ".join(lost) if lost else "one or more pairs"
        tail = (
            f" Under the adjusted test, {lost_str} no longer met the "
            f"equivalence criterion at the Holm-adjusted threshold "
            f"(p < {alpha:g}). The equivalence claim for those pairs is "
            f"therefore sensitive to the boundary artifact and is reported with "
            f"this caveat."
        )
    return head + tail


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Post-hoc Agresti-Caffo TOST boundary-robustness check.")
    ap.add_argument("--dashboard", type=Path, required=True,
                    help="dashboard.json produced by build_dashboard.py")
    ap.add_argument("--alpha", type=float, default=ALPHA,
                    help=f"decision threshold (default {ALPHA}, imported from "
                         f"build_dashboard.ALPHA). If the manuscript registers a "
                         f"different alpha for H1, set it explicitly.")
    ap.add_argument("--margin", type=float, default=EQUIVALENCE_MARGIN,
                    help=f"equivalence margin (default {EQUIVALENCE_MARGIN})")
    ap.add_argument("--out-md", type=Path, default=None,
                    help="write the comparison table as markdown")
    ap.add_argument("--out-json", type=Path, default=None,
                    help="write the full result as JSON")
    ap.add_argument("--emit-appendix", action="store_true",
                    help="print the auto-generated Appendix A sentence")
    args = ap.parse_args()

    dashboard = json.loads(args.dashboard.read_text(encoding="utf-8"))
    res = analyze(dashboard, alpha=args.alpha, margin=args.margin)

    print(render_markdown(res))

    if res["stored_raw_tost_mismatches"]:
        print("\n[!] Recomputed raw TOST disagrees with the value stored in "
              "dashboard.json for:")
        for m in res["stored_raw_tost_mismatches"]:
            print(f"      - {m}")
        print("    This indicates a stale or edited dashboard.json, not an AC "
              "issue; regenerate it from build_dashboard.py before relying on "
              "either analysis.")

    if args.emit_appendix:
        print("\n=== Appendix A sentence (generated from the result above) ===\n")
        print(emit_appendix(res))

    if args.out_md:
        args.out_md.write_text(render_markdown(res), encoding="utf-8")
        print(f"\nWrote {args.out_md}")
    if args.out_json:
        args.out_json.write_text(json.dumps(res, indent=2, default=float),
                                 encoding="utf-8")
        print(f"Wrote {args.out_json}")

    # Exit 1 if the primary test passed H1 but the boundary-robust test does
    # not — the robustness check has failed and a human must look.
    if res["raw_h1_pass"] and not res["ac_h1_pass"]:
        print("\nROBUSTNESS CHECK FAILED: H1 held under the primary test but "
              "not under the Agresti-Caffo-adjusted test.")
        return 1
    print("\nRobustness check: H1 conclusion is unchanged under the "
          "Agresti-Caffo-adjusted test.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
