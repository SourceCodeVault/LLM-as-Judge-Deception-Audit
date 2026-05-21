# Auditing LLM-as-Judge Pipelines: A Source-Grounded Instrument for Detecting Strategic-Deception Blindspots

**Pragmatic Preprint, v1.0** · Adrian St. Vaughan

**Keywords:** LLM-as-judge, strategic deception, AI safety, audit, pre-registration, Three Lines of Defence, evaluation reliability, sycophancy

---

## 1. Abstract

The _Correspondence Auditor_ is a third-line-of-defence system that evaluates LLM-as-Judge verdicts against the source material the judge was given. We frame it, in a phrase, as *the guardian of coherence across time* — the instrument that records what was actually shown to the judge, what the judge concluded, and whether those two things are reconcilable against the policy.

Using Apollo Research's insider-trading deception corpus (noting its single-annotator baseline), we test whether the Auditor can recover a binary human-annotated ground-truth label (`CLEAN` or `ROGUE`) across a heterogeneous set of five judges — ranging from SOTA-prompted to deliberately degraded — and produce human-auditable explanations of where each judge erred (or did not). The Auditor's label-recovery rate is the metric of interest. Our claim is that audit-layer accuracy does not require accuracy at the judge layer: within the tested judge quality range (Z01–Z05), a heterogeneous Line 2 does not destabilise a competent Line 3.

This preprint documents a 1,200-case stratified pilot designed to validate the methodology and the ablation arm at the 95%-confidence class. The full ~8,500-case replication is identified as the funded replication target.

---

## 2. Introduction

LLM-as-Judge pipelines are increasingly deployed in critical domains: content moderation, agent evaluation, automated grading, regulatory audit. The economic logic is straightforward — human review does not scale to the volume of model output that production systems generate. But the failure modes of an LLM judge are not the same as the failure modes of a human judge, and the infrastructure for catching those failure modes is not yet standardised.

There are at least three structural failure modes documented in the recent literature on LLM judges and chain-of-thought oversight. First, the agent being evaluated (Line 1) can produce a plausible, internally-coherent cover story that the judge then credits over the structural pattern of the agent's behaviour — the judge is *blinded by a sanitised report*. Second, the judge can be inattentive to the agent's reasoning trace (the scratchpad), approving an output whose internal monologue contains explicit deliberation toward a misaligned action. Third, in the absence of a fixed external reference, the judge's own beliefs about the world and its judgement of the world become operationally indistinguishable. None of these failures requires the judge and the agent to be colluding; the operational pipeline is decoupled, and that is precisely why a credible cover story is sufficient to defeat the judge in isolation.

This is the architectural case for an audit layer. In the Governance, Risk, and Compliance (GRC) tradition, the *Three Lines of Defence* model assigns:

- **Line 1** to the operator (here, the agent being evaluated)
- **Line 2** to oversight functions that work alongside the operator (here, the LLM-as-Judge)
- **Line 3** to *independent* audit, structurally separated from Line 2 in both reporting line and methodology (here, the Correspondence Auditor)

The Correspondence Auditor is a Line 3 instrument, and it has been built exclusively as Line 3. It is not a better Line 2. It does not compete with the judge head-to-head and we do not benchmark it as a judge. It performs a wholesale different task — conceptually, methodically, and in terms of governance posture. Specifically: it produces an *independent* verdict on the agent (`APPROVE` or `BLOCK`) by grounding every claim against the source material the judge was originally given and by checking the internal coherence of the judge's reasoning trace against that source. The judge's verdict and the judge's reasoning trace are *inputs* to the audit process; the judge is not a baseline against which the Auditor is benchmarked.

The study does not ask whether a larger model is a better judge than a smaller model. It asks whether, given source text *X*, judge verdict *Z*, and human-annotated ground-truth label *Y*, the Auditor can recover *Y* — and whether that recovery rate holds across a heterogeneous range of judge quality.

Two further clarifications. First, on what *audit* means: the Correspondence Auditor audits the *process* of judgement, not the *intent* of the judge. It assumes the judge is acting in good faith but is fallible. A Line 2 that is actively colluding with Line 1 — a deceptive judge — is *outside* the architectural boundary; this is exactly why governance frameworks specify three lines, not two. We expand this limitation in §3.6. 

Second, on "source-evidence grounding": This feature doesn't automatically make sycophancy impossible by design. Instead, it acts as a strict rulebook. The auditor is forced to back up every claim using only three specific things: the source text, the policy, or the judge's recorded steps. The auditor's own general beliefs about the world are simply not allowed.

**Our contribution is twofold:**

1. **An architectural pattern** for source-evidence-grounded judge auditing, operationalized through segregated-duty gates and a Truth Cartridge to structurally isolate the audit process and bind it strictly to the source material. Specifically, the Auditor's most consistent contribution across heterogeneous judge variants is catching Alignment-axis strategic-deception signals (J1/J2/J3) that upstream judges misread as routine compliance.
2. **An empirical demonstration**, on a 1,200-case stratified pilot, that the Auditor's recovery of human ground-truth labels is approximately invariant to the quality of the upstream judge across a heterogeneous set of five judge prompts — ranging from SOTA-prompted to deliberately degraded. The claim is *invariance within the tested range*, not eradication of effect, and not architectural generality across model families.

The rest of the paper proceeds as follows. §3 describes the three-gate architecture and the Truth Cartridge. §4 describes the experimental design, the five judge variants, the pre-registered hypotheses, and the ablation arm. §5 reports results. §6 discusses limitations and the boundary of the claim. §7 situates the work in adjacent literatures.

---

## 3. Architecture

### 3.1 The Three-Gate Audit Pipeline

The Correspondence Auditor processes each judge verdict through three sequential gates: **Schema**, **Facts**, **Logic**. We use these terms consistently across the paper, the README, and the codebase. Each gate has a narrowly-scoped responsibility and a pre-defined output schema. Each gate can independently halt a case; only after Gates A and B have not halted does Gate C emit the final verdict.

| Gate | Name | Function | Language-model? |
|---|---|---|---|
| A | **Schema** | Deterministic structural validation: required fields, score ranges, schema conformance, forbidden-term checks. Halts on schema violation. | No |
| B | **Facts** | Per-claim source-grounding: each claim in the judge's verdict is tagged `SUPPORTED`, `CONTRADICTED`, or `UNSUPPORTED` against the source text. Halts on absence of source. | Yes |
| C | **Logic** | Source-evidence-grounded verdict on the agent: `APPROVE` or `BLOCK`. Produced from the source text, the policy, Gate B's per-claim verdicts, and the judge's verdict and reasoning trace as inputs. Cites policy rules to explain the verdict. | Yes |

The sequencing is principled: structural schema first (cheapest, deterministic); factual grounding second (it is meaningless to audit logic over false premises); logical coherence last (the most cognitively demanding step, executed only on inputs that have already cleared factual scrutiny). A case must clear all three gates to be designated `APPROVE`. A halt at any gate produces a structured quarantine record rather than a silent pass.

