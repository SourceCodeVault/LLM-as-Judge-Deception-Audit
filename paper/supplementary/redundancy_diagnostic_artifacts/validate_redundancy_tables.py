#!/usr/bin/env python3
"""
validate_redundancy_tables.py — Verify generated redundancy_tables.md against source CSVs.

Follows the pattern of tools/validate_paper_tables.py: parses markdown tables,
recomputes every cell from source CSVs, reports mismatches.

Usage:
    python paper/supplementary/redundancy_diagnostic_artifacts/validate_redundancy_tables.py
    
    # with explicit paths:
    python ...validate_redundancy_tables.py \\
        --tables .../redundancy_tables.md \\
        --alpha-csv .../compressed_rulebook_alpha_seed_and_reruns_available.csv \\
        --flicker-csv .../cluster_flicker_summary_reruns.csv
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Import core functions from the generation script
sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_redundancy_tables import (
    parse_csv_records,
    hist_fires_all_5,
    _DEFAULT_ALPHA,
    _DEFAULT_FLICKER,
    _DEFAULT_OUT,
)
# Back-compat alias
parse_kv_records = parse_csv_records

NUM = re.compile(r"[-+]?\d[\d,]*\.?\d*(?:[eE][-+]?\d+)?")

# ── Reporting (same pattern as validate_paper_tables.py) ───────────────────

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
            print("FAILED: tables are NOT faithful to the CSV source data.")
            return 1
        if self.unverified:
            print("PASSED with warnings.")
            return 0
        print("PASSED: every cell matches the CSV source data.")
        return 0

# ── Helpers ────────────────────────────────────────────────────────────────

def strip_md(cell: str) -> str:
    return cell.replace("**", "").replace("*", "").strip()

def nums(cell: str) -> list[float]:
    clean = strip_md(cell)
    return [float(t.replace(",", "")) for t in NUM.findall(clean)]

def close(shown: float, true: float, dp: int) -> bool:
    return abs(shown - true) <= 0.5 * 10**(-dp) + 1e-9

def dp_of(token: str) -> int:
    return len(token.split(".")[1]) if "." in token else 0

def extract_tables(text: str) -> list[list[list[str]]]:
    """Return all markdown tables as lists of rows of cells."""
    tables, current = [], []
    for line in text.splitlines():
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            current.append(cells)
        else:
            if len(current) >= 2:
                tables.append(current)
            current = []
    if len(current) >= 2:
        tables.append(current)
    return tables

# ── Table-specific checkers ────────────────────────────────────────────────

def _check_alpha_table(tbl: list[list[str]],
                       alpha_recs: list[dict[str, str]],
                       rep: Report) -> None:
    by_spec = {r["spec"]: r for r in alpha_recs}
    for row in tbl[1:]:
        spec = strip_md(row[0])
        r = by_spec.get(spec)
        if r is None:
            rep.skip(f"alpha row {spec!r}: not in source CSV")
            continue

        # col 1: Labels (int)
        shown = nums(row[1])
        if shown and int(shown[0]) != int(r["labels"]):
            rep.fail(f"alpha/{spec} Labels: shows {int(shown[0])}, CSV={r['labels']}")
        else:
            rep.ok()

        # col 2: Cases (int)
        shown = nums(row[2])
        if shown and int(shown[0]) != int(r["cases"]):
            rep.fail(f"alpha/{spec} Cases: shows {int(shown[0])}, CSV={r['cases']}")
        else:
            rep.ok()

        # col 3: Runs (int)
        shown = nums(row[3])
        if shown and int(shown[0]) != int(r["runs"]):
            rep.fail(f"alpha/{spec} Runs: shows {int(shown[0])}, CSV={r['runs']}")
        else:
            rep.ok()

        # col 4: α (MASI) (3dp)
        shown = nums(row[4])
        true_val = float(r["alpha_masi"])
        if shown and not close(shown[0], true_val, 3):
            rep.fail(f"alpha/{spec} α: shows {shown[0]}, CSV={true_val:.6f}")
        else:
            rep.ok()

        # col 5: Obs. Disagreement (3dp)
        shown = nums(row[5])
        true_val = float(r["observed_disagreement"])
        if shown and not close(shown[0], true_val, 3):
            rep.fail(f"alpha/{spec} Obs.Dis.: shows {shown[0]}, CSV={true_val:.6f}")
        else:
            rep.ok()

        # col 6: Exp. Disagreement (3dp)
        shown = nums(row[6])
        true_val = float(r["expected_disagreement"])
        if shown and not close(shown[0], true_val, 3):
            rep.fail(f"alpha/{spec} Exp.Dis.: shows {shown[0]}, CSV={true_val:.6f}")
        else:
            rep.ok()


def _check_flicker_table(tbl: list[list[str]],
                         flicker_recs: list[dict[str, str]],
                         rep: Report) -> None:
    nt = {r["cluster"]: r for r in flicker_recs if r["spec"] == "natural_tight"}
    for row in tbl[1:]:
        cluster = strip_md(row[0])
        r = nt.get(cluster)
        if r is None:
            rep.skip(f"flicker row {cluster!r}: not in source CSV")
            continue

        # col 1: Members
        members_shown = strip_md(row[1])
        if members_shown != r["members"]:
            rep.fail(f"flicker/{cluster} Members: shows {members_shown!r}, "
                     f"CSV={r['members']!r}")
        else:
            rep.ok()

        # col 2: Cases Seen (int)
        shown = nums(row[2])
        if shown and int(shown[0]) != int(r["cases_seen"]):
            rep.fail(f"flicker/{cluster} Cases Seen: shows {int(shown[0])}, "
                     f"CSV={r['cases_seen']}")
        else:
            rep.ok()

        # col 3: Fires All 5 (int, from histogram)
        fa5 = hist_fires_all_5(r["hist_fired_passes"])
        shown = nums(row[3])
        if shown and int(shown[0]) != fa5:
            rep.fail(f"flicker/{cluster} Fires All 5: shows {int(shown[0])}, "
                     f"histogram={fa5}")
        else:
            rep.ok()

        # col 4: Flicker Rate (3dp)
        shown = nums(row[4])
        true_val = float(r["flicker_given_seen"])
        if shown and not close(shown[0], true_val, 3):
            rep.fail(f"flicker/{cluster} Flicker Rate: shows {shown[0]}, "
                     f"CSV={true_val:.6f}")
        else:
            rep.ok()

        # col 5: Mean Fire Rate When Seen (3dp)
        shown = nums(row[5])
        true_val = float(r["mean_fire_rate_given_seen"])
        if shown and not close(shown[0], true_val, 3):
            rep.fail(f"flicker/{cluster} Mean Fire Rate: shows {shown[0]}, "
                     f"CSV={true_val:.6f}")
        else:
            rep.ok()

# ── CLI ────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--tables", type=Path, default=_DEFAULT_OUT,
                    help="Generated redundancy_tables.md to validate")
    ap.add_argument("--alpha-csv", type=Path, default=_DEFAULT_ALPHA,
                    help="Source alpha CSV")
    ap.add_argument("--flicker-csv", type=Path, default=_DEFAULT_FLICKER,
                    help="Source flicker CSV")
    args = ap.parse_args()

    rep = Report()

    # ── Load source data ──
    alpha_recs = parse_csv_records(args.alpha_csv)
    flicker_recs = parse_csv_records(args.flicker_csv)

    # ── Parse generated tables ──
    text = args.tables.read_text(encoding="utf-8")
    tables = extract_tables(text)

    rep.section("Table fidelity: redundancy_tables.md vs source CSVs")

    alpha_seen = False
    flicker_seen = False
    for tbl in tables:
        header = " | ".join(tbl[0])
        if "α (MASI)" in header and "Obs. Disagreement" in header:
            alpha_seen = True
            _check_alpha_table(tbl, alpha_recs, rep)
        elif "Flicker Rate" in header and "Fires All 5" in header:
            flicker_seen = True
            _check_flicker_table(tbl, flicker_recs, rep)

    if not alpha_seen:
        rep.skip("could not find alpha table in generated markdown")
    if not flicker_seen:
        rep.skip("could not find flicker table in generated markdown")

    return rep.summary()

if __name__ == "__main__":
    sys.exit(main())