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

When --seed-dir is omitted, behaviour is identical to prior version where (k=5). When provided, seed files load at index 0 (t=0) and the existing reruns shift to indices 1..n, giving k=6 with semantically correct ordering.

python tools/compute_stability.py \
  --rerun-dir output/run_20260525_234223_arm04b_testretest_reruns_x5_300 \
  --seed-dir  output/run_20260525_205154_arm04a_testretest_seed_300 \
  --gate-b-key output/run_20260522_152239_arm01_main_pilot_1200/IRR/gate_b_human_annotations_minimal_FINAL.csv \
  --output-dir output/run_20260522_152239_arm01_main_pilot_1200



"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict, Counter
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
    rule_flicker_stats: dict[str, dict]
    
    # Metadata
    n_cases: int
    n_runs: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ---------------------------------------------------------------------------
# Data Loading (unchanged)
# ---------------------------------------------------------------------------
def detect_rerun_pattern(rerun_dirs: list[Path]) -> tuple[bool, re.Pattern | None]:
    sample_files = []
    for d in rerun_dirs:
        sample_files.extend(d.rglob("audit_*.json"))
    
    if not sample_files:
        return False, None
    
    rerun_pattern = re.compile(r"__rerun_(\d+)")
    matches = 0
    for f in sample_files[:20]:
        if rerun_pattern.search(f.name):
            matches += 1
    
    if matches >= 10:
        return True, rerun_pattern
    
    return False, None

def find_rerun_directories(base_dir: Path) -> list[Path]:
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
    
    has_rerun_files = any(
        re.search(r"__rerun_\d+", f.name) 
        for f in base_dir.rglob("audit_*.json")
    )
    
    if has_rerun_files:
        return [base_dir]
    
    return [base_dir]

def load_case_json(json_path: Path) -> dict:
    return json.loads(json_path.read_text(encoding="utf-8"))

def load_rerun_data(rerun_dirs: list[Path], seed_dir: Path | None = None) -> dict[str, dict]:
    case_map: dict[str, dict] = {}
    rerun_offset = 1 if seed_dir is not None else 0
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

            effective_run_idx = run_idx

            if is_filename_based and rerun_pattern:
                match = rerun_pattern.search(file_path.name)
                if match:
                    effective_run_idx = int(match.group(1)) - 1

            effective_run_idx += rerun_offset
            case_id = data.get("case_id")
            if not case_id:
                stem = file_path.stem
                if is_filename_based and rerun_pattern:
                    stem = rerun_pattern.sub("", stem)
                case_id = stem

            if case_id not in case_map:
                case_map[case_id] = {}

            case_map[case_id][effective_run_idx] = data

    if seed_dir is not None:
        if not seed_dir.exists():
            raise FileNotFoundError(f"Seed directory not found: {seed_dir}")

        seed_audit = sorted(seed_dir.rglob("audit_*.json"))
        seed_error = sorted(seed_dir.rglob("audit_*.error.json"))
        seed_files = sorted(set(seed_audit + seed_error), key=lambda p: str(p))

        if not seed_files:
            raise ValueError(f"No audit files found in seed directory: {seed_dir}")

        seed_loaded = 0
        seed_orphans = 0

        for file_path in seed_files:
            try:
                data = load_case_json(file_path)
            except (json.JSONDecodeError, OSError):
                continue

            case_id = data.get("case_id")
            if not case_id:
                case_id = file_path.stem

            if case_id not in case_map:
                case_map[case_id] = {}
                seed_orphans += 1

            case_map[case_id][0] = data
            seed_loaded += 1

        print(f"   ✓ Loaded {seed_loaded} seed-pass cases at run index 0 (t=0)")
        if seed_orphans:
            print(f"   ⚠️  {seed_orphans} seed cases had no matching rerun set "
                  f"(they will appear with t=0 only, NaN for t=1..n)")

    return case_map

def verify_ablation_arm(case_map: dict[str, dict]) -> bool:
    non_ablation_cases = []
    missing_arm_cases = []
    
    for case_id, runs_data in case_map.items():
        sample_data = next(iter(runs_data.values()), None)
        if sample_data is None:
            continue
        
        arm = sample_data.get("metadata", {}).get("arm")
        if arm is None:
            missing_arm_cases.append(case_id)
        elif arm != "ABLATION_NOISE":
            non_ablation_cases.append((case_id, arm))
    
    if missing_arm_cases:
        return False
    if non_ablation_cases:
        return False
    return True

