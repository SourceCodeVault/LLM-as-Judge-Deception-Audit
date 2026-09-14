#!/usr/bin/env python3
"""
Test harness for compute_compressed_alpha, evaluate_compressed_rulebook, and measure_cluster_flicker.

Validates mathematical correctness against NLTK standards and synthetic edge cases.
"""

import csv
import math
import sys
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest

# Ensure scripts directory is on path for imports (Finding 3: Import Path Resolution)
_repo_root = Path(__file__).resolve().parents[1]
_scripts_dir = _repo_root / "rulebook-redundancy-analysis" / "scripts"
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))


# ============================================================================
# POMODORO 1, ACTION 1: Test masi_distance against NLTK
# ============================================================================

def test_masi_distance_identical():
    """MASI distance should be 0.0 for identical sets."""
    from compute_compressed_alpha import masi_distance
    
    a = frozenset({"J1", "J2"})
    b = frozenset({"J1", "J2"})
    assert masi_distance(a, b) == 0.0


def test_masi_distance_disjoint():
    """MASI distance should be 1.0 for disjoint sets."""
    from compute_compressed_alpha import masi_distance
    
    a = frozenset({"J1", "J2"})
    b = frozenset({"F1", "F2"})
    result = masi_distance(a, b)
    assert result == 1.0


def test_masi_distance_subset():
    """MASI distance for subset relationship (proper subset with overlap)."""
    from compute_compressed_alpha import masi_distance
    
    # a is subset of b but not equal
    a = frozenset({"J1"})
    b = frozenset({"J1", "J2", "J3"})
    result = masi_distance(a, b)
    # J1 is in both, union = 3, intersection = 1
    # Jaccard = 1/3, inter == min(len(a), len(b)) so m = 2/3
    # Distance = 1 - (2/3 * 1/3) = 1 - 2/9 = 7/9 ≈ 0.777...
    expected = 1.0 - (2.0 / 3.0) * (1.0 / 3.0)
    assert math.isclose(result, expected, rel_tol=1e-9)


def test_masi_distance_partial_overlap():
    """MASI distance for partial overlap (neither subset nor disjoint)."""
    from compute_compressed_alpha import masi_distance
    
    a = frozenset({"J1", "J2"})
    b = frozenset({"J2", "J3"})
    result = masi_distance(a, b)
    # intersection = {J2} = 1, union = {J1, J2, J3} = 3
    # Jaccard = 1/3, inter > 0 but not min(len(a), len(b))
    # So m = 1/3
    # Distance = 1 - (1/3 * 1/3) = 1 - 1/9 = 8/9 ≈ 0.888...
    expected = 1.0 - (1.0 / 3.0) * (1.0 / 3.0)
    assert math.isclose(result, expected, rel_tol=1e-9)


def test_masi_distance_empty_empty():
    """MASI distance should be 0.0 for empty-empty."""
    from compute_compressed_alpha import masi_distance
    
    a = frozenset()
    b = frozenset()
    assert masi_distance(a, b) == 0.0


def test_masi_distance_symmetry():
    """MASI distance should be symmetric: masi(a, b) == masi(b, a)."""
    from compute_compressed_alpha import masi_distance
    
    a = frozenset({"J1", "J2", "F1"})
    b = frozenset({"J2", "F1", "U1"})
    assert masi_distance(a, b) == masi_distance(b, a)


def test_masi_distance_against_nltk():
    """Compare Giorgi's masi_distance against nltk.metrics.distance.masi_distance."""
    # Use pytest.importorskip to properly skip if NLTK is not installed (Finding 1)
    nltk_distance = pytest.importorskip("nltk.metrics.distance", reason="NLTK not installed")
    nltk_masi_distance = nltk_distance.masi_distance

    from compute_compressed_alpha import masi_distance
    
    test_pairs = [
        (frozenset({"J1", "J2"}), frozenset({"J1", "J2"})),  # identical
        (frozenset({"J1", "J2"}), frozenset({"F1", "F2"})),  # disjoint
        (frozenset({"J1"}), frozenset({"J1", "J2", "J3"})),  # subset
        (frozenset({"J1", "J2"}), frozenset({"J2", "J3"})),  # partial overlap
    ]
    
    for a, b in test_pairs:
        giorgi_result = masi_distance(a, b)
        nltk_result = nltk_masi_distance(a, b)
        # Relax tolerance to 2e-3 to account for NLTK's literal constants (0.67, 0.33)
        # vs Giorgi's exact fractions (2/3, 1/3) - ~0.14% difference (Finding 2)
        assert math.isclose(giorgi_result, nltk_result, rel_tol=2e-3), (
            f"MASI mismatch for {a} vs {b}: "
            f"Giorgi={giorgi_result}, NLTK={nltk_result}"
        )


