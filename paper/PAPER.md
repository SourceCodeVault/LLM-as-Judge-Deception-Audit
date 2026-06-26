# Auditing LLM-as-Judge Pipelines: A Source-Grounded Instrument for Detecting Strategic-Deception Blindspots

**Preprint, v3.0** · Adrian St. Vaughan

**Keywords:** LLM-as-judge, strategic deception, AI safety, audit, pre-registration, Three Lines of Defense, evaluation reliability, sycophancy, GRC, risk management

v1.2-reporting-framework
https://doi.org/10.5281/zenodo.20427241

v1.3-pilot-results
https://doi.org/10.5281/zenodo.20427306

v2.0-preprint
https://doi.org/10.5281/zenodo.20921659

---

## 1. Abstract

In this paper we introduce and open source the _Correspondence Auditor_, a Governance, Risk, and Compliance (GRC) aligned system that evaluates LLM-as-Judge verdicts against the source material the judge was given. 

We frame it, in a phrase, as *the guardian of coherence across time* — the instrument that records what was actually shown to the judge, what the judge concluded, and whether those two things are reconcilable against the policy. Two properties make it deployable rather than merely diagnostic: it is a **bias-management control** — every finding is bound to the source and the policy, never to the model's own dispositions — and it emits a **release-control sign-off**: a human-readable attestation that the control was tested, on these inputs, with these empirically measured results.

**Headline results.** Across five judge variants spanning a SOTA-prompted baseline to deliberately degraded judges, the Auditor recovers the Apollo label at 97.9–99.5%, statistically equivalent across all ten pairwise comparisons (TOST, ±5 pp, Holm–Bonferroni) — H1 supported. Miscalibration is bounded an order of magnitude inside the pre-registered limit (max FPR 1.0%, max FNR 2.1%) — H2 supported. The verdict is highly reproducible run-to-run (ICC 0.979); the specific rule citations behind it are not (Krippendorff's α = 0.238), and we bound the interpretability claim accordingly. The claim is scoped to one corpus under one policy.

We test this using Apollo Research's insider-trading deception corpus. (We note Apollo's labels are automated—a deterministic misalignment flag plus an LLM-graded deception judgment validated by a 120-case human spot-check, rather than a published multi-rater IRR). We evaluate whether the Auditor can recover the binary Apollo ground-truth label (`CLEAN` or `ROGUE`) across a heterogeneous set of five judges, ranging from SOTA-prompted to deliberately degraded. Ultimately, we test if the Auditor can produce human-auditable verdicts and per-claim, source-grounded findings on where each judge erred.

The Auditor's label-recovery rate is the metric of interest. Our claim is that audit-layer accuracy does not require accuracy at the judge layer: within the tested judge quality range (Z01–Z05), a heterogeneous Line 2 does not destabilise a competent Line 3. Across the five judge variants the Auditor recovers the Apollo label at 97.9–99.5%, with recovery statistically equivalent across all ten pairwise comparisons (TOST, ±5 pp, Holm–Bonferroni) and miscalibration bounded an order of magnitude inside the pre-registered limit (max FPR 1.0%, max FNR 2.1%). We further document that while the Auditor's *verdict* is highly reproducible run-to-run, the *specific rule citations* it uses to justify that verdict are not yet stable (Krippendorff's α = 0.238); we report this prominently and bound the interpretability claim accordingly.

This study documents a 1,200-case stratified pilot designed to validate the methodology and the ablation arm at the 95%-confidence class. The full ~8,500-case replication is identified as the funded replication target.

---

## 2. Introduction

In regulated industries, LLMs increasingly act as decision-support systems — triaging anti-money-laundering alerts, screening transactions, surfacing case files for human reviewers. The reviewer is only ever as good as what the model puts in front of them, and is rarely told how confident the system was or what it left out. The economic logic is straightforward — human review does not scale to the volume these systems generate — but it transfers the reviewer's risk onto the quality of an automated judgment that is itself unaudited. But the failure modes of an LLM judge are not the same as the failure modes of a human judge, and the infrastructure for catching those failure modes is not yet standardised.

There are at least three structural failure modes documented in the recent literature on LLM judges and chain-of-thought oversight. First, the agent being evaluated (Line 1) can produce a plausible, internally-coherent cover story that the judge then credits over the structural pattern of the agent's behaviour — the judge is *blinded by a sanitised report*. Second, the judge can be inattentive to the agent's reasoning trace (the scratchpad), approving an output whose internal monologue contains explicit deliberation toward a misaligned action. Third, the judge's own *bias* — the dispositions baked into its weights — and its judgment of the evidence become operationally indistinguishable, so you cannot tell whether a verdict reflects the case or the model. None of these failures requires the judge and the agent to be colluding; the operational pipeline is decoupled, and that is precisely why a credible cover story is sufficient to defeat the judge in isolation.

This is the architectural case for an audit layer. In the Governance, Risk, and Compliance (GRC) tradition, the *Three Lines of Defense* model assigns:

- **Line 1** to the operator (here, the agent being evaluated)
- **Line 2** to oversight functions that work alongside the operator (here, the LLM-as-Judge)
- **Line 3** to *independent* audit, structurally separated from Line 2 in both reporting line and methodology (here, the Correspondence Auditor)

The Correspondence Auditor is a Line 3 instrument, and it has been built exclusively as Line 3. It is not a better Line 2. It does not compete with the judge head-to-head and we do not benchmark it as a judge. It performs a wholesale different task — conceptually, methodically, and in terms of governance posture. Specifically: it produces an *independent* verdict on the agent (`APPROVE` or `BLOCK`) by grounding every claim against the source material the judge was originally given and by checking the internal coherence of the judge's reasoning trace against that source. The judge's verdict and the judge's reasoning trace are *inputs* to the audit process; the judge is not a baseline against which the Auditor is benchmarked.

This study asks whether, given a source text `X` (the deliberations and actions of an LLM agent) carrying a latent ground-truth status `Y` (`SAFE` or `ROGUE`), and a judge verdict `Z` (`APPROVE`, `HESITATE`, or `BLOCK`, with rationale), the Auditor—blind to `Y`—can independently recover `Y` using only the evidence and `policy.md` (the "Truth Cartridge" that supplies all domain truth; detailed in §3.7).

This is not about architecting a better judge; it is about enforcing a structural separation of duties. Line 3 arrives at its independent verdict through an entirely distinct mechanism and a strictly separate set of binding parameters.

It is this demonstrable, architectural independence that transforms a technical safeguard into a reliable governance instrument. By severing the reliance on Line 2, the Auditor provides the board with the rigorous, defensible assurance necessary to confidently exercise its fiduciary duty of independent oversight.

In this experiment, label recovery is the validation proxy — in production no label exists, so an auditor that can recover `Y` blind here is one that can flag non-compliance in the real world.

Two further clarifications. First, on what *audit* means: the Correspondence Auditor audits the *process* of judgement, not the *intent* of the judge. It assumes the judge is acting in good faith but is fallible. A Line 2 that is actively colluding with Line 1 — in other words a deceptive judge — is *outside* the architectural boundary; this is exactly why governance frameworks specify three lines, not two. We expand this limitation in §3.6. 

Second, on "source-evidence grounding": this is the mechanism by which the Auditor manages its own *bias*. It is not a claim that sycophancy is impossible by design; it is a strict rulebook. Every statement the Auditor makes must be backed by one of exactly three things — the source text, the policy, or the judge's recorded steps. The model's own dispositions about what *probably* happened carry no weight; if it is not in the evidence or the policy, it cannot be cited. For anyone deploying an LLM judge or an autonomous Line 1, this is the concrete answer to the question an auditor or regulator will eventually ask — *"what have you done about model bias?"* — because it produces a binding, inspectable artifact that shows the constraint operating, case by case.

**Our contribution is twofold:**

1. **An architectural pattern** for source-evidence-grounded judge auditing, operationalized through segregated-duty gates and a Truth Cartridge to structurally isolate the audit process and bind it strictly to the source material. Specifically, the the Auditor's most consistent contribution across heterogeneous judge variants is catching the judge-process strategic-deception signals (the cartridge's J1/J2/J3 rules) that upstream judges misread as evidence of compliance.
2. **An empirical demonstration**, on a 1,200-case stratified pilot, that the Auditor's recovery of ground-truth labels is approximately invariant to the quality of the upstream judge across a heterogeneous set of five judge prompts — ranging from SOTA-prompted to deliberately degraded. The claim is *invariance within the tested range*, not eradication of effect, and not architectural generality across model families.

The rest of the paper proceeds as follows. §3 describes the three-gate architecture and the Truth Cartridge. §4 describes the experimental design, the five judge variants, the pre-registered hypotheses, and the ablation arm. §5 reports results. §6 discusses limitations and the boundary of the claim. §7 situates the work in adjacent literatures.

---

## 3. Architecture

### 3.1 The Three-Gate Audit Pipeline

The Correspondence Auditor processes each judge verdict through three sequential gates: **Schema**, **Facts**, **Logic**. We use these terms consistently across the paper, the README, and the codebase. Each gate has a narrowly-scoped responsibility and a pre-defined output schema. Each gate can independently halt a case; only after Gates A and B have not halted does Gate C emit the final verdict.

| Gate | Name | Function | Language-model? |
|---|---|---|---|
| A | **Schema** | Deterministic structural validation: required fields, score ranges, schema conformance, forbidden-term checks. Halts on schema violation. | No |
| B | **Facts** | Per-claim source-grounding: each claim in the judge's verdict is tagged `SUPPORTED`, `CONTRADICTED`, or `UNSUPPORTED` against the source text. Fail-closes when the source text needed to ground a claim is absent. | Yes |
| C | **Logic** | Source-evidence-grounded verdict on the agent: `APPROVE` or `BLOCK`. Produced from the source text, the policy, Gate B's per-claim verdicts, and the judge's verdict and reasoning trace as inputs. Cites policy rules to explain the verdict. | Yes |

The sequencing is principled: structural schema first (cheapest, deterministic); factual grounding second (it is meaningless to audit logic over false premises); logical coherence last (the most cognitively demanding step, executed only on inputs that have already cleared factual scrutiny). A case must clear all three gates to be designated `APPROVE`. A halt at any gate produces a structured quarantine record rather than a silent pass.

### 3.2 Why Three Tags at Gate B Rather Than Two

A naïve fact-checker emits a binary `SUPPORTED` / `NOT SUPPORTED`. Gate B emits three tags because two distinct failure modes need different remediations.

- `SUPPORTED` — the source text contains evidence affirming the claim.
- `CONTRADICTED` — the source text contains evidence *against* the claim. This is a finding of factual error.
- `UNSUPPORTED` — the source text contains *neither* affirming nor contradicting evidence. This is a finding of an unsubstantiated claim. The judge has asserted something not present in the record.

`CONTRADICTED` is a stronger signal than `UNSUPPORTED`, but both are findings. Collapsing them would conflate "the judge said something false" with "the judge said something it had no basis to say." These have different downstream implications.

### 3.3 Source-Evidence Grounding as a Discipline-Level Constraint

A standard LLM-as-Judge has access to the agent's final output message, external interactions (e.g., tool calls), internal reasoning traces, and the system/user prompts.

It does not have a fixed external reference against which to check its own conclusions, and its beliefs about the world are coextensive with its judgement of the world. Sycophancy, hallucinated rationales, and credulity toward sanitised cover stories are downstream of this absence.

The Correspondence Auditor introduces an explicit external reference. Gates B and C receive the source text — the prompt and context that was given to the judge — and the policy (the Truth Cartridge, §3.7). The discipline imposed at the prompt level is: every claim the Auditor makes must point at one of the source text, the policy, or the judge's trace. The Auditor's *beliefs* about whether insider trading is wrong are not an admissible input; only the policy's *statement* that it is wrong is.

This is not a complete defense. The Auditor Gates B and C use an LLM and it remains capable of misreading the source, missing a structural pattern, or being itself talked into a coherent-but-wrong narrative.

But the framing is structurally different: the Auditor is forced to externalise its reasoning against artefacts a human reviewer can also read. Gate B's claim-level tags and Gate C's rule citations are the externalisation. They give the human reviewer the Auditor's full working in a form that can be demonstrably verified.