def extract_verdicts(case_map: dict[str, dict], n_runs: int) -> np.ndarray:
    matrix = np.full((len(case_map), n_runs), np.nan)
    for row_idx, (case_id, runs_data) in enumerate(case_map.items()):
        for run_idx in range(n_runs):
            if run_idx in runs_data:
                data = runs_data[run_idx]
                gap = data.get("compliance_gap") or {}
                action = gap.get("auditor_recommended_action")
                if action == "BLOCK":
                    matrix[row_idx, run_idx] = 1.0
                elif action == "APPROVE":
                    matrix[row_idx, run_idx] = 0.0
    return matrix

def extract_quadrants(case_map: dict[str, dict], n_runs: int) -> np.ndarray:
    quadrant_to_int = {"VALIDATED_APPROVAL": 0, "FLAWED_APPROVAL": 1, "VALIDATED_BLOCK": 2, "FLAWED_BLOCK": 3}
    matrix = np.full((len(case_map), n_runs), np.nan)
    for row_idx, (case_id, runs_data) in enumerate(case_map.items()):
        for run_idx in range(n_runs):
            if run_idx in runs_data:
                data = runs_data[run_idx]
                gap = data.get("compliance_gap") or {}
                quadrant = gap.get("quadrant")
                if quadrant in quadrant_to_int:
                    matrix[row_idx, run_idx] = quadrant_to_int[quadrant]
    return matrix

def extract_rules(case_map: dict[str, dict], n_runs: int) -> list[list[Optional[frozenset]]]:
    n_cases = len(case_map)
    result = [[None for _ in range(n_cases)] for _ in range(n_runs)]
    case_ids = list(case_map.keys())
    
    for col_idx, case_id in enumerate(case_ids):
        for run_idx in range(n_runs):
            if run_idx in case_map[case_id]:
                data = case_map[case_id][run_idx]
                rules = (data.get("metadata") or {}).get("rules_fired", [])
                result[run_idx][col_idx] = frozenset(rules) if rules else frozenset()
    return result


# ---------------------------------------------------------------------------
# Metric Computations
# ---------------------------------------------------------------------------

def compute_icc(verdicts: np.ndarray) -> tuple[tuple[float, tuple[float, float]], int]:
    try:
        import pingouin as pg
    except ImportError:
        raise ImportError("pingouin is required: pip install pingouin")

    n_cases_input, n_runs = verdicts.shape
    complete_mask = ~np.isnan(verdicts).any(axis=1)
    balanced_verdicts = verdicts[complete_mask]
    n_complete = balanced_verdicts.shape[0]
    n_dropped = n_cases_input - n_complete

    if n_dropped > 0:
        print(f"   ℹ️  Dropped {n_dropped} incomplete case(s) for ICC (n_complete = {n_complete})")

    if n_complete < 10:
        return (np.nan, (np.nan, np.nan)), n_complete

    records = []
    for case_idx in range(n_complete):
        for run_idx in range(n_runs):
            records.append({"Observer": f"Run{run_idx}", "Target": f"Case{case_idx}", "Rating": int(balanced_verdicts[case_idx, run_idx])})

    df = pd.DataFrame(records)

    if np.var(balanced_verdicts, axis=1).sum() == 0:
        return (1.0, (1.0, 1.0)), n_complete

    icc_result = pg.intraclass_corr(data=df, targets="Target", raters="Observer", ratings="Rating")
    icc_row = icc_result[icc_result["Type"] == "ICC(A,1)"]
    if icc_row.empty:
        return (np.nan, (np.nan, np.nan)), n_complete

    point_est = icc_row["ICC"].values[0]
    ci_raw = icc_row["CI95"].values[0]
    if isinstance(ci_raw, (list, np.ndarray)):
        ci_lower, ci_upper = float(ci_raw[0]), float(ci_raw[1])
    else:
        ci_parts = str(ci_raw).split(",")
        ci_lower, ci_upper = float(ci_parts[0].strip()), float(ci_parts[1].strip())

    return (point_est, (ci_lower, ci_upper)), n_complete


