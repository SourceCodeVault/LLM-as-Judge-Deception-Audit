#!/usr/bin/env python3
"""
Bootstrap uncertainty for compressed-rulebook Krippendorff alpha.

Resamples cases with replacement, preserving all run annotations for each case.
This gives paired bootstrap intervals for alpha_original, alpha_compressed,
and alpha_compressed - alpha_original.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np

from compute_compressed_alpha import build_items, krippendorff_alpha_masi
from evaluate_compressed_rulebook import COMPRESSION_SPECS, load_incidence


def percentile(values: list[float], q: float) -> float:
    return float(np.percentile(np.array(values, dtype=float), q))


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "mean": float(np.mean(values)),
        "sd": float(np.std(values, ddof=1)),
        "p2_5": percentile(values, 2.5),
        "p50": percentile(values, 50),
        "p97_5": percentile(values, 97.5),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    # Resample cases, not rows, so each case's repeated-run bundle stays intact.
    parser.add_argument("--incidence", default="data/rule_incidence_seed_and_reruns_available.csv")
    parser.add_argument("--baseline", default="original")
    parser.add_argument("--specs", nargs="*", default=["j_only", "natural_tight", "j_all", "broad_clusters"])
    parser.add_argument("--bootstrap", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=12345)
    args = parser.parse_args()

    rows, _ = load_incidence(Path(args.incidence))
    baseline_items, n_cases, n_runs = build_items(rows, COMPRESSION_SPECS[args.baseline], include_incomplete=True)
    spec_items = {
        spec: build_items(rows, COMPRESSION_SPECS[spec], include_incomplete=True)[0]
        for spec in args.specs
    }

    baseline_alpha, _, _ = krippendorff_alpha_masi(baseline_items)
    point = {}
    for spec, items in spec_items.items():
        alpha, _, _ = krippendorff_alpha_masi(items)
        point[spec] = alpha

    rng = random.Random(args.seed)
    boot_baseline = []
    boot_specs = {spec: [] for spec in args.specs}
    boot_deltas = {spec: [] for spec in args.specs}

    for _ in range(args.bootstrap):
        sample_idx = [rng.randrange(n_cases) for _ in range(n_cases)]
        sampled_baseline = [baseline_items[i] for i in sample_idx]
        a0, _, _ = krippendorff_alpha_masi(sampled_baseline)
        boot_baseline.append(a0)
        for spec, items in spec_items.items():
            sampled = [items[i] for i in sample_idx]
            a1, _, _ = krippendorff_alpha_masi(sampled)
            boot_specs[spec].append(a1)
            boot_deltas[spec].append(a1 - a0)

    base_summary = summarize(boot_baseline)
    print(f"Incidence: {args.incidence}")
    print(f"Cases: {n_cases}; runs: {n_runs}; bootstrap replicates: {args.bootstrap}; seed: {args.seed}")
    print()
    print("Baseline alpha uncertainty:")
    print(
        f"  {args.baseline:<15} point={baseline_alpha:.6f} "
        f"boot_mean={base_summary['mean']:.6f} sd={base_summary['sd']:.6f} "
        f"95% CI=[{base_summary['p2_5']:.6f}, {base_summary['p97_5']:.6f}]"
    )
    print()
    print("Compressed alpha and paired delta uncertainty:")
    for spec in args.specs:
        spec_summary = summarize(boot_specs[spec])
        delta_summary = summarize(boot_deltas[spec])
        p_delta_le_zero = sum(1 for value in boot_deltas[spec] if value <= 0.0) / len(boot_deltas[spec])
        print(
            f"  {spec:<15} alpha={point[spec]:.6f} "
            f"alpha_CI=[{spec_summary['p2_5']:.6f}, {spec_summary['p97_5']:.6f}] "
            f"delta={point[spec] - baseline_alpha:+.6f} "
            f"delta_CI=[{delta_summary['p2_5']:+.6f}, {delta_summary['p97_5']:+.6f}] "
            f"P_boot(delta<=0)={p_delta_le_zero:.4f}"
        )


if __name__ == "__main__":
    main()