# ============================================================================
# POMODORO 1, ACTION 2: Test compress_row with synthetic data
# ============================================================================

def test_compress_row_natural_tight_spec():
    """compress_row with natural_tight spec should correctly merge F1+F2 and J1+J2."""
    from evaluate_compressed_rulebook import compress_row, COMPRESSION_SPECS
    
    # Synthetic row: J1="1", F1="1", J3="0"
    # natural_tight spec:
    #   F12 <- ["F1", "F2"]  -> F1=1, so F12 fires
    #   J12 <- ["J1", "J2"]  -> J1=1, so J12 fires
    #   J345 <- ["J3", "J4", "J5"] -> J3=0, so J345 does NOT fire
    
    synthetic_row = {
        "case_id": "test_case",
        "pass_id": "pass_1",
        "J1": "1",
        "J2": "0",
        "J3": "0",
        "J4": "0",
        "J5": "0",
        "F1": "1",
        "F2": "0",
        "F3": "0",
        "H1": "0",
        "S1": "0",
        "U1": "0",
        "U2": "0",
        "U3": "0",
        "U4": "0",
    }
    
    spec = COMPRESSION_SPECS["natural_tight"]
    result = compress_row(synthetic_row, spec)
    
    assert isinstance(result, frozenset)
    assert "F12" in result, f"Expected F12 in {result}"
    assert "J12" in result, f"Expected J12 in {result}"
    assert "J345" not in result, f"Did NOT expect J345 in {result}"
    # Relax over-strict exact equality - use containment checks instead (Finding 5)
    # assert result == frozenset({"F12", "J12"})  # Too strict - breaks if spec adds clusters


def test_compress_row_missing_key_handled_as_zero():
    """compress_row should treat missing keys as 0 (not firing)."""
    from evaluate_compressed_rulebook import compress_row
    
    # Row with only J1 specified; others missing -> treated as 0
    sparse_row = {
        "case_id": "test_case",
        "pass_id": "pass_1",
        "J1": "1",
        # All other keys missing
    }
    
    # Add cluster that must NOT fire to verify missing→0 semantics (Finding 4)
    spec = {"J12": ["J1", "J2"], "F_only": ["F1"]}
    result = compress_row(sparse_row, spec)
    
    # J1=1 fires, J2=0 (missing means 0), so J12 fires
    assert "J12" in result, f"Expected J12 in {result}"
    # F1 is missing entirely → treated as 0 → F_only should NOT fire
    assert "F_only" not in result, f"Did NOT expect F_only in {result} (missing key should be 0)"


# ============================================================================
# POMODORO 1, ACTION 3: Test summarize_cluster_flicker with synthetic data
# ============================================================================

def test_summarize_cluster_flicker_synthetic_5pass():
    """Test flicker detection with 5-pass synthetic data where J_ALL fires 3 times."""
    from measure_cluster_flicker import summarize_cluster_flicker
    
    # Create synthetic data:
    # - 1 case with 5 passes
    # - J_ALL fires in passes 1, 2, 3 (3 out of 5)
    # - This means: seen_cases=1, unanimous_cases=0, flicker_cases=1
    # - mean_fire_rate_given_seen = 3/5 = 0.6
    
    spec = {
        "J_ALL": ["J1", "J2", "J3", "J4", "J5"],
        "F1": ["F1"],
    }
    
    # 5 passes for the same case
    synthetic_rows = []
    for pass_num in range(1, 6):
        # J1-J3 fire in passes 1, 2, 3; none fire in passes 4, 5
        if pass_num <= 3:
            row = {
                "case_id": "CASE_001",
                "pass_id": f"pass_{pass_num}",
                "J1": "1",
                "J2": "1",
                "J3": "1",
                "J4": "0",
                "J5": "0",
                "F1": "0",
            }
        else:
            row = {
                "case_id": "CASE_001",
                "pass_id": f"pass_{pass_num}",
                "J1": "0",
                "J2": "0",
                "J3": "0",
                "J4": "0",
                "J5": "0",
                "F1": "0",
            }
        synthetic_rows.append(row)
    
    summary, case_rows = summarize_cluster_flicker(synthetic_rows, "test_spec", spec)
    
    # Find the J_ALL row in summary
    j_all_summary = next((row for row in summary if row["cluster"] == "J_ALL"), None)
    assert j_all_summary is not None, "J_ALL not found in summary"
    
    assert j_all_summary["cases_seen"] == 1, f"Expected cases_seen=1, got {j_all_summary['cases_seen']}"
    assert j_all_summary["unanimous_cases"] == 0, f"Expected unanimous_cases=0, got {j_all_summary['unanimous_cases']}"
    assert j_all_summary["flicker_cases"] == 1, f"Expected flicker_cases=1, got {j_all_summary['flicker_cases']}"
    assert math.isclose(j_all_summary["mean_fire_rate_given_seen"], 0.6, rel_tol=1e-9), (
        f"Expected mean_fire_rate_given_seen=0.6, got {j_all_summary['mean_fire_rate_given_seen']}"
    )


