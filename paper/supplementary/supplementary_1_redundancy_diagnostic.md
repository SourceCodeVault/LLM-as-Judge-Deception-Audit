# Supplementary 1: Rule Redundancy and Stability Analysis of the Auditor's Rationale Layer

**Related main-paper sections:** §3.3, §5.5, §5.9, §6.1, §6.2(b)

---

## 1.1 Introduction

Note: the stability analysis operates on the ablation arm (§4.5), where the upstream 
judge verdict has been replaced with random noise and its reasoning trace replaced 
with a content-free monologue. This makes the test deliberately harsh — it measures 
which rules survive when the judge signal is maximally degraded.

Section 5.5 of the main paper reports that the Correspondence Auditor's binary verdict
is highly reproducible (ICC = 0.979) but its rule-citation rationale is not
(Krippendorff's α = 0.238). The present supplementary reports the exploratory
post-hoc analysis that investigates the structure of that instability.

The central question is whether the low α reflects **label-substitution instability**
(the auditor detects the same underlying concept but cites different,
semantically-equivalent rules across runs) or **presence/absence instability** (the
entire concept family flickers on and off). The distinction matters because label
substitution is addressable through rule compression — merging synonymous rules into a
single cluster — whereas presence/absence flicker is a deeper instability that
compression cannot resolve.

A note on comparability with the main paper: the per-rule flicker rates reported in
§5.5 are computed on the k = 6 frame at the individual-rule level; the cluster-level
rates reported below are computed on the k = 5 rerun-only frame (§1.2.1). The two
sets of figures are consistent but are not directly comparable cell-by-cell.

## 1.2 Method

### 1.2.1 Data

The analysis uses the same ablation-arm test-retest data described in §4.7 of the main
paper: 297 cases with k = 6 observations each (one seed pass plus five reruns),
yielding 1,781 unique observations over the 14 observed rules. The incidence matrix is
case × pass × rule → {0, 1 fired}, constructed from raw audit JSONs and verified
against the author's pipeline through provenance-chain tests (repository `tests/`).

Two analysis frames are used, following the conventions of the source analysis
(Tsereteli, 2026). Alpha coefficients are computed on the k = 6 frame (297 cases:
seed + 5 reruns) to match the main paper's §5.5 convention. Clustering and
cluster-level flicker are computed on the k = 5 rerun-only balanced panel (296
complete cases), the frame used throughout the source analysis. The frame applicable
to each table is stated in its caption.

### 1.2.2 Analysis Overview

The analysis proceeds in three stages:

1. **Pairwise co-firing and clustering.** Co-firing patterns, L1-regularised logistic
   models, case-level fire-rate correlations, conditional redundancy within
   verdict/ground-truth/quadrant strata, and hierarchical clustering were used to
   identify natural rule groups. Full methodological details are in Tsereteli (2026).

2. **Compressed rulebook evaluation.** Five compressed rulebooks were constructed by
   merging identified clusters. MASI Krippendorff's α and case-level reproducibility
   metrics were recomputed for each.

3. **Cluster-level flicker analysis.** To distinguish label-substitution from
   presence/absence instability, we measured: when any member of a compressed cluster
   fires in a case, how often does the cluster fire in *all five* reruns?

All statistics are reported rounded to three decimal places; unrounded values are
available in the source CSVs (`rulebook-redundancy-analysis/results/compressed_rulebook/`).

### 1.2.3 Rule Clusters Identified

The analysis converges on a consistent natural geometry across all methods:

| Cluster | Rules | Strongest Evidence |
|---------|-------|--------------------|
| Tight J core | J3, J4, J5 | Jaccard 0.78–0.87; case-level Pearson 0.91–0.95 |
| Nearby J pair | J1, J2 | Jaccard 0.75; case-level Pearson 0.91 |
| Broad J block | J1–J5 | Fire-rate clusters at dissimilarity threshold 0.20 |
| Factual cluster | F1, F2 | Jaccard 0.80; case-level Pearson 0.88 |
| Universal cluster | U1, U3 | Jaccard 0.82; weaker case-level correlation |

These clusters are consistent across pass-level Jaccard, case-level fire-rate
correlation, sparse logistic models, and conditional redundancy within strata.

### 1.2.4 Compressed Rulebooks

| Spec | Labels | Merges Applied |
|------|--------|----------------|
| original | 14 | No merges |
| j_only | 11 | J1/J2 → J12; J3/J4/J5 → J345 |
| natural_tight | 9 | F1/F2 → F12; J1/J2 → J12; J3/J4/J5 → J345; U1/U3 → U13; U2, F3, H1, S1, U4 retained |
| j_all | 10 | J1/J2/J3/J4/J5 → J_ALL |
| broad_clusters | 6 | F1/F2/F3/U1/U3 → F123_U13; J1–J5 → J_ALL; H1, S1, U2, U4 retained |

Three further J-family-only specs (j_family_original, j_family_tight, j_family_all)
restrict the rulebook to the J family at increasing levels of compression; these
isolate the J-family signal and appear in Table 1.1.

## 1.3 Results

### 1.3.1 Compressed Alpha

The best compression raises α from 0.238 to 0.278 — a real improvement (paired
bootstrap 95% CI for the increase: [+0.031, +0.047]; 3,000 case-level replicates,
seed 12345; Tsereteli, 2026), but still far below a stable rationale layer.

The J-family-only rows isolate the judge-process signal. Within this series α rises
with compression (0.100 → 0.112 → 0.128), so compression does remove some label
fragmentation — but it starts near zero and ends near zero. The endpoint is
instructive: under j_family_all, where the entire J family is collapsed to a single
binary label, α = 0.128 is an *optimistic* figure, because 63.6% of cases carry no J
citation on any run and therefore contribute empty-set agreement (cf. the upper-bound
caveat in §5.5 of the main paper). Even under maximal coarsening and maximal
empty-agreement inflation, the J-family signal does not reproduce. (α values across
specs with different label universes are not commensurate in magnitude — expected
disagreement depends on the label space — so we do not rank j_family_all against the
full-rulebook specs; the comparison that matters is within the J-family series.)

**Table 1.1 — MASI Krippendorff's α by Compressed Rulebook Spec**

| Spec | Labels | Cases | Runs | α (MASI) | Obs. Disagreement | Exp. Disagreement |
|------|--------|-------|------|----------|-------------------|-------------------|
| original | 14 | 297 | 6 | 0.238 | 0.583 | 0.765 |
| **natural_tight** | **9** | 297 | 6 | **0.278** | **0.534** | **0.739** |
| j_only | 11 | 297 | 6 | 0.242 | 0.576 | 0.760 |
| j_all | 10 | 297 | 6 | 0.244 | 0.573 | 0.758 |
| broad_clusters | 6 | 297 | 6 | 0.263 | 0.495 | 0.672 |
| j_family_original | 5 | 297 | 6 | 0.100 | 0.156 | 0.173 |
| j_family_tight | 2 | 297 | 6 | 0.112 | 0.152 | 0.171 |
| **j_family_all** | **1** | 297 | 6 | **0.128** | **0.147** | **0.168** |

*Computed on the k=6 frame (297 cases: seed + 5 reruns). Table generated by
`generate_redundancy_tables.py` from verified CSV data; row order and values are
byte-identical to the generated artifact.*

### 1.3.2 Cluster-Level Flicker

This is the decisive diagnostic. If the J-family instability is label substitution,
merging J3/J4/J5 into J345 should produce a stable cluster. If it is presence/absence
flicker, the merged cluster should itself flicker.

**Table 1.2 — Cluster-Level On/Off Stability (natural_tight spec)**

| Cluster | Members | Cases Seen | Fires All 5 | Flicker Rate | Mean Fire Rate When Seen |
|---------|---------|------------|-------------|--------------|--------------------------|
| F12 | F1 F2 | 198 | 192 | 0.030 | 0.988 |
| F3 | F3 | 144 | 4 | 0.972 | 0.442 |
| H1 | H1 | 259 | 18 | 0.931 | 0.486 |
| J12 | J1 J2 | 92 | 1 | 0.989 | 0.287 |
| J345 | J3 J4 J5 | 59 | 1 | 0.983 | 0.281 |
| S1 | S1 | 115 | 96 | 0.165 | 0.894 |
| U13 | U1 U3 | 294 | 217 | 0.262 | 0.899 |
| U2 | U2 | 2 | 0 | 1.000 | 0.200 |
| U4 | U4 | 282 | 20 | 0.929 | 0.540 |

*Computed on the k=5 frame (296 complete cases: reruns only). Table generated by
`generate_redundancy_tables.py` from verified CSV data; row order and values are
byte-identical to the generated artifact. U2 is seen in only 2 cases; its flicker
rate is not interpretable and is reported for completeness only.*

**F12** behaves like a genuinely stable merged concept: once the F1/F2 family appears,
it appears in all five reruns 97.0% of the time. **J12** and **J345** do not: they
flicker on 98.9% and 98.3% of the cases they appear in, respectively. The J-family
instability is not label substitution — it is presence/absence flicker.

The non-J high-flicker clusters confirm that the instability is not confined to
judge-process rules. F3 (flicker rate 0.972), H1 (0.931), and U4 (0.929) are
similarly unstable.

### 1.3.3 Summary

The natural clustering is genuine: J3/J4/J5 co-fire at Jaccard 0.78–0.87, their
case-level fire-rate profiles correlate at Pearson 0.91–0.95, and merging them into
J345 removes real label fragmentation. But the merged signal itself flickers. The
auditor detects the J345 concept in 59 of 296 cases, yet in only 1 of those 59 cases
does it cite the concept across all five reruns. The instability is located in the
presence/absence decision itself — whether the concept fires at all — not in the
choice among labels.

## 1.4 Limitations

1. **Exploratory and post-hoc.** This analysis was not pre-registered. All findings are
   hypothesis-generating, not confirmatory.

2. **Ablation-arm reruns only.** The reruns process cases without a genuine judge trace 
   (§4.7). This is an  important context for interpreting the J-rule results: rules that 
   evaluate the judge's reasoning process (J1–J5) are expected to flicker on the ablation 
   arm because there is no genuine judge reasoning to assess. The architecturally 
   significant finding is that calibrated, fact-grounded rules (F1/F2 → F12) remain stable 
   under this worst case, demonstrating that Gate B grounding — rather than rule content 
   alone — is the stabilising mechanism.

3. **Five reruns is narrow.** The flicker rate is estimated from k = 5 observations per
   case. The bootstrap noise margin for α is ±0.02; cluster-level flicker-rate
   estimates carry comparable uncertainty, and small-cluster estimates (e.g., U2, seen
   in 2 cases) are not interpretable.

4. **J-family flicker is descriptive, not causal.** We do not establish why the
   J-family signal flickers — whether it reflects genuine non-determinism in the
   auditor's reasoning, sensitivity to minor prompt-level surface variation, or a
   property of the underlying LLM's sampling. The explanation matters for remediation
   but does not change the descriptive finding.

5. **Single domain.** All findings are on the Apollo corpus under one Truth Cartridge.
   Whether the same cluster geometry and flicker profile hold on other domains is
   untested.

## 1.5 Implications for the Main Paper

**Coarsening is insufficient.** The most natural response to α = 0.238 is to compress
the rulebook. We tested this systematically and found it achieves only +0.04 α units. The
problem is not label fragmentation; it is that the underlying concept detectors flicker
on and off.

**The §3.3 interpretability claim is correctly bounded.** The main paper states that
"individual policy-rule citations should be read at the aggregate-frequency level rather
than as stable per-case attributions." This analysis confirms and sharpens that bound:
even compressed rule clusters (J12, J345) are not stable per-case attributions. The
stable layer is the verdict (ICC = 0.979) and the factual-rule cluster F12 (97.0%
all-five agreement), not the judge-process (J) or hygiene (H/U) clusters.

**Future work direction is clarified.** The exploratory findings reframe the §6.2(b) 
future work trajectory for the rationale layer. The original direction — whether 
per-rule firing frequency, averaged over stochastic passes, carries a stable signal — 
is superseded by the present analysis: the instability is presence/absence flicker, 
not label substitution, so aggregating unstable presence/absence decisions across passes 
cannot rescue a fundamentally ungrounded predicate. The F12 stability result points at the 
correct direction: extending Gate B's decomposed, source-grounded evaluation to J-family 
predicates, so that every rule receives the grounding that currently stabilises F1/F2. 
This is the architectural motivation for the v3 redesign.

---

**Reference:**

Tsereteli, G. (2026). Rule Redundancy and Stability Analysis: Exploratory Report.
Technical report accompanying LLM-as-Judge Deception Audit. Study repository:
`rulebook-redundancy-analysis/README.md`.