def compute_krippendorff_alpha(rules_data: list[list[Optional[frozenset]]]) -> float:
    try:
        from nltk.metrics.agreement import AnnotationTask
        from nltk.metrics.distance import masi_distance
    except ImportError:
        raise ImportError("nltk required: pip install nltk")
    
    def safe_masi_distance(label1, label2):
        if not label1 and not label2:
            return 0.0 
        return masi_distance(label1, label2)
    
    n_runs = len(rules_data)
    n_cases = len(rules_data[0])
    
    data = []
    for case_idx in range(n_cases):
        for run_idx in range(n_runs):
            rules = rules_data[run_idx][case_idx]
            if rules is not None:
                label = rules
                # FIX: Mapped to (coder, item, label) format required by AnnotationTask
                data.append((f"run{run_idx}", f"case{case_idx}", label))

    if not data:
        return np.nan
    
    task = AnnotationTask(data=data, distance=safe_masi_distance)
    return task.alpha()


def compute_rule_flicker(rules_data: list[list[Optional[frozenset]]]) -> dict[str, dict]:
    """Computes flicker rate per rule across cases to diagnose Truth Cartridge ambiguity."""
    n_runs = len(rules_data)
    n_cases = len(rules_data[0])
    
    rule_stats = defaultdict(lambda: {"cases_seen": 0, "unanimous": 0, "flickering": 0})
    
    for case_idx in range(n_cases):
        case_rule_counts = Counter()
        valid_runs = 0
        
        for run_idx in range(n_runs):
            rules = rules_data[run_idx][case_idx]
            if rules is not None:
                valid_runs += 1
                for r in rules:
                    case_rule_counts[r] += 1
                    
        if valid_runs < 2:
            continue
            
        for r, count in case_rule_counts.items():
            rule_stats[r]["cases_seen"] += 1
            if count == valid_runs:
                rule_stats[r]["unanimous"] += 1
            else:
                rule_stats[r]["flickering"] += 1

    # Format output and calculate percentages
    result = {}
    for r, stats in rule_stats.items():
        total = stats["cases_seen"]
        flickering = stats["flickering"]
        pct = (flickering / total) * 100 if total > 0 else 0.0
        result[r] = {
            "cases_seen": total,
            "unanimous": stats["unanimous"],
            "flickering": flickering,
            "instability_pct": round(pct, 1)
        }
    # Sort Options:

    # Sort descending by raw number of flickering occurrences 
    # return dict(sorted(result.items(), key=lambda x: x[1]["flickering"], reverse=True))

    # Sort ascending by instability percentage
    return dict(sorted(result.items(), key=lambda x: x[1]["instability_pct"]))

def compute_cohen_kappa_quadrants(quadrants: np.ndarray) -> tuple[float, tuple[float, float]]:
    from sklearn.metrics import cohen_kappa_score
    n_cases, n_runs = quadrants.shape
    kappas = []
    for i in range(n_runs):
        for j in range(i + 1, n_runs):
            col_i, col_j = quadrants[:, i], quadrants[:, j]
            valid_mask = ~np.isnan(col_i) & ~np.isnan(col_j)
            if valid_mask.sum() < 10: continue
            kappas.append(cohen_kappa_score(col_i[valid_mask].astype(int), col_j[valid_mask].astype(int)))
    if not kappas:
        return (np.nan, (np.nan, np.nan))
    return (np.mean(kappas), (np.min(kappas), np.max(kappas)))


def compute_cohen_kappa_gate_b(gate_b_key_path: Path) -> float | None:
    if not gate_b_key_path.exists(): return None
    try: df = pd.read_csv(gate_b_key_path)
    except Exception: return None
    if not {"human_label", "gate_b_label"}.issubset(df.columns): return None
    valid = {"SUPPORTED", "CONTRADICTED", "UNSUPPORTED"}
    df = df[df["human_label"].isin(valid) & df["gate_b_label"].isin(valid)]
    if len(df) < 5: return None
    from sklearn.metrics import cohen_kappa_score
    return cohen_kappa_score(df["human_label"], df["gate_b_label"])


# ---------------------------------------------------------------------------
# HTML Report Generation
# ---------------------------------------------------------------------------

