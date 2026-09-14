# Rulebook Redundancy Analysis

This repository contains the analysis artifacts for studying rule-citation redundancy and stability in the LLM Auditor test-retest data.

The repository starts from the **case-pass rule incidence matrices** in `data/`. It does not require access to the original raw audit JSONs for the main analysis pipeline.

## Inputs

Primary rerun matrix:

```text
data/rule_incidence_reruns.csv
```

This is the balanced rerun panel:

```text
296 cases x 5 reruns = 1,480 observations
```

Available rerun matrix:

```text
data/rule_incidence_reruns_available.csv
```

This keeps all 297 cases, including the case missing `rerun_05`.

Seed+rerun matrix for k=6 alpha reproduction:

```text
data/rule_incidence_seed_and_reruns_available.csv
```

This keeps all 297 cases and treats the one missing rerun as a missing annotation.

## Main Report

The main written review is:

```text
docs/rule_redundancy_analysis_report.md
docs/rule_redundancy_analysis_report.tex
```

The Markdown report links to all generated CSV outputs and plots.

## Pipeline

Run from the repository root.

1. Sparse L1 logistic models:

```powershell
python scripts/fit_l1_rule_models.py
```

2. Case-level fire-rate profiles:

```powershell
python scripts/analyze_rule_stability_profiles.py
```

3. Conditional redundancy by verdict, ground truth, and quadrant:

```powershell
python scripts/analyze_conditional_rule_redundancy.py
```

4. Rule-rule clustering:

```powershell
python scripts/cluster_rules.py
```

5. Plot cluster heatmaps and dendrograms:

```powershell
python scripts/visualize_rule_clusters.py
```

6. Evaluate compressed rulebooks:

```powershell
python scripts/evaluate_compressed_rulebook.py
```

7. Recompute MASI Krippendorff alpha:

```powershell
python scripts/compute_compressed_alpha.py
```

8. Bootstrap alpha uncertainty:

```powershell
python scripts/bootstrap_alpha_uncertainty.py --bootstrap 1000
```

9. Measure cluster presence/absence flicker:

```powershell
python scripts/measure_cluster_flicker.py
```

10. Measure entropy per case and per rule/cluster:

```powershell
python scripts/measure_entropy.py
```

## Optional Provenance Script

`scripts/analyze_rule_incidence.py` is included for provenance. It reconstructs incidence matrices from the v2 preprint zip, but the zip is not included in this repository.

## Outputs

Generated outputs are committed under `results/`:

- `results/*.csv`: main rerun analyses
- `results/conditional/`: conditional analyses
- `results/clusters/`: distance matrices and cluster assignments
- `results/compressed_rulebook/`: compressed rulebook reproducibility, alpha, and flicker analyses
- `results/entropy/`: entropy diagnostics
- `results/plots/`: PNG heatmaps and dendrograms

## Dependencies

The scripts use only:

- Python 3.10+
- `numpy`
- `Pillow`

No `scikit-learn`, `scipy`, `nltk`, or `matplotlib` dependency is required. L1 logistic regression, average-linkage clustering, MASI alpha, and plotting are implemented directly for reproducibility.

## Core Conclusion

Natural clustering improves the rulebook slightly, but does not rescue rationale reproducibility. The 9-rule `natural_tight` compression improves MASI alpha from about `0.238` to about `0.278`, with a paired bootstrap delta CI of about `[+0.031, +0.047]`.

The dominant residual issue is not label substitution. It is presence/absence flicker, especially for `J12`, `J345`, `F3`, `H1`, and `U4`.