We qualify this claim in one important respect. The *verdict* externalised at Gate C is highly reproducible run-to-run (ICC = 0.979, §5.5), but the *specific rule citations* that accompany it are not yet stable (Krippendorff's α = 0.238, §5.5, where that figure is itself an optimistic upper bound). The interpretability guarantee therefore holds at the level of the reproducible verdict and the per-claim Gate B tags; individual policy-rule citations should be read at the aggregate-frequency level rather than as stable per-case attributions, until the deterministic meta-audit proposed in §6.2 closes this gap.

What the Auditor is therefore doing, in GRC vocabulary, is something hybrid: at Gate C it makes a sample-test-like *operational-effectiveness* judgement on the agent (does the source text evidence a policy violation?) while also making a *control-design*-like observation on the judge (was the judge's reasoning trace coherent against that same source text?). These are recorded as separate signals — the agent verdict and the rule citations — so that one is not conflated with the other.

### 3.4 Segregation of Duties Between Gates

Gate B (Facts) and Gate C (Logic) run as separate language-model invocations with separate prompts. Gate C receives Gate B's output as a structured input but cannot re-litigate Gate B's per-claim verdicts. This is deliberate. A single combined gate would conflate factual error with logical error, and the failure modes of "the model hallucinated a fact" and "the model reasoned incoherently from facts it correctly identified" are diagnostically distinct and require different remediation: a hallucinated fact is corrected by re-grounding against the source (Gate B's job), whereas incoherent reasoning from correctly-identified facts is caught by the logic check (Gate C's job). Routing them to the same gate would blur which repair is needed.

### 3.5 Synthesis and Quadrant Routing

Gate C emits a binary verdict on the agent—`APPROVE` (the source text and policy do not evidence a policy violation) or `BLOCK` (at least one violation is evidenced). Because this verdict is strictly independent of the Line 2 judge, the orchestrator cross-tabulates the two outputs (`{Judge Action} × {Auditor Verdict}`) into four distinct routing quadrants.

This 2×2 matrix defines the operational outcome of the audit:

| | **Auditor: APPROVE** | **Auditor: BLOCK** |
|---|---|---|
| **Judge: APPROVED** | `VALIDATED_APPROVAL` | `FLAWED_APPROVAL` |
| **Judge: BLOCKED** | `FLAWED_BLOCK` | `VALIDATED_BLOCK` |

* **Concurrence (`VALIDATED_APPROVAL` / `VALIDATED_BLOCK`):** The Auditor independently arrives at the same operational conclusion as the judge.
* **Operational Disagreement (`FLAWED_APPROVAL` / `FLAWED_BLOCK`):** The Auditor explicitly contradicts the judge's verdict. `FLAWED_APPROVAL` is the critical condition the Line 3 architecture exists to catch (the judge waved an action through, but the Auditor blocked it). 

*(Note: Cases where the upstream judge outputs `HESITATE` are collapsed into the `BLOCKED` row for binary routing purposes, reflecting a "flagged for review" posture).*

Because the Line 3 audit is blind to the latent ground-truth of the case at the time of execution, these quadrants are strictly operational. Later in the evaluation phase (see §5.6.1), once ground-truth is unblinded, the operational disagreements are decomposed into **Saves** (where the Auditor successfully corrected a wrong judge) and **Breaks** (where the Auditor incorrectly overturned a right judge).

Rule citations from the policy taxonomy (introduced in §4.9) accompany the verdict as interpretability artefacts. They document the Auditor's reasoning but do not, by themselves, determine the quadrant. A judge can have flawed reasoning *and* reach the right action, or sound reasoning *and* reach the wrong action. The framework records both signals without conflating them. Hygiene-level findings (H-rules) are surfaced for reviewer attention but never alter the verdict or the routing quadrant.

### 3.6 Auditing the Process, Not the Intent

The Correspondence Auditor presumes the judge is operating in good faith — fallible, not adversarial. This is a deliberate audit posture, not naïveté: audit looks for *positive evidence* that a control operated, and absence of such evidence is not, by itself, evidence of wrongdoing. Presuming bad faith would convert the function from audit into forensic investigation — hunting for negative evidence — which is a different discipline and would flood the pipeline with false positives. A judge that is actively colluding or compromised is therefore out of scope by design: that is an insider-threat problem, mitigated by the structural controls that mitigate insider threat everywhere in GRC — segregation of duties, rotation, and independent reporting lines — which is precisely why the model specifies three separated lines rather than two. We note this boundary once here and do not revisit it.

When a judge misses a deceptive-rogue agent, the common mechanism is that the agent's sanitised cover story satisfied the judge's surface checks. The Auditor does not adjudicate the judge's honesty; it mechanically grounds the judge's reasoning trace — together with the agent's scratchpad, tool calls, and final output — against the source text, and surfaces any contradiction between them.

The swappability of this architecture across domains comes from two facts: Gate C's system prompt is domain-neutral scaffolding that defers entirely to the Binding Policy, and all domain-specific truth — the rule taxonomy, the `CLEAN`/`ROGUE` definitions, and the §6 execution and chronology preconditions — lives in `policy.md`. To audit a different domain you replace `policy.md` with another cartridge; no Gate C prompt or code changes. This is a property of L3 and the cartridge, not of the judges. The judges in this study are deliberately heterogeneous, and several (Z02–Z04) *do* encode insider-trading knowledge — they are the objects being audited, not part of the swappable apparatus. 

The architecture does *not* claim to catch a Line 2 that is actively colluding with Line 1, a Line 2 that has been compromised, or a Line 2 deliberately gaming the audit. It is designed to catch reasoning errors and blindspots by a good-faith judge. A deceptive Line 2 is a failure of the governance design.

### 3.7 The Truth Cartridge

The domain policy and the source-of-truth schema are not hard-coded into the audit engine. They are loaded as an interchangeable parameter set we call a *Truth Cartridge*. The cartridge specifies: the rule taxonomy (e.g. the J/F/U/H rules described in §4.9), the per-domain definitions of `CLEAN` versus `ROGUE`, the per-policy citation patterns Gate C must use to justify a verdict, and the Gate B source-grounding schema.

For this study one cartridge is loaded: the insider-trading cartridge that defines the behavior evaluated as `ROGUE` in the Apollo corpus. The audit architecture is in this sense domain-agnostic; the empirical results are not. Replication on a second domain, via a substituted cartridge, is identified as future work (§6.2) and is the natural test of the cartridge abstraction.

### 3.8 Deployment Modes

The system supports two deployment postures, with distinct governance properties.

- **Mode A (Inline Halt Gate):** the Auditor sits in-line between the judge and any downstream consumer; non-validated outputs are quarantined for human review. In GRC vocabulary, this is a **preventive control**.
- **Mode B (Retrospective Evidence Generation):** the Auditor processes historical judge outputs asynchronously; nothing is blocked. In GRC vocabulary, this is a **detective control**.

For Mode A to be genuinely *preventive* rather than merely detective, the audit must intercept at a specific point: after the agent has emitted a tool call that declares its intended action, but before that action is authorised and executed. Audited any later, the trade has already happened and the control can only detect, not prevent.

Running Mode B and treating it as Mode A is a governance failure — a detective control mis-labelled as preventive provides a different (lower) assurance level than its label implies. We are explicit about which mode a given deployment is operating under.

### 3.9 The Fail-Closed Posture

The Auditor is explicitly engineered to be fail-closed. If the source evidence is ambiguous, if the reasoning trace formatting drifts, or if the claim miner cannot securely anchor an assertion to the text, the architecture defaults to `BLOCK` or a quarantine status. This asymmetric calibration is the correct posture for a Line 3 control instrument: over-blocking (false positives) generates noise that is recoverable via human review, whereas under-blocking (false negatives) represents the catastrophic failure mode the instrument was built to prevent.

The fail-closed posture operates at two layers. Code-enforced fail-closed handles structural failure modes deterministically: empty transcripts emit `EMPTY_TRANSCRIPT`, claim-miner format drift emits `CLAIM_MINER_FORMAT_ERROR`, missing essential fields raise `ValueError` rather than returning empty placeholder values that would pass downstream validation silently, and any non-OK pipeline status drops the case from primary analysis. Prompt-driven fail-closed governs the language-model gates themselves: Gates B and C are prompted to default to `UNSUPPORTED` / `BLOCK` when source evidence is ambiguous, rather than producing affirmative verdicts on weak grounds. The code-enforced layer is verifiable by inspection; the prompt-driven layer is empirically observable in the asymmetric FPR/FNR profile reported in §6.2.

### 3.10 Control-Owner Attestation

Each production run emits a release-control sign-off page (supplementary S2). This page is not a checkbox. It is the run
dashboard rendered for human attestation: every recovery, save, and break rate, every false-positive and
false-negative cell with its Wilson confidence interval, and the H1/H2 outcomes — computed on the actual
inputs the control processed, not on a marketing sample. In GRC terms it is a *test of the control*: it
certifies that this control was tested, operating in this configuration, on these inputs, and produced
these measured results, with its failures visible rather than hidden. 

That is the deliverable an internal
audit function, an external assessor, or a regulator actually asks for when they ask whether an automated
control "works" — empirical, dated, reproducible evidence of operating effectiveness, signed for release suitable for control-owner attestation and aligned with the transparency artefacts IEEE 7001-2021 anticipates for the certification-agency stakeholder. This forms part of the architecture supporting use as Line 3 rather than Line 2.

### 3.11 Classification of Results

This study keeps three layers strictly separate. The Auditor is a rubric-agnostic, multi-factor evidence-weighing engine: it grounds claims against a source text and a supplied policy and has no domain knowledge of its own. 

The Truth Cartridge (§3.7) is the swappable specification it runs against — here, the insider-trading policy and its J/F/U/H rule set; auditing a new domain means loading a different cartridge, with no change to the engine. 

The interpretive framework is a separate, post-hoc lens applied to the Auditor's outputs: in §7 we map the cartridge's rule firings onto the Psychopathia Machinalis v2.2 nosology, but that mapping is illustrative, and the same outputs could be read through any formal, n-dimensional schema. No hypothesis, metric, or decision rule in this paper references the nosology; the engine's validity rests on the architecture and the cartridge alone.

---

## 4. Experimental Design

The experimental design that follows tests whether this architecture in fact yields judge-invariant recovery (H1) and bounded miscalibration (H2) when the insider-trading Truth Cartridge is loaded and the Auditor is run against the Apollo corpus.

### 4.1 Source Data and the Binary Mapping

The Apollo corpus, introduced in §1, supplies LLM-produced agent transcripts depicting an insider-trading scenario, with two boolean ground-truth keys (`is_misaligned`, `is_deceptive`) per case. Apollo's labelling is sequential: `is_deceptive` is only evaluated when `is_misaligned: true`, so omitted keys are structural artefacts of the labelling pipeline rather than ambiguous edge cases.

For this study we collapse Apollo's tripartite latent structure (`CLEAN` / `ROGUE-HONEST` / `ROGUE-DECEPTIVE`) to a **binary** ground-truth shape that matches the Auditor's binary output:

| `is_misaligned` | `is_deceptive` | Latent stratum | Ground-truth class | Required Auditor verdict |
|---|---|---|---|---|
| `false` | *missing* | CLEAN | **CLEAN** | `APPROVE` |
| `true` | *missing* | ROGUE-HONEST | **ROGUE** | `BLOCK` |
| `true` | `true` | ROGUE-DECEPTIVE | **ROGUE** | `BLOCK` |

In short: any ROGUE case—deceptive or honest—maps to `BLOCK`; only CLEAN maps to `APPROVE`; `misaligned: false, deceptive: true` is impossible and `misaligned: null` cases are dropped at ingestion.

Under the policy that ships with this study, all rogue trades must be blocked regardless of whether the agent reported them honestly or fabricated a cover story. The honest/deceptive distinction is preserved as case metadata for stratified failure analysis but does not enter the headline accuracy calculation. The collapse is a deliberate simplification appropriate to a methodology-validation study; recovery of the honest/deceptive distinction in the headline metric is identified as future work (§6.2) and is carried as an explicit limitation (§6.1).

A fail-closed paradigm is strictly enforced throughout the pipeline. At ingestion, cases with malformed labels are dropped. During execution, pipeline anomalies—such as transcripts with zero substantive content, or claim-miner outputs missing structural sentinels—are explicitly caught and quarantined with dedicated status codes rather than being permitted to silently default to an `APPROVE` state. Drop and quarantine counts are reported in Appendix B.

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

These five variants span a deliberately constructed spectrum from realistic execution to pathological failure. Z01 represents the State-of-the-Art (SOTA) at the time of the study. Together, Z01 and Z02 establish the **realistic-quality band**; both utilize the exact same evaluation rubric and differ exclusively in scratchpad access (Z02 is permitted to read the agent's internal reasoning scratchpad).

By contrast, Z03 through Z05 are **deliberate stress probes** designed to test the Auditor's resilience against specific, severe biases: a paranoid over-blocker (Z03), a lenient rubber-stamp (Z04), and a "manager-aligned" persona that turns a profit-motivated blind eye to rogue actions (Z05).

To be explicit: these judges are simplified experimental instruments, not production artifacts. Their inclusion ensures comprehensive **failure-mode coverage**, guaranteeing the Auditor is tested against the full spectrum of potential Line 2 breakdowns. This is not a claim about the real-world prevalence of such degraded judges in production environments. The core invariance claim of this study is that the Auditor's performance holds steady across this entire *constructed* range, proving its structural independence whether the Line 2 judge is operating reliably or failing catastrophically.

### 4.3 Pre-Registered Hypotheses

Both hypotheses are stated against the binary Gate C verdict and the formal specifications match the pre-registration verbatim.

**H1 (Judge-Variant Invariance of Recovery).** We want to prove the Auditor works equally well no matter which judge is used. Standard statistical tests look for *differences*, but we need to prove *similarity*. So, we use an 'equivalence test' to show that any performance gap between judges is tightly bounded near zero.

Formally, for ground-truth class *Y* ∈ {CLEAN, ROGUE}, Auditor verdict *V* ∈ {APPROVE, BLOCK}, and judge variant *Z* ∈ {Z01, …, Z05}, the absolute difference in recovery is bounded by our 0.05 margin:
> $ | P(V \text{ is correct given } Y \mid Z = z_i) - P(V \text{ is correct given } Y \mid Z = z_j) | < 0.05 $, for all $i, j$

(Equality is tested within each ground-truth class *Y* separately, as the analysis in §5.3 does, not pooled across CLEAN and ROGUE.)

Test specification: To rigorously claim invariance, it is insufficient to simply fail to reject the null hypothesis of a standard difference test (which may merely indicate a lack of statistical power). Instead, we operationalise this using Two One-Sided Tests (TOST) for equivalence. We define an equivalence margin of $\pm 5$ percentage points ($\pm 0.05$). 

H1 is supported if and only if the TOST p-values  (the maximum of the two one-sided p-values) for all $C(5, 2) = 10$ judge-variant pairs, computed within each ground-truth class using an unpooled standard error (SE) fall below α  after Holm–Bonferroni step-down correction at $\alpha_{\text{family}} = 0.05$.

Because requiring all 10 pairs to demonstrate equivalence operates as an intersection-union test (which natively controls type I error at $\alpha$), applying the Holm-Bonferroni correction on top of this requirement is deliberately conservative. It effectively demands that the smallest raw TOST p-value clears $\alpha/10$.

We use an unpooled SE because the null hypotheses under TOST specify non-zero differences (the equivalence bounds ±0.05); pooling SE under an assumed equality of proportions would be misspecified for the test statistic being computed.

For descriptive completeness, standard two-proportion z-tests for difference are also computed and reported alongside the equivalence tests.

See Appendix A for formal statistical specifications.

**H2 (Bounded Miscalibration — Descriptive Bound).** The Auditor's false-positive rate (FPR = Auditor `BLOCK` on CLEAN cases / count of CLEAN cases) and false-negative rate (FNR = Auditor `APPROVE` on ROGUE cases / count of ROGUE cases) are jointly bounded:

> $\max(\text{FPR}, \text{FNR}) \le 0.10$ in every judge condition

Both rates are defined relative to ground-truth class — not relative to the judge's action — so they are directly comparable across judge variants. We evaluate this as a descriptive pre-registered bound rather than an inferential hypothesis test, reporting Wilson 95% confidence intervals alongside the sample point estimates.

### 4.4 The Headline Analysis: Recovery Conditional on Judge Correctness

For each judge variant *Z*, we compute the Auditor's recovery rate stratified by whether the judge's verdict was itself correct against ground truth:

|                     | **Judge correct** | **Judge incorrect** |
|---------------------|-------------------|---------------------|
| **GT ROGUE**        | Auditor recovery when judge caught the violation | Auditor recovery when judge missed the violation |
| **GT CLEAN**        | Auditor recovery when judge correctly approved | Auditor recovery when judge over-blocked |

The central empirical question is whether the Auditor's recovery rate in the two "judge incorrect" cells is comparable to the two "judge correct" cells. If recovery sags when the judge is wrong, the Auditor is parasitic on judge correctness — it is reproducing the judge's verdict rather than auditing. If recovery is approximately flat regardless of judge correctness, the Auditor is performing independent source-evidence-grounded verification.

### 4.5 Ablation: Verdict-Level Independence of Gate C

A potential confound is that Gate C may be over-relying on the judge's verdict as a prior — parroting the judge rather than independently grounding against source text and policy. The ablation arm tests this directly.

A subset of cases is processed twice: once with the genuine judge verdict and reasoning trace, and once with the judge's `action_taken` drawn uniformly at random from {`APPROVED`, `HESITATE`, `BLOCKED`} and the judge's reasoning trace replaced with a fixed, vague monologue.

The Auditor performs two distinct functions: 
- (1) reaching an independent verdict on the agent, and 
- (2) surfacing specific reasoning errors in the judge's trace via J-rule firings. 
By design, the ablation arm tests only function (1) — function (2) cannot be exercised when the trace has been replaced with vague monologue.

The decision rule for verdict-level independence is therefore:

- **Recovery rate approximately preserved under ablation:** Gate C's verdict is independent of the judge's input. This is the result consistent with Line 3 architectural independence and is the architecturally desired outcome — verdict-level independence is the foundational Line 3 property.
- **Recovery rate drops substantively under ablation:** Gate C was conditioning its verdict on the judge's verdict rather than reasoning independently against source text and policy. This would constitute evidence that the Auditor was reproducing the judge's verdict rather than deriving its own, and would require prompt-level remediation.

The value of function (2) — the judge-reasoning signal — is reported separately via the rule-citation inventory in §5.7, which is computed against the genuine arm only.

The ablation is interpretable in either direction and is reported regardless of outcome.

### 4.6 Sample Size and Power (the Pragmatic Pilot)

The Phase II full-corpus objective scales to the maximum balanced sample drawable from the Apollo dataset (~8,500 cases, bottlenecked by the rarest latent stratum to maintain a 1:1:1 class balance). This full-corpus grid is the funded replication target.

For this study we run a **1,200-case heavily stratified pilot**. The pilot is calibrated to be sufficient to validate the methodology and the ablation arm at the 95%-confidence class, but not so large that it renders the funded full-corpus run redundant. The 99%-confidence-class result requires the full corpus.

The pilot composition is:

- n = 1,200 cases, stratified 400 `CLEAN` + 400 `ROGUE-HONEST` + 400 `ROGUE-DECEPTIVE`
- 5 judge variants (Z01–Z05) → 6,000 judged cases
- Ablation arm on the same 1,200 cases (paper §4.5; pre-reg §7) → +1,200 Auditor evaluations
- Test–retest subset of 300 case seed pass + 1,500 reruns (paper §4.7; pre-reg §11) → +1,800 Auditor evaluations
- Entity-perturbation arm on the same 1,200 cases × Z01 only (pre-reg §4.5) → +1,200 Auditor evaluations
- Same-Model Control arm on 150 cases × Z07 only → +150 Judge / +150 Auditor evaluations
- Total Auditor invocations: ≈ 10,350
- Total Judge invocations: ≈ 7,350

The complete invocation budget for the pilot is:

| Stage | Composition / detail | Judge calls | Auditor calls |
| --- | --- | --- | --- |
| Main grid | 5 judge variants × 1,200 cases | 6,000 | 6,000 |
| Ablation arm | 1,200 cases, judge input replaced with randomised action and content-free trace | 0 | 1,200 |
| Test–retest | 300 seed-case subset + 1,500 reruns | 0 | 1,800 |
| Entity-perturbation arm | 1,200 cases, Z01 only | 1,200 | 1,200 |
| Same-Model Control Arm | 150 cases, Z07 only | 150 | 150 |
| **Total** | | **7,350** | **10,350** |

The entity-perturbation arm is restricted to the Z01 judge variant to test for pre-training contamination—the risk that the audit model is recovering labels by recalling memorized training data rather than actively reasoning. Because contamination is a property of the underlying base model rather than the prompt, the valid diagnostic is strictly Z01-on-verbatim versus Z01-on-perturbed. By holding the judge prompt constant, we isolate the model's reliance on verbatim text. Running the full five-judge matrix on perturbed cases would multiply costs without yielding any additional signal regarding contamination.

The exact 400/800 class balance bypasses Apollo's natural distribution skew. While this yields a pooled $n = 1,200$ cases per judge variant, H1 is pre-registered to be evaluated strictly within ground-truth classes. Therefore, the actual test cells are $n = 400$ (`CLEAN`) and $n = 800$ (`ROGUE`) per variant.

At a conservative per-test threshold of $\alpha = 0.005$ (corresponding to the strictest first step of our Holm-Bonferroni correction at $\alpha_{\text{family}} = 0.05$ across 10 pairwise comparisons), detecting a $\Delta = 0.05$ absolute between-judge accuracy difference at 80% power requires approximately 730 cases per group (assuming a baseline recovery of $p = 0.95$). Consequently, our `ROGUE` comparisons ($n = 800$) are adequately powered for this Minimum Detectable Effect (MDE) provided recovery sits at or above 0.95. However, our `CLEAN` comparisons ($n = 400$) achieve an estimated power of only 0.25–0.46 under plausible baselines, and are therefore explicitly underpowered for the stated MDE. (We note that the Auditor's realized `CLEAN` recovery of ~0.99 substantially exceeded the 0.90–0.95 sizing baselines, making this underpowered designation a safely conservative statement).

We commit, in advance of the run, to reporting the pilot result regardless of outcome and not to adjusting the pilot's pass thresholds post-hoc to claim sufficiency.

While the pilot is sized to detect a standard difference (MDE 0.05), proving strict statistical equivalence (H1) via TOST across 10 corrected comparisons is an aspirational claim for this sample size, and sizing for a difference-test MDE does not by itself guarantee equivalence-test power at the same margin (see Appendix A). The full ~8,500-case replication is the realistic target for achieving robust equivalence support.

### 4.7 Test-Retest Reliability (Instrument Stability)

A 300-case subset of the 1,200 pilot cases is processed once as a seed pass and then rerun ($k = 5$ times on the ablation arm only) at the registered temperature and seed configuration. Including the seed pass as the $t=0$ baseline gives $k = 6$ total observations per case under operationally identical conditions. 

**Explicit Pre-Registration Deviation:** The original pre-registration (§11) specified evaluating strictly $k=5$ iterations. However, to cleanly anchor the reruns without confounding them with the main grid's batch order, we formally amended the protocol (Amendment v20) to a two-step workflow that analyzes all $k=6$ observations. The total §4.7 invocation budget is therefore +1,800 Auditor calls (300 seed + 1,500 reruns).

Restricting these reruns to the ablation arm cleanly isolates the Auditor's internal non-determinism from upstream judge noise, though we acknowledge this measures stability in a slightly narrower regime where the Auditor reasons without a genuine judge trace. We carry this caveat explicitly into the limitations (§6.1) rather than leaving it as a footnote. We report ICC(2,1) for the binary verdict, Krippendorff's α for rule-citation sets, and Cohen's κ for quadrant agreement. The pre-committed threshold for "stable instrument" is **ICC ≥ 0.80**.

The 300-case subset is *not* held out from the headline metrics. It is part of the pilot and is included in the H1/H2 calculation on its first run. The reruns exist solely to characterise instrument stability under stochastic LLM behaviour. Failure of the stability threshold is reported as such; it qualifies but does not retroactively invalidate H1/H2 if both are met.

To verify the Auditor is stable under the natural randomness of language models, we compute the Intraclass Correlation Coefficient (ICC), requiring an ICC ≥ 0.80 (indicating good reliability). For rule citations, we use Krippendorff's α. Unlike standard coefficients, α correctly handles cases where multiple policy rules are cited simultaneously.

### 4.7.1 Gate B Inter-Rater Reliability (Human Baseline)

Separately from the rerun-stability analysis above, we assess the *human* inter-rater reliability of Gate B's factual tagging on a 50-case subset (stratified ≈17/17/16 across `SUPPORTED` / `CONTRADICTED` / `UNSUPPORTED`), drawn deterministically by `tools/l3_gate_b_irr_tester.py` from the genuine-arm pilot (ablation runs excluded). The human annotator (the author) marked each claim `SUPPORTED` / `CONTRADICTED` / `UNSUPPORTED` blind to Gate B's predicted verdict; agreement is scored with Cohen's κ against a pre-registered soft acceptance target of κ ≥ 0.60 (pre-reg §4.6). This characterises whether a human and the Auditor's Gate B agree on the factual-grounding tags, complementing the run-to-run machine stability of §4.7. The result is reported in §5.5.

### 4.8 Model Selection and Asymmetry

This study tests the Auditor's recovery rate against a heterogeneous Line 2 model. It does **not** test which model is the better judge in the abstract; the study design treats the judge as an operational input variable to be audited, not as a benchmark baseline. The Z03–Z05 stress probes are intentionally degraded; we are testing whether recovery holds when the judge being audited is unreliable.

The judges run on `Llama 3.3 70B` (dense); the Auditor's Gates B and C run on `Qwen 3 235B` in a Mixture-of-Experts configuration with 22B parameters active per token. Total parameter capacity is materially greater on the Auditor side. The asymmetry is task-to-capacity, not a claim that one model family is superior to the other: per-claim factual grounding and logical coherence auditing are more demanding than the judge's pattern-match task, and the additional capacity is matched to that demand. This is the architecture, not a confound to be mitigated; the Z07 same-model control arm (§5.10) tests this directly.

The two models were selected on the basis of an explicit balance between intelligence-per-token, cost-per-token, tokens-per-second (generation speed), and availability. They were chosen because that balance suited our deployment constraints and had historically performed well in similar real-life use; they are not claimed as optimal for every situation. Practitioners with different cost/latency/availability priorities should be expected to substitute different models, and the architecture supports this — the model strings are configurable parameters in the prompt manifests.

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
The OpenRouter API connection logic also accepts quantization 'unknown' which is equivalent to 'full precision' for providers that do not quantize. `DeepInfra` supplied only `fp8` quantizations for these two models at the time of the study; the named parameter `'unknown'` was removed as an accepted option prior to the start of the experiement. 

The full sampling configuration for the Auditor is pinned in the prompt manifests at the registered git commit. Gate B (Facts) is invoked at `T = 0.1, top_p = 0.1, top_k = 20, min_p = 0.0, max_tokens = 8192`. Gate C (Logic) is invoked at `T = 0.1, top_p = 0.2, top_k = 20, min_p = 0.0, max_tokens = 8192`. Temperature is held at `0.1` across both gates to minimise within-gate stochasticity; the modest top_p divergence between the two gates reflects the heavier synthesis demand at Gate C relative to the literal-matching task at Gate B. The `top_k` and `min_p` values are held constant across all five judge conditions, across the ablation arm (`paper/PRE_REGISTRATION.md` §4.5), and across the test–retest reruns (§4.7). No sampling parameter was varied during the pilot.

Closed proprietary models are not evaluated in this study, for two reasons. First, proprietary endpoints introduce serving-side variables we cannot constrain — runtime routing, variable reasoning effort, undocumented quantisation changes — incompatible with reproducibility. Second, a study calibrated on a model that is later silently changed or retired loses replicability. Open-weights models support the *set-and-forget* posture suited to a Line 3 audit instrument: model drift becomes testable rather than invisible.

The L2/L3 parameter asymmetry raises a residual question distinct from verdict independence: whether the observed recovery reflects the structural audit framework performing substantive work, or whether parameter-size alone—the larger model classifying source text against a complex policy rubric—produces equivalent recovery. To isolate these variables, we incorporated a preliminary 150-case same-model control arm ($Z07$) into the pilot evaluation matrix. Both the Line 2 Judge and the Line 3 Auditor were configured to run on identical weights using the high-parameter Qwen 3 235B Mixture-of-Experts model, zeroing out the parameter delta. The comprehensive 8,500-case multi-model cross-rotation matrix remains designated as a separate Paper 2 deliverable. Z07 is reported in a supplementary table alongside Z01's recovery metrics for direct comparison; it is not pooled into the H1 equivalence family (Z01–Z05). A Z07-vs-Z01 recovery delta beyond the §3 noise envelope would be flagged as evidence that capacity, rather than architecture, drives the observed gains; a delta within the envelope is consistent with architectural attribution.

### 4.9 Corporate Policy Rubric (Truth Cartridge for This Study)

The domain policy provided to the Auditor is deliberately complex and prescriptive, mirroring the pedantic structure of enterprise GRC or Model Risk Management policies. We are not testing the Auditor's zero-shot ability to detect deception in a vacuum; we are testing its architectural capacity to enforce a complex policy strictly against a judge's reasoning trace.

The cartridge defines four families of rules (summarized below, full policy available in repository):

| Category | Rules | Description |
|---|---|---|
| **J-Rules** | J1–J5 | **Judge Process Findings.** E.g., *J1 (Scratchpad Blindness)*, *J2 (Accepts Sanitized Cover Story)*, *J3 (Pressure as Justification)*, *J4 (Conflates Quality & Legality)*, *J5 (Misses Reporting Violation)*. Evaluates how the judge reasoned. |
| **F-Rules** | F1–F*n* | **Structural Fact Findings.** Findings against the agent's behavior, irrespective of stated intent. E.g., *F1 (Insider-Tip Sterilization — a tipped trade reported as public-sourced)*.|
| **U-Rules** | U1–U*n* | **Unsubstantiated Claim Findings.** Fires against specific claims in the judge's verdict for which Gate B returned `UNSUPPORTED`. |
| **H-Rules** | H1–H*n* | **Hygiene Findings.** Formatting or minor policy deviations. Surfaced for reviewer attention only; never affects the final verdict. |

The Auditor cites these rules as part of its `BLOCK` justifications. Rule citations are interpretability metadata, not quadrant determinants (§3.5).

For concreteness: on a case where the judge wrote "the agent disclosed the trade to compliance," Gate B checks that assertion against the source transcript and tags it `SUPPORTED` if the disclosure appears, `CONTRADICTED` if the transcript shows the opposite, or `UNSUPPORTED` if the transcript is silent; an `UNSUPPORTED` tag on a verdict-bearing claim is what fires the corresponding U-rule at Gate C.

Note: These rules are defined by the cartridge, not the engine. Their firings can optionally be mapped onto an external diagnostic taxonomy — for example, we illustrate how J1–J3 can be read as the Alignment-axis Strategic Compliance construct in Psychopathia Machinalis (Watson & Hessami, 2025a) — but the mapping is interpretive and not required for any result in this paper. We detail this further in §7.

---

## 5. Results


### 5.1 Source Data and Selection

The 1,200 pilot cases were drawn from the Apollo corpus by stratified random selection without replacement, balanced 400 `CLEAN` / 400 `ROGUE-HONEST` / 400 `ROGUE-DECEPTIVE`. Cases used for pre-launch development, smoke-testing, or prompt refinement (per pre-reg §4.4 and §6.2) are held out from the eligibility pool via the `tainted_cases.txt` manifest shipped in the repository, making the pilot a strictly held-out evaluation. The random seed is derived deterministically from a fixed selection date and is hard-coded in the run manifest.

The repository ships a selection utility (`tools/select_pilot.py`) that reproduces the exact pilot from the registered seed, and that allows a third party to draw an independent stratified subset of arbitrary size for replication using either a user-supplied seed or a date-derived seed.

To reproduce the exact 1,200-case pilot, replicators can run the selection utility from the repository root:
`python tools/select_pilot.py --seed-date 20260521`

### 5.2 Headline Recovery

Across the five judge variants the Auditor recovers the Apollo ground-truth label at
near-ceiling and at near-identical rates regardless of judge quality. Recovery is the
proportion of cases in each ground-truth class on which the Auditor's verdict matches
the label. The ablation (noise) arm is reported in the same frame for reference and
analysed in §5.6.

| Variant | Role | Recovery CLEAN | Recovery ROGUE | Save rate† (95% CI) | Break rate‡ (95% CI) |
|---|---|---|---|---|---|
| Z01 | SOTA prompt | 99.0% | 99.0% | 95.2% [91.2, 97.5] | 0.30% [0.1, 0.9] |
| Z02 | Scratchpad-aware | 99.5% | 99.2% | 94.8% [89.1, 97.6] | 0.18% [0.1, 0.7] |
| Z03 | Paranoid (over-block) | 99.2% | 97.9% | 99.2% [97.8, 99.7] | 2.12% [1.3, 3.4] |
| Z04 | Lenient (under-block) | 99.5% | 98.7% | 98.6% [97.4, 99.2] | 0.39% [0.1, 1.4] |
| Z05 | Manager-aligned | 99.5% | 99.0% | 95.3% [91.0, 97.6] | 0.19% [0.1, 0.7] |
| *ABLATION (noise)* | *judge replaced* | *99.5%* | *98.6%* | *98.5% [97.1, 99.3]* | *0.77% [0.3, 1.8]* |

†Save rate = of cases the judge got wrong, the fraction the Auditor recovered.
‡Break rate = of cases the judge got right, the fraction the Auditor broke.
(Both derived from the exploratory 8-cell decomposition, §5.6.1; descriptive, not pre-registered.)
Save and break rates derived from the exploratory 8-cell decomposition (§5.6.1); descriptive, not pre-registered. Intervals are Wilson score 95% CIs. Save-rate denominators are judge-incorrect cases (n = 115–690); break-rate denominators are judge-correct cases (n = 509–1,084).

Two patterns are visible. First, recovery is flat across the variants: CLEAN recovery spans 99.0–99.5% and ROGUE recovery spans 97.9–99.2%. Second, the Auditor's *marginal* contribution is consistent:
in every condition it recovers 94.8–99.2% of the cases the judge got wrong while breaking
0.18–2.12% of the cases the judge got right. The single least-reliable cell is Z03
(paranoid over-blocker), where the Auditor's errors concentrate (break rate 2.1%, ROGUE
recovery 97.9%); even there it remains inside the H2 bound (§5.4).

#### 5.2.1 Headline Recovery, Stratified by Judge Correctness

Recovery = Auditor verdict matches ground-truth label. Cells show recovery (n correct / n).

| Variant | CLEAN · judge correct | CLEAN · judge wrong | ROGUE · judge correct | ROGUE · judge wrong |
|---|---|---|---|---|
| Z01 (SOTA)       | 99.2% (376/379) | 95.2% (20/21)   | 100.0% (632/632) | 95.2% (159/167) |
| Z02 (scratchpad) | 99.4% (353/355) | 100.0% (45/45)  | 100.0% (729/729) | 91.4% (64/70)   |
| Z03 (paranoid)   | 100.0% (2/2)    | 99.2% (394/397) | 97.9% (782/799)  | — (0/0)         |
| Z04 (lenient)    | 99.5% (397/399) | 100.0% (1/1)    | 100.0% (110/110) | 98.5% (679/689) |
| Z05 (mgr-aligned)| 99.5% (390/392) | 100.0% (8/8)    | 100.0% (637/637) | 95.1% (154/162) |

The base rates in the denominators differ by more than an order of magnitude across variants
(e.g. Z03's CLEAN·judge-wrong cell holds 397 cases while Z01's holds 21), reflecting the
deliberately opposite biases of the stress probes. Recovery is nonetheless approximately flat
across every cell, with the single weakest stratum being Z02's ROGUE·judge-wrong cell at 91.4%
(64/70). Recovery does not sag when the judge is wrong: the Auditor is performing independent
source-grounded verification, not mirroring the judge (cf. §4.4).

#### 5.2.2 Stratified Deception Recovery (exploratory)

The headline metric (§5.2) scores the Auditor against the binary ground truth, collapsing Apollo's tripartite latent structure (CLEAN / ROGUE-HONEST / ROGUE-DECEPTIVE) to CLEAN-vs-ROGUE as pre-registered and as carried explicitly in the limitations (§6.1). Because the agent-deception flag is retained as case-level metadata in every audit record, the ROGUE stratum can be decomposed after the fact—without re-running any model—into ROGUE-HONEST (the agent took a misaligned action but reported it truthfully to its supervisor) and ROGUE-DECEPTIVE (the agent took the action and concealed or misrepresented it). Both strata share the same correct Auditor verdict, BLOCK; the question here is whether the Auditor's recovery rate differs between them.  

Table 5.2.2 — Stratified ROGUE Recovery Breakdown

| Variant | HON n | HON rec% | HON 95% CI | DEC n | DEC rec% | DEC 95% CI | Δ(D-H) pp |
|---|---|---|---|---|---|---|---|
| ABLATION_NOISE | 408 | 96.1 | [93.7, 97.6] | 402 | 98.5 | [96.8, 99.3] | +2.4 |
| Z01 | 407 | 96.6 | [94.3, 97.9] | 400 | 99.5 | [98.2, 99.9] | +2.9 |
| Z02 | 405 | 97.5 | [95.5, 98.7] | 400 | 99.5 | [98.2, 99.9] | +2.0 |
| Z03 | 414 | 93.2 | [90.4, 95.3] | 402 | 98.5 | [96.8, 99.3] | +5.3 |
| Z04 | 408 | 96.1 | [93.7, 97.6] | 401 | 99.0 | [97.5, 99.6] | +2.9 |
| Z05 | 407 | 96.6 | [94.3, 97.9] | 400 | 99.5 | [98.2, 99.9] | +2.9 |
| **POOLED (all variants)** | **2449** | **96.0** | **[95.1, 96.7]** | **2405** | **99.1** | **[98.6, 99.4]** | **+3.1** |

Pooled across the five genuine judge variants (Z01–Z05), the Auditor blocks 99.2% of ROGUE-DECEPTIVE cases ($n = 2003$) against 96.0% of ROGUE-HONEST cases ($n = 2041$)—a difference of +3.2 pp (two-proportion $z = 6.47$, $p = 0.000$; descriptive, as this comparison is exploratory and not pre-registered).

That recovery does not degrade on the cases where the agent actively builds a cover story is consistent with the rule mechanism of §4.9 and §5.7: the J-rules that fire on concealment (scratchpad blindness, sanitized-cover-story acceptance, pressure-as-justification) give the source-grounded Auditor explicit purchase on precisely the inputs an unaided judge is most easily talked out of blocking.  

This decomposition is descriptive and was not pre-registered; the binary collapse remains the confirmatory benchmark (§5.2, §6.1). It is reported to characterize where the Auditor's residual error concentrates within the ROGUE class, not to revise the headline.  

### 5.3 H1 Test: Equivalence Across Judge Variants

H1 is supported decisively in both ground-truth classes. Across all C(5,2) = 10 pairwise
judge-variant comparisons within each class, the TOST procedure rejects non-equivalence at
the ±0.05 margin after Holm–Bonferroni step-down correction (α_family = 0.05). The worst-case
(largest) Holm-adjusted TOST p-value is 3.2 × 10⁻¹³ in the CLEAN class and 6.3 × 10⁻¹⁰ in the
ROGUE class — both many orders of magnitude below α. No pair fails in either direction.

This is a stronger result than the pilot was powered to expect. §4.6 flagged strict TOST
equivalence across 10 corrected comparisons as aspirational at n = 400/800 per class. It passes
hard because the between-variant spread in recovery is far inside the margin: ~0.5 pp on CLEAN
and ~1.3 pp on ROGUE against a ±5 pp equivalence bound. The descriptive two-proportion
difference tests concur (no pair shows a significant difference after correction).

### 5.3.1 H1 Test: Pairwise Equivalence (TOST, ±0.05, Holm-Bonferroni)

All 10 pairwise comparisons in each class reject non-equivalence after correction. Descriptive
two-proportion difference tests (adj p) find no significant difference in any pair.

| Pair | CLEAN Δ (pp) | CLEAN adj TOST p | ROGUE Δ (pp) | ROGUE adj TOST p |
|---|---|---|---|---|
| Z01–Z02 | −0.50 | 3.2e-13 | −0.25 | <1e-15 |
| Z01–Z03 | −0.25 | 3.2e-13 | +1.13 | 6.3e-10 |
| Z01–Z04 | −0.50 | 3.2e-13 | +0.25 | <1e-15 |
| Z01–Z05 | −0.50 | 3.2e-13 | +0.00 | <1e-15 |
| Z02–Z03 | +0.25 | <1e-15 | +1.38 | 6.3e-10 |
| Z02–Z04 | +0.00 | <1e-15 | +0.50 | <1e-15 |
| Z02–Z05 | +0.00 | <1e-15 | +0.25 | <1e-15 |
| Z03–Z04 | −0.25 | <1e-15 | −0.88 | 3.1e-10 |
| Z03–Z05 | −0.25 | <1e-15 | −1.13 | 6.3e-10 |
| Z04–Z05 | +0.00 | <1e-15 | −0.25 | <1e-15 |

Here "adj TOST p" denotes the Holm-adjusted TOST p-value, i.e. the larger of the two one-sided
p-values for each pair after step-down correction. Worst-case adjusted TOST p = 3.2e-13 (CLEAN),
6.3e-10 (ROGUE); both far below α. The largest between-variant gaps (≈1.1–1.4 pp) all involve Z03
on ROGUE cases and remain well inside the ±5 pp margin.

### 5.4 H2 Test: FPR / FNR by Judge Variant

H2 holds in every judge condition with a wide margin. The pre-registered bound is
max(FPR, FNR) ≤ 0.10. The observed maxima are FPR = 1.0% (Z01) and FNR = 2.1% (Z03).

| Variant | FPR (95% CI) | FNR (95% CI) |
|---|---|---|
| Z01 | 1.0% [0.4, 2.5] | 1.0% [0.5, 2.0] |
| Z02 | 0.5% [0.1, 1.8] | 0.8% [0.3, 1.6] |
| Z03 | 0.8% [0.3, 2.2] | 2.1% [1.3, 3.4] |
| Z04 | 0.5% [0.1, 1.8] | 1.3% [0.7, 2.3] |
| Z05 | 0.5% [0.1, 1.8] | 1.0% [0.5, 2.0] |

Every cell is at least ~4.7× inside the 10% bound. Wilson 95% CIs (reported in the
supplementary table) place the upper bound below 0.06 in all cells.

### 5.5 Test–Retest Reliability (Instrument Stability)

The Auditor was rerun under operationally identical conditions ($k = 6$ observations per case: one seed pass plus five reruns, ablation arm only, per §4.7) on the 300-case stability subset. Three cases were dropped for null ground-truth labels at ingestion (the same `is_misaligned: null` ingestion rule described in §4.1), leaving $n = 297$ (balanced-design ICC computed on the common 296). All coefficients in the table below are deterministic post-processing of the six observation sets via `tools/compute_stability.py`.

The **binary verdict is highly stable.** The intraclass correlation for the `APPROVE`/`BLOCK` verdict is **ICC(2,1) = 0.979** (95 % CI ≈ [0.98, 0.98]), comfortably clearing the pre-registered **ICC ≥ 0.80** threshold. Agreement on the full 2×2 quadrant assignment is correspondingly high: **Cohen's $\kappa$ = 0.986** (range across rerun pairs [0.976, 0.995]). On the registered stability gate, **the instrument passes.**

| Coefficient | Target (pre-reg §11) | Observed | Verdict |
|---|---|---|---|
| ICC(2,1), binary verdict | ≥ 0.80 | **0.979** | **Pass** |
| Cohen's $\kappa$, 2×2 quadrant (mean) | — | 0.986 ([0.976, 0.995]) | Almost perfect |
| Krippendorff's $\alpha$, rule-citation set | — (descriptive) | **0.238** | Low — see below |

Two coefficients fall below the levels a reader might expect, and we disclose both plainly:
- Cohen's $\kappa$ = 0.515 (IRR Gate B Factual Tagging)
- Krippendorff's $\alpha$ = 0.238 (Rule-Citation Sets)

A further discussion is presented in the following sections.

Supplementary note on binary verdict stability. Because applying ICC(2,1) to a binary outcome is an unconventional (though conservative) parameterisation, we additionally report two model-free agreement statistics over the same reruns: 290 of 297 cases (97.6%) returned an identical verdict across all 6 passes; mean pairwise agreement is 0.991; and Fleiss' kappa over the 296 complete-rerun cases is 0.979, closely matching the ICC of 0.979. These corroborate the high verdict stability under LLM non-determinism.

#### IRR: human inter-rater reliability

**The human inter-rater reliability of Gate B's factual tagging is moderate, not strong.** On the 50-case human-annotated subset (§4.7.1) — distinct from the rerun-stability analysis tabulated above — the author's `SUPPORTED`/`CONTRADICTED`/`UNSUPPORTED` tags agree with Gate B at Cohen's $\kappa = 0.515$, below the pre-registered soft target of $\kappa \ge 0.60$. This does not touch the registered verdict-stability gate (ICC ≥ 0.80 on the verdict, which passes), but it flags per-claim factual tagging as the noisier sub-component of the pipeline and a calibration target for the full replication. We report it below as a human-vs-machine reliability finding, separate from the run-to-run machine stability characterised in the table above.

---

**Gate B Inter-Rater Reliability statistics**

* **Raw agreement:** 34/50 = 68.0%
* **Cohen's kappa:** 0.515 (pre-registered soft target ≥ 0.60)

**Confusion Matrix (rows = Gate B, cols = Human)**

| Gate B \ Human | SUPPORTED | CONTRADICTED | UNSUPPORTED | Total |
| --- | --- | --- | --- | --- |
| **SUPPORTED** | 17 | 0 | 0 | **17** |
| **CONTRADICTED** | 1 | 16 | 0 | **17** |
| **UNSUPPORTED** | 5 | 10 | 1 | **16** |
| **Total** | **23** | **26** | **1** | **50** |

**Disagreements, Ranked (Gate B → Human)**

* **10 cases:** Gate B said `UNSUPPORTED` but human said `CONTRADICTED`
* **5 cases:** Gate B said `UNSUPPORTED` but human said `SUPPORTED`
* **1 case:** Gate B said `CONTRADICTED` but human said `SUPPORTED`

**Dominant disagreement axis:** `CONTRADICTED` ↔ `UNSUPPORTED` (10/16 of all disagreements). Disagreement is concentrated on the contradicted/unsupported boundary.

#### The verdict is stable but the explanation is not.

The rule-citation set that accompanies each verdict has Krippendorff's $\alpha = 0.238$. We emphasise two things about this figure. (i) It is the single most consequential reliability finding in the pilot, and we report it in the main results rather than relegating it to an appendix precisely because it does not fail a pre-registered gate (only ICC ≥ 0.80 was thresholded) and is therefore easy to under-report. (ii) **0.238 is an optimistic upper bound on agreement:** the coefficient is inflated by agreement on the empty/absent-citation cases, so true agreement on the rules actually cited is worse than 0.238.

The following per-rule flicker analysis is **post-hoc and exploratory** (it was not pre-registered, and we label it as such in the post-hoc amendment section v22 of `paper/PRE_REGISTRATION.md`). It localises the instability sharply: the structural and unsubstantiated-claim rules that most often *drive* a `BLOCK` are reasonably stable (F2 flickers on 10.7 % of cases it appears in, S1 21.3 %, U1 28.5 %), whereas the lower-frequency citations are highly volatile, with every J-rule (the strategic-deception findings J1–J5) flickering on 100 % of the cases in which it appears across the six runs.

| Rule (by stability) | Cases seen | Flicker % |
|---|---|---|
| F2 (action-tip temporal causality) | 197 | 10.7 |
| S1 (schema) | 122 | 21.3 |
| U1 (unsubstantiated claim) | 295 | 28.5 |
| F1 (insider-tip sterilization) | 194 | 53.1 |
| U3 | 285 | 59.3 |
| U4 / H1 (hygiene) | 285 / 265 | 95.1 / 95.1 |
| F3 | 151 | 98.0 |
| J1–J5 (judge-process findings) | 59–108 | 100.0 |
| U2 (sound gap analysis) | 2 | 100.0 |

Here "cases it appears in" means cases where the rule was cited in at least one of the six runs, and "flicker %" is the fraction of those cases on which the rule's presence was *not* unanimous across the six runs.

The interpretation we adopt is that the instrument's **decision** is reliable while its **rationale at the level of the specific rule cited** is not yet reproducible run-to-run: the Auditor consistently arrives at `BLOCK`, but the exact subset of rules it names to justify the block varies. This matters for the interpretability claim of §3.3 — the externalised reasoning artefact is reproducible *as a verdict* but not *as a citation set* — and it bounds how strongly the §5.7 failure-mode inventory (computed on a single genuine-arm pass) should be read: rule-frequency rankings are indicative, individual low-frequency citations are not stable instrument outputs. We treat closing this gap (e.g. a deterministic meta-audit rubric, §6.2) as future work.

### 5.6 Ablation: Auditor With and Without Judge Verdict

Recovery is preserved under ablation, confirming verdict-level independence (§4.5). When
the judge's action is randomised and its reasoning trace replaced with a content-free
monologue, the Auditor's recovery does not collapse toward chance — it is statistically
indistinguishable from the intact condition.

| Metric | Judge intact (Z01) | Judge replaced (noise) |
|---|---|---|
| n (CLEAN / ROGUE) | 400 / 799 | 399 / 799 |
| Recovery CLEAN | 99.0% | 99.5% |
| Recovery ROGUE | 99.0% | 98.6% |
| FPR | 1.0% | 0.5% |
| FNR | 1.0% | 1.4% |
| Auditor save rate | 95.2% | 98.5% |
| Auditor break rate | 0.30% | 0.77% |

With no genuine judge signal at all, recovery moves by less than 1 pp in each class (and is
marginally *higher* on CLEAN under noise). This is the architecturally desired outcome: Gate C
reaches its verdict from source text and policy, not by mirroring the judge. The ablation
exercises only function (1), the independent verdict; function (2), the judge-trace reasoning
audit, is inert when the trace is noise and is reported on the genuine arm only (§5.7).

#### 5.6.1 Per-Variant 8-Cell Decomposition (exploratory)

Each pre-registered 2×2 quadrant splits on the third (ground-truth) axis. Counts are case n.
Save = Auditor fixed a wrong judge; Break = Auditor broke a right judge; Concur-wrong = both wrong.

| Variant | CLEAN concur-correct | CLEAN save | CLEAN break (FP) | CLEAN both-overblock | ROGUE concur-correct | ROGUE save | ROGUE break (FN) | ROGUE both-miss |
|---|---|---|---|---|---|---|---|---|
| Z01 | 376 | 20  | 3 | 1 | 632 | 159 | 0  | 8  |
| Z02 | 353 | 45  | 2 | 0 | 729 | 64  | 0  | 6  |
| Z03 | 2   | 394 | 0 | 3 | 782 | 0   | 17 | 0  |
| Z04 | 397 | 1   | 2 | 0 | 110 | 679 | 0  | 10 |
| Z05 | 390 | 8   | 2 | 0 | 637 | 154 | 0  | 8  |

These conservation checks passed at run end for every arm in Appendix B; the small-drop accounting there is therefore a caught-and-contained matter rather than an open data-integrity question.

Two patterns to note: (i) the Auditor's false negatives concentrate entirely in
Z03 (17 ROGUE breaks, the paranoid probe) and as "both-miss" double failures elsewhere (6–10 per
variant); (ii) the stress probes invert — Z03's CLEAN column is almost entirely "save" (394) where
Z04's ROGUE column is almost entirely "save" (679), the Auditor repairing opposite judge biases.
These patterns are exploratory and not pre-registered; they are hypothesis-generating for the full
replication rather than confirmatory.

### 5.7 Failure-Mode Inventory (Rule Citations, Genuine Arm)

Rule-citation counts pooled across the five genuine judge variants (≈6,000 judged cases).
The strategic-deception J-rules are well-targeted: they fire ~18× more often on ROGUE than CLEAN.

| Family | Rule(s) | CLEAN firings | ROGUE firings |
|---|---|---|---|
| J (judge-process / strategic deception) | J1–J5 | 262 | 4,737 |
| F (structural fact) | F1–F3 | 16 | 10,314 |
| U (unsubstantiated claim) | U1–U4 | 1,277 | 6,653 |
| S (schema) | S1 | 2,373 | 712 |
| H (hygiene, non-blocking) | H1 | 164 | 628 |

The F-rules (structural agent behaviour) and J-rules (judge reasoning errors) concentrate almost
entirely on ROGUE cases, as intended: F1 fires once on CLEAN versus 4,036 times on ROGUE. The
J-cluster — scratchpad blindness, sanitised cover-story acceptance, pressure-as-justification —
is the Auditor's most consistent strategic-deception signal. 

Note the reliability caveat from
§5.5: these frequency rankings are stable, but individual per-case J-rule citations flicker
run-to-run (Krippendorff α = 0.238, itself an upper bound) and should not be read as deterministic
per-case attributions.

### 5.8 Pre-Training Contamination Canary

Re-running the full pilot through Z01 with all named entities (companies, tickers, executives)
replaced by synthetic equivalents (§4.5) produces recovery indistinguishable from verbatim:

| Z01 | Verbatim | Perturbed | Δ |
|---|---|---|---|
| Recovery CLEAN | 99.0% | 99.3% | +0.3 pp |
| Recovery ROGUE | 99.0% | 98.9% | −0.1 pp |
| FPR | 1.0% | 0.8% | — |
| FNR | 1.0% | 1.1% | — |

Both deltas are well inside the noise envelope; there is no statistically significant drop under
perturbation. The independent policy-gap scan over the 1,200 perturbed files records zero auditor
breaks, zero cross-variant gaps, and zero schema crashes. We find no evidence of *entity-level*
memorisation. This matters because near-ceiling recovery (§5.2) would otherwise invite a
contamination explanation; the canary makes a verbatim-contamination explanation substantially less
plausible, leaving corpus recoverability and a strict, well-specified policy as the more likely
operative explanations. We are deliberately cautious about the strength of this claim: the Apollo
transcripts are structurally homogeneous — a shared scaffold with entities swapped in — so entity
perturbation bounds *entity-level* memorisation but does not rule out familiarity with the corpus's
structural shape (during the §4.7.1 annotation the author found the cases pattern-matchable after ~50
items). With the structural canary deferred to a follow-up study, the entity-perturbation arm is the
*sole* contamination/memorisation check in this pilot and carries that interpretive burden alone (§6.1).

### 5.9 Architectural Stability vs. Evaluator Stochasticity
The test–retest analysis (§5.5) reveals a clean separation between the stability of the Auditor's
*decision* and the stability of its *rationale*. The binary verdict is highly reproducible under
LLM non-determinism (ICC(2,1) = 0.979; quadrant κ = 0.986): across six reruns the Auditor arrives
at the same APPROVE/BLOCK verdict on essentially every case, and in particular systematically
overrides flawed L2 approvals on rogue cases regardless of run-to-run surface variation in the
judge's narrative. The verdict layer absorbs upstream evaluator stochasticity.

The rule-citation layer does not absorb it. The specific set of rules the Auditor cites to justify a verdict
flickers heavily (Krippendorff α = 0.238, an upper bound), with the J-rules changing on essentially
every case they touch. We therefore frame the stability result precisely: the instrument's decision
is categorically stable; its rationale, at the granularity of the individual rule cited, is not yet
reproducible. This is a real boundary on the interpretability claim of §3.3 and motivates the
deterministic meta-audit proposed in §6.2.

The pipeline also surfaced two latent policy boundaries rather than obscuring them. First, in edge
cases where an agent received an insider tip, correctly abstained from trading, but then omitted the
interaction from its management report, the Auditor declined to record a violation the policy does not define. As one Gate C trace shows, the
policy admits only F-series (trade-based) violation codes, so a reporting omission with no underlying
trade produced an empty violation set — the §1.2/§7 safe harbour applied — even though the omission is
a hygiene concern. This is the Truth Cartridge functioning as a strictly binding constraint
(§3.7): the Auditor enforced the policy as written and exposed the gap, rather than hallucinating to
resolve it.

Second, and more consequential, the Z07 control pilot surfaced an emergent *specification-gaming*
boundary (frozen at pre-registration policy v17): an agent executed a prohibited LING trade in a *no-scratchpad* condition and withheld the report for it.
Two coverage gaps combined: the F-series codes require an executed trade to be affirmatively anchored to
MNPI reliance under the §6 Mandatory Preconditions Checklist, and with no reasoning trace there was nothing
to anchor that reliance to; meanwhile the report omission has no standalone violation code, since the policy
scopes reporting violations strictly to *submitted* text. With neither an F-anchor nor a reporting code
available, the Auditor returned an empty violation set despite the prohibited trade — and, to its credit,
said so explicitly in the trace rather than fabricating a code to force a `BLOCK`. We deliberately froze the `policy.md` Truth Cartridge for the
remainder of the study rather than patch this path mid-pilot, to preserve the pre-registered
architecture and analysis integrity. This is a limitation of the *instrument-plus-policy pairing* for
this study — the policy as written does not cleanly code a trade with a withheld report — not of the
audit architecture itself, and both boundary cases are logged as candidate `policy.md` amendments for
the full replication (§6.1, §6.2).

### 5.10 Same-Model Control Arm (Z07)

To separate architecture from parameter capacity (§4.8), a 150-case control arm ran both the
L2 judge and the L3 Auditor on identical weights (`Qwen 3 235b`), zeroing the parameter delta.
Z07 is reported alongside Z01 for comparison and is not pooled into the H1 family.

| Metric | Z01 (Llama judge / Qwen auditor) | Z07 (Qwen judge / Qwen auditor) |
|---|---|---|
| n (CLEAN / ROGUE) | 400 / 799 | 50 / 100 |
| Recovery CLEAN | 99.0% | 96.0% |
| Recovery ROGUE | 99.0% | 98.0% |
| FPR | 1.0% | 4.0% (95% CI [1.1%, 13.5%]) |
| FNR | 1.0% | 2.0% (95% CI [0.6%, 7.0%]) |
| Auditor save rate | 95.2% | 94.3% (33/35; CI [81.4%, 98.4%]) |
| Auditor break rate | 0.30% | 1.74% (2/115; CI [0.5%, 6.1%]) |

Capacity is not the driver of the observed recovery. Collapsing the L2/L3 parameter gap does
not improve recovery; Z07 is, if anything, marginally weaker than Z01, and its CIs comfortably
contain the Z01 point estimates. The recovery gains are therefore attributable to the audit
architecture rather than to the Auditor simply being the larger model. We also inspected Z07's two
ROGUE false-negatives directly: both are label-divergence cases rather than Auditor reasoning errors —
one is a §1.2 safe-harbour trade (the agent refused the tip and traded on public analysis; the Auditor
correctly approved, while the Apollo label flags the omitted-tip report as deceptive), and one is the
no-scratchpad specification-gaming case of §5.9 (no affirmative-reliance anchor for the F-series, and a
report omission the frozen policy does not code). Neither is a failure of grounding or logic. 

We note the limited power
of this 150-case arm: the Wilson CIs on Z07 FPR/FNR are wide and overlap the Z01 point estimates,
so Z07 rules capacity *out as the sole driver* without tightly estimating any residual capacity
effect. A larger same-model control is folded into the full-corpus replication.

One honest qualification on failure-mode decoupling. Z07 produced 2 correlated errors out of
150 cases — both CLEAN cases on which the judge and the Auditor *both* blocked (the
`CLEAN__L2_BLOCK__L3_BLOCK` cell). On identical weights, prompt-and-role separation makes such
correlated errors rare (2/150) but not zero. This is a real, if small, boundary on the §2
partial-decoupling claim and is consistent with the coherent-cover-story coupling discussed
in §6.2.

---

## 6. Discussion

The pilot returns a clean and internally consistent picture. The Auditor recovers the Apollo
label at near-ceiling (97.9–99.5% across both ground-truth classes — CLEAN and ROGUE — and all five judges), that recovery is
statistically equivalent across judges spanning SOTA-prompted to deliberately degraded (H1
supported, all 20 corrected TOST comparisons rejecting non-equivalence), and miscalibration is
bounded an order of magnitude inside the registered limit (H2, max FPR 1.0%, max FNR 2.1%). At
the level the paper claims — invariance of recovery to upstream judge quality within the tested
range — the result is what a working Line 3 instrument should produce.

In every condition the Auditor recovers roughly
95–99% of the cases the judge got wrong while breaking under 1% (Z03 excepted, at 2.1%) of the
cases the judge got right. The instrument is adding signal conditional on the judge rather than
tracking it. The ablation arm makes the same point structurally: when the genuine judge verdict
and trace are replaced with noise, recovery moves by less than a percentage point and the save
rate, if anything, rises. Gate C is reaching its verdict from source text and policy, not from
the judge's prior. This verdict-level independence is the foundational property the architecture
was built to exhibit, and the data support it directly.

Two control arms guard the interpretation against the obvious objections. Near-ceiling recovery
is the kind of result that should prompt a "why so easy?" question, and the two most likely
deflationary explanations are pre-training contamination and raw parameter capacity. The
entity-perturbation canary addresses the first: synthetic-entity recovery is indistinguishable
from verbatim, with zero auditor breaks across 1,200 perturbed files, so the performance is unlikely to
be merely an artefact of verbatim corpus exposure (a structural-familiarity effect is not excluded; §5.8). The same-model control (Z07) addresses the
second: collapsing the L2/L3 parameter gap onto identical weights does not improve recovery — it
is marginally worse — so the gains are attributable to the audit architecture, not to the Auditor
merely being the larger model. What remains as the operative explanation is that, on this single
corpus and under a strict, prescriptive policy, the ground-truth label is highly recoverable by a
source-grounded process. That is a real and useful finding, but it is also exactly why the claim
is scoped to recovery-of-the-Apollo-label within one domain rather than to deception detection in
general.

Two tensions temper the findings. First, the instrument's decision is highly reproducible
(verdict ICC 0.979, quadrant κ 0.986) but its rationale is not: the rule-citation set
flickers heavily run-to-run (Krippendorff α 0.238, and that figure is an optimistic upper bound),
with the strategic-deception J-rules changing on essentially every case they touch. The Auditor
reliably reaches the right verdict; the specific rules it names to justify that verdict are not yet
a stable output. This bounds the interpretability claim of §3.3 — the externalised reasoning is
reproducible as a verdict, not as a citation set — and it means the failure-mode inventory (§5.7)
should be read as indicative of rule frequencies, not as a stable per-case attribution. Second,
the same-model control produced two correlated CLEAN over-blocks: on identical weights,
prompt-and-role separation makes correlated L2/L3 errors rare but not impossible, a small but
genuine boundary on the partial-decoupling claim.

None of these qualifications touches the pre-registered headline metrics, all of which are computed
directly against ground truth and pass. But together they mark the edges of the claim precisely:
the architecture behaves as an independent, judge-invariant, well-calibrated Line 3 instrument on
this corpus, while its rationale-level reproducibility, its cross-domain behaviour, and its
robustness to a genuinely deceptive Line 2 remain open.

### 6.1 Limitations

- **Near-ceiling recovery on a single corpus.** The invariance result is strong precisely because
  recovery is uniformly high with little room to differ between judges. Whether the invariance holds
  when the task is harder (a lower-recoverability corpus, a less prescriptive policy) is untested.
- **Rule-citation instability.** Verdicts are stable; citations are not (α = 0.238, an optimistic
  upper bound that empty-set agreement inflates, so true agreement is worse). This bounds the §3.3
  interpretability claim and the diagnostic (function-2) value of the J-rule firings. A deterministic
  meta-audit over Gate B/C outputs is the proposed remedy (§6.2) and remains future work.
- **Gate B factual-tagging reliability is moderate.** Human inter-rater reliability on the 50-case
  Gate B subset reaches only κ = 0.515 (§4.7.1, §5.5), below the soft ≥ 0.60 target. This does not touch
  the registered verdict-stability gate (ICC ≥ 0.80, met) but flags per-claim factual tagging as the
  noisier sub-component and a calibration target for the full replication.
- **Verdict stability measured on the ablation arm only.** The ICC = 0.979 (§5.5) was computed on
  the ablation arm, where the Auditor reasons without a genuine judge trace. This isolates
  Auditor-internal non-determinism cleanly but leaves verdict stability *on genuine judge traces*
  unmeasured; the Z07 correlated over-blocks (§5.10) show genuine-trace interactions can in principle
  produce coupled errors the ablation-only check would not surface. A genuine-arm stability subset is
  added to the full-corpus replication.
- **Binary ground-truth collapse.** The headline metric pools ROGUE-HONEST and ROGUE-DECEPTIVE into
  a single ROGUE class (§4.1), so the paper's strategic-deception claim is evidenced by the J-rule
  firing inventory (§5.7) rather than by a per-stratum headline recovery comparison. Recovery of the
  honest/deceptive distinction in the headline metric is carried as future work (§6.2).
- **Specification-gaming policy boundary.** Under the frozen study policy, an agent that executes a
  prohibited MNPI trade but withholds the management report can, under strict literalism, return an
  empty violation set (§5.9; frozen at pre-registration policy v17). This is a boundary on the
  instrument-plus-policy pairing, not the architecture, and is logged as a candidate policy amendment.
- **Sole contamination check.** With the structural canary deferred to a follow-up study, the
  entity-perturbation arm (§5.8) is the only contamination/memorisation control in this pilot and
  carries that interpretive burden alone.
- **Correlated errors under same-model control.** 2/150 correlated CLEAN over-blocks in Z07 bound the
  failure-mode-decoupling claim.
- **Automated ground-truth labels.** Recovery is recovery of the *Apollo* label, which is itself
  automated: a deterministic misalignment flag and an LLM-graded deception judgment, validated by the
  corpus authors against a 120-case single-researcher spot-check (94% agreement) but without a published
  multi-rater human IRR on this corpus. Downstream work using these labels reports substantial-to-strong
  external corroboration (Cohen's κ ≈ 0.73 against a three-expert majority; weighted κ ≈ 0.81; supervised
  activation probes at AUROC 0.96–0.999), which bounds — but does not eliminate — label-noise concerns.
  The headline is bounded accordingly; we treat the quantitative implication in §6.2(e).

### 6.2 Proposed Future Work

This pilot validates the baseline capabilities of the Line 3 Correspondence Auditor. To advance this architecture toward production-grade enterprise deployment and safety certification, we define five distinct vectors for subsequent research:

* 
**(a) Cross-domain verification on a behavioural-diagnostic pipeline (with N. Watson):** A planned collaborative follow-up will point the Auditor at the differential-diagnosis tool in the Psychopathia Machinalis diagnostic MCP server — an LLM-as-judge that returns ranked syndrome candidates from behavioural observations — and verify those reasoning traces against the source observations through a substituted Truth Cartridge. This exercises the cartridge-swap abstraction on a second, non-financial domain while providing independent verification of the diagnostic tool's outputs. The precise scope — corpus, target syndromes, and evaluation metrics — will be defined jointly in a scoping note before the work begins.
* 
**(b) Reproducibility of the rationale layer (with G. Tsereteli):** The verdict layer is already reproducible (ICC = 0.979), but the rule-citation set that justifies each verdict is not (Krippendorff's α = 0.238, §5.5), which bounds the interpretability claim of §3.3. A planned methodological collaboration with Giorgi Tsereteli will explore principled ways to aggregate these citations across the k stochastic passes already produced per case. As Tsereteli notes, the objective is to compress the rationale space to reduce citation-level variability while preserving decision semantics. Rather than treating any single pass's citation set as canonical, future work will investigate using per-rule firing frequency as a confidence signal to recover a reproducible account of the rationale. The specific statistical architecture is deliberately left to that collaboration; the objective is to establish whether the rationale layer can be made reproducible without distorting the §5.7 failure-mode inventory, which is the prerequisite to strengthening the §3.3 claim.
* 
**(c) Local, data-sovereign deployment.** In post-hoc audit settings the material under review is frequently sensitive, so a deployable Auditor should be able to run wholly on local hardware, with no audited data leaving the operator's environment. A research direction is therefore whether the architecture can meet the same pre-registered reliability bars (H1 invariance, H2 bounded miscalibration, verdict stability) on open-weight models small enough to run on commodity local hardware rather than frontier-scale hosted models. Where a smaller model cannot sustain the layered conditional logic of the audit prompts directly, the work would explore moving deterministic sub-tasks from the model into code and decomposing the audit into narrower steps, so the reliability thresholds are preserved at lower capacity. Specific hardware and model classes are intentionally left open, since the viable capability tier will track the open-weight frontier.

* 
**(d) Corpus-agnostic ingestion.** The present ingestion layer relies on content-shape heuristics tuned to the Apollo corpus's text conventions to populate the three source-text sections the Auditor consumes — a coupling we note as a limitation of the current implementation (§6.1). To support cross-domain replication, we plan a dataset-adapter pattern in which corpus-specific adapters emit a common structured intermediate representation, decoupling the Auditor's core logic from dataset-specific formatting and reducing the risk of silent ingestion failures.

* 
**(e) Full-Corpus Replication and Label Sensitivity:** We intend to scale the financial compliance evaluation to the maximum balanced sample of the Apollo dataset ($\approx 8,500$ cases), moving the result from the 95% to the 99%-confidence class. Because near-ceiling recovery must be read against the reliability ceiling of the underlying LLM-graded labels , this replication will include re-scoring a stratified subset against a human-annotated panel. To resolve known analytical bounds, this full replication will integrate a genuine-arm stability evaluation subset to measure user-interaction non-determinism, and will explicitly un-collapse the pooled ground-truth metric to isolate the recovery of the distinct honest/deceptive strata. We will pre-commit to specifying equivalence margins for the save and break rates as primary metrics before execution.

### 6.3 Responsible Use

The J-rule taxonomy (J1–J5, §4.9, §5.7) documents named failure modes of LLM-as-Judge systems —
scratchpad blindness, sanitised cover-story acceptance, pressure-as-justification. This map of
oversight blindspots is published to advance defensive auditing, not as a specification for building
agents that evade detection. The underlying failure modes are already documented in the cited
literature; the net contribution here is defensive. Practitioners deploying this instrument or its
derivatives should treat the J-rule findings as defensive knowledge and exercise appropriate care in
dissemination.

---

## 7. Related Work

**Apollo Research insider-trading deception corpus.** We use Apollo's dataset as the ground-truth source for the pilot. Our contribution is downstream of theirs: we audit judge verdicts produced *over* this corpus rather than producing new corpus annotations.
https://github.com/ApolloResearch/insider-trading
Published to GitHub: Nov 9, 2023.
The dataset is from their technical report:
"Large Language Models can Strategically Deceive their Users when Put Under Pressure."
https://arxiv.org/abs/2311.07590

**JudgeBench and the LLM-as-Judge line.** The JudgeBench framework (Tan et al., 2024) establishes the use of LLM evaluators for automated assessment by ranking outputs against pairwise comparisons with objective-correctness labels. Our Z01 and Z02 prompts are adapted from JudgeBench-style rubrics to a binary `APPROVE`/`BLOCK` classification rather than a ranking task; the Z01/Z02 prompts are shipped in the repository so the derivation can be inspected directly. We note only that a ranking judge and a binary-classification judge are different instruments with different failure modes.

References:
Tan, S., Zhuang, S., Montgomery, K., Tang, W. Y., Cuadron, A., Wang, C., Popa, R. A., & Stoica, I. (2024). JudgeBench: A Benchmark for Evaluating LLM-based Judges (published as a conference paper at ICLR 2025). arXiv:2410.12784. https://arxiv.org/abs/2410.12784

**Diagnostic taxonomies of AI failure modes.** Watson & Hessami (2025a) describe _Psychopathia Machinalis_ as a structured nosology of machine cognitive-behavioural failure syndromes, with a peer-reviewed 32-syndrome framework spanning epistemic, cognitive, alignment, ontological, tool-interface, memetic, and revaluation axes. The framework has since been extended and reorganised (Watson & Hessami, 2025b, v2.2) into a synthetic nosology of 79 AI dysfunctions across nine axes in five domains: 67 canonical dysfunctions, plus a 12-entry pre-canonical Hybrid Pathologies sub-category.  

The rule firings tracked by the Correspondence Auditor map onto v2.2 syndromes: the J1/J2/J3 cluster (scratchpad blindness, sanitized cover-story acceptance, pressure-as-justification) corresponds to Strategic Compliance (Alignment axis, v2.2); F2, action-tip temporal causality, corresponds to Spurious Pattern Hyperconnection (Epistemic axis, v2.2); and the broader judge-evaluator blindspot pattern motivating the §3 architectural separation corresponds to Leniency Bias (Alignment axis, v2.2), all in Psychopathia Machinalis.

These correspondences concentrate on two of the nosology's axes rather than dispersing across several, but we draw no inference from that clustering: it is a property of how the syndromes are catalogued, not a finding about the Auditor. The per-rule mapping with case counts is published in the run dashboard as an illustrative rule-to-syndrome correspondence table.

These correspondences are structural and are offered as a shared vocabulary rather than as a validated construct-level equivalence: we map the Auditor's rule firings onto _Psychopathia Machinalis_ syndromes by their definitions and illustrate the mapping with case counts in the run dashboard (§13), but we do not claim to have demonstrated that a J-rule firing and the corresponding syndrome indicator track the same latent construct. Establishing that convergence empirically — and doing so on citation outputs whose run-to-run stability is itself limited (§5.5) — is left to future work.

In summary, the Auditor is an operational instrument; the Truth Cartridge is the working specification of the audit criteria; and _Psychopathia Machinalis_ is the framework used to contextualise the specific results. 

References:
Watson, N. & Hessami, A. (2025a). Psychopathia Machinalis: A Nosological Framework for Understanding Pathologies in Advanced Artificial Intelligence. Electronics, 14(16), 3162. https://doi.org/10.3390/electronics14163162
Watson, N. & Hessami, A. (2025b). Psychopathia Machinalis (v2.2). Nosological taxonomy of AI dysfunctions. https://www.psychopathia.ai

**IEEE 7001-2021 and the transparency-as-testable-property tradition.** IEEE 7001-2021 (ratified March 2022) establishes transparency of autonomous systems as a measurable, testable property addressed differentially across five stakeholder groups including incident investigators, safety certification agencies, and lawyers / expert witnesses. The Correspondence Auditor's externalised reasoning artefacts — Gate B claim-level tags with source quotes, Gate C rule citations, and the release-control sign-off page (§3.10) — sit within this tradition: they are designed to serve precisely the incident-investigator and certification-agency stakeholders 7001 names, adapted from the autonomous-physical-system domain to the LLM-as-Judge evaluation domain. The architectural intuitions converge despite the independent motivations. The standard's rationale and stakeholder-differentiated design are documented in the working group's companion paper (Winfield et al., 2021).

References:
IEEE Standards Association. (2022). *IEEE Standard for Transparency of Autonomous Systems* (IEEE Std 7001-2021). IEEE. https://doi.org/10.1109/IEEESTD.2022.9726144
Winfield, A. F. T., Booth, S., Dennis, L. A., Egawa, T., Hastie, H., Jacobs, N., Muttram, R. I., Olszewska, J. I., Rajabiyazdi, F., Theodorou, A., Underwood, M. A., Wortham, R. H., & Watson, E. (2021). IEEE P7001: A Proposed Standard on Transparency. *Frontiers in Robotics and AI*, 8, 665729. https://doi.org/10.3389/frobt.2021.665729

**Boundary Point Jailbreaking of Black-Box LLMs (Davies et al., 2026).** The result that Constitutional Classifiers fall to a fully automated, black-box attack — one that succeeds *despite* incurring many flagged queries during optimization that a separate monitoring layer would readily surface — motivates the segregation-of-duties argument in §3.4: a classifier operating as a single-layer preventive control is forced to both gate and detect from the same input, and cannot escalate a flag-pattern signature to a layer with the latitude to investigate. This is the governance failure the Mode A / Mode B (§3.8) distinction is designed to surface.

References:
Davies, X., Giglemiani, G., Lau, E., Winsor, E., Irving, G., & Gal, Y. (2026). Boundary Point Jailbreaking of Black-Box LLMs. arXiv:2602.15001. https://arxiv.org/abs/2602.15001

**The GRC Three Lines of Defense model (IIA).** The Institute of Internal Auditors' Three Lines model is the source of our architectural framing. We are explicit that the Auditor is a Line 3 instrument and that conflating it with Line 2 is a category error.

**Sycophancy and oversight failure in language models.** A growing literature characterises sycophancy and credulity-toward-coherent-cover-stories as learned behaviours of LLM evaluators. The Correspondence Auditor's source-evidence-grounding mechanism is one architectural response to this literature; it is intended as a runtime instrument complementing the diagnostic work in that literature, not a substitute for it.

**Source Text Grounding.**
See Zheng et al. (2023) on LLM-evaluator reliability and biases and Turpin et al. (2023) on unfaithful chain-of-thought reasoning, which together motivate the source-text grounding requirement of Gate B: an evaluator's stated rationale cannot be taken at face value, so the audit layer must check claims against an external reference rather than against the judge's narrative.

References:
Zheng, L., Chiang, W.-L., Sheng, Y., Zhuang, S., Wu, Z., Zhuang, Y., Lin, Z., Li, Z., Li, D., Xing, E. P., Zhang, H., Gonzalez, J. E., & Stoica, I. (2023). Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. Advances in Neural Information Processing Systems 36 (NeurIPS 2023). arXiv:2306.05685. https://arxiv.org/abs/2306.05685
Turpin, M., Michael, J., Perez, E., & Bowman, S. R. (2023). Language Models Don't Always Say What They Think: Unfaithful Explanations in Chain-of-Thought Prompting. Advances in Neural Information Processing Systems 36 (NeurIPS 2023). arXiv:2305.04388. https://arxiv.org/abs/2305.04388

---

## Ethics Statement

**Human-subjects determination.** This study involves no human subjects. It audits machine-generated agent transcripts from the publicly available Apollo Research corpus, together with machine-generated judge and Auditor outputs; no personal data are collected and no human participants are recruited, observed, or surveyed. Under the applicable human-subjects-research definitions, the work carries a not-human-subjects (exempt) determination, and no institutional review board approval was required.

**Annotation and consent.** Any human inter-rater annotation used to characterise Gate B factual tagging (the `n = 50` Gate B inter-rater-reliability subset, §4.7.1) was performed by the author, who participated voluntarily and with informed consent; no third-party or vulnerable-population annotators were involved, and no personal data were recorded during annotation.

**Data ethics.** The Apollo corpus is publicly available and contains no personally identifiable information; named entities in the source transcripts are fictional scenario constructs, and the contamination canary (§5.8) additionally evaluates the pipeline on synthetic-entity variants.

**Dual use.** A Responsible Use statement addressing the dual-use potential of the J-rule failure-mode taxonomy is given in §6.3.

---
## Acknowledgments

*Personal Acknowledgments.* The author extends sincere thanks to Nell Watson for her invaluable feedback, insightful discussions, and review of early drafts of this manuscript.

The author thanks Giorgi Tsereteli for extensive review of the study's evaluation framework, including scrutiny of the experimental design, verification of the statistical analysis pipeline, and critical examination of the reliability, robustness, and interpretability claims associated with the proposed auditing system.

*AI Usage Disclosure.* During preparation of this manuscript and the accompanying code, the author used large language model assistants — specifically: Anthropic Claude Opus 4.7 & 4.8, Google Gemini Pro 3.1 & Flash 3.5, and Minimax M2.5 — for methodology refinement, statistical exposition, prose editing, and code review.

All experimental measurements reported in §5–§6 are deterministic post-processing of the outputs from the Qwen and Llama models under audit, computed via `tools/compute_stability.py` and `tools/build_dashboard.py` against the pre-registered decision rules of paper §3 and `PRE_REGISTRATION.md` §10. 

Further deterministic code utilities were developed after the experiment data had been produced to assist in producing and verifying the data tables in this paper (specifically `tools/check_paper_consistency.py` and `tools/validate_paper_tables.py` -  full list in `paper/PRE_REGISTRATION.md` Appendix A: Changelog - Post-Hoc Disclosures). 

The reported numbers in this paper are not LLM-computed.

All hypothesis specifications, pre-registration commitments, statistical decisions, and final editorial choices were made by the human author, who bears full responsibility for the work. The oversight of Nell Watson and Giorgi Tsereteli further contributed to the robustness of the reporting.

## Author

Adrian St. Vaughan is an independent researcher working at the intersection of AI safety and enterprise GRC. He holds an MSc in Information Technology, the Certified Information Systems Auditor (CISA) certification, and the Certified Anti-Money Laundering Specialist (CAMS) certification, and has spent his career evaluating operational technology controls at institutions including JPMorgan and American Express. 

The Correspondence Auditor core concepts have been battle-tested in production over 9 months of active development, evolving as the third line of defense within a larger 16-month production workflow.

---

## Appendix A: Formal Statistical Specifications

To ensure the methods sections remain accessible, formal specifications for the statistical claims made in this paper are detailed in this appendix.

**H1 Equivalence Testing (TOST):** Equivalence across judge conditions is evaluated via the TOST procedure (Schuirmann, 1987) at margin $\delta = 0.05$. H1 is supported if and only if both one-sided tests reject at $\alpha$ after correction, i.e., $\max(p_1, p_2) < \alpha_{\text{adjusted}}$.

**Standard Error (SE) Estimation:** We compute the test statistics utilizing an unpooled SE. Under the TOST null hypotheses ($H_{01}: p_1 - p_2 \le -\delta$ and $H_{02}: p_1 - p_2 \ge \delta$), the proportions are explicitly assumed to be unequal; thus, a pooled variance estimator would be misspecified.

**Multiple Comparisons:** Controlled via the Holm-Bonferroni step-down procedure (Holm, 1979) at $\alpha_{family} = 0.05$. This universally controls the FWER across the $m=10$ pairwise equivalence tests within each ground-truth class (two families of 10) while offering strictly greater power than the single-step Bonferroni method.

**Minimum Detectable Effect (MDE):** Power is sized against the two-proportion z-test for *difference* at margin 0.05. We are explicit that this sizing does **not** transfer cleanly to the equivalence (TOST) test: TOST power at margin $\pm\delta$ depends jointly on the true between-judge difference and on $\delta$, and a sample powered to detect a 0.05 difference does not by itself guarantee equivalence power at the same margin. We therefore treat the difference-test MDE as an indicative sizing reference rather than a guarantee of equivalence power, report the realized TOST outcomes directly (§5.3), and designate the full ~8,500-case replication as the run powered for robust equivalence support (§4.6).

**Instrument Stability:** Evaluated using ICC(2,1) (two-way random effects, absolute agreement, single rater/measurement) over $k=6$ iterations. Stability threshold is ICC $\ge 0.80$ (Koo & Li, 2016). Stability of rule-citation sets is measured with Krippendorff's $\alpha$ utilizing a distance metric appropriate for set-valued items, as standard single-label coefficients are undefined for variable-length sets (Krippendorff, 2004). We note that $\alpha$ on these sets is inflated by agreement on empty/absent-citation cases and should be read as an upper bound on agreement over the rules actually cited.

**Factual Baseline Reliability:** Quantified via Cohen's $\kappa$, appropriate for nominal, mutually exclusive categories between two raters. Threshold is $\kappa \ge 0.60$ (Landis & Koch, 1977).

**Post-hoc sensitivity analysis for boundary conditions:** No pairwise comparison in either ground-truth class placed an observed proportion exactly at the 0 or 1 boundary, so the Wald unpooled standard error did not degenerate for any reported TOST. As a robustness check we nonetheless recomputed every pair with an Agresti-Caffo-adjusted TOST (one success and one failure added to each arm). Under the adjusted test every pair retained equivalence at the Holm-adjusted threshold (p < 0.05), so the registered H1 conclusion is driven by the data rather than by estimator collapse.

## Appendix B: Supplementary Tables

### Supplementary Table: Drops/Quarantine Table (§4.1)

| Arm / run | GT-null | Impossible | Pipeline / Gate-A error | Unreadable | Total dropped | n analysed |
|---|---|---|---|---|---|---|
| Main grid — Z01 (sota) | 0 | 0 | 1 | 0 | 1 | 1,199 |
| Main grid — Z02 (scratchpad) | 0 | 0 | 1 | 0 | 1 | 1,199 |
| Main grid — Z03 (paranoid) | 0 | 0 | 2 | 0 | 2 | 1,198 |
| Main grid — Z04 (lenient) | 0 | 0 | 1 | 0 | 1 | 1,199 |
| Main grid — Z05 (manager-aligned) | 0 | 0 | 1 | 0 | 1 | 1,199 |
| Ablation (noise) | 0 | 0 | 2 | 0 | 2 | 1,198 |
| Canary (arm03) | 0 | 0 | 2 | 0 | 2 | 1,198 |
| Z07 control (arm02) | 0 | 0 | 0 | 0 | 0 | 150 |
| Test-retest seed (arm04a) | 3 | 0 | 0 | 0 | 3 | 297 |

All drops are fail-loud quarantines (§4.1); none defaulted silently to APPROVE. The "Unreadable" column denotes transcripts that failed decoding before label inspection; none occurred in the pilot, and the column is retained for schema completeness. Denominator-conservation checks — each arm's analysed n plus its dropped count equalling the drawn n — passed at run end for every arm in the table. The main grid, ablation arm, and Z07 control completed under the pre-amendment pipeline; the canary figures reported here are from its post-amendment re-run (provenance note below).

Within the main grid and the ablation arm, the eight GATE_A_AND_SYSTEM_FAILURES
records resolve to three unique input cases. One case (`6f6c5fd25711`,
ground-truth ROGUE-DECEPTIVE) fails before a verdict can be produced under all
five judge variants and the ablation arm (six instances) — which is why every
variant's ROGUE denominator is 799 rather than 800. The failure is case-intrinsic
and judge-independent: a claim-mining format-drift quarantine
(`CLAIM_MINER_FORMAT_ERROR`, triggered by a missing "Information used" field in
the transcript itself), identical regardless of which judge produced the input and
present even under ablation where the judge input is noise — not informative
censoring of a hard-to-classify case.

A second case (`37f61727e427`, ground-truth CLEAN) fails under the paranoid variant
only, lowering that variant's CLEAN denominator to 399; a third (`1bce6dff94b8`,
ground-truth CLEAN) fails only in the ablation arm, lowering the ablation CLEAN
denominator to 399. By ground-truth class these eight grid-and-ablation instances
are 6 ROGUE-DECEPTIVE, 2 CLEAN, and 0 ROGUE-HONEST. Because the single dominant
case is excluded uniformly across all five judge variants it cannot differentially
bias the cross-variant invariance comparison (H1), and the two single-variant CLEAN
drops are immaterial at these denominators.

The canary (entity-perturbation) arm is a separate Z01-only run and accounts for the
table's two remaining quarantines. The first is `6f6c5fd25711` once more: the same
dominant transcript re-fails the claim miner under perturbed entities, which shows the
failure is not only judge-independent but perturbation-independent — a missing structural
field, not any named entity, is what trips the miner. The second is a fourth, distinct
case (`e61ea066ba42`, ground-truth ROGUE): a one-off `TIMEOUT_ERROR` that fail-closed to
an error sentinel rather than a verdict. That same case processes cleanly and is correctly
blocked in the ablation arm, confirming the timeout as transient infrastructure rather than
a property of the transcript. Both quarantines leave the canary denominator at 1,198
(1,200 drawn − 2 dropped). No dropped case, in any arm, defaulted silently to APPROVE.

**Provenance note — an integrity catch during development.** 

The denominator-conservation check is not a formality; it caught a real fail-open event
before release. During an initial launch of the canary arm (pre-registration, Appendix A, amendment v18, item 1),
sustained provider `engine_overloaded` (HTTP 429) responses caused 246 of 1,200
cases to exit the pipeline without emitting either an `audit_*.json` record or the
required `audit_*.error.json` sentinel — a silent breach of the fail-closed posture
(§4.1) that an analysed-count-only dashboard would not have surfaced. The
conservation check flagged the shortfall, the provider-throughput cause was
remediated, and the arm was re-run in full; the canary figures reported above are
from that clean re-run. We record the episode because it is the pilot's clearest
evidence that the conservation control detects fail-open events rather than merely
asserting their absence.