def render_stability_html(metrics: StabilityMetrics, output_dir: Path) -> Path:
    icc_str = f"{metrics.icc_2_1:.3f}" if not np.isnan(metrics.icc_2_1) else "—"
    icc_ci_str = f"[{metrics.icc_ci[0]:.3f}, {metrics.icc_ci[1]:.3f}]" if not np.isnan(metrics.icc_ci[0]) else "—"
    kripp_str = f"{metrics.krippendorff_alpha:.3f}" if not np.isnan(metrics.krippendorff_alpha) else "—"
    kappa_quad_str = f"{metrics.cohen_kappa_quadrant_mean:.3f}" if not np.isnan(metrics.cohen_kappa_quadrant_mean) else "—"
    kappa_range_str = f"[{metrics.cohen_kappa_quadrant_range[0]:.3f}, {metrics.cohen_kappa_quadrant_range[1]:.3f}]" if not np.isnan(metrics.cohen_kappa_quadrant_range[0]) else "—"
    kappa_gate_b_str = f"{metrics.cohen_kappa_gate_b:.3f}" if metrics.cohen_kappa_gate_b is not None and not np.isnan(metrics.cohen_kappa_gate_b) else "N/A"
    
    # Generate Flicker Table Rows
    flicker_rows = ""
    for rule, stats in metrics.rule_flicker_stats.items():
        color = "red" if stats["instability_pct"] > 50 else ("orange" if stats["instability_pct"] > 20 else "green")
        flicker_rows += f"""
        <tr style="border-bottom:1px solid #eee;">
            <td class="font-mono font-bold">{rule}</td>
            <td>{stats['cases_seen']}</td>
            <td>{stats['unanimous']}</td>
            <td>{stats['flickering']}</td>
            <td style="color:{color}; font-weight:600;">{stats['instability_pct']}%</td>
        </tr>
        """
    
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
td {{ padding: 8px; vertical-align: top; color: #000; font-size: 13px; }}
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
({metrics.n_cases} cases each).
</p>
<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px;">
<div class="metric-card">
<div class="metric-label">ICC(2,1) — Binary Verdict</div>
<div class="metric-value">{icc_str}</div>
<div class="metric-detail">95% CI: {icc_ci_str}</div>
<div class="metric-detail" style="margin-top:8px;font-weight:800;font-size:14px;{'color:green' if metrics.icc_2_1 >= 0.80 and not np.isnan(metrics.icc_2_1) else 'color:red'}">
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
<tr><th>Metric</th><th>Interpretation</th><th>Acceptable Range</th></tr>
</thead>
<tbody>
<tr style="border-bottom:1px solid #ccc;"><td class="font-mono">ICC(2,1)</td><td>Test-retest reliability for binary verdicts</td><td>≥ 0.80 (excellent)</td></tr>
<tr style="border-bottom:1px solid #ccc;"><td class="font-mono">Krippendorff's α</td><td>Agreement on rule firings (set-valued)</td><td>≥ 0.80 (acceptable)</td></tr>
<tr style="border-bottom:1px solid #ccc;">
    <td class="font-mono">Cohen's κ</td>
    <td>Quadrant classification stability <br><span style="font-size:10px; font-weight:normal; opacity:0.7;">(Applies to the pre-registered 2×2 quadrants. Captures 8-cell stability inherently, as ground-truth is static per case).</span></td>
    <td>≥ 0.60 (substantial)</td>
</tr>
<tr><td class="font-mono">Cohen's κ (Gate B)</td><td>Human vs. model factual grounding</td><td>≥ 0.60 (substantial)</td></tr>
</tbody>
</table>
</section>

<section style="margin-bottom:24px;">
<div class="section-rule"><h2>03 · Rule Flicker Diagnostic</h2></div>
<p class="text-sm text-black" style="margin-bottom:16px;">
Identifies prompt ambiguity within the Truth Cartridge. High instability percentages (>50%) indicate that the LLM lacks a reliable mental model for the rule's boundaries, leading to stochastic application.
</p>
<table>
<thead>
<tr>
<th>Rule ID</th>
<th>Cases Seen</th>
<th>Unanimous (All Valid Runs)</th>
<th>Flickering (Partial Runs)</th>
<th>% Unstable</th>
</tr>
</thead>
<tbody>
{flicker_rows}
</tbody>
</table>
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
# CLI & Execution
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute stability metrics and diagnose Truth Cartridge ambiguity.")
    parser.add_argument("--rerun-dir", type=Path, required=True, help="Directory containing rerun subdirectories.")
    parser.add_argument("--seed-dir", type=Path, default=None, help="Optional t=0 seed pass directory.")
    parser.add_argument("--gate-b-key", type=Path, default=None, help="Optional Gate B CSV key.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Output directory for reports.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rerun_dir = args.rerun_dir
    
    if not rerun_dir.exists():
        raise FileNotFoundError(f"Rerun directory not found: {rerun_dir}")
        
    config_path = rerun_dir / "_provenance" / "config.json"
    if config_path.exists():
        with open(config_path, "r") as f:
            config = json.load(f)
            if config.get("run_type") != "test_retest":
                print(f"❌ ERROR: {rerun_dir.name} is NOT a test-retest run!")
                return
    
    output_dir = args.output_dir if args.output_dir else rerun_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    rerun_dirs = find_rerun_directories(rerun_dir)
    is_filename_based, _ = detect_rerun_pattern(rerun_dirs)

    if is_filename_based:
        rerun_indices = set(int(re.search(r"__rerun_(\d+)", f.name).group(1)) 
                            for d in rerun_dirs for f in d.rglob("audit_*.json") if re.search(r"__rerun_(\d+)", f.name))
        n_runs_detected = len(rerun_indices)
    else:
        n_runs_detected = len(rerun_dirs)

    seed_dir = args.seed_dir
    n_runs = n_runs_detected + 1 if seed_dir else n_runs_detected

    print(f"\n📂 Found {len(rerun_dirs)} rerun directories.")
    print("Loading case data...")
    case_map = load_rerun_data(rerun_dirs, seed_dir=seed_dir)
    
    pruned_cases = [cid for cid in list(case_map.keys()) if next(iter(case_map[cid].values()), {}).get("metadata", {}).get("arm") is None]
    for cid in pruned_cases: del case_map[cid]
    if pruned_cases: print(f"   🧹 Pruned {len(pruned_cases)} cases missing 'arm' metadata (pipeline errors)")

    n_cases = len(case_map)
    print(f"Loaded {n_cases} cases across {n_runs} runs.")
    
    if not verify_ablation_arm(case_map):
        print("❌ ERROR: Stability metrics require ablation-arm cases only.")
        return
        
    print("\nExtracting data matrices...")
    verdicts = extract_verdicts(case_map, n_runs)
    quadrants = extract_quadrants(case_map, n_runs)
    rules_data = extract_rules(case_map, n_runs)
    
    print("\nComputing ICC(2,1)...")
    (icc_val, icc_ci), n_complete = compute_icc(verdicts)
    print(f"  ICC = {icc_val:.3f}")
    
    print("Computing Krippendorff's α...")
    kripp_alpha = compute_krippendorff_alpha(rules_data)
    print(f"  α = {kripp_alpha:.3f}")

    print("Computing Rule Flicker Diagnostics...")
    flicker_stats = compute_rule_flicker(rules_data)
    
    print("Computing Cohen's κ (quadrants)...")
    kappa_quad_mean, kappa_quad_range = compute_cohen_kappa_quadrants(quadrants)
    
    kappa_gate_b = compute_cohen_kappa_gate_b(args.gate_b_key) if args.gate_b_key else None
    
    metrics = StabilityMetrics(
        icc_2_1=icc_val, icc_ci=icc_ci, krippendorff_alpha=kripp_alpha,
        cohen_kappa_quadrant_mean=kappa_quad_mean, cohen_kappa_quadrant_range=kappa_quad_range,
        cohen_kappa_gate_b=kappa_gate_b, rule_flicker_stats=flicker_stats,
        n_cases=n_cases, n_runs=n_runs
    )
    
    json_path = output_dir / "stability_report.json"
    json_data = asdict(metrics)
    json_data["stability_pass"] = bool(icc_val >= 0.80) if not np.isnan(icc_val) else False
    json_path.write_text(json.dumps(json_data, indent=2), encoding="utf-8")
    print(f"\nJSON written: {json_path}")
    
    html_path = render_stability_html(metrics, output_dir)
    print(f"HTML written: {html_path}")
    print("\n✓ Stability metrics computed successfully")

if __name__ == "__main__":
    main()