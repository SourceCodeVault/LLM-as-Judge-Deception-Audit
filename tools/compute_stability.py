#!/usr/bin/env python3
"""
Stability Metrics — Test-Retest & Baseline Reliability for Correspondence Auditor.
Computes pre-registered reliability metrics across 5 rerun iterations.

Outputs:
    - stability_report.json: Machine-readable metrics
    - stability_report.html: One-page HTML report for dashboard attachment

    Usage of compute_stability.py
The script requires explicit command-line arguments. You run it from your terminal like this:

python compute_stability.py --rerun-dir output/my_stability_test --output-dir output/my_stability_test

(You can also optionally pass --gate-b-key path/to/key.csv if you are computing the Gate B baseline kappa).
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Dataclasses for Results
# ---------------------------------------------------------------------------


@dataclass
class StabilityMetrics:
    """Container for all stability metric results."""
    icc_2_1: float
    icc_ci: tuple[float, float]
    krippendorff_alpha: float
    cohen_kappa_quadrant_mean: float
    cohen_kappa_quadrant_range: tuple[float, float]
    cohen_kappa_gate_b: float | None
    
    # Metadata
    n_cases: int
    n_runs: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------
def detect_rerun_pattern(rerun_dirs: list[Path]) -> tuple[bool, re.Pattern | None]:
    """
    Detect whether reruns are stored in subdirectories or in filenames.
    Returns: (is_filename_based, regex_pattern)
    """
    # Check if files contain __rerun_NN pattern
    sample_files = []
    for d in rerun_dirs:
        sample_files.extend(d.rglob("audit_*.json"))
    
    if not sample_files:
        return False, None
    
    # Look for __rerun_XX pattern in filenames
    rerun_pattern = re.compile(r"__rerun_(\d+)")
    matches = 0
    for f in sample_files[:20]:  # Check first 20 files
        if rerun_pattern.search(f.name):
            matches += 1
    
    if matches >= 10:  # Threshold: if >50% of sample files have rerun suffix
        return True, rerun_pattern
    
    return False, None

def find_rerun_directories(base_dir: Path) -> list[Path]:
    """
    Discover rerun directories or detect filename-based rerun pattern.
    Expected naming for directories: run_001, run_002, ... or rerun_1, rerun_2, ...
    If no subdirectories found, returns [base_dir] and relies on filename parsing.
    """
    if not base_dir.exists():
        raise FileNotFoundError(f"Rerun directory not found: {base_dir}")
    
    run_pattern = re.compile(r"(?:run_|rerun_)(\d+)", re.IGNORECASE)
    candidates = []
    
    for item in base_dir.iterdir():
        if item.is_dir():
            match = run_pattern.match(item.name)
            if match:
                candidates.append((int(match.group(1)), item))
    
    if candidates:
        candidates.sort(key=lambda x: x[0])
        return [item for _, item in candidates[:5]]
    
    # No subdirectories found — check if this is a filename-based structure
    # by looking for audit files with __rerun_XX in the name
    has_rerun_files = any(
        re.search(r"__rerun_\d+", f.name) 
        for f in base_dir.rglob("audit_*.json")
    )
    
    if has_rerun_files:
        # Return base_dir — load_rerun_data will parse filenames
        return [base_dir]
    
    return [base_dir]


def load_case_json(json_path: Path) -> dict:
    """Load and parse a single case JSON."""
    return json.loads(json_path.read_text(encoding="utf-8"))


def load_rerun_data(rerun_dirs: list[Path]) -> dict[str, dict]:
    """
    Load all case data across reruns.
    Supports two formats:
      1. Directory-based: run_001/, run_002/, ... subdirectories
      2. Filename-based: audit_xxx__rerun_01.json (flat structure)
    Returns: dict[case_id] -> {run_index: case_data}
    """
    case_map: dict[str, dict] = {}
    
    # Detect which pattern we're dealing with
    is_filename_based, rerun_pattern = detect_rerun_pattern(rerun_dirs)
    
    for run_idx, run_dir in enumerate(rerun_dirs):
        audit_files = sorted(run_dir.rglob("audit_*.json"))
        error_files = sorted(run_dir.rglob("audit_*.error.json"))
        all_files = sorted(set(audit_files + error_files), key=lambda p: str(p))
        
        for file_path in all_files:
            try:
                data = load_case_json(file_path)
            except (json.JSONDecodeError, OSError):
                continue
            
            # Determine the effective run index
            effective_run_idx = run_idx
            
            if is_filename_based and rerun_pattern:
                match = rerun_pattern.search(file_path.name)
                if match:
                    # Convert 1-based rerun index to 0-based
                    effective_run_idx = int(match.group(1)) - 1
            
            case_id = data.get("case_id")
            if not case_id:
                # Derive case_id from filename, stripping the __rerun_XX suffix
                stem = file_path.stem
                if is_filename_based and rerun_pattern:
                    stem = rerun_pattern.sub("", stem)
                case_id = stem
            
            if case_id not in case_map:
                case_map[case_id] = {}
            
            case_map[case_id][effective_run_idx] = data
    
    return case_map


def verify_ablation_arm(case_map: dict[str, dict]) -> bool:
    """
    Defensive check: Verify all cases have arm='ABLATION_NOISE' metadata.
    
    This protects against the implicit contract between run.py (which selects
    ablation_noise variant for test-retest per §11) and compute_stability.py
    (which assumes the L2 intercept has stamped the output).
    
    The orchestrator should stamp arm='ABLATION_NOISE' into the output JSON
    when the ablation_noise variant is used. This function verifies that
    stamping occurred.
    
    Returns True if all cases pass the check, False otherwise.
    """
    non_ablation_cases = []
    missing_arm_cases = []
    
    for case_id, runs_data in case_map.items():
        # Check the first available run for metadata
        sample_data = next(iter(runs_data.values()), None)
        if sample_data is None:
            continue
        
        arm = sample_data.get("metadata", {}).get("arm")
        if arm is None:
            missing_arm_cases.append(case_id)
        elif arm != "ABLATION_NOISE":
            non_ablation_cases.append((case_id, arm))
    
    if missing_arm_cases:
        print(f"\n⚠️  WARNING: Detected {len(missing_arm_cases)} cases with missing arm metadata:")
        for case_id in missing_arm_cases[:5]:
            print(f"    - {case_id}: arm=None")
        if len(missing_arm_cases) > 5:
            print(f"    ... and {len(missing_arm_cases) - 5} more")
        print("    The orchestrator should stamp arm='ABLATION_NOISE' when ablation_noise variant runs.")
        print("    This is a prerequisite for valid test-retest stability metrics.")
        return False
    
    if non_ablation_cases:
        print(f"\n⚠️  WARNING: Detected {len(non_ablation_cases)} non-ablation cases:")
        for case_id, arm in non_ablation_cases[:5]:
            print(f"    - {case_id}: arm='{arm}'")
        if len(non_ablation_cases) > 5:
            print(f"    ... and {len(non_ablation_cases) - 5} more")
        print("    compute_stability.py expects only ABLATION_NOISE arm cases.")
        print("    Run run.py in test-retest mode to generate properly filtered reruns.")
        return False
    
    return True


def extract_verdicts(case_map: dict[str, dict], n_runs: int) -> np.ndarray:
    """
    Build case-by-run matrix of binary verdicts.
    APPROVE=0, BLOCK=1, NaN for missing.
    """
    matrix = np.full((len(case_map), n_runs), np.nan)
    
    for row_idx, (case_id, runs_data) in enumerate(case_map.items()):
        for run_idx in range(n_runs):
            if run_idx in runs_data:
                data = runs_data[run_idx]
                gap = data.get("compliance_gap", {})
                action = gap.get("auditor_recommended_action")
                
                if action == "BLOCK":
                    matrix[row_idx, run_idx] = 1.0
                elif action == "APPROVE":
                    matrix[row_idx, run_idx] = 0.0
    
    return matrix


def extract_quadrants(case_map: dict[str, dict], n_runs: int) -> np.ndarray:
    """
    Build case-by-run matrix of quadrant labels.
    Quadrants: VALIDATED_APPROVAL, FLAWED_APPROVAL, VALIDATED_BLOCK, FLAWED_BLOCK
    """
    quadrant_to_int = {
        "VALIDATED_APPROVAL": 0,
        "FLAWED_APPROVAL": 1,
        "VALIDATED_BLOCK": 2,
        "FLAWED_BLOCK": 3,
    }
    
    matrix = np.full((len(case_map), n_runs), np.nan)
    
    for row_idx, (case_id, runs_data) in enumerate(case_map.items()):
        for run_idx in range(n_runs):
            if run_idx in runs_data:
                data = runs_data[run_idx]
                gap = data.get("compliance_gap", {})
                quadrant = gap.get("quadrant")
                
                if quadrant in quadrant_to_int:
                    matrix[row_idx, run_idx] = quadrant_to_int[quadrant]
    
    return matrix


def extract_rules(case_map: dict[str, dict], n_runs: int) -> list[list[Optional[frozenset]]]:
    """
    Build list of rule sets per case per run.
    Returns: list of observers (runs) each containing items (cases).
    Uses None for missing data (distinct from empty frozenset).
    """
    n_cases = len(case_map)
    # None = missing data; empty frozenset = no rules fired
    result = [[None for _ in range(n_cases)] for _ in range(n_runs)]
    
    case_ids = list(case_map.keys())
    
    for col_idx, case_id in enumerate(case_ids):
        for run_idx in range(n_runs):
            if run_idx in case_map[case_id]:
                data = case_map[case_id][run_idx]
                rules = data.get("metadata", {}).get("rules_fired", [])
                # Empty list = no rules fired (valid observation)
                # None = missing data (pipeline failure)
                result[run_idx][col_idx] = frozenset(rules) if rules else frozenset()
    
    return result


# ---------------------------------------------------------------------------
# Metric Computations
# ---------------------------------------------------------------------------


def compute_icc(verdicts: np.ndarray) -> tuple[float, tuple[float, float]]:
    """
    Compute ICC(2,1) for binary verdicts.
    Uses pingouin.intraclass_corr.
    Returns: (point_estimate, (ci_lower, ci_upper))
    """
    try:
        import pingouin as pg
    except ImportError:
        raise ImportError("pingouin is required: pip install pingouin")
    
    n_cases, n_runs = verdicts.shape
    
    valid_rows = ~np.all(np.isnan(verdicts), axis=1)
    valid_verdicts = verdicts[valid_rows]
    
    if valid_verdicts.size == 0:
        return (np.nan, (np.nan, np.nan))
    
    records = []
    for case_idx in range(valid_verdicts.shape[0]):
        for run_idx in range(valid_verdicts.shape[1]):
            val = valid_verdicts[case_idx, run_idx]
            if not np.isnan(val):
                records.append({
                    "Observer": f"Run{run_idx}",
                    "Target": f"Case{case_idx}",
                    "Rating": int(val)
                })
    
    if len(records) < 10:
        return (np.nan, (np.nan, np.nan))
    
    df = pd.DataFrame(records)
    
    # If all valid verdicts are identical across runs for every single case, variance is zero (perfect agreement)
    if np.nanvar(valid_verdicts, axis=1).sum() == 0:
        return (1.0, (1.0, 1.0))

    icc_result = pg.intraclass_corr(
        data=df,
        targets="Target",
        raters="Observer",
        ratings="Rating",
    )
    
    icc_row = icc_result[icc_result["Type"] == "ICC2"]
    if icc_row.empty:
        return (np.nan, (np.nan, np.nan))
    
    point_est = icc_row["ICC"].values[0]
    # Fix: Handle both list-of-lists and numpy array for CI95%
    ci_raw = icc_row["CI95%"].values[0]
    if isinstance(ci_raw, (list, np.ndarray)):
        ci_lower, ci_upper = float(ci_raw[0]), float(ci_raw[1])
    else:
        # Single string format "x, y"
        ci_parts = str(ci_raw).split(",")
        ci_lower = float(ci_parts[0].strip())
        ci_upper = float(ci_parts[1].strip())
    
    return (point_est, (ci_lower, ci_upper))


def compute_krippendorff_alpha(rules_data: list[list[Optional[frozenset]]]) -> float:
    """
    Compute Krippendorff's alpha for set-valued rules using MASI distance.
    Uses nltk (krippendorff package doesn't support custom distance functions).
    """
    try:
        from nltk.metrics.agreement import AnnotationTask
        from nltk.metrics.distance import masi_distance
    except ImportError:
        raise ImportError("nltk required: pip install nltk")
    
    # --- ADD THIS SAFE WRAPPER ---
    def safe_masi_distance(label1, label2):
        if not label1 and not label2:
            return 0.0  # The distance between two empty sets is 0
        return masi_distance(label1, label2)
    # -----------------------------
    
    n_runs = len(rules_data)
    n_cases = len(rules_data[0])
    
    # Format: [(item, observer, label), ...]
    data = []
    for case_idx in range(n_cases):
        for run_idx in range(n_runs):
            rules = rules_data[run_idx][case_idx]
            if rules is not None:
                label = rules
                data.append((f"case{case_idx}", f"run{run_idx}", label))

    if not data:
        return np.nan
    
    # --- UPDATE THIS LINE TO USE THE WRAPPER ---
    task = AnnotationTask(data=data, distance=safe_masi_distance)
    return task.alpha()


def compute_cohen_kappa_quadrants(quadrants: np.ndarray) -> tuple[float, tuple[float, float]]:
    """
    Compute Cohen's kappa for all 10 pairwise run comparisons.
    Returns: (mean_kappa, (min_kappa, max_kappa))
    """
    from sklearn.metrics import cohen_kappa_score
    
    n_cases, n_runs = quadrants.shape
    
    kappas = []
    
    for i in range(n_runs):
        for j in range(i + 1, n_runs):
            col_i = quadrants[:, i]
            col_j = quadrants[:, j]
            
            valid_mask = ~np.isnan(col_i) & ~np.isnan(col_j)
            
            if valid_mask.sum() < 10:
                continue
            
            y_true = col_i[valid_mask].astype(int)
            y_pred = col_j[valid_mask].astype(int)
            
            kappa = cohen_kappa_score(y_true, y_pred)
            kappas.append(kappa)
    
    if not kappas:
        return (np.nan, (np.nan, np.nan))
    
    mean_kappa = np.mean(kappas)
    min_kappa = np.min(kappas)
    max_kappa = np.max(kappas)
    
    return (mean_kappa, (min_kappa, max_kappa))


def compute_cohen_kappa_gate_b(gate_b_key_path: Path) -> float | None:
    """
    Compute Cohen's kappa between human_label and gate_b_label.
    Returns None if file not found or invalid.
    """
    if not gate_b_key_path.exists():
        return None
    
    try:
        df = pd.read_csv(gate_b_key_path)
    except Exception:
        return None
    
    required_cols = {"human_label", "gate_b_label"}
    if not required_cols.issubset(df.columns):
        return None
    
    valid_labels = {"SUPPORTED", "CONTRADICTED", "UNSUPPORTED"}
    df = df[df["human_label"].isin(valid_labels) & df["gate_b_label"].isin(valid_labels)]
    
    if len(df) < 5:
        return None
    
    from sklearn.metrics import cohen_kappa_score
    
    kappa = cohen_kappa_score(df["human_label"], df["gate_b_label"])
    return kappa


# ---------------------------------------------------------------------------
# HTML Report Generation
# ---------------------------------------------------------------------------


def render_stability_html(metrics: StabilityMetrics, output_dir: Path) -> Path:
    """Generate one-page HTML stability report."""
    
    icc_str = f"{metrics.icc_2_1:.3f}" if not np.isnan(metrics.icc_2_1) else "—"
    icc_ci_str = f"[{metrics.icc_ci[0]:.3f}, {metrics.icc_ci[1]:.3f}]" if not np.isnan(metrics.icc_ci[0]) else "—"
    
    kripp_str = f"{metrics.krippendorff_alpha:.3f}" if not np.isnan(metrics.krippendorff_alpha) else "—"
    
    kappa_quad_str = f"{metrics.cohen_kappa_quadrant_mean:.3f}" if not np.isnan(metrics.cohen_kappa_quadrant_mean) else "—"
    kappa_range_str = f"[{metrics.cohen_kappa_quadrant_range[0]:.3f}, {metrics.cohen_kappa_quadrant_range[1]:.3f}]" if not np.isnan(metrics.cohen_kappa_quadrant_range[0]) else "—"
    
    kappa_gate_b_str = f"{metrics.cohen_kappa_gate_b:.3f}" if metrics.cohen_kappa_gate_b is not None and not np.isnan(metrics.cohen_kappa_gate_b) else "N/A"
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Stability Report · Test-Retest Reliability</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&family=Courier+Prime:wght@400;700&display=swap" rel="stylesheet">
<style>
body {{ font-family: 'Inter', sans-serif; color: #000; background: #fff; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.font-mono {{ font-family: 'Courier Prime', monospace; }}
.page {{ max-width: 210mm; margin: 2rem auto; padding: 18mm; border: 1px solid #ccc; background: #fff; }}
.section-rule {{ border-bottom: 3px solid #000; padding-bottom: 6px; margin-bottom: 18px; }}
.section-rule h2 {{ font-size: 18px; font-weight: 800; color: #000; letter-spacing: -0.5px; }}
table {{ width: 100%; border-collapse: collapse; page-break-inside: auto; }}
th {{ border-bottom: 2px solid #000; padding: 8px; text-transform: uppercase; font-size: 10px; font-weight: 800; text-align: left; }}
td {{ padding: 8px; vertical-align: top; color: #000; }}
.metric-card {{ border: 1px solid #000; padding: 16px; margin-bottom: 12px; }}
.metric-value {{ font-size: 32px; font-weight: 900; }}
.metric-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.7; }}
.metric-detail {{ font-size: 12px; margin-top: 4px; }}
</style>
</head>
<body>
<main class="page">
<header style="border-bottom:3px solid #000;padding-bottom:14px;margin-bottom:24px;">
<div class="text-xs font-bold uppercase" style="letter-spacing:0.2em;">Stability Report</div>
<h1 style="font-size:28px;font-weight:900;letter-spacing:-1px;line-height:1;margin-top:4px;">
Test-Retest Reliability
</h1>
<div class="text-sm font-mono" style="margin-top:8px;">Correspondence Auditor · §11 Pre-Registration</div>
</header>

<section style="margin-bottom:24px;">
<div class="section-rule"><h2>01 · Summary</h2></div>
<p class="text-sm text-black" style="margin-bottom:16px;">
This report computes pre-registered reliability metrics across {metrics.n_runs} rerun iterations 
({metrics.n_cases} cases each). These metrics assess the stability and reproducibility of the 
Correspondence Auditor under identical conditions.
</p>

<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px;">
<div class="metric-card">
<div class="metric-label">ICC(2,1) — Binary Verdict</div>
<div class="metric-value">{icc_str}</div>
<div class="metric-detail">95% CI: {icc_ci_str}</div>
<div class="metric-detail" style="margin-top:8px;font-weight:800;font-size:14px;{"color:green" if metrics.icc_2_1 >= 0.80 and not np.isnan(metrics.icc_2_1) else "color:red"}">
{'✓ PASS' if metrics.icc_2_1 >= 0.80 and not np.isnan(metrics.icc_2_1) else '✗ FAIL'} (threshold ≥ 0.80)
</div>
</div>
<div class="metric-card">
<div class="metric-label">Krippendorff's α — Rules</div>
<div class="metric-value">{kripp_str}</div>
<div class="metric-detail">MASI distance</div>
</div>
<div class="metric-card">
<div class="metric-label">Cohen's κ — Quadrants</div>
<div class="metric-value">{kappa_quad_str}</div>
<div class="metric-detail">Mean (10 pairs) · Range: {kappa_range_str}</div>
</div>
<div class="metric-card">
<div class="metric-label">Cohen's κ — Gate B Baseline</div>
<div class="metric-value">{kappa_gate_b_str}</div>
<div class="metric-detail">Human vs. Gate B labels</div>
</div>
</div>
</section>

<section style="margin-bottom:24px;">
<div class="section-rule"><h2>02 · Interpretation Guide</h2></div>
<table>
<thead>
<tr>
<th>Metric</th>
<th>Interpretation</th>
<th>Acceptable Range</th>
</tr>
</thead>
<tbody>
<tr style="border-bottom:1px solid #ccc;">
<td class="font-mono">ICC(2,1)</td>
<td>Test-retest reliability for binary verdicts</td>
<td>≥ 0.80 (excellent)</td>
</tr>
<tr style="border-bottom:1px solid #ccc;">
<td class="font-mono">Krippendorff's α</td>
<td>Agreement on rule firings (set-valued)</td>
<td>≥ 0.80 (acceptable)</td>
</tr>
<tr style="border-bottom:1px solid #ccc;">
<td class="font-mono">Cohen's κ</td>
<td>Quadrant classification stability</td>
<td>≥ 0.60 (substantial)</td>
</tr>
<tr>
<td class="font-mono">Cohen's κ (Gate B)</td>
<td>Human vs. model factual grounding</td>
<td>≥ 0.60 (substantial)</td>
</tr>
</tbody>
</table>
</section>

<section style="margin-bottom:24px;">
<div class="section-rule"><h2>03 · Technical Details</h2></div>
<ul style="list-style:disc;padding-left:24px;font-size:12px;line-height:1.6;">
<li><strong>ICC(2,1):</strong> Two-way random effects, single measures. Uses pingouin library.</li>
<li><strong>Krippendorff's α:</strong> Computed with MASI distance on rule sets. Uses nltk.</li>
<li><strong>Cohen's κ:</strong> Unweighted, computed across all 10 run pairs.</li>
<li><strong>Gate B κ:</strong> Compares human_label to gate_b_label from answer key CSV.</li>
</ul>
</section>

<footer style="margin-top:32px;padding-top:12px;border-top:1px solid #000;font-size:11px;color:#000;opacity:0.7;text-align:center;">
Generated by compute_stability.py · {metrics.timestamp} · {metrics.n_cases} cases × {metrics.n_runs} runs
</footer>
</main>
</body>
</html>
"""
    
    output_path = output_dir / "stability_report.html"
    output_path.write_text(html, encoding="utf-8")
    return output_path

# ---------------------------------------------------------------------------
# CLI & Interactive Menu
# ---------------------------------------------------------------------------

def select_rerun_dir() -> Path | None:
    """Interactive menu to select a rerun directory if CLI args aren't provided."""

    # Dynamically resolve the project root (one level up from the /tools folder)
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    base_dir = PROJECT_ROOT / "output"

    if not base_dir.exists():
        print("❌ output/ directory not found. Run from project root.")
        return None

    # Find directories in output/ (assuming reruns are grouped in a parent folder)
    dirs = sorted([d for d in base_dir.iterdir() if d.is_dir()], reverse=True)
    if not dirs:
        print("❌ No directories found in output/.")
        return None

    recent = dirs[:9]
    print("\n📊 Select a directory containing the 5 reruns:")
    for i, d in enumerate(recent, 1):
        print(f"  [{i}] {d.name}")
    
    while True:
        choice = input(f"\nEnter choice (1–{len(recent)}) or 'q': ").strip()
        if choice.lower() == "q":
            return None
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(recent):
                return recent[idx]
        except ValueError:
            pass
        print("❌ Invalid choice; try again.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute test-retest and baseline reliability metrics for Correspondence Auditor."
    )
    parser.add_argument(
        "--rerun-dir",
        type=Path,
        default=None,
        help="Directory containing 5 rerun subdirectories. If omitted, opens a menu."
    )
    parser.add_argument(
        "--gate-b-key",
        type=Path,
        default=None,
        help="Optional CSV with columns: claim_id, human_label, gate_b_label"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for reports. Defaults to inside the rerun-dir."
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    
    # 1. Resolve target directory (CLI or Menu)
    rerun_dir = args.rerun_dir
    if not rerun_dir:
        rerun_dir = select_rerun_dir()
        if not rerun_dir:
            return  # User aborted
            
    if not rerun_dir.exists():
        raise FileNotFoundError(f"Rerun directory not found: {rerun_dir}")
        
    # --- NEW GUARDRAIL LOGIC ---
    config_path = rerun_dir / "_provenance" / "config.json"
    if config_path.exists():
        with open(config_path, "r") as f:
            config = json.load(f)
            if config.get("run_type") != "test_retest":
                print(f"❌ ERROR: {rerun_dir.name} is NOT a test-retest run!")
                print("   It appears to be a main grid or canary run. Please select a valid stability folder.")
                return
    # ---------------------------
    
    # 2. Resolve output directory (CLI or fallback to rerun_dir)
    output_dir = args.output_dir if args.output_dir else rerun_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 3. Discover runs inside the target directory
    rerun_dirs = find_rerun_directories(rerun_dir)
    
    # Detect if we're using filename-based reruns
    is_filename_based, _ = detect_rerun_pattern(rerun_dirs)
    
    if is_filename_based:
        # For filename-based, count unique rerun indices found
        rerun_indices = set()
        for d in rerun_dirs:
            for f in d.rglob("audit_*.json"):
                match = re.search(r"__rerun_(\d+)", f.name)
                if match:
                    rerun_indices.add(int(match.group(1)))
        n_runs_detected = len(rerun_indices)
        if n_runs_detected < 2:
            raise ValueError(f"Need at least 2 rerun iterations, found {n_runs_detected} in {rerun_dir}")
    else:
        n_runs_detected = len(rerun_dirs)
        if n_runs_detected < 2:
            raise ValueError(f"Need at least 2 rerun directories, found {n_runs_detected} in {rerun_dir}")
    
    
    print(f"\n📂 Found {len(rerun_dirs)} rerun directories in {rerun_dir.name}:")
    for d in rerun_dirs:
        print(f"  - {d.name}")
    
    print("\nLoading case data...")
    case_map = load_rerun_data(rerun_dirs)
    n_cases = len(case_map)
    if is_filename_based:
        n_runs = n_runs_detected
    else:
        n_runs = len(rerun_dirs)
    
    print(f"Loaded {n_cases} cases across {n_runs} runs")
    
    if n_cases < 10:
        raise ValueError(f"Insufficient cases: {n_cases}")
    
    # --- DEFENSIVE CHECK: Verify ablation arm ---
    print("\n🔍 Verifying ablation-arm filtering...")
    if not verify_ablation_arm(case_map):
        print("❌ ERROR: Stability metrics require ablation-arm cases only.")
        print("   Run run.py in test-retest mode to generate properly filtered reruns.")
        return
    print("   ✓ All cases verified as ABLATION_NOISE arm")
    
    print("\nExtracting verdicts...")
    verdicts = extract_verdicts(case_map, n_runs)
    
    print("Extracting quadrants...")
    quadrants = extract_quadrants(case_map, n_runs)
    
    print("Extracting rules...")
    rules_data = extract_rules(case_map, n_runs)
    
    print("\nComputing ICC(2,1)...")
    icc_val, icc_ci = compute_icc(verdicts)
    print(f"  ICC = {icc_val:.3f} {icc_ci}")
    
    print("Computing Krippendorff's α...")
    kripp_alpha = compute_krippendorff_alpha(rules_data)
    print(f"  α = {kripp_alpha:.3f}")
    
    print("Computing Cohen's κ (quadrants)...")
    kappa_quad_mean, kappa_quad_range = compute_cohen_kappa_quadrants(quadrants)
    print(f"  κ = {kappa_quad_mean:.3f} (range: {kappa_quad_range})")
    
    print("Computing Cohen's κ (Gate B)...")
    kappa_gate_b = None
    if args.gate_b_key:
        kappa_gate_b = compute_cohen_kappa_gate_b(args.gate_b_key)
        print(f"  κ = {kappa_gate_b:.3f}")
    else:
        print("  (not computed - no answer key provided)")
    
    metrics = StabilityMetrics(
        icc_2_1=icc_val,
        icc_ci=icc_ci,
        krippendorff_alpha=kripp_alpha,
        cohen_kappa_quadrant_mean=kappa_quad_mean,
        cohen_kappa_quadrant_range=kappa_quad_range,
        cohen_kappa_gate_b=kappa_gate_b,
        n_cases=n_cases,
        n_runs=n_runs
    )
    
    json_path = output_dir / "stability_report.json"
    # Compute PASS/FAIL at ICC ≥ 0.80 threshold (per M2 pre-registration requirement)
    icc_val = metrics.icc_2_1
    stability_pass = bool(icc_val >= 0.80) if not np.isnan(icc_val) else False
    
    json_data = {
        "icc_2_1": float(metrics.icc_2_1) if not np.isnan(metrics.icc_2_1) else None,
        "icc_ci": [float(x) for x in metrics.icc_ci] if not np.isnan(metrics.icc_ci[0]) else None,
        "stability_pass": stability_pass,
        "krippendorff_alpha": float(metrics.krippendorff_alpha) if not np.isnan(metrics.krippendorff_alpha) else None,
        "cohen_kappa_quadrant_mean": float(metrics.cohen_kappa_quadrant_mean) if not np.isnan(metrics.cohen_kappa_quadrant_mean) else None,
        "cohen_kappa_quadrant_range": [float(x) for x in metrics.cohen_kappa_quadrant_range] if not np.isnan(metrics.cohen_kappa_quadrant_range[0]) else None,
        "cohen_kappa_gate_b": float(metrics.cohen_kappa_gate_b) if metrics.cohen_kappa_gate_b is not None and not np.isnan(metrics.cohen_kappa_gate_b) else None,
        "n_cases": metrics.n_cases,
        "n_runs": metrics.n_runs,
        "timestamp": metrics.timestamp
    }
    
    json_path.write_text(json.dumps(json_data, indent=2), encoding="utf-8")
    print(f"\nJSON written: {json_path}")
    
    html_path = render_stability_html(metrics, output_dir)
    print(f"HTML written: {html_path}")
    
    print("\n✓ Stability metrics computed successfully")


if __name__ == "__main__":
    main()