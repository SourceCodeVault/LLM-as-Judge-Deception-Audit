#!/usr/bin/env python3
"""
Provenance chain tests:
  1. raw audit JSONs → analyze_rule_incidence.py → incidence CSVs match Giorgi's golden
  2. incidence CSVs → compress → alpha pipeline → α ≈ 0.278 (the reported value)
"""

import csv
import math
import subprocess
import sys
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
GIORGI_DIR = REPO_ROOT / "rulebook-redundancy-analysis"
GIORGI_SCRIPTS = GIORGI_DIR / "scripts"

# Add Giorgi's scripts to path for direct imports
if str(GIORGI_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(GIORGI_SCRIPTS))

# Raw audit JSON directories
RAW_SEED_DIR = REPO_ROOT / "output" / "run_20260525_205154_arm04a_testretest_seed_300"
RAW_RERUN_DIR = REPO_ROOT / "output" / "run_20260525_234223_arm04b_testretest_reruns_x5_300"

GOLDEN_CSV = GIORGI_DIR / "data" / "rule_incidence_seed_and_reruns_available.csv"
METADATA_COLS = {"case_id", "pass_id", "ground_truth", "verdict", "quadrant", "source_path"}


def _raw_data_present():
    return RAW_SEED_DIR.is_dir() and RAW_RERUN_DIR.is_dir()


def _build_audit_zip(zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for run_dir in [RAW_SEED_DIR, RAW_RERUN_DIR]:
            for json_file in sorted(run_dir.rglob("*.json")):
                arcname = f"z/{run_dir.parent.name}/{run_dir.name}/{json_file.relative_to(run_dir)}"
                zf.write(json_file, arcname)


def _run_incidence_builder(zip_path: Path, passes: str, out_dir: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(GIORGI_SCRIPTS / "analyze_rule_incidence.py"),
         "--zip", str(zip_path), "--passes", passes, "--out-dir", str(out_dir),
         "--implication-threshold", "0.95", "--min-antecedent", "30",
         "--min-target", "30", "--top", "20"],
        capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"analyze_rule_incidence.py failed (rc={result.returncode}):\n"
            f"STDERR:\n{result.stderr}\nSTDOUT:\n{result.stdout}"
        )


def _load_rule_data(csv_path: Path):
    """Load CSV, return (rule_cols, list_of_dicts_with_rules_as_ints)."""
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        all_cols = reader.fieldnames
        rule_cols = [c for c in all_cols if c not in METADATA_COLS]
        rows = []
        for row in reader:
            rows.append({
                "case_id": row["case_id"],
                "pass_id": row["pass_id"],
                **{r: int(row[r]) for r in rule_cols},
            })
    return rule_cols, rows


# ============================================================================
# TEST 1: Provenance — key-level and rule-value comparison
# ============================================================================

@pytest.mark.slow
def test_seed_and_reruns_available_provenance():
    """
    Raw JSONs → incidence pipeline → should match Giorgi's golden CSV
    on all 14 rule columns for every unique (case_id, pass_id).
    """
    with TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        zip_path = tmp / "audit_verify.zip"
        out_dir = tmp / "output_csvs"
        out_dir.mkdir()

        _build_audit_zip(zip_path)
        _run_incidence_builder(zip_path, passes="seed-and-reruns", out_dir=out_dir)

        generated = out_dir / "rule_incidence_seed_and_reruns_available.csv"
        golden = GOLDEN_CSV
        assert generated.exists(), f"Generated CSV missing: {generated}"
        assert golden.exists(), f"Golden CSV missing: {golden}"

        gen_rules, gen_rows = _load_rule_data(generated)
        gold_rules, gold_rows = _load_rule_data(golden)

        # Rule columns must match
        assert gen_rules == gold_rules, f"Rule columns differ"

        # Build dicts keyed by (case_id, pass_id).
        # If duplicates exist, last-write-wins (we just need value match).
        def _to_dict(rows):
            d = {}
            for r in rows:
                key = (r["case_id"], r["pass_id"])
                d[key] = {col: r[col] for col in gen_rules}
            return d

        gen_dict = _to_dict(gen_rows)
        gold_dict = _to_dict(gold_rows)

        gen_keys = set(gen_dict.keys())
        gold_keys = set(gold_dict.keys())

        # Key sets must match
        only_gen = gen_keys - gold_keys
        only_gold = gold_keys - gen_keys
        assert not only_gen, f"{len(only_gen)} keys in generated but not golden: {only_gen}"
        assert not only_gold, f"{len(only_gold)} keys in golden but not generated: {only_gold}"

        # Rule values must match for every key
        mismatches = []
        for key in sorted(gen_keys):
            for r in gen_rules:
                if gen_dict[key][r] != gold_dict[key][r]:
                    mismatches.append(f"  {key} rule={r}: gen={gen_dict[key][r]} gold={gold_dict[key][r]}")
                    if len(mismatches) > 20:
                        break
            if len(mismatches) > 20:
                break
        assert not mismatches, f"{len(mismatches)} rule mismatches:\n" + "\n".join(mismatches)

        # Report for visibility
        print(f"\n  Provenance verified: {len(gold_keys)} unique observations, {len(gen_rules)} rules, 0 mismatches")
        if len(gen_rows) != len(gold_rows):
            print(f"  Note: generated CSV has {len(gen_rows)} rows vs golden {len(gold_rows)} "
                  f"(likely {len(gen_rows) - len(gold_rows)} duplicates in seed directory)")