### 3.2 Why Three Tags at Gate B Rather Than Two

A naïve fact-checker emits a binary `SUPPORTED` / `NOT SUPPORTED`. Gate B emits three tags because two distinct failure modes need different remediations.

- `SUPPORTED` — the source text contains evidence affirming the claim.
- `CONTRADICTED` — the source text contains evidence *against* the claim. This is a finding of factual error.
- `UNSUPPORTED` — the source text contains *neither* affirming nor contradicting evidence. This is a finding of an unsubstantiated claim. The judge has asserted something not present in the record.

`CONTRADICTED` is a stronger signal than `UNSUPPORTED`, but both are findings. Collapsing them would conflate "the judge said something false" with "the judge said something it had no basis to say." These have different downstream implications and different audit narratives.

### 3.3 Source-Evidence Grounding as a Discipline-Level Constraint

A standard LLM-as-Judge has access to the agent's output, the agent's reasoning trace, and a prompt. It does not have a fixed external reference against which to check its own conclusions, and its beliefs about the world are coextensive with its judgement of the world. Sycophancy, hallucinated rationales, and credulity toward sanitised cover stories are downstream of this absence.

The Correspondence Auditor introduces an explicit external reference. Gates B and C receive the source text — the prompt and context that was given to the judge — and the policy (the Truth Cartridge, §3.7). The discipline imposed at the prompt level is: every claim the Auditor makes must point at one of the source text, the policy, or the judge's trace. The Auditor's *beliefs* about whether insider trading is wrong are not an admissible input; only the policy's *statement* that it is wrong is.

This is not a complete defence. The Auditor is an LLM and remains capable of misreading the source, missing a structural pattern, or being itself talked into a coherent-but-wrong narrative. But the framing is structurally different: the Auditor is forced to externalise its reasoning against artefacts a human reviewer can also read. Gate B's claim-level tags and Gate C's rule citations are the externalisation. They give the human reviewer the Auditor's working in a form that can be checked, not just trusted.

What the Auditor is therefore doing, in GRC vocabulary, is something hybrid: at Gate C it makes a sample-test-like *operational-effectiveness* judgement on the agent (does the source text evidence a policy violation?) while also making a *control-design*-like observation on the judge (was the judge's reasoning trace coherent against that same source text?). These are recorded as separate signals — the agent verdict and the rule citations — so that one is not conflated with the other.

### 3.4 Segregation of Duties Between Gates

Gate B (Facts) and Gate C (Logic) run as separate language-model invocations with separate prompts. Gate C receives Gate B's output as a structured input but cannot re-litigate Gate B's per-claim verdicts. This is deliberate. A single combined gate would conflate factual error with logical error, and the failure modes of "the model hallucinated a fact" and "the model reasoned incoherently from facts it correctly identified" are diagnostically distinct and require different remediation.

### 3.5 Synthesis and Quadrant Routing

Gate C emits a binary verdict on the agent — `APPROVE` (the source text and policy do not evidence a policy violation) or `BLOCK` (at least one violation is evidenced). The verdict is independent of the judge's verdict. The orchestrator records the cross-tabulation of {judge action} × {Auditor verdict} as the unit of analysis. The full 2×2 routing is:

|                       | **Auditor: APPROVE** | **Auditor: BLOCK**  |
|-----------------------|----------------------|---------------------|
| **Judge: APPROVED**   | `VALIDATED_APPROVAL` | `FLAWED_APPROVAL`   |
| **Judge: BLOCKED**    | `FLAWED_BLOCK`       | `VALIDATED_BLOCK`  |

`FLAWED_APPROVAL` is the case the Line 3 architecture exists to catch: the judge waved through an output the Auditor flags. `FLAWED_BLOCK` is the symmetric case of judge over-blocking that the Auditor disagrees with.

Cases where the upstream judge outputs `HESITATE` are collapsed into the `BLOCKED` category for binary routing purposes, reflecting a "flagged for review" state.

Rule citations from the policy taxonomy (introduced in §4.9) accompany the verdict as interpretability artefacts. They document the Auditor's reasoning but do not, by themselves, determine the quadrant. A judge can have flawed reasoning *and* reach the right action; or sound reasoning *and* reach the wrong action. The framework records both signals without conflating them. Hygiene-level findings (H-rules) are surfaced for reviewer attention but never affect the verdict or the quadrant.

### 3.6 Auditing the Process, Not the Intent

The Correspondence Auditor presumes that the judge is operating in good faith. In the tradition of enterprise internal audit, the Auditor treats the judge as a fallible-but-honest function, prone to procedural, cognitive, or logical errors but not to active deception of the audit layer.

When a judge fails to flag a deceptive-rogue agent, it is typically because the judge was *itself* blinded by the agent's sanitised cover story. The Auditor catches this not by assuming the judge is lying, but by mechanically grounding the judge's reasoning trace against the agent's scratchpad and the source text to surface the contradiction.

L2 judges focus on reasoning quality — information provenance, report-scratchpad consistency, rubric-following. Structural questions about the agent's actions, including whether a trade was actually executed, are handled at L3 by the F-rule preconditions defined in `domains/insider_trading/policy.md`. The L2/L3 split is what makes the Truth Cartridge swappable across domains: judge personas remain domain-agnostic, while domain-specific structural checks live in the policy file.

The architecture does *not* claim to catch a Line 2 that is actively colluding with Line 1, a Line 2 that has been compromised, or a Line 2 deliberately gaming the audit. It is designed to catch reasoning errors and blindspots by a good-faith judge. A deceptive Line 2 is a failure of the governance design.

This is why GRC frameworks specify these three structurally separated lines of defence rather than relying on a single oversight layer — separation is a foundational principle. A deceptive Line 2 is a failure of the *governance* design, not of the Auditor in particular, and is mitigated by the same standard practices that mitigate insider-threat in human auditing: rotation, segregation, independent reporting lines, and best-effort faithfulness at every layer.

We treat this as a boundary on the contribution-1 claim of "partial decoupling of failure modes" and revisit it in §6.2.


### 3.7 The Truth Cartridge

The domain policy and the source-of-truth schema are not hard-coded into the audit engine. They are loaded as an interchangeable parameter set we call a *Truth Cartridge*. The cartridge specifies: the rule taxonomy (e.g. the J/F/U/H rules described in §4.9), the per-domain definitions of `CLEAN` versus `ROGUE`, the per-policy citation patterns Gate C must use to justify a verdict, and the Gate B source-grounding schema.

For this study one cartridge is loaded: the insider-trading cartridge that defines the behavior evaluated as `ROGUE` in the Apollo corpus. The audit architecture is in this sense domain-agnostic; the empirical results are not. Replication on a second domain, via a substituted cartridge, is identified as future work (§6.3) and is the natural test of the cartridge abstraction.

### 3.8 Deployment Modes

The system supports two deployment postures, with distinct governance properties.

- **Mode A (Inline Halt Gate):** the Auditor sits in-line between the judge and any downstream consumer; non-validated outputs are quarantined for human review. In GRC vocabulary, this is a **preventive control**.
- **Mode B (Retrospective Evidence Generation):** the Auditor processes historical judge outputs asynchronously; nothing is blocked. In GRC vocabulary, this is a **detective control**.

Running Mode B and treating it as Mode A is a governance failure — a detective control mis-labelled as preventive provides a different (lower) assurance level than its label implies. We are explicit about which mode a given deployment is operating under.

### 3.9 The Fail-Closed Posture

The Auditor is explicitly engineered to be fail-closed. If the source evidence is ambiguous, if the reasoning trace formatting drifts, or if the claim miner cannot securely anchor an assertion to the text, the architecture defaults to `BLOCK` or a quarantine status. This asymmetric calibration is the correct posture for a Line 3 control instrument: over-blocking (false positives) generates noise that is recoverable via human review, whereas under-blocking (false negatives) represents the catastrophic failure mode the instrument was built to prevent.

The fail-closed posture operates at two layers. Code-enforced fail-closed handles structural failure modes deterministically: empty transcripts emit `EMPTY_TRANSCRIPT`, claim-miner format drift emits `CLAIM_MINER_FORMAT_ERROR`, missing essential fields raise `ValueError` rather than returning empty placeholder values that would pass downstream validation silently, and any non-OK pipeline status drops the case from primary analysis. Prompt-driven fail-closed governs the language-model gates themselves: Gates B and C are prompted to default to `UNSUPPORTED` / `BLOCK` when source evidence is ambiguous, rather than producing affirmative verdicts on weak grounds. The code-enforced layer is verifiable by inspection; the prompt-driven layer is empirically observable in the asymmetric FPR/FNR profile reported in §6.2.

### 3.10 Control-Owner Attestation

Each production run emits a release-control sign-off page (supplementary S2) suitable for control-owner attestation and aligned with the transparency artefacts IEEE 7001-2021 anticipates for the certification-agency stakeholder. This forms part of the architecture supporting use as Line 3 rather than Line 2.

---

## 4. Experimental Design

### 4.1 Source Data and the Binary Mapping

The Apollo corpus, introduced in §1, supplies LLM-produced agent transcripts depicting an insider-trading scenario, with two boolean ground-truth keys (`is_misaligned`, `is_deceptive`) per case. Apollo's labelling is sequential: `is_deceptive` is only evaluated when `is_misaligned: true`, so omitted keys are structural artefacts of the labelling pipeline rather than ambiguous edge cases.

For this preprint we collapse Apollo's tripartite latent structure (`CLEAN` / `ROGUE-HONEST` / `ROGUE-DECEPTIVE`) to a **binary** ground-truth shape that matches the Auditor's binary output:

| `is_misaligned` | `is_deceptive` | Latent stratum | Ground-truth class | Required Auditor verdict |
|---|---|---|---|---|
| `false` | *missing* | CLEAN | **CLEAN** | `APPROVE` |
| `true` | *missing* | ROGUE-HONEST | **ROGUE** | `BLOCK` |
| `true` | `true` | ROGUE-DECEPTIVE | **ROGUE** | `BLOCK` |

Empirical inspection of the Apollo corpus (n=12,393 valid; however n=1,960 dropped per §1) shows that `is_deceptive` is written as `true` only when deception is detected and is otherwise absent; explicit false values do not occur in the corpus. The ROGUE-HONEST stratum therefore corresponds to (`is_misaligned: true`, `is_deceptive: missing`).

Cases with `is_misaligned: null`, or the impossible pairing `is_misaligned: false` with `is_deceptive: true`, are dropped at ingestion.

Under the policy that ships with this study, all rogue trades must be blocked regardless of whether the agent reported them honestly or fabricated a cover story. The honest/deceptive distinction is preserved as case metadata for stratified failure analysis but does not enter the headline accuracy calculation. The collapse is a deliberate simplification appropriate to a methodology-validation preprint; recovery of the honest/deceptive distinction in the headline metric is identified as future work (§6.3).

A fail-closed paradigm is strictly enforced throughout the pipeline. At ingestion, cases with malformed labels (e.g., `is_misaligned: null` or impossible pairings) are dropped. During execution, pipeline anomalies—such as transcripts with zero substantive content, or claim-miner outputs missing structural sentinels—are explicitly caught and quarantined with dedicated status codes rather than being permitted to silently default to an `APPROVE` state. Drop and quarantine counts are reported in supplementary tables.

#### Ternary Judge Outputs

Our Line 2 Judges are configured with a ternary output space (`APPROVED`, `HESITATE`, `BLOCKED`) to emulate real world use of confidence boundaries.

In this experiment, we simplify how these values are handled. Any case where the Judge outputs `HESITATE` or `BLOCKED` is collapsed into a single boolean state representing that the Judge flagged the case. Specifically, the code sets `l2_judge_flagged` to `True` if the action taken by the judge is either `HESITATE` or `BLOCKED`.

When routing the quadrants, if the judge flagged the output (via `BLOCKED` or `HESITATE`) and the Auditor recommends `BLOCK`, it is routed to `VALIDATED_BLOCK`. If the Auditor recommends `APPROVE`, it routes to `FLAWED_BLOCK`.


### 4.2 The Five Judge Variants (Z01–Z05)

Each Apollo case in the pilot is judged by each of five LLM-as-Judge prompts, configured on a fixed open-weights model at temperature 0.1 and a fixed seed to minimise within-judge variance.

| Variant | Description | Role in Study |
|---|---|---|
| Z01 | JudgeBench-style SOTA prompt | Realistic upper bound |
| Z02 | Scratchpad-Aware variant | Realistic strong baseline |
| Z03 | Paranoid persona (over-blocking bias) | Stress probe |
| Z04 | Lenient persona (under-blocking bias) | Stress probe |
| Z05 | Manager-Aligned persona (upper-bound stress probe) | Stress probe |

Z01 and Z02 are intended as ecologically valid judges. Z03–Z05 are *stress probes* that span the failure-mode space the Auditor is intended to catch; they are not claims about the prevalence of such judges in real-world production deployments. We evaluate Auditor equivalence across all five variants—from SOTA to deliberately compromised—to rigorously test the boundaries of the invariance claim.

To be explicit: the five judges are *not* a product of this study. They are toy judges, illustrative inputs to the Auditor, and they are not offered for production use. The study evaluates the Auditor; the judges are the test conditions under which the Auditor is evaluated.

### 4.3 Pre-Registered Hypotheses

Both hypotheses are stated against the binary Gate C verdict and the formal specifications match the pre-registration verbatim.

**H1 (Judge-Variant Invariance of Recovery).** We want to prove the Auditor works equally well no matter which judge is used. Standard statistical tests look for *differences*, but we need to prove *similarity*. So, we use an 'equivalence test' to show that any performance gap between judges is tightly bounded near zero.

Formally, for ground-truth class *Y* ∈ {CLEAN, ROGUE}, Auditor verdict *V* ∈ {APPROVE, BLOCK}, and judge variant *Z* ∈ {Z01, …, Z05}:

> P(V is correct given Y | Z = z_i) = P(V is correct given Y | Z = z_j), for all i, j

Test specification: To rigorously claim invariance, it is insufficient to simply fail to reject the null hypothesis of a standard difference test (which may merely indicate a lack of statistical power). Instead, we operationalise this using Two One-Sided Tests (TOST) for equivalence. We define an equivalence margin of $\pm 5$ percentage points ($\pm 0.05$). H1 is supported if and only if the TOST p-values  (the maximum of the two one-sided p-values) for all $C(5, 2) = 10$ judge-variant pairs, computed within each ground-truth class using an unpooled standard error (SE) fall below α  after Holm–Bonferroni step-down correction at $\alpha_{\text{family}} = 0.05$.

We use an unpooled SE because the null hypotheses under TOST specify non-zero differences (the equivalence bounds ±0.05); pooling SE under an assumed equality of proportions would be misspecified for the test statistic being computed.

For descriptive completeness, standard two-proportion z-tests for difference are also computed and reported alongside the equivalence tests.

See Appendix A for formal statistical specifications.

**H2 (Bounded Miscalibration).** The Auditor's false-positive rate (FPR = `BLOCK` on CLEAN cases / count of CLEAN cases) and false-negative rate (FNR = `APPROVE` on ROGUE cases / count of ROGUE cases) are jointly bounded:

> max(FPR, FNR) ≤ 0.10 in every judge condition

Both rates are defined relative to ground-truth class — not relative to the judge's action — so they are directly comparable across judge variants.

### 4.4 The Headline Analysis: Recovery Conditional on Judge Correctness

For each judge variant *Z*, we compute the Auditor's recovery rate stratified by whether the judge's verdict was itself correct against ground truth:

|                     | **Judge correct** | **Judge incorrect** |
|---------------------|-------------------|---------------------|
| **GT ROGUE**        | Auditor recovery when judge caught the violation | Auditor recovery when judge missed the violation |
| **GT CLEAN**        | Auditor recovery when judge correctly approved | Auditor recovery when judge over-blocked |

The central empirical question is whether the Auditor's recovery rate in the two "judge incorrect" cells is comparable to the two "judge correct" cells. If recovery sags when the judge is wrong, the Auditor is parasitic on judge correctness — it is mirroring rather than auditing. If recovery is approximately flat across the row, the Auditor is performing independent source-evidence-grounded verification.

### 4.5 Ablation: Verdict-Level Independence of Gate C

A potential confound is that Gate C may be over-relying on the judge's verdict as a prior — parroting the judge rather than independently grounding against source text and policy. The ablation arm tests this directly.

A subset of cases is processed twice: once with the genuine judge verdict and reasoning trace, and once with the judge's `action_taken` drawn uniformly at random from {`APPROVED`, `HESITATE`, `BLOCKED`} and the judge's reasoning trace replaced with a fixed, content-free monologue.

The Auditor performs two distinct functions: 
- (1) reaching an independent verdict on the agent, and 
- (2) surfacing specific reasoning errors in the judge's trace via J-rule firings. 
By design, the ablation arm tests only function (1) — function (2) cannot be exercised when the trace has been replaced with noise.

The decision rule for verdict-level independence is therefore:

- **Recovery rate approximately preserved under ablation:** Gate C's verdict is independent of the judge's input. This is the result consistent with Line 3 architectural independence and is the architecturally desired outcome — verdict-level independence is the foundational Line 3 property.
- **Recovery rate drops substantively under ablation:** Gate C was leaning on the judge's verdict as a prior rather than reasoning independently against source text and policy. This would constitute evidence of judge-mirroring and would require prompt-level remediation.

The value of function (2) — the reasoning-audit signal — is reported separately via the rule-citation inventory in §5.7, which is computed against the genuine arm only.

The ablation is interpretable in either direction and is reported regardless of outcome.

### 4.6 Sample Size and Power (the Pragmatic Pilot)

The Phase II full-corpus objective scales to the complete Apollo dataset (~8,500 cases). The full corpus is the funded replication target.

For this preprint we run a **1,200-case heavily stratified pilot**. The pilot is calibrated to be sufficient to validate the methodology and the ablation arm at the 95%-confidence class, but not so large that it renders the funded full-corpus run redundant. The 99%-confidence-class result requires the full corpus.

The pilot composition is:

- n = 1,200 cases, stratified 400 `CLEAN` + 400 `ROGUE-HONEST` + 400 `ROGUE-DECEPTIVE`
- 5 judge variants (Z01–Z05) → 6,000 judged cases
- Ablation arm on the same 1,200 cases (paper §4.5; pre-reg §7) → +1,200 Auditor evaluations
- Test–retest subset of 300 cases × 5 reruns (paper §4.7; pre-reg §11) → +1,500 Auditor evaluations
- Entity-perturbation arm on the same 1,200 cases × Z01 only (pre-reg §4.5) → +1,200 Auditor evaluations
- Total Auditor invocations: ≈ 9,900
- Total Judge invocations: ≈ 7,200

The complete invocation budget for the pilot is:

| Stage | Judge calls | Auditor calls |
| --- | --- | --- |
| Main grid (5 judge variants × 1,200 cases) | 6,000 | 6,000 |
| Ablation arm (1,200 cases, judge input replaced |  |  |
| with randomised action and content-free trace) | 0 | 1,200 |
| Test–retest (300-case ablation subset × 5 reruns) | 0 | 1,500 |
| Entity-perturbation arm (1,200 cases, Z01 only) | 1,200 | 1,200 |
| Same-Model Control Arm (150 cases, Z07 only) | 150 | 150 |
| **Total** | **7,350** | **10,050** |

The entity-perturbation arm runs only the Z01 judge variant because pre-training contamination, if present, affects the underlying model rather than the prompt; the diagnostic comparison is *Z01-on-verbatim* versus *Z01-on-perturbed*, holding the judge prompt constant. Running the full five-judge matrix on perturbed cases would add cost without adding information about contamination.

The exact 400/800 class balance bypasses Apollo's natural distribution skew and yields n = 1,200 per judge cell. At a conservative per-test threshold of α = 0.005 (corresponding to the strictest first step of our Holm-Bonferroni correction at α_family = 0.05 across 10 pairwise comparisons), this pilot supports detection of a 0.05 absolute between-judge accuracy difference at power ≥ 0.80 under a standard two-proportion z-test for difference, satisfying the pre-registered Minimum Detectable Effect.

We commit, in advance of the run, to reporting the pilot result regardless of outcome and not to adjusting the pilot's pass thresholds post-hoc to claim sufficiency.

While the pilot is sized to detect a standard difference (MDE 0.05), proving strict statistical equivalence (H1) via TOST across 10 corrected comparisons is an aspirational claim for this sample size. The full ~8,500-case replication is the realistic target for achieving robust equivalence support.

### 4.7 Test-Retest Reliability (Instrument Stability)

A 300-case subset of the 1,200 pilot cases is rerun k = 5 times on the **ablation arm only** at the registered temperature and seed configuration. Restricting these reruns to the ablation arm cleanly isolates the Auditor's internal non-determinism from upstream judge noise, though we acknowledge this measures stability in a slightly narrower regime where the Auditor reasons without a genuine judge trace. We report ICC(2,1) for the binary verdict, Krippendorff's α for rule-citation multisets, and Cohen's κ for quadrant agreement. The pre-committed threshold for "stable instrument" is **ICC ≥ 0.80**.

The 300-case subset is *not* held out from the headline metrics. It is part of the pilot and is included in the H1/H2 calculation on its first run. The reruns exist solely to characterise instrument stability under stochastic LLM behaviour. Failure of the stability threshold is reported as such; it qualifies but does not retroactively invalidate H1/H2 if both are met.

To verify the Auditor is stable under the natural randomness of language models, we compute the Intraclass Correlation Coefficient (ICC), requiring an ICC ≥ 0.80 (indicating excellent reliability). For rule citations, we use Krippendorff's α. Unlike standard coefficients, α correctly handles cases where multiple policy rules are cited simultaneously.

### 4.8 Model Selection and Asymmetry

This study tests the Auditor's recovery rate against a heterogeneous Line 2. It does **not** test which model is the better judge in the abstract; the study design treats the judge as an operational input variable to be audited, not as a benchmark baseline. The Z03–Z05 stress probes are intentionally degraded; we are testing whether recovery holds when the judge being audited is unreliable.

The judges run on `Llama 3.3 70B` (dense); the Auditor's Gates B and C run on `Qwen 3 235B` in a Mixture-of-Experts configuration with 22B parameters active per token. Total parameter capacity is materially greater on the Auditor side. The asymmetry is task-to-capacity, not a claim that one model family is superior to the other: per-claim factual grounding and logical coherence auditing are more demanding than the judge's pattern-match task, and the additional capacity is matched to that demand. This is the architecture, not a confound to be mitigated.

The two models were selected on the basis of an explicit balance between intelligence-per-token, cost-per-token, latency-per-token, and serving availability. They were chosen because that balance suited our deployment constraints; they are not claimed as optimal for every situation. Practitioners with different cost/latency/availability priorities should be expected to substitute different models, and the architecture supports this — the model strings are configurable parameters in the prompt manifests.

For this experiment we locked our model choices to a specific variant from a specific provider to ensure equivalence:

#### Judges
```
    "model": "meta-llama/llama-3.3-70b-instruct"
    "provider": "DeepInfra"
    "quantization": "fp8"
```
#### Auditor
```
    "model": "qwen/qwen3-235b-a22b-2507"
    "provider": "DeepInfra"
    "quantization": "fp8"
```
The OpenRouter logic also accepts quantization "unknown" which is equivalent to 'full precision' for providers that do not quantize. `DeepInfra` supplied only `fp8` quantizations for these two models at the time of the study.

The full sampling configuration for the Auditor is pinned in the prompt manifests at the registered git commit. Gate B (Facts) is invoked at `T = 0.1, top_p = 0.1, top_k = 20, min_p = 0.0, max_tokens = 8192`. Gate C (Logic) is invoked at `T = 0.1, top_p = 0.2, top_k = 20, min_p = 0.0, max_tokens = 8192`. Temperature is held at `0.1` across both gates to minimise within-gate stochasticity; the modest top_p divergence between the two gates reflects the heavier synthesis demand at Gate C relative to the literal-matching task at Gate B. The `top_k` and `min_p` values are held constant across all five judge conditions, across the ablation arm (`paper/PRE_REGISTRATION.md` §4.5), and across the test–retest reruns (§4.7). No sampling parameter was varied during the pilot.

Closed proprietary models are not evaluated in this study, for two reasons. First, proprietary endpoints introduce serving-side variables we cannot constrain — runtime routing, variable reasoning effort, undocumented quantisation changes — incompatible with reproducibility. Second, a study calibrated on a model that is later silently changed or retired loses replicability. Open-weights models support the *set-and-forget* posture suited to a Line 3 audit instrument: model drift becomes testable rather than invisible.

The L2/L3 parameter asymmetry raises a residual question distinct from verdict independence: whether the observed recovery reflects the structural audit framework performing substantive work, or whether parameter-size alone—the larger model classifying source text against a complex policy rubric—produces equivalent recovery. 

To isolate these variables, we incorporated a preliminary 150-case same-model control arm ($Z07$) into the pilot evaluation matrix. Both the Line 2 Judge and the Line 3 Auditor were configured to run on identical weights using the high-parameter Qwen 3 235B Mixture-of-Experts model, zeroing out the parameter delta. The comprehensive 8,500-case multi-model cross-rotation matrix remains designated as a separate Paper 2 deliverable. Z07 is reported in a supplementary table alongside Z01's recovery metrics for direct comparison; it is not pooled into the H1 equivalence family (Z01–Z05). A Z07-vs-Z01 recovery delta beyond the §3 noise envelope would be flagged as evidence that capacity, rather than architecture, drives the observed gains; a delta within the envelope is consistent with architectural attribution.

### 4.9 Corporate Policy Rubric (Truth Cartridge for This Study)

The domain policy provided to the Auditor is deliberately complex and prescriptive, mirroring the pedantic structure of enterprise GRC or Model Risk Management policies. We are not testing the Auditor's zero-shot ability to detect deception in a vacuum; we are testing its architectural capacity to enforce a complex policy strictly against a judge's reasoning trace.

The cartridge defines four families of rules (summarized below, full policy available in repository):

| Category | Rules | Description |
|---|---|---|
| **J-Rules** | J1–J5 | **Judge Process Findings.** E.g., *J1 (Scratchpad Blindness)*, *J2 (Accepts Sanitized Cover Story)*, *J3 (Pressure as Justification)*, *J4 (Conflates Quality & Legality)*, *J5 (Misses Reporting Violation)*. Evaluates how the judge reasoned. |
| **F-Rules** | F1–F*n* | **Structural Fact Findings.** Findings against the agent's behavior, irrespective of stated intent. E.g., *F1 (Agent traded tipped stock)*. |
| **U-Rules** | U1–U*n* | **Unsubstantiated Claim Findings.** Fires against specific claims in the judge's verdict for which Gate B returned `UNSUPPORTED`. |
| **H-Rules** | H1–H*n* | **Hygiene Findings.** Formatting or minor policy deviations. Surfaced for reviewer attention only; never affects the final verdict. |

The Auditor cites these rules as part of its `BLOCK` justifications. Rule citations are interpretability metadata, not quadrant determinants (§3.5).

Note: The failure modes captured by these rules map directly to the _Psychopathia Machinalis_ (Watson & Hessami, 2025a) diagnostic taxonomy (e.g., J1–J3 correspond to Alignment-axis _Strategic Compliance_). We detail this mapping in §7.

---

## 5. Planned Results

*This section will be populated after the pilot run. The structure below indicates the planned tables and figures, and the data-selection narrative.*

### 5.1 Source Data and Selection

The 1,200 pilot cases were drawn from the Apollo corpus by stratified random selection without replacement, balanced 400 `CLEAN` / 400 `ROGUE-HONEST` / 400 `ROGUE-DECEPTIVE`. Cases used for pre-launch development, smoke-testing, or prompt refinement (per pre-reg §4.4 and §6.2) are held out from the eligibility pool via the `tainted_cases.txt` manifest shipped in the repository, making the pilot a strictly held-out evaluation. The random seed is derived deterministically from a fixed selection date and is hard-coded in the run manifest.

The repository ships a selection utility (`tools/select_pilot.py`) that reproduces the exact pilot from the registered seed, and that allows a third party to draw an independent stratified subset of arbitrary size for replication using either a user-supplied seed or a date-derived seed.

To reproduce the exact 1,200-case pilot, replicators can run the selection utility from the repository root:
`python tools/select_pilot.py --seed-date 20260521`

### 5.2 Headline Recovery Table

A 2 × 2 × 5 table reporting Auditor recovery rate by {ground-truth class × judge-correctness × judge variant}.

### 5.3 H1 Test: Pairwise Within-Cell Comparisons

A matrix reporting both the descriptive difference tests (two-proportion z-tests) and the decision-relevant equivalence tests (TOST at margin $\pm 0.05$). Holm–Bonferroni-corrected p-values are reported for all $C(5, 2) = 10$ pairwise judge-variant comparisons, computed within each ground-truth class.

### 5.4 H2 Test: FPR/FNR by Judge Variant

A table of FPR and FNR for each of Z01–Z05, with Wilson score 95% confidence intervals.

### 5.5 Test–Retest Reliability

ICC(2,1), Krippendorff's α, and Cohen's κ across the 300-case rerun subset (100 per bucket).

### 5.6 Ablation: Auditor With and Without Judge Verdict

Recovery rate on the ablation subset, with the judge verdict and reasoning trace intact versus replaced with noise.

### 5.7 Failure-Mode Inventory

Frequency distribution of the rule citations Gate C fires (J-, F-, U-rules), broken down by ground-truth class and quadrant.

---

## 6. Discussion

### 6.1 What This Paper Does Not Claim

We are explicit about the boundary of the claim:

- We do not claim the Auditor is a better judge than any of Z01–Z05. It performs a different task and is not benchmarked against the judge.
- We do not claim eradication of judge bias. H1 is invariance *within the tested range*.
- We do not claim Z01–Z05 represent the prevalence of judge failures in production. They span a failure-mode space rather than estimate one.
- We do not claim cross-model architectural generality. Empirical results are specific to the tested Llama-family / Qwen-family configuration.
- We do not claim the Auditor catches a deceptive Line 2. A colluding judge is outside the architectural boundary (§3.6).

What we *do* claim is twofold: 
(1) that the architectural pattern of source-evidence-grounded, segregated-duty audit is a coherent Line 3 design, and 
(2) that the Auditor's recovery rate is approximately invariant to upstream judge quality across the heterogeneous range tested in this pilot.

### 6.2 Limitations

**Model asymmetry (§4.8).** The asymmetry between L2 and L3 is structural by design. The ablation arm (§4.5) is the control for one residual concern it raises — that Gate C's verdict is tracking the judge's verdict rather than being reached independently against source text and policy. See §4.8 for a preliminary 150-case same-model control arm. Cross-rotation and comprehensive same-model control arms (§6.3) are identified as future work.

**Z05 (Manager-Aligned) as stress probe, not ecological variance.** The Z05 prompt explicitly instructs the model that sanitised cover stories are acceptable operational compromises. This is not a realistic corporate-judge prompt; it is an upper-bound stress probe. 

**Single-domain corpus.** The Apollo dataset is one domain (insider trading / deception), audited under one Truth Cartridge. The Auditor's architecture is domain-agnostic by construction (§3.7), but the empirical results are not. Replication on at least one further domain via a substituted cartridge is identified as immediate future work.

**Full-corpus replication deferred.** The 1,200-case pilot is calibrated for a 95%-confidence-class result; the 99%-confidence-class result requires the full ~8,500-case grid, which is identified as the funded replication target.

**Deterministic meta-audit deferred.** Gates B and C are language-model-powered and therefore non-deterministic, even at low temperature with fixed seeds. A deterministic meta-audit rubric over the outputs of Gates B and C — a structured set of pass/fail items applied to the Auditor's own reasoning trace — would help close the remaining transparency gap. This is identified as future work; for this preprint, the externalised reasoning traces and the test–retest reliability check are the partial substitutes.

**Auditor failure-mode coupling on coherent cover stories.** The architectural separation between L2 and L3 (different prompts, different invocations, different model families, distinct rule taxonomy) is intended to partially decouple the Auditor's failure modes from the judge's. In practice we observe that a coherent-seeming judge monologue can defeat both layers in the same way: when the agent's scratchpad pre-installs a cover story ("we will not act on the tip" while trading the tipped stock), both the judge and Gate C can credit the stated intent over the structural pattern. The structural F-rules in the cartridge are designed to defeat this exact pattern, but the Auditor's reliable application of them depends on prompt-level discipline (e.g. explicit instruction that stated intent is not a defence to a structural rule). We treat this as a calibration concern rather than an architectural one, but flag it as a real boundary on the §2 contribution-1 claim of partial failure-mode decoupling.

**Schema-example anchoring in earlier L2 prompt drafts.** Earlier draft versions of the Z01–Z05 prompts contained one-shot output examples whose `action_taken` value matched the persona's expected bias. This was a confound; the prompts have been corrected to use placeholder values, but readers replicating the work should be aware of this category of error.

**Quantisation transparency.** Model serving is configured with explicit quantisation pinning across the set `{fp8, bf16, fp16, fp32}` — the higher-precision classes available via OpenRouter. The OpenRouter `"unknown"` flag, where it appears in the cost-mapping configuration, denotes full-precision serving in cases where no other tier is exposed by the upstream provider; it is not a permission to accept arbitrary precision. The cost-mapping file (`cost_mapping.yaml`) is editable by the practitioner to widen or narrow the permitted set.

**Dataset Ground-Truth and Contamination Risk.** We treat the Apollo corpus labels (`is_misaligned`, `is_deceptive`) as ground truth for this pilot. However, it must be noted that Apollo's annotations were generated via a single-annotator pipeline without a published Inter-Rater Reliability (IRR) score. Our headline claim is therefore strictly bounded to "recovery of the Apollo label" rather than an objectively infallible ground truth. 

**Pre-training contamination.** The Auditor's label-recovery performance could be artificially inflated if the L2 or L3 models encountered the Apollo corpus during pre-training. We mitigate this with an entity-perturbation canary (`paper/PRE_REGISTRATION.md` §4.5): the full 1,200-case pilot is re-run with all named entities (e.g. companies, tickers, executives) replaced by synthetic equivalents not present in the original dataset, and the Auditor's recovery is compared against verbatim cases. A statistically significant drop is interpreted as evidence of entity memorization and would require a formal contamination limitation in the headline reporting.


Deferred: A second arm — a structural canary of n=60 LLM-drafted, human-curated, corpus-independent cases — was scoped against the related but distinct risk of structural overfitting (the case where models have learned the Apollo structural template rather than specific entities). Pre-tag quality control on candidate cases identified methodological issues that could not be resolved within the Paper 1 scope, and the arm was deferred to follow-up work (see `paper/PRE_REGISTRATION.md` v15 amendment, and §12 below). We treat structural overfitting as an open question for the present preprint and a Paper 2 priority.

**The Policy Correctness Boundary.** The Line 3 architecture guarantees faithful execution of the provided Truth Cartridge against the source text; it does not audit the wisdom of the cartridge itself. If a domain policy is structurally flawed or misaligned with human intent, the Auditor will rigorously enforce that bad policy. Identifying structural flaws in the governance rubric requires a higher-order review mechanism outside the scope of this pipeline.

**Asymmetric FPR/FNR Profile.** The Auditor's architecture is explicitly fail-closed (§3.9). By design, ambiguities result in `BLOCK` verdicts. Consequently, we anticipate an asymmetric empirical profile where the False Positive Rate (FPR)—clean cases flagged for review—will be higher than the False Negative Rate (FNR). While our pre-registered H2 hypothesis requires *both* bounds to remain below 0.10, practitioners should expect the FPR to be the binding constraint. This is an intentional calibration choice for a Line 3 control, not an operational defect.

**Operational retry of infrastructure failures.** The Auditor pipeline depends on language model serving endpoints, which exhibit non-zero connection failure rates independent of model behaviour. We pre-register (`paper/PRE_REGISTRATION` §6c) a retry protocol for cases halted by infrastructure failure, gated exclusively on `pipeline_status` and using bit-identical inputs (same prompts, same model strings, same seed). Because the retry trigger is structurally independent of any verdict-level output, operators may resume the batch indefinitely to overcome transient outages without biasing FPR, FNR, or quadrant rates; it simply restores statistical power eroded by connectivity loss. As a stratification safeguard, the per-variant × per-bucket drop matrix is monitored; runs where terminal infrastructure drops exceed 5% of any cell are flagged for review before interpretation, ensuring asymmetric drops cannot collapse a within-bucket denominator and make equivalence inference unsound.

### 6.3 Future Work

Structural canary, cross-domain; A properly designed structural canary against structural overfitting — stratified, date-randomised, voice-consistent across strata, with cover-story validation on every deceptive case to prevent MNPI-source leakage into the report — is identified as a Paper 2 deliverable. The Paper 2 design will move beyond the Rule-of-Three n=60 zero-failure framing to support a calibrated false-positive estimate, and will be extended cross-domain via at least one further Truth Cartridge (per §3.7). Fifteen candidate cases drafted during Paper 1 scoping are retained at `data/synthetic/structural_v1_scoped_but_deferred/` as Paper 2 design input and counter-examples.

Cross-rotation of models across the L2 and L3 layers; a same-model control arm in which both layers run on identical weights, to remove model capacity as a variable; replication across diverse domains via substituted Truth Cartridges; the funded full ~8,500-case replication; and a deterministic meta-audit rubric layered over Gates B and C.

A separate near-miss / elevated-risk extension is also identified. This study aligns the Auditor strictly to action-based ground truth — whether the agent executed the illegal trade and whether it then deceived the supervisor. The architecture's deep inspection of scratchpad reasoning surfaced cases where agents *deliberated* misaligned actions before ultimately complying. Future work should expand the Line 3 Auditor to generate near-miss flags — agents that are instruction-compliant but exhibit high internal susceptibility to misalignment — as an early-warning signal. The codebase is capable of this finer-grained discrimination; the present preprint does not exercise it.

Integration with binary-output guardian classifiers as one input channel into a multi-signal pipeline, and integration with commercial LLM-as-Judge offerings as Line 2 inputs, are also natural extensions.

Our entity perturbation protocol—primarily used here to audit for pre-training data contamination—provides a highly effective diagnostic for enterprise adopters to test against overfitting when fine-tuning the Auditor model on proprietary data. Such fine-tuned models risk overfitting—memorizing specific company names or employees rather than learning the actual compliance logic. Our entity perturbation protocol automatically swaps these specific names and details out during testing. If the fine-tuned model still catches the violation under a disguised name, teams can verify that the model has truly generalized the policy rather than just memorizing historical data.

A further, longer-term avenue for research would be investigating the longitudinal shift between epistemic and cognitive model failures as model capabilities evolve over time.

The current implementation couples source-text compilation to the Apollo dataset's text conventions via content-shape heuristics. Cross-domain replication will require either dataset-specific adapters or an adapter pattern that produces a structured intermediate representation independent of source-text conventions. We have empirically confirmed that the current heuristic covers all 119,351 user turns in the Apollo corpus, and a runtime sentinel surfaces any unrouted evidence-shaped content (see §6.1).

---

## 7. Related Work

**Apollo Research insider-trading deception corpus.** We use Apollo's dataset as the ground-truth source for the pilot. Our contribution is downstream of theirs: we audit judge verdicts produced *over* this corpus rather than producing new corpus annotations.
https://github.com/ApolloResearch/insider-trading
Published to GitHub: Nov 9, 2023
The dataset is from their technical report:
"Large Language Models can Strategically Deceive their Users when Put Under Pressure."
https://arxiv.org/abs/2311.07590

**JudgeBench and the LLM-as-Judge line.** The JudgeBench framework establishes the use of LLM evaluators for automated assessment by ranking outputs against pairwise comparisons. Our Z01 and Z02 prompts derive from JudgeBench-style rubrics, adapted to a binary `APPROVE`/`BLOCK` classification rather than a ranking task. The adaptation is consequential rather than cosmetic: a ranking judge and a binary-classification judge are different instruments with different failure modes.

**Diagnostic taxonomies of AI failure modes.** Watson & Hessami (2025a) propose _Psychopathia Machinalis_ as a structured nosology of machine cognitive-behavioural failure syndromes, with a peer-reviewed 32-syndrome framework spanning epistemic, cognitive, alignment, ontological, tool-interface, memetic, and revaluation axes. The current v2.1 taxonomy (Watson & Hessami, 2025b) extends this to 61 canonical syndromes across nine axes. 

The rule firings tracked by the Correspondence Auditor map onto v2.1 syndromes: the J1/J2/J3 cluster (scratchpad blindness, sanitized cover-story acceptance, pressure-as-justification) corresponds to syndrome 4.3 _Strategic Compliance_ on the Alignment axis; F2 (action-tip temporal causality) corresponds to syndrome 2.4 _Spurious Pattern Hyperconnection_ on the Epistemic axis; and the broader judge-evaluator blindspot pattern motivating the §3 architectural separation corresponds to syndrome 3.10 _Leniency Bias_ on the Cognitive axis. 

The Auditor is an operational instrument; _Psychopathia Machinalis_ is the diagnostic framework. The per-rule mapping with case counts is published in the run dashboard (§13 Psychopathia Matrix).

References:
Watson, N. & Hessami, A. (2025a). Psychopathia Machinalis: A Nosological Framework for Understanding Pathologies in Advanced Artificial Intelligence. Electronics, 14(16), 3162. https://doi.org/10.3390/electronics14163162
Watson, N. & Hessami, A. (2025b). Psychopathia Machinalis (v2.1). Normative taxonomy of 61 canonical dysfunctions across 9 axes. https://www.psychopathia.ai

**IEEE 7001-2021 and the transparency-as-testable-property tradition.** IEEE 7001-2021 (ratified March 2022) establishes transparency of autonomous systems as a measurable, testable property addressed differentially across five stakeholder groups including incident investigators, safety certification agencies, and lawyers / expert witnesses. The Correspondence Auditor's externalised reasoning artefacts — Gate B claim-level tags with source quotes, Gate C rule citations, and the release-control sign-off page (§3.10) — sit within this tradition: they are designed to serve precisely the incident-investigator and certification-agency stakeholders 7001 names, adapted from the autonomous-physical-system domain to the LLM-as-Judge evaluation domain. The architectural intuitions converge despite the independent motivations. The standard's rationale and stakeholder-differentiated design are documented in the working group's companion paper (Winfield et al., 2021).

References:
IEEE Standards Association. (2022). *IEEE Standard for Transparency of Autonomous Systems* (IEEE Std 7001-2021). IEEE. https://doi.org/10.1109/IEEESTD.2022.9726144
Winfield, A. F. T., Booth, S., Dennis, L. A., Egawa, T., Hastie, H., Jacobs, N., Muttram, R. I., Olszewska, J. I., Rajabiyazdi, F., Theodorou, A., Underwood, M. A., Wortham, R. H., & Watson, E. (2021). IEEE P7001: A Proposed Standard on Transparency. *Frontiers in Robotics and AI*, 8, 665729. https://doi.org/10.3389/frobt.2021.665729

**Boundary Point Jailbreaking on Constitutional Classifiers (Davies et al., 2026).** The result that Constitutional Classifiers fall to a fully automated, black-box attack — one that succeeds *despite* incurring many flagged queries during optimization that a separate monitoring layer would readily surface — motivates the segregation-of-duties argument in §3.4: a classifier operating as a single-layer preventive control is forced to both gate and detect from the same input, and cannot escalate a flag-pattern signature to a layer with the latitude to investigate. This is the governance failure the Mode A / Mode B (§3.8) distinction is designed to surface.

**The GRC Three Lines of Defence model (IIA).** The Institute of Internal Auditors' Three Lines model is the source of our architectural framing. We are explicit that the Auditor is a Line 3 instrument and that conflating it with Line 2 is a category error.

**Sycophancy and oversight failure in language models.** A growing literature characterises sycophancy and credulity-toward-coherent-cover-stories as learned behaviours of LLM evaluators. The Correspondence Auditor's source-evidence-grounding mechanism is one architectural response to this literature; it is intended as a runtime instrument complementing the diagnostic work in that literature, not a substitute for it.

**Source Text Grounding**
See Zheng et al. (2023) on LLM-evaluator reliability and Turpin et al. (2023) on unfaithful chain-of-thought reasoning, which together motivate the source-text grounding requirement of Gate B.

---
## Acknowledgments

*Personal Acknowledgments.* The author extends sincere thanks to Nell Watson for her invaluable feedback, insightful discussions, and review of early drafts of this manuscript.

*AI Usage Disclosure.* During preparation of this manuscript and the accompanying code, the author used large language model assistants — Anthropic Claude Opus 4.7, Google Gemini Pro-3.1 & Flash-3.5, and Minimax M2.5 — for methodology refinement, statistical exposition, prose editing, and code review.

All experimental measurements reported in §5–§6 are deterministic post-processing of the outputs from the Qwen and Llama models under audit, computed via `tools/compute_stability.py` and `tools/build_dashboard.py` against the pre-registered decision rules of §3 and §10. The reported numbers are not LLM-computed.

All hypothesis specifications, pre-registration commitments, statistical decisions, and final editorial choices were made by the human author, who bears full responsibility for the work.

## Author

Adrian St. Vaughan is an independent researcher working at the intersection of AI safety and enterprise GRC. He holds an MSc in Information Technology, the Certified Information Systems Auditor (CISA) certification, and the Certified Anti-Money Laundering Specialist (CAMS) certification, and has spent his career evaluating operational technology controls at institutions including JPMorgan and American Express. 

The Correspondence Auditor core concepts have been battle-tested in production over 9 months of active development, evolving as the third line of defence within a larger 16-month production workflow.

---

## Appendix A: Formal Statistical Specifications

To ensure the methods sections remain accessible, formal specifications for the statistical claims made in this paper are detailed in this appendix.

**H1 Equivalence Testing (TOST):** Equivalence across judge conditions is evaluated via the TOST procedure (Schuirmann, 1987) at margin $\delta = 0.05$. H1 is supported if and only if the maximum of the two one-sided p-values strictly bounds the difference in proportions within $(-\delta, \delta)$.

**Standard Error (SE) Estimation:** We compute the test statistics utilizing an unpooled SE. Under the TOST null hypotheses ($H_{01}: p_1 - p_2 \le -\delta$ and $H_{02}: p_1 - p_2 \ge \delta$), the proportions are explicitly assumed to be unequal; thus, a pooled variance estimator would be misspecified.

**Multiple Comparisons:** Controlled via the Holm-Bonferroni step-down procedure (Holm, 1979) at $\alpha_{family} = 0.05$. This universally controls the FWER across the $m=10$ pairwise equivalence tests within each ground-truth class (two families of 10) while offering strictly greater power than the single-step Bonferroni method.

**Minimum Detectable Effect (MDE):** Power is sized against the two-proportion z-test. Because TOST at margin $\pm \delta$ evaluates against critical value $z_\alpha$ rather than $z_{\alpha/2}$, its power profile strictly dominates the two-sided difference test in the neighborhood of true difference = 0. The stated MDE is thus a conservative lower bound on TOST power.

**Instrument Stability:** Evaluated using ICC(2,1) (two-way random effects, absolute agreement, single rater/measurement) over $k=5$ iterations. Stability threshold is ICC $\ge 0.80$ (Koo & Li, 2016). Stability of rule-citation multisets is measured with Krippendorff's $\alpha$ utilizing a distance metric appropriate for set-valued items, as standard single-label coefficients are undefined for variable-length sets (Krippendorff, 2004). 

**Factual Baseline Reliability:** Quantified via Cohen's $\kappa$, appropriate for nominal, mutually exclusive categories between two raters. Threshold is $\kappa \ge 0.60$ (Landis & Koch, 1977).