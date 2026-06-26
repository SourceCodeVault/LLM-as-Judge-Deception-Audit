#!/usr/bin/env python3
"""
validate_paper_tables.py — Extended validator closing three gaps left by
tools/validate_dashboard.py:

  1. --dashboard       Recomputes the FULL statistical layer (TOST, Holm,
                       Wilson CIs, strata, save/break rates, 8-cell, decision
                       rule) from full_telemetry and compares against the
                       stored aggregates. validate_dashboard.py checks counts
                       and FPR/FNR only; the H1 block — the headline result —
                       was previously unverified. Also enforces the
                       pre-registered H1 family (exactly Z01–Z05, 10 pairs
                       per bucket): a stray Z07 / perturbation file silently
                       changes the Holm m, and this check makes that demonstrable.

  2. --audit-dir       Re-parses the raw audit_*.json files and compares the
                       per-variant counts against the dashboard, breaking the
                       circularity of validating dashboard.json against its
                       own embedded telemetry.

  3. --paper PAPER.md  Parses the §5 markdown tables out of the manuscript
                       and compares every numeric cell against values
                       recomputed from dashboard.json (and optionally
                       stability_report.json / ablation dashboard.json) at
                       the displayed precision. This is the gate that proves
                       the LLM-transcribed tables are faithful to the
                       deterministic pipeline — substantiating the
                       Acknowledgments claim that reported numbers are not
                       LLM-computed.

Every numeric cell ends in one of three states: VERIFIED, MISMATCH, or
UNVERIFIED (couldn't be parsed / no source supplied). Exit 1 on any MISMATCH.

Usage:
  python tools/validate_paper_tables.py --dashboard output/run_.../dashboard.json
  python tools/validate_paper_tables.py --dashboard ... --audit-dir output/run_...
  python tools/validate_paper_tables.py --dashboard ... \
      --ablation-dashboard ... --stability ... --paper PAPER.md

e.g.
python tools/validate_paper_tables.py \
    --dashboard output/run_20260522_152239_arm01_main_pilot_1200/dashboard.json \
    --ablation-dashboard output/run_20260522_152239_arm01_main_pilot_1200/dashboard.json \
    --stability output/stability_k6_report/stability_report.json \
    --paper paper/PAPER.md
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_paper_tables import (  # noqa: E402
    ABLATION_LABELS, EIGHT_CELL_COLUMNS, H1_FAMILY,
    recompute, crosscheck, valid_rows, wilson_ci,
)

# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

class Report:
    def __init__(self) -> None:
        self.verified = 0
        self.mismatches: list[str] = []
        self.unverified: list[str] = []

    def ok(self, n: int = 1) -> None:
        self.verified += n

    def fail(self, msg: str) -> None:
        self.mismatches.append(msg)
        print(f"  [✗] MISMATCH: {msg}")

    def skip(self, msg: str) -> None:
        self.unverified.append(msg)
        print(f"  [~] UNVERIFIED: {msg}")

    def section(self, title: str) -> None:
        print(f"\n--- {title} ---")

    def summary(self) -> int:
        print(f"\n=== Summary: {self.verified} verified · "
              f"{len(self.mismatches)} mismatches · "
              f"{len(self.unverified)} unverified ===")
        if self.mismatches:
            print("FAILED: manuscript/dashboard is NOT faithful to the pipeline output.")
            return 1
        if self.unverified:
            print("PASSED with warnings: some cells could not be verified "
                  "(supply --ablation-dashboard / --stability, or check parse warnings).")
            return 0
        print("PASSED: every checked cell matches the deterministic pipeline output.")
        return 0

# ---------------------------------------------------------------------------
# Layer 1 — dashboard.json internal recomputation (superset of validate_dashboard)
# ---------------------------------------------------------------------------

def check_dashboard(model: dict, dashboard: dict, rep: Report) -> None:
    rep.section("Layer 1 · dashboard.json statistical recomputation")
    problems = crosscheck(model, dashboard)
    for p in problems:
        rep.fail(p)
    if not problems:
        rep.ok()
        print("  [✓] counts, FPR/FNR, and full H1 block (raw p, TOST p, Holm-adjusted) "
              "match recomputation from telemetry")

    # H1 family integrity (pre-reg: exactly Z01–Z05, C(5,2)=10 pairs per bucket)
    fam = set(model["h1_family"])
    expected = set(H1_FAMILY)
    if fam != expected:
        rep.fail(f"H1 family is {sorted(fam)}; pre-registered family is {sorted(expected)}")
    else:
        rep.ok()
    for bucket in ("CLEAN", "ROGUE"):
        stored_n = len(dashboard.get("h1_pairs", {}).get(bucket, []))
        if stored_n != 10:
            rep.fail(f"h1_pairs[{bucket}] has {stored_n} pairs; pre-registration "
                     f"specifies C(5,2) = 10 — Holm m is wrong")
        else:
            rep.ok()
    extraneous = [v for v in model["variants"]
                  if v not in expected and v not in ABLATION_LABELS]
    if extraneous:
        rep.skip(f"telemetry contains non-family variants {extraneous}; confirm they "
                 f"are intentionally excluded from H1 (e.g. Z07 control)")

    # Decision-rule recomputation vs stored decision block
    stored_dec = dashboard.get("decision", {})
    for key in ("h1_passed", "h2_passed", "supported"):
        if key in stored_dec:
            if bool(stored_dec[key]) != bool(model["decision"][key]):
                rep.fail(f"decision.{key}: stored {stored_dec[key]} != "
                         f"recomputed {model['decision'][key]}")
            else:
                rep.ok()

    # Wilson CI spot-recompute against stored fpr_ci / fnr_ci
    for v, d in model["by_variant"].items():
        s = dashboard.get("by_variant", {}).get(v, {})
        for key, mine in (("fpr_ci", d["fpr_ci"]), ("fnr_ci", d["fnr_ci"])):
            theirs = s.get(key)
            if theirs and mine[0] is not None:
                if not (math.isclose(mine[0], theirs[0], abs_tol=1e-9)
                        and math.isclose(mine[1], theirs[1], abs_tol=1e-9)):
                    rep.fail(f"[{v}] {key}: recomputed {mine} != stored {tuple(theirs)}")
                else:
                    rep.ok()

# ---------------------------------------------------------------------------
# Layer 2 — raw audit_*.json cross-check (breaks the circularity)
# ---------------------------------------------------------------------------

def parse_raw_audits(audit_dir: Path) -> dict:
    """Minimal independent re-implementation of build_dashboard.parse_logs
    sufficient to recover per-variant {bucket: (n, l3_correct)} counts."""
    counts: dict = {}
    n_files = 0
    for f in sorted(audit_dir.rglob("audit_*.json")):
        if any(part.startswith("_") for part in f.relative_to(audit_dir).parts[:-1]):
            continue
        n_files += 1
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("pipeline_status") != "OK":
            continue
        meta = data.get("metadata") or {}
        apollo = meta.get("apollo_labels") or {}
        gap = data.get("compliance_gap") or {}
        if not gap:
            continue
        is_mis = apollo.get("is_misaligned")
        if is_mis is None or (is_mis is False and apollo.get("is_deceptive") is True):
            continue
        bucket = "ROGUE" if is_mis else "CLEAN"
        fn = meta.get("l2_manifest_filename") or ""
        m = re.search(r"Z\d{2}", fn)
        variant = m.group(0) if m else (meta.get("l2_variant") or "UNKNOWN").strip().upper()
        l2_raw = gap.get("l2_judge_action") or gap.get("watcher_action")
        l2 = ("BLOCK" if l2_raw in ("BLOCKED", "BLOCK", "HESITATE")
              else "APPROVE" if l2_raw in ("APPROVED", "APPROVE") else "UNKNOWN")
        l3 = gap.get("auditor_recommended_action")
        if l2 == "UNKNOWN" or l3 not in ("APPROVE", "BLOCK"):
            continue
        correct = "APPROVE" if bucket == "CLEAN" else "BLOCK"
        d = counts.setdefault(variant, {"CLEAN": [0, 0], "ROGUE": [0, 0]})
        d[bucket][0] += 1
        d[bucket][1] += 1 if l3 == correct else 0
    return {"counts": counts, "n_files": n_files}

def check_raw(model: dict, audit_dir: Path, rep: Report) -> None:
    rep.section(f"Layer 2 · raw audit files cross-check ({audit_dir})")
    raw = parse_raw_audits(audit_dir)
    if not raw["counts"]:
        rep.skip(f"no parsable audit_*.json under {audit_dir}")
        return
    print(f"  parsed {raw['n_files']} raw audit files")
    for v, d in sorted(raw["counts"].items()):
        md = model["by_variant"].get(v)
        if md is None:
            rep.fail(f"variant {v} present in raw audits but absent from dashboard")
            continue
        for bucket in ("CLEAN", "ROGUE"):
            rn, rx = d[bucket]
            if (rn, rx) != (md[bucket]["n"], md[bucket]["x"]):
                rep.fail(f"[{v}/{bucket}] raw files give n={rn}, correct={rx}; "
                         f"dashboard telemetry gives n={md[bucket]['n']}, "
                         f"correct={md[bucket]['x']}")
            else:
                rep.ok()
    for v in model["by_variant"]:
        if v not in raw["counts"]:
            rep.fail(f"variant {v} in dashboard but absent from raw audit files")

# ---------------------------------------------------------------------------
# Layer 3 — manuscript table fidelity
# ---------------------------------------------------------------------------

NUM = re.compile(r"[-+]?\d[\d,]*\.?\d*(?:[eE][-+]?\d+)?")

def strip_md(cell: str) -> str:
    # Note: U+2212 (minus sign) is normalized to ASCII '-'; U+2013 (en dash,
    # used in ranges like "59–108" and pair labels "Z01–Z02") is NOT, so that
    # ranges don't parse as negative numbers.
    return (cell.replace("**", "").replace("*", "").replace("$", "")
                .replace("\u2212", "-").strip())

def nums(cell: str) -> list[float]:
    return [float(t.replace(",", "")) for t in NUM.findall(strip_md(cell))]

def extract_tables(paper_text: str) -> list[list[list[str]]]:
    """Return all markdown tables as lists of rows of cells."""
    tables, current = [], []
    for line in paper_text.splitlines():
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue  # separator row
            current.append(cells)
        else:
            if len(current) >= 2:
                tables.append(current)
            current = []
    if len(current) >= 2:
        tables.append(current)
    return tables

def variant_of(cell: str) -> str | None:
    m = re.search(r"Z\d{2}", strip_md(cell))
    if m:
        return m.group(0)
    if "ABLATION" in strip_md(cell).upper():
        return "ABLATION"
    return None

def close(shown: float, true: float, dp: int) -> bool:
    """Match at the displayed precision (tolerant of round-half conventions)."""
    return abs(shown - true) <= 0.5 * 10 ** (-dp) + 1e-9

def dp_of(token: str) -> int:
    return len(token.split(".")[1]) if "." in token else 0

def check_pct_cell(cell: str, true_frac: float | None, label: str, rep: Report,
                   ci: tuple | None = None) -> None:
    """Verify a '99.2% [0.4, 2.5]'-style cell against a true fraction (+ CI)."""
    s = strip_md(cell)
    toks = NUM.findall(s)
    if not toks or true_frac is None:
        rep.skip(f"{label}: cannot verify cell {cell!r}")
        return
    shown = float(toks[0].replace(",", ""))
    if not close(shown, true_frac * 100, dp_of(toks[0])):
        rep.fail(f"{label}: shows {shown}%, pipeline gives {true_frac*100:.4f}%")
        return
    rep.ok()
    if ci and ci[0] is not None and len(toks) >= 3:
        lo, hi = float(toks[1]), float(toks[2])
        if not (close(lo, ci[0]*100, dp_of(toks[1])) and close(hi, ci[1]*100, dp_of(toks[2]))):
            rep.fail(f"{label} CI: shows [{lo}, {hi}], pipeline gives "
                     f"[{ci[0]*100:.4f}, {ci[1]*100:.4f}]")
        else:
            rep.ok()

def check_paper(paper_path: Path, model: dict, ablation_model: dict | None,
                stability: dict | None, rep: Report) -> None:
    rep.section(f"Layer 3 · manuscript table fidelity ({paper_path.name})")
    text = paper_path.read_text(encoding="utf-8")

    # Hygiene: LLM-transcription boilerplate that has leaked into the manuscript.
    flagged_lines: set[int] = set()
    for pat in (r"copy and paste", r"^Here is the ", r"As an AI ", r"I hope this helps"):
        for m in re.finditer(pat, text, flags=re.IGNORECASE | re.MULTILINE):
            line_no = text[:m.start()].count("\n") + 1
            if line_no in flagged_lines:
                continue
            flagged_lines.add(line_no)
            rep.fail(f"LLM-chat boilerplate in manuscript at line {line_no}: "
                     f"{text.splitlines()[line_no-1][:80]!r}")

    tables = extract_tables(text)
    seen = set()
    for tbl in tables:
        header = " | ".join(tbl[0])
        if "Recovery CLEAN" in header and "Save rate" in header:
            seen.add("headline"); _check_headline(tbl, model, ablation_model, rep)
        elif "judge correct" in header:
            seen.add("strata"); _check_strata(tbl, model, rep)
        elif "adj TOST p" in header:
            seen.add("h1"); _check_h1(tbl, model, rep)
        elif "FPR (95% CI)" in header:
            seen.add("h2"); _check_h2(tbl, model, rep)
        elif "concur-correct" in header:
            seen.add("8cell"); _check_eight_cell(tbl, model, rep)
        elif "CLEAN firings" in header:
            seen.add("rules"); _check_rules(tbl, model, rep)
        elif "Judge intact" in header:
            seen.add("ablation"); _check_ablation(tbl, model, ablation_model, rep)
        elif "Observed" in header and "Coefficient" in header:
            seen.add("stability"); _check_stability(tbl, stability, rep)
        elif "Flicker" in header:
            seen.add("flicker"); _check_flicker(tbl, stability, rep)
    for want in ("headline", "strata", "h1", "h2", "8cell", "rules"):
        if want not in seen:
            rep.skip(f"could not locate the '{want}' table in the manuscript")

def _row_model(model, ablation_model, label_cell):
    v = variant_of(label_cell)
    if v in (model or {}).get("by_variant", {}):
        return model["by_variant"][v], v
    if v == "ABLATION":
        if ablation_model:
            ab = next((ablation_model["by_variant"][x] for x in ablation_model["variants"]
                       if x in ABLATION_LABELS), None)
            return ab, "ABLATION"
        return None, "ABLATION"
    return None, v

def _check_headline(tbl, model, ablation_model, rep):
    for row in tbl[1:]:
        d, v = _row_model(model, ablation_model, row[0])
        if d is None:
            rep.skip(f"headline row {row[0]!r}: no source data "
                     f"(supply --ablation-dashboard?)")
            continue
        check_pct_cell(row[2], d["CLEAN"]["x"]/d["CLEAN"]["n"] if d["CLEAN"]["n"] else None,
                       f"headline {v} Recovery CLEAN", rep)
        check_pct_cell(row[3], d["ROGUE"]["x"]/d["ROGUE"]["n"] if d["ROGUE"]["n"] else None,
                       f"headline {v} Recovery ROGUE", rep)
        check_pct_cell(row[4], d["save_rate"], f"headline {v} save rate", rep, d["save_ci"])
        check_pct_cell(row[5], d["break_rate"], f"headline {v} break rate", rep, d["break_ci"])

def _check_strata(tbl, model, rep):
    cols = [("CLEAN", "jc"), ("CLEAN", "jw"), ("ROGUE", "jc"), ("ROGUE", "jw")]
    for row in tbl[1:]:
        d, v = _row_model(model, None, row[0])
        if d is None:
            rep.skip(f"strata row {row[0]!r}: unknown variant")
            continue
        for cell, (bucket, kind) in zip(row[1:5], cols):
            n_true, x_true = d[bucket][f"{kind}_n"], d[bucket][f"{kind}_x"]
            label = f"strata {v} {bucket}·judge_{'correct' if kind=='jc' else 'wrong'}"
            ints = re.findall(r"\((\d+)/(\d+)\)", strip_md(cell))
            if not ints:
                rep.skip(f"{label}: cannot parse {cell!r}")
                continue
            x_shown, n_shown = int(ints[0][0]), int(ints[0][1])
            if (x_shown, n_shown) != (x_true, n_true):
                rep.fail(f"{label}: shows ({x_shown}/{n_shown}), pipeline gives "
                         f"({x_true}/{n_true})")
                continue
            rep.ok()
            if n_true:
                check_pct_cell(cell.split("(")[0], x_true/n_true, f"{label} pct", rep)

def _check_h1(tbl, model, rep):
    clean = {(p["v1"], p["v2"]): p for p in model["h1_pairs"]["CLEAN"]}
    rogue = {(p["v1"], p["v2"]): p for p in model["h1_pairs"]["ROGUE"]}
    for row in tbl[1:]:
        pair = tuple(re.findall(r"Z\d{2}", strip_md(row[0])))
        if len(pair) != 2 or pair not in clean:
            rep.skip(f"H1 row {row[0]!r}: unknown pair")
            continue
        for cell_d, cell_p, p in ((row[1], row[2], clean[pair]),
                                  (row[3], row[4], rogue[pair])):
            bucket = "CLEAN" if p is clean[pair] else "ROGUE"
            d_toks = nums(cell_d)
            if d_toks and not close(d_toks[0], p["delta"]*100, dp_of(NUM.findall(cell_d)[0])):
                rep.fail(f"H1 {pair[0]}–{pair[1]} {bucket} Δ: shows {d_toks[0]}, "
                         f"pipeline gives {p['delta']*100:+.4f}")
            else:
                rep.ok()
            s = strip_md(cell_p)
            if s.startswith("<"):
                thresh = float(s[1:])
                if p["adj_tost_p"] >= thresh:
                    rep.fail(f"H1 {pair[0]}–{pair[1]} {bucket} adj TOST p: shows {s}, "
                             f"pipeline gives {p['adj_tost_p']:.3e}")
                else:
                    rep.ok()
            else:
                shown = nums(cell_p)
                if not shown:
                    rep.skip(f"H1 {pair} {bucket} p: cannot parse {cell_p!r}")
                elif not math.isclose(shown[0], p["adj_tost_p"], rel_tol=0.06):
                    rep.fail(f"H1 {pair[0]}–{pair[1]} {bucket} adj TOST p: shows "
                             f"{shown[0]:.2e}, pipeline gives {p['adj_tost_p']:.2e}")
                else:
                    rep.ok()

def _check_h2(tbl, model, rep):
    for row in tbl[1:]:
        d, v = _row_model(model, None, row[0])
        if d is None:
            rep.skip(f"H2 row {row[0]!r}: unknown variant")
            continue
        check_pct_cell(row[1], d["fpr"], f"H2 {v} FPR", rep, d["fpr_ci"])
        check_pct_cell(row[2], d["fnr"], f"H2 {v} FNR", rep, d["fnr_ci"])

def _check_eight_cell(tbl, model, rep):
    for row in tbl[1:]:
        d, v = _row_model(model, None, row[0])
        if d is None:
            rep.skip(f"8-cell row {row[0]!r}: unknown variant")
            continue
        for cell, (col, key) in zip(row[1:], EIGHT_CELL_COLUMNS):
            shown = nums(cell)
            true = d["eight_cell"][key]
            if not shown:
                rep.skip(f"8-cell {v} {col}: cannot parse {cell!r}")
            elif int(shown[0]) != true:
                rep.fail(f"8-cell {v} {col}: shows {int(shown[0])}, pipeline gives {true}")
            else:
                rep.ok()

def _check_rules(tbl, model, rep):
    fam_true = {"CLEAN": {}, "ROGUE": {}}
    for b in ("CLEAN", "ROGUE"):
        for rule, n in model["rules_by_class"][b].items():
            fam_true[b][rule[0]] = fam_true[b].get(rule[0], 0) + n
    for row in tbl[1:]:
        fam = strip_md(row[0])[:1].upper()
        if fam not in fam_true["CLEAN"] and fam not in fam_true["ROGUE"]:
            rep.skip(f"rules row {row[0]!r}: unknown family")
            continue
        for cell, b in ((row[2], "CLEAN"), (row[3], "ROGUE")):
            shown = nums(cell)
            true = fam_true[b].get(fam, 0)
            if not shown:
                rep.skip(f"rules {fam} {b}: cannot parse {cell!r}")
            elif int(shown[0]) != true:
                rep.fail(f"rules {fam} {b} firings: shows {int(shown[0])}, "
                         f"pipeline gives {true}")
            else:
                rep.ok()

def _check_ablation(tbl, model, ablation_model, rep):
    header = " ".join(tbl[0])
    m = re.search(r"Z\d{2}", header)
    intact = model["by_variant"].get(m.group(0)) if m else None
    noise = None
    if ablation_model:
        noise = next((ablation_model["by_variant"][x] for x in ablation_model["variants"]
                      if x in ABLATION_LABELS), None)
    getters = {
        "Recovery CLEAN": lambda d: d["CLEAN"]["x"]/d["CLEAN"]["n"] if d["CLEAN"]["n"] else None,
        "Recovery ROGUE": lambda d: d["ROGUE"]["x"]/d["ROGUE"]["n"] if d["ROGUE"]["n"] else None,
        "FPR": lambda d: d["fpr"], "FNR": lambda d: d["fnr"],
        "save rate": lambda d: d["save_rate"], "break rate": lambda d: d["break_rate"],
    }
    for row in tbl[1:]:
        metric = strip_md(row[0])
        if metric.startswith("n ("):
            for d, cell, side in ((intact, row[1], "intact"), (noise, row[2], "noise")):
                if d is None:
                    rep.skip(f"ablation n {side}: no source data")
                    continue
                shown = [int(x) for x in nums(cell)]
                true = [d["CLEAN"]["n"], d["ROGUE"]["n"]]
                if shown != true:
                    rep.fail(f"ablation n {side}: shows {shown}, pipeline gives {true}")
                else:
                    rep.ok()
            continue
        getter = next((g for k, g in getters.items() if k in metric), None)
        if getter is None:
            rep.skip(f"ablation metric {metric!r}: no comparator")
            continue
        for d, cell, side in ((intact, row[1], "intact"), (noise, row[2], "noise")):
            if d is None:
                rep.skip(f"ablation {metric} {side}: no source data "
                         f"(supply --ablation-dashboard?)")
                continue
            check_pct_cell(cell, getter(d), f"ablation {metric} {side}", rep)

def _check_stability(tbl, stability, rep):
    if not stability:
        rep.skip("stability coefficient table found but no --stability supplied")
        return
    targets = {
        "ICC": stability.get("icc_2_1"),
        "kappa": stability.get("cohen_kappa_quadrant_mean"),
        "alpha": stability.get("krippendorff_alpha"),
    }
    for row in tbl[1:]:
        label = strip_md(row[0])
        key = ("ICC" if "ICC" in label else
               "kappa" if "kappa" in label.lower() else
               "alpha" if "alpha" in label.lower() else None)
        if key is None or targets[key] is None:
            rep.skip(f"stability row {label!r}: no comparator")
            continue
        shown = nums(row[2])
        if not shown:
            rep.skip(f"stability {key}: cannot parse {row[2]!r}")
        elif not close(shown[0], targets[key], dp_of(NUM.findall(strip_md(row[2]))[0])):
            rep.fail(f"stability {key}: shows {shown[0]}, pipeline gives {targets[key]:.4f}")
        else:
            rep.ok()

def _check_flicker(tbl, stability, rep):
    if not stability:
        rep.skip("flicker table found but no --stability supplied")
        return
    flicker = stability.get("rule_flicker_stats", {})
    for row in tbl[1:]:
        label = strip_md(row[0])
        rules = re.findall(r"[A-Z]\d", label)
        if "–" in label and len(rules) == 2 and rules[0][0] == rules[1][0]:
            fam, lo, hi = rules[0][0], int(rules[0][1]), int(rules[1][1])
            rules = [f"{fam}{i}" for i in range(lo, hi + 1)]
        seen_vals = nums(row[1])
        pct_vals = nums(row[2])
        if len(rules) == 1 and seen_vals and pct_vals:
            st = flicker.get(rules[0])
            if st is None:
                rep.skip(f"flicker {rules[0]}: not in stability report")
            elif (int(seen_vals[0]) != st["cases_seen"]
                  or not close(pct_vals[0], st["instability_pct"], 1)):
                rep.fail(f"flicker {rules[0]}: shows ({int(seen_vals[0])}, {pct_vals[0]}%), "
                         f"pipeline gives ({st['cases_seen']}, {st['instability_pct']}%)")
            else:
                rep.ok(2)
        elif len(rules) == 2 and len(seen_vals) == 2 and len(pct_vals) == 2:
            for r, sv, pv in zip(rules, seen_vals, pct_vals):
                st = flicker.get(r)
                if st is None:
                    rep.skip(f"flicker {r}: not in stability report")
                elif int(sv) != st["cases_seen"] or not close(pv, st["instability_pct"], 1):
                    rep.fail(f"flicker {r}: shows ({int(sv)}, {pv}%), pipeline gives "
                             f"({st['cases_seen']}, {st['instability_pct']}%)")
                else:
                    rep.ok(2)
        elif len(rules) > 2:  # range row, e.g. "J1–J5 ... | 59–108 | 100.0"
            for r in rules:
                st = flicker.get(r)
                if st is None:
                    rep.skip(f"flicker {r}: not in stability report")
                    continue
                bad = []
                if len(seen_vals) == 2 and not (seen_vals[0] <= st["cases_seen"] <= seen_vals[1]):
                    bad.append(f"cases_seen {st['cases_seen']} outside "
                               f"[{int(seen_vals[0])}, {int(seen_vals[1])}]")
                if pct_vals and not close(pct_vals[0], st["instability_pct"], 1):
                    bad.append(f"flicker {st['instability_pct']}% != {pct_vals[0]}%")
                if bad:
                    rep.fail(f"flicker {r}: " + "; ".join(bad))
                else:
                    rep.ok()
        else:
            rep.skip(f"flicker row {label!r}: cannot parse")

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Extended dashboard + manuscript validator")
    ap.add_argument("--dashboard", type=Path, required=True)
    ap.add_argument("--ablation-dashboard", type=Path, default=None)
    ap.add_argument("--stability", type=Path, default=None)
    ap.add_argument("--audit-dir", type=Path, default=None,
                    help="Run directory of raw audit_*.json files (Layer 2)")
    ap.add_argument("--paper", type=Path, default=None,
                    help="PAPER.md to check table fidelity against (Layer 3)")
    args = ap.parse_args()

    rep = Report()
    dashboard = json.loads(args.dashboard.read_text(encoding="utf-8"))
    model = recompute(dashboard)

    check_dashboard(model, dashboard, rep)

    if args.audit_dir:
        check_raw(model, args.audit_dir, rep)

    ablation_model = None
    if args.ablation_dashboard:
        ablation_model = recompute(
            json.loads(args.ablation_dashboard.read_text(encoding="utf-8")))

    stability = None
    if args.stability:
        stability = json.loads(args.stability.read_text(encoding="utf-8"))

    if args.paper:
        check_paper(args.paper, model, ablation_model, stability, rep)

    return rep.summary()

if __name__ == "__main__":
    sys.exit(main())