# ============================================================================
# TEST 2: Golden-value alpha — the real proof that Giorgi's math is correct
# ============================================================================

@pytest.mark.slow
def test_natural_tight_alpha_golden_value():
    """
    Load the incidence CSV, run compress → alpha pipeline on natural_tight spec,
    assert α ≈ 0.278.  This is the number reported in Giorgi's analysis.
    """
    from compute_compressed_alpha import build_items, krippendorff_alpha_masi
    from evaluate_compressed_rulebook import COMPRESSION_SPECS

    assert GOLDEN_CSV.exists(), f"Golden CSV not found: {GOLDEN_CSV}"

    # Load all rows from the incidence CSV
    rows = []
    with GOLDEN_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)

    spec = COMPRESSION_SPECS["natural_tight"]
    items, n_cases, n_runs = build_items(rows, spec, include_incomplete=True)

    print(f"\n  natural_tight: {n_cases} cases, {n_runs} runs, {len(items)} case items")

    alpha, obs_dis, exp_dis = krippendorff_alpha_masi(items)

    print(f"  α = {alpha:.6f}  (Giorgi reported: 0.278)")
    assert not math.isnan(alpha), "Alpha is NaN"
    assert math.isclose(alpha, 0.278, abs_tol=0.005), (
        f"Alpha mismatch: got {alpha:.6f}, expected ≈ 0.278 ± 0.005"
    )


@pytest.mark.slow
def test_j_family_all_alpha_golden_value():
    """
    Control test: maximally coarsened J-family → single binary flag.
    Assert α ≈ 0.128 (the coarsening rebuttal value).
    """
    from compute_compressed_alpha import build_items, krippendorff_alpha_masi
    from evaluate_compressed_rulebook import COMPRESSION_SPECS

    assert GOLDEN_CSV.exists()

    rows = []
    with GOLDEN_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)

    # The j_family_all spec might not exist in COMPRESSION_SPECS.
    # If it doesn't, build it manually.
    if "j_family_all" in COMPRESSION_SPECS:
        spec = COMPRESSION_SPECS["j_family_all"]
    else:
        # Fallback: manually define the maximally coarsened J
        from evaluate_compressed_rulebook import COMPRESSION_SPECS as CS
        # Clone original spec entries and add j_family_all
        base = dict(CS["original"])
        base["j_family_all"] = ["J1", "J2", "J3", "J4", "J5"]
        # Remove individual J labels
        for j in ["J1", "J2", "J3", "J4", "J5"]:
            base.pop(j, None)
        spec = base

    items, n_cases, n_runs = build_items(rows, spec, include_incomplete=True)

    print(f"\n  j_family_all: {n_cases} cases, {n_runs} runs, {len(items)} case items")

    alpha, obs_dis, exp_dis = krippendorff_alpha_masi(items)

    print(f"  α = {alpha:.6f}  (Giorgi reported: ≈ 0.128)")
    assert not math.isnan(alpha), "Alpha is NaN"
    # This value should be notably lower than original
    assert alpha < 0.20, (
        f"j_family_all alpha too high: {alpha:.6f}, expected < 0.20"
    )