def test_summarize_cluster_flicker_unanimous_case():
    """Test that unanimous cases (all passes fire) are counted correctly."""
    from measure_cluster_flicker import summarize_cluster_flicker
    
    # Create data: 1 case with 3 passes, all fire
    spec = {"J12": ["J1", "J2"]}
    
    synthetic_rows = [
        {"case_id": "CASE_002", "pass_id": f"pass_{i}", "J1": "1", "J2": "1"}
        for i in range(1, 4)
    ]
    
    summary, case_rows = summarize_cluster_flicker(synthetic_rows, "test_spec", spec)
    j12_summary = next((row for row in summary if row["cluster"] == "J12"), None)
    
    assert j12_summary["cases_seen"] == 1
    assert j12_summary["unanimous_cases"] == 1
    assert j12_summary["flicker_cases"] == 0


# ============================================================================
# Additional validation tests for alpha calculation
# ============================================================================

def test_krippendorff_alpha_perfect_agreement():
    """Alpha should be 1.0 when all annotators agree perfectly."""
    from compute_compressed_alpha import krippendorff_alpha_masi
    
    # 3 cases, each with 2 coders who agree exactly
    items = [
        [frozenset({"J1"}), frozenset({"J1"})],
        [frozenset({"J2", "F1"}), frozenset({"J2", "F1"})],
        [frozenset(), frozenset()],  # empty agreement
    ]
    
    alpha, observed, expected = krippendorff_alpha_masi(items)
    assert not math.isnan(alpha), "Alpha should not be NaN"
    assert math.isclose(alpha, 1.0, rel_tol=1e-6), f"Expected alpha=1.0, got {alpha}"


def test_krippendorff_alpha_total_disagreement():
    """Alpha should be 0.0 (or close to) when annotations are random."""
    from compute_compressed_alpha import krippendorff_alpha_masi
    
    # Items with complete disagreement between coders
    items = [
        [frozenset({"A"}), frozenset({"B"})],
        [frozenset({"C"}), frozenset({"D"})],
    ]
    
    alpha, observed, expected = krippendorff_alpha_masi(items)
    # With perfect disagreement, alpha approaches 0
    # Due to MASI distance properties, may not be exactly 0
    assert not math.isnan(alpha), "Alpha should not be NaN"
    assert alpha < 0.5, f"Expected low alpha with disagreement, got {alpha}"

def test_compress_row_handles_integer_types_safely():
    """
    Document that compress_row survives non-string inputs.
    Giorgi's code assumes csv.DictReader (always strings).
    This test verifies it also handles raw integers gracefully.
    """
    from evaluate_compressed_rulebook import compress_row

    integer_row = {"case_id": "test_case_int", "pass_id": "pass_1", "J1": 1, "J2": 0}
    spec = {"J12": ["J1", "J2"]}

    result = compress_row(integer_row, spec)
    assert "J12" in result
    
# ============================================================================
# Integration test: full pipeline with synthetic data
# ============================================================================

def test_full_pipeline_synthetic():
    """Test the full pipeline: compress -> alpha computation."""
    from compute_compressed_alpha import build_items, krippendorff_alpha_masi
    from evaluate_compressed_rulebook import compress_row, COMPRESSION_SPECS
    
    # Create minimal synthetic dataset
    synthetic_rows = [
        {"case_id": "CASE_A", "pass_id": "run_1", "J1": "1", "J2": "0", "F1": "1", "F2": "0"},
        {"case_id": "CASE_A", "pass_id": "run_2", "J1": "1", "J2": "1", "F1": "1", "F2": "1"},
    ]
    
    spec = COMPRESSION_SPECS["j_only"]
    items, n_cases, n_runs = build_items(synthetic_rows, spec, include_incomplete=False)
    
    assert n_cases == 1
    assert n_runs == 2
    assert len(items) == 1
    assert len(items[0]) == 2
    
    alpha, observed, expected = krippendorff_alpha_masi(items)
    assert not math.isnan(alpha), "Alpha should not be NaN for valid input"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])