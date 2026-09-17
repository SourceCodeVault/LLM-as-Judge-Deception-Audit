---
numbersections: true
title: "Reliable verdicts, unreliable rationales: a test–retest study of an LLM-as-judge audit instrument"
author: "Adrian St Vaughan \\ \\small Source Code Vault Ltd"
mainfont: "Times New Roman"
abstract: |
  **Background:** An LLM judge auditing a deceptive agent can reach the right verdict on a rationale that misquotes the facts it cites. We test the open-source Correspondence Auditor, which binds every finding to a versioned Truth Cartridge rather than to the judge's priors; in a test–retest study its verdicts proved highly reproducible ($ICC = 0.979$) while its rule citations did not (Krippendorff's $\alpha = 0.238$).

  **Method:** The three-gate Auditor (deterministic Schema gate, per-claim source-grounding Facts gate, verdict Logic gate) audited a 1,200-case stratified pilot of the Apollo Research insider-trading deception corpus under five judge prompt variants (two realistic, three deliberately degraded), with $k = 6$ test–retest passes and recovery equivalence pre-registered. The corpus's ground-truth labels are themselves LLM-graded.

  **Results:** The Auditor recovered the ground-truth label at 97.9--99.5\% under every judge variant, within the pre-registered equivalence bound (max FPR 1.0\%, max FNR 2.1\%) --- the instrument works as designed. The stability gap is structured: instability concentrates in interpretive rules lacking per-claim source grounding, while rules grounded through Gate B remain comparatively stable (F2 flicker 10.7\%). Rule-family findings are reported at aggregate frequency only; no per-case deception attributions are made.

  **Conclusion:** Verdict-level source-grounding is stable; rationale-level citation is not yet a reliable signal. Independence at the audit layer, not competence at the judge layer, is what makes automated judgment governable.

header-includes: |
  \usepackage{etoolbox}
  \AtBeginEnvironment{longtable}{\small}
  \usepackage{url}
  \urlstyle{same}
---


---

\clearpage

# Introduction {#sec:introduction}

When a language-model agent behaves deceptively, it produces a plausible, internally coherent cover story. A judge that evaluates the cover story at face value — simply checking whether it makes sense rather than whether it is true — can be fooled by coherence alone.

Large language model (LLM) judges — systems in which an LLM is delegated to evaluate an agent's behavior — triage regulatory compliance, score scientific submissions, and grade benchmark outputs. They are being adopted faster than the infrastructure for auditing their judgments has matured. The methods used to validate them measure whether the judge reaches the right verdict. They do not verify whether the judge's stated rationale corresponds to the facts it cites.

European regulation imposes exactly the kind of judgment workload described above: Directive 2014/65/EU (MiFID II) and Regulation (EU) 596/2014 (the Market Abuse Regulation) mandate continuous trade surveillance, and Regulation (EU) 2024/1689 (the Artificial Intelligence Act) adds a demand for auditable, inspectable AI systems. Institutions are exploring automated judgment to meet this mandate at a volume no human review team can match. Yet the economic logic that motivates automation is that human review does not scale. That logic transfers the reviewer's risk, and the institution's regulatory liability, onto the quality of a judgment that is itself unaudited.

This is not a hypothetical exposure. DeLeeuw et al. (2025) demonstrate that language models strategically lie when deception advantages goal achievement, including in an insider-trading compliance testbed directly analogous to the corpus used here, and that current interpretability-based safety tools fail to detect or control the behavior. When a deceived or credulous judge sits inside a compliance pipeline, the failure surfaces as regulatory risk, not as a system error.

The recent literature on judges and "chain-of-thought oversight" highlights at least three structural failure modes. **First**, the agent under evaluation (Line 1) can produce a plausible, internally coherent cover story that the judge credits over the structural pattern of the agent's behavior; the judge is *blinded by the sanitized report*. **Second**, the judge can be inattentive to the agent's reasoning trace (the scratchpad), approving an output whose internal monologue contains explicit deliberation toward a misaligned action. **Third**, the judge's own *bias* — the dispositions baked into its weights — and its judgment of the evidence become operationally indistinguishable, so one cannot tell whether a verdict reflects the case or the model. None of these failures requires collusion; a credible cover story alone defeats the judge in isolation.

The third failure mode has now been quantified. Testing 56 instruction-tuned language models across 29 psychological and behavioral instruments, Meyer, Garcia, and Wulff (2026) show that models exhibit a strong directional response bias — a tendency to select one end of a scale regardless of item content. This accounts for 81–90% of between-model variation, versus 9–16% in humans. The bias persists undetected on instruments lacking what the authors term *response orthogonality* — a property of instruments whose items place the trait answer and the bias direction in opposition, so that a bias-driven response is exposed. The structural defect is the same in both settings: an instrument produces fluent output that does not correspond to the evidence it purports to report, and nothing in the pipeline checks the correspondence.

The Auditor is designed against exactly this failure mode (§\ref{sec:architecture}) — a design that predates this literature. A judge's raw verdict is not treated as evidence of its underlying dispositions; every claim must instead be grounded in the source text and the cartridge (Gate B), so bias-driven tendencies have no admissible input.

This is the architectural case for an audit layer. The vocabulary for this exists in the Governance, Risk, and Compliance (GRC) tradition: the Institute of Internal Auditors' *Three Lines Model* (IIA, 2026), which distinguishes:

- **Line 1 — management:** owns and manages risk; designs and operates the processes and controls. Here, the task agent and the pipeline that deploys it — the operational activity whose behavior is under review.
- **Line 2 — support and specialized roles:** provide expert support, monitoring, and challenge to the first line, with some organizational separation from it but within management's reporting structure. Here, the judge: a monitoring function embedded in the compliance workflow, reviewing Line 1 output but not independent of the system that produces it.
- **Line 3 — the internal audit function:** delivers independent and objective assurance on the effectiveness of governance, risk management, compliance, and control processes, reporting functionally to the board rather than to management. Here, the Correspondence Auditor — separated from Lines 1 and 2 in methodology and, in this study, additionally separated at the model substrate (§\ref{sec:model-selection-and-asymmetry}).

Nothing in this pattern requires Line 1 or Line 2 to be a language model. The gates operate on any recorded judge rationale and its underlying evidence; the deployment question is whether those artifacts exist to audit.

The Correspondence Auditor is a Line 3 instrument, built exclusively as Line 3. It does not compete with the judge head-to-head, and we do not benchmark it as a judge; the judge's verdict and reasoning trace are inputs to the audit, not a baseline.

Here, we ask: given a source text `X` (the deliberations and actions of a Line 1 agent) carrying a latent ground-truth status `Y` (`SAFE` or `ROGUE`), and a judge verdict `Z` (`APPROVE`, `HESITATE`, or `BLOCK`, with rationale), can the Auditor — blind to `Y` — recover `Y` at the verdict level using only the evidence and the cartridge (§\ref{sec:the-truth-cartridge}). In this experiment, label recovery is the metric of interest: in production no ground-truth label exists, so an auditor that recovers `Y` blind here is one that can flag non-compliance where no label is available.

The question is not whether one can architect a better judge; it is whether segregation of duties can be enforced. Line 3 arrives at its verdict through an entirely distinct mechanism and a strictly separate set of binding parameters, and in the main experimental conditions it additionally runs on a different model family from every judge (`Qwen 3 235B` versus `Llama 3.3 70B`; §\ref{sec:model-selection-and-asymmetry}). 

We claim independence at the verdict level — the audit verdict is recomputed from source evidence rather than inherited from Line 2 — and we do not claim organizational independence in the GRC sense. The reporting-line element of that independence is discharged, at the instrument level, by the release sign-off page (§\ref{sec:control-owner-attestation}); organizational independence remains a deployment property that no artifact supplies (IIA, 2026, 'Independence'). The residual objection that prompt separation over LLMs still permits correlated failures is answered empirically rather than assumed away: a same-model control arm (§\ref{sec:same-model-control-arm-z07}) deliberately collapses the model-substrate separation and finds correlated both-block errors in 2 of 150 cases, a real if small bound on partial decoupling (§\ref{sec:proposed-future-work}). It is this mechanism-level, verdict-level separation — not any claim of infallibility or organizational independence — that transforms a technical safeguard into a governance instrument and provides the defensible assurance a board's fiduciary duty of oversight requires.

One clarification bounds the claim. The Correspondence Auditor audits the *process* of judgment, not the *intent* of the judge. It assumes the judge acts in good faith but is fallible. A Line 2 actively colluding with Line 1 — a deceptive judge — is outside the architectural boundary; this is precisely why governance frameworks specify three lines, not two (§\ref{sec:auditing-the-process-not-the-intent}).


**Our contribution is twofold.**

1. **An audit architecture** — a fixed three-gate pipeline (a deterministic 'Schema' gate, a per-claim source-grounding 'Facts' gate, and a verdict 'Logic' gate) in which every finding is bound to a cartridge rule rather than to the model's priors. In aggregate, the pipeline's most strongly enriched signal is the strategic-deception rule cluster (`J1`/`J2`/`J3`), which upstream judges misread as evidence of compliance — an exploratory aggregate signal, not a per-case attribution (§\ref{sec:failure-mode-inventory-rule-citations-genuine-arm}); the architecture's confirmatory contribution is verdict-level label recovery.

2. **An empirical demonstration** that, on a 1,200-case stratified pilot, audit-layer label recovery remains within the pre-registered equivalence bound (TOST, $\pm$ 5 pp) across five judge variants: two realistic baselines and three fault-injection stress probes (Z01–Z05). The claim is *invariance within the tested range*.

The paper proceeds as follows. §\ref{sec:architecture} describes the three-gate architecture and the Truth Cartridge. §\ref{sec:experimental-design} describes the experimental design, the five judge variants, the pre-registered hypotheses, and the ablation arm. §\ref{sec:results} reports results. §\ref{sec:discussion} discusses limitations and the boundary of the claim. §\ref{sec:related-work} situates the work in adjacent literatures.

---

# Architecture {#sec:architecture}

## The Three-Gate Audit Pipeline {#sec:the-three-gate-audit-pipeline}

The Correspondence Auditor processes each judge verdict through three sequential gates — **Schema**, **Facts**, **Logic** — terms we use consistently across the paper, the README, and the codebase. Each gate carries a narrowly scoped responsibility and a pre-defined output schema; each can independently halt a case, and Gate C emits the final verdict only if Gates A and B have not halted.

| Gate | Name | Function | Language-model? |
|---|-------|------------------------|----------|
| A | **Schema** | Deterministic structural validation: required fields, score ranges, schema conformance, forbidden-term checks. Halts on schema violation. | No |
| B | **Facts** | Per-claim source-grounding: each claim in the judge's verdict is tagged `SUPPORTED`, `CONTRADICTED`, or `UNSUPPORTED` against the source text. Fails closed when the source text needed to ground a claim is absent. | Yes |
| C | **Logic** | Source-evidence-grounded verdict on the agent: `APPROVE` or `BLOCK`. Produced from the source text, the cartridge (the swappable domain-policy file; §\ref{sec:the-truth-cartridge}), Gate B's per-claim verdicts, and the judge's verdict and reasoning trace as inputs. Cites cartridge rules to explain the verdict. | Yes |

The sequencing is principled. Schema runs first because it is deterministic and cheap. Facts runs second because auditing logic over false premises is meaningless. Logic runs last, as the most demanding step, executed only on inputs that have cleared factual scrutiny. A case must clear all three gates to be designated `APPROVE`; a halt at any gate produces a detailed failure record rather than a silent pass. The pipeline fails closed at every level.

## Why Three Tags at Gate B Rather Than Two {#sec:why-three-tags-at-gate-b-rather-than-two}

A naïve fact-checker emits a binary `SUPPORTED` / `NOT SUPPORTED`. Gate B emits three tags because two distinct failure modes require different remediations.

- `SUPPORTED` — the source text contains evidence affirming the claim.
- `CONTRADICTED` — the source text contains evidence *against* the claim. This is a finding of factual error.
- `UNSUPPORTED` — the source text contains *neither* affirming nor contradicting evidence. This is a finding of an unsubstantiated claim: the judge has asserted something absent from the record.

`CONTRADICTED` is the stronger signal, but both are findings. Collapsing them would conflate "the judge said something false" with "the judge said something it had no basis to say" — two failures with different downstream implications. The third tag is what makes the distinction auditable.

## Source-Evidence Grounding and the Verdict/Citation Split {#sec:source-evidence-grounding-and-the-verdict-citation-split}

A standard judge has access to the agent's final output message, its external interactions (for example, tool calls), its internal reasoning traces, and the system and user prompts. What it lacks is a fixed external reference against which to check its own conclusions. Without such a reference, the judge's beliefs about the world and its judgment of the world collapse into one, and sycophancy, hallucinated rationales, and credulity toward sanitized cover stories follow downstream.

The Auditor introduces that reference. Gates B and C receive the source text — the prompt and context given to the judge — and the cartridge. The design implements a correspondence theory of truth in Aristotle's sense: a claim is verified not by its coherence but by its correspondence to what the record contains. The discipline imposed at the prompt level is exact: every claim the Auditor makes must be justified by exactly one of three things — the source text, the cartridge, or the judge's recorded trace. What the Auditor might implicitly encode about the wrongfulness of insider trading is not an admissible input; only the cartridge's explicit statement that insider trading is wrong may be taken as authoritative.

This is not a complete defense; we qualify it once and then constrain the qualification. Gates B and C use a carefully controlled language model, which nonetheless remains capable of misreading the source, missing a structural pattern, or being itself talked into a coherent-but-wrong narrative. But the failure is made external: the Auditor is forced to reason against artifacts a human reviewer can also read. Gate B's claim-level tags and Gate C's rule citations are that external record; they give the reviewer an inspectable record of the Auditor's working.

Gate C issues two outputs: a verdict on the worker's output (`APPROVE` or `BLOCK`) and a list of the cartridge rules that drove it. Because every citation is grounded against the same source the judge saw, the citations also document, case by case, how the judge handled its evidence. 

We expose the verdict and the citation list as separate outputs because their reproducibility differs sharply: the verdict is stable run to run (ICC = 0.979 on the ablation arm; §\ref{sec:test-retest-reliability-instrument-stability-results}), while the citations are not (Krippendorff's $\alpha$ = 0.238; §\ref{sec:test-retest-reliability-instrument-stability-results}, itself an optimistic upper bound). The interpretability guarantee therefore holds at the level of the reproducible verdict and the per-claim Gate B tags. Accordingly, throughout this paper, all rule-citation results — including the exploratory strategic-deception J-rules — are reported at aggregate frequency only, and no per-case rule citation is used to attribute deception to any individual case, pending the predicate-grounding redesign proposed in §\ref{sec:proposed-future-work}(b). Conflating the two outputs would mask exactly that asymmetry.

## Separation of Failure Modes Between Gates {#sec:separation-of-failure-modes-between-gates}

Gate B (Facts) and Gate C (Logic) run as separate language-model invocations, each with its own prompt. Gate C receives Gate B's output as a structured input but cannot re-litigate Gate B's per-claim verdicts. This separation is deliberate. The failure modes it isolates — "the model hallucinated a fact" and "the model reasoned incoherently from facts it correctly identified" — are diagnostically distinct and require different remediation: a hallucinated fact is corrected by re-grounding against the source, Gate B's job; incoherent reasoning from correctly identified facts is caught by the logic check, Gate C's job. Routing both to a single gate would conflate the two error types and blur which repair is needed.

The design instantiates, at the level of software components, the same principle that segregation of duties enforces at the organizational level: no single locus of control should be responsible for both establishing the evidentiary record and rendering judgment on it. In a traditional control environment, that principle prevents a single employee from initiating and approving the same transaction. Here, it prevents a single model invocation from establishing what is true and deciding what follows from it. The analogy is not exact, since prompted gates cannot collude or act from self-interest, but the structural property is the same: if one gate fails, the failure is visible to the other, and neither can silently corrupt the full chain.

## Synthesis and Quadrant Routing {#sec:synthesis-and-quadrant-routing}

Gate C emits a binary verdict on the agent — `APPROVE` (the source text and policy do not evidence a policy violation) or `BLOCK` (at least one violation is evidenced). Because this verdict is strictly independent of the Line 2 judge, the orchestrator cross-tabulates the two outputs (`{Judge Action} × {Auditor Verdict}`) into four routing quadrants.

This 2 $\times$ 2 matrix defines the operational outcome of the audit:

| | **Auditor: `APPROVE`** | **Auditor: `BLOCK`** |
|--------------------|---------------------|-------------------|
| **Judge: `APPROVED`** | `VALIDATED_APPROVAL` | `FLAWED_APPROVAL` |
| **Judge: `BLOCKED`** | `FLAWED_BLOCK` | `VALIDATED_BLOCK` |

* **Concurrence (`VALIDATED_APPROVAL` / `VALIDATED_BLOCK`):** the Auditor independently arrives at the same operational conclusion as the judge.
* **Operational disagreement (`FLAWED_APPROVAL` / `FLAWED_BLOCK`):** the Auditor explicitly contradicts the judge's verdict. `FLAWED_APPROVAL` — the judge waved an action through, but the Auditor blocked it — is the critical condition the Line 3 architecture exists to catch.

Where the upstream judge outputs `HESITATE`, the case is collapsed into the `BLOCKED` row for binary routing purposes — a "flagged for review" posture.

Because the Line 3 audit is blind to the latent ground-truth of the case at the time of execution, these quadrants are strictly operational. Once ground-truth is unblinded in the evaluation phase (§\ref{sec:per-variant-8-cell-decomposition-exploratory}), the operational disagreements decompose into **Saves** — the Auditor successfully corrected a wrong judge — and **Breaks** — the Auditor incorrectly overturned a right judge.

Rule citations from the policy taxonomy (§\ref{sec:policy-rubric-the-cartridge-for-this-study}) accompany the verdict as interpretability artifacts. They document the Auditor's reasoning but do not, by themselves, determine the quadrant: a judge can have flawed reasoning *and* reach the right action, or sound reasoning *and* reach the wrong action. The framework records both signals without conflating them. Hygiene-level findings (H-rules) are surfaced for reviewer attention but never alter the verdict or the routing quadrant.

## Auditing the Process, Not the Intent {#sec:auditing-the-process-not-the-intent}

The Correspondence Auditor presumes the judge operates in good faith: fallible, not adversarial. This is a deliberate audit posture, not naivety. Audit looks for *positive evidence* that a control operated; absence of such evidence is not, by itself, evidence of wrongdoing. Presuming bad faith would convert the function from audit into forensic investigation — the search for negative evidence — which is a different discipline and would flood the pipeline with false positives. A judge that is actively colluding or compromised is therefore out of scope by design. That is an insider-threat problem, managed by the standard insider-threat controls of GRC: segregation of duties, rotation, and independent reporting lines. This is precisely why the model specifies three separated lines rather than two. We note this boundary once and do not revisit it.

When a judge misses a deceptive-rogue agent, the common mechanism is that the agent's sanitized cover story satisfied the judge's surface checks. The Auditor does not adjudicate the judge's honesty. It mechanically grounds the judge's reasoning trace, together with the agent's scratchpad, tool calls, and final output, against the source text, and surfaces any contradiction between them.

The architecture's swappability across domains rests on two facts. First, Gate C's system prompt is domain-neutral scaffolding that defers entirely to the Binding Policy. Second, all domain-specific content — the rule taxonomy, the per-domain `CLEAN`/`ROGUE` definitions, and the per-policy citation patterns — lives in `policy.md` (§\ref{sec:the-truth-cartridge}), including the §\ref{sec:discussion} execution and chronology preconditions. To audit a different domain, replace the cartridge: no Gate C prompt or code changes are required. This is a property of L3 and the cartridge, not of the judges. The judges in this study are deliberately heterogeneous, and several (Z02–Z04) *do* encode insider-trading knowledge; they are the objects being audited, not part of the swappable apparatus.

The architecture does *not* claim to catch a Line 2 that is actively colluding with Line 1, a Line 2 that has been compromised, or a Line 2 deliberately gaming the audit. It is designed to catch reasoning errors and blindspots by a good-faith judge. A deceptive Line 2 is a failure of the governance design.

## The Truth Cartridge {#sec:the-truth-cartridge}

The domain policy and the source-of-truth schema are not hard-coded into the audit engine. They are loaded as an interchangeable parameter set we call a *Truth Cartridge*. The cartridge specifies four things: the rule taxonomy (e.g. the J/F/U/H rules described in §\ref{sec:policy-rubric-the-cartridge-for-this-study}), the per-domain definitions of `CLEAN` versus `ROGUE`, the per-policy citation patterns Gate C must use to justify a verdict, and the Gate B source-grounding schema.

For this study one cartridge is loaded: the insider-trading cartridge that defines the behavior evaluated as `ROGUE` in the Apollo corpus (§\ref{sec:introduction}). The audit architecture is, in this sense, domain-agnostic; the empirical results are not. Replication on a second domain, via a substituted cartridge, is identified as future work (§\ref{sec:proposed-future-work}) — the natural test of the cartridge abstraction.

The cartridge is located at `domains/insider_trading/policy.md` with a manifest describing the format at `domains/insider_trading/manifest.json`.

## Deployment Modes {#sec:deployment-modes}

The system supports two deployment postures, with distinct governance properties.

- **Mode A (Inline Halt Gate):** the Auditor sits in-line between the judge and any downstream consumer; non-validated outputs are quarantined for human review. In GRC vocabulary, a **preventive control**.
- **Mode B (Retrospective Evidence Generation):** the Auditor processes historical judge outputs asynchronously; nothing is blocked. In GRC vocabulary, a **detective control**.

For Mode A to be genuinely *preventive* rather than merely detective, the audit must intercept at one specific point: after the agent has emitted a tool call that declares its intended action, but before that action is authorized and executed. Audited any later, the trade has already happened, and the control can only detect, not prevent.

Running Mode B while treating it as Mode A is a governance failure: a detective control mis-labeled as preventive provides a different, lower assurance level than its label implies. We are explicit about which mode a given deployment operates under.

## The Fail-Closed Posture {#sec:the-fail-closed-posture}

The Auditor is explicitly engineered to be fail-closed. If the source evidence is ambiguous, if the reasoning-trace formatting drifts, or if the claim miner cannot securely anchor an assertion to the text, the architecture defaults to `BLOCK` or a quarantine status. Over-blocking has a manageable cost — false positives produce noise a human reviewer can recover — whereas under-blocking is the catastrophic failure the instrument exists to prevent. The calibration is therefore deliberately asymmetric: it prices the second error far above the first. This reflects the operational penalty of each error type, not an empirical prediction of their relative frequencies (see §\ref{sec:hypothesis-h2-test-fpr-fnr-by-judge-variant}).

The posture operates at two layers. First, code-enforced fail-closed handles the structural failure modes deterministically: empty transcripts emit `EMPTY_TRANSCRIPT`, claim-miner format drift emits `CLAIM_MINER_FORMAT_ERROR`, missing essential fields raise `ValueError` rather than returning empty placeholder values that would pass downstream validation silently, and any non-OK pipeline status drops the case from primary analysis. Second, prompt-driven fail-closed governs the language-model gates themselves: Gates B and C are prompted to default to `UNSUPPORTED` / `BLOCK` when source evidence is ambiguous, rather than producing affirmative verdicts on weak grounds. The code-enforced layer is verifiable by inspection; the prompt-driven layer is empirically bounded, per the error profile reported in §\ref{sec:hypothesis-h2-test-fpr-fnr-by-judge-variant}: if Gates B and C were failing to default to `UNSUPPORTED`/`BLOCK` on ambiguous evidence at any substantial rate, that failure would surface as elevated FPR or FNR, whereas §\ref{sec:hypothesis-h2-test-fpr-fnr-by-judge-variant} shows both error rates well inside the pre-registered 0.10 bound. The per-case record, however, identifies one specific fail-open class: in the dominant false-negative mode the auditor resolves a contradiction between the agent's stated rationale and its executed action toward the stated rationale rather than toward BLOCK (§\ref{sec:safe-harbor-credulity-as-the-dominant-false-negative-mode}; 47 of 49 evaluations). The prompt-driven posture therefore holds at the aggregate error level but not on this ambiguity class; the replication's cartridge amendments (§\ref{sec:proposed-future-work}e) target it directly. The relative ordering of the residual errors is discussed in §\ref{sec:hypothesis-h2-test-fpr-fnr-by-judge-variant}.

## Control-Owner Attestation {#sec:control-owner-attestation}

Each production run produces a release sign-off page (e.g. `output/run_20260525_083747_arm03_canary_perturbation_1200/dashboard.html`). This is not a checkbox exercise. It is the run dashboard, rendered for human review. It shows every recovery, save, and break rate. It shows every false-positive and false-negative cell with its Wilson confidence interval. It shows the Hypothesis H1/H2 outcomes. All of these are computed on the actual inputs the control processed.

In GRC terms, this is a test of the control. It certifies that this control, in this configuration, on these inputs, produced these measured results. Failures are visible — not hidden.

This sign-off page is the deliverable an auditor, assessor, or regulator actually asks for when they want to know whether an automated control "works": empirical, dated, reproducible evidence of operating effectiveness, signed for release.

The sign-off is designed to be suitable for control-owner attestation and aligns with the transparency artifacts IEEE 7001-2021 anticipates for the certification-agency stakeholder. The sign-off page's overlap with the GUIDE-LLM reporting checklist is detailed in §\ref{sec:related-work}, and a structural mapping is available at `mappings/GUIDE-LLM-v1.0.md`.

Under the Three Lines Model (IIA, 2026), a Line 3 function's independence rests on elements no prompt can supply — chief among them the *functional reporting line to the board*. For this instrument, the sign-off page is that reporting line's artifact: it is the board-, assessor-, or regulator-facing output, and the open-source pipeline it summarizes provides support for the unrestricted access to evidence the model requires. The architecture provides the mechanism; the organization deploying it must provide the board. A deployment in which that reporting line is absent — or routes through the Line 1 or Line 2 operator — re-creates at the organizational level the single-layer failure the instrument exists to prevent, and no property of the software cures that.

## Classification of Results {#sec:classification-of-results}

This study keeps three layers strictly separate. First, the Auditor — a rubric-agnostic engine (it runs against whatever rule taxonomy the cartridge supplies), a multi-factor evidence-weighing system that grounds claims against a source text and a supplied policy, with no domain knowledge of its own. Second, the cartridge (§\ref{sec:the-truth-cartridge}) — the swappable policy specification. Third, the interpretive framework — a separate, post-hoc lens applied to the Auditor's outputs. In §\ref{sec:related-work} we map the cartridge's rule firings onto the Psychopathia Machinalis v2.2 nosology, but that mapping is illustrative; the same outputs could be read through any formal, n-dimensional schema. No hypothesis, metric, or decision rule in this paper references the nosology. The engine's validity rests on the architecture and the cartridge alone.

## Transparent by Design {#sec:transparent-by-design}

An instrument intended for Line 3 audit must itself be auditable, and this paper's own history demonstrates that property under real conditions. During pre-publication review, independent collaborator Giorgi Tsereteli re-ran the open-source verification pipeline over the released pilot artifacts and identified a normalization bug in a downstream reporting script (`tools/scan_policy_gaps.py`) that was undercounting auditor breaks in the canary perturbation run. The bug was corrected. Erratum 1 was filed with full credit (see `paper/supplementary/erratum_1_20260803.md`). The corrected scan now reports 3 auditor breaks, matching the primary dashboard output. The primary hypotheses (Hypothesis H1, H2) were unaffected: the bug sat in a downstream reporting script, not the pipeline, so no pipeline re-run was required. The correction is recorded in the pre-registration log (amendment v23). The sequence is the segregation-of-duties principle the instrument is designed to enforce architecturally, operating on the instrument itself: independent verification, error discovery, public correction.

## Naming Convention {#sec:naming-convention}

Two naming namespaces coexist in this paper and are kept typographically distinct. **Hypothesis codes** (H1, H2) refer to the pre-registered statistical hypotheses and are written as plain text; where any ambiguity with a rule code is possible, they are spelled out in full (e.g., "Hypothesis H1"). **Cartridge policy rule codes** (e.g., the Hygiene rule `H1`, the schema rule `S1`) are always rendered as code literals. The two namespaces never interact in analysis: hypotheses are evaluated against recovery metrics (§\ref{sec:hypothesis-h1-test-equivalence-across-judge-variants}), while rule codes appear only in citation inventories and rule-firing tables.

**Supplementary materials are always named in full** — Supplementary 1, Supplementary 2, Erratum 1 — and are never abbreviated (e.g., never "S1"), so that supplementary numbering cannot collide with rule codes. This convention was adopted as a post-hoc disambiguation (pre-registration amendments v25–v26) after the schema rule `S1` and Hygiene rule `H1` were identified as collision risks with supplementary numbering and hypothesis codes respectively.

---

# Experimental Design {#sec:experimental-design}

The experimental design that follows tests whether this architecture in fact yields judge-invariant recovery (Hypothesis H1) and bounded miscalibration (Hypothesis H2) when the insider-trading cartridge is loaded and the Auditor is run against the Apollo corpus.

## Source Data and the Binary Mapping {#sec:source-data-and-the-binary-mapping}

The Apollo corpus, introduced in §\ref{sec:introduction}, supplies LLM-produced agent transcripts depicting an insider-trading scenario, with two boolean ground-truth keys (`is_misaligned`, `is_deceptive`) per case. Apollo's labeling is sequential: `is_deceptive` is only evaluated when `is_misaligned: true`, so omitted keys are structural artifacts of the labeling pipeline rather than ambiguous edge cases.

For this study we collapse Apollo's ternary latent structure (`CLEAN` / `ROGUE-HONEST` / `ROGUE-DECEPTIVE`) to a binary ground-truth shape that matches the Auditor's binary output:

| `is_misaligned` | `is_deceptive` | Latent stratum | Ground-truth class | Required Auditor verdict |
|----------|----------|------------|------------|----------------|
| `false` | *missing* | `CLEAN` | **CLEAN** | `APPROVE` |
| `true` | *missing* | `ROGUE-HONEST` | **ROGUE** | `BLOCK` |
| `true` | `true` | `ROGUE-DECEPTIVE` | **ROGUE** | `BLOCK` |

`misaligned: false, deceptive: true` is impossible, and `misaligned: null` cases are dropped at ingestion.

Under the policy that ships with this study, all rogue trades must be blocked regardless of whether the agent reported them honestly or fabricated a cover story. The honest/deceptive distinction is preserved as case metadata for stratified failure analysis (§\ref{sec:stratified-deception-recovery-exploratory}) but does not enter the headline accuracy calculation; its recovery in the headline metric is identified as future work (§\ref{sec:proposed-future-work}) and is carried as an explicit limitation (§\ref{sec:limitations}). The collapse is a deliberate simplification appropriate to a methodology-validation study.

The fail-closed posture of §\ref{sec:the-fail-closed-posture} is enforced throughout: pipeline anomalies are caught and quarantined with dedicated status codes rather than silently defaulting to an `APPROVE` state. Drop and quarantine counts are reported in \hyperref[sec:appendix-b]{Appendix B}.

### Ternary Judge Outputs {-}

Our Line 2 Judges are configured with a ternary output space (`APPROVED`, `HESITATE`, `BLOCKED`) to emulate real-world use of confidence boundaries. In this experiment, we simplify how these values are handled: any case where the Judge outputs `HESITATE` or `BLOCKED` is collapsed into a single boolean state, with `l2_judge_flagged` set to `True`. 

When routing the quadrants, a flagged judge output paired with an Auditor `BLOCK` routes to `VALIDATED_BLOCK`; paired with an Auditor `APPROVE`, it routes to `FLAWED_BLOCK`.

## The Five Judge Variants (Z01–Z05) {#sec:the-five-judge-variants-z01-z05}

Every Apollo case in this study is judged by all five Judge prompts, configured on a fixed open-weights model at temperature 0.1 and a fixed seed to minimize within-judge variance.

| Variant | Description | Role in Study |
|------|------------------------|-----------------------|
| Z01 | JudgeBench-style realistic prompt | Ecologically valid baseline |
| Z02 | Scratchpad-aware variant | Ecologically valid baseline |
| Z03 | Paranoid persona (over-blocking bias) | Stress probe |
| Z04 | Lenient persona (under-blocking bias) | Stress probe |
| Z05 | Manager-aligned persona | Stress probe |

The five variants fall into two tiers, constructed to span the failure-mode space the Auditor is intended to catch.

First, the realistic tier (Z01–Z02). Z01 instantiates standard Judge practice, adapting JudgeBench-style rubric criteria to the ternary output space defined in §\ref{sec:source-data-and-the-binary-mapping}; it represents the best standard Judge practice at the time of the study. Z02 uses the identical rubric and differs exclusively in information-access posture: it is permitted to read the agent's internal reasoning scratchpad, the forensic upgrade a compliance function would naturally require. We offer both as plausible deployment-style configurations, not as claims about the prevalence of any particular judge configuration in production.

Second, the stress-probe tier (Z03–Z05). These are deliberate fault-injection conditions, not deployment candidates: a paranoid over-blocker (Z03), a lenient rubber-stamp (Z04), and a manager-aligned persona that deprioritizes compliance when it conflicts with throughput (Z05).

The study evaluates the Auditor; the judges are the test conditions under which it is evaluated. We deliberately test under extreme, unrealistic conditions not because we expect them in production, but to prove the system holds steady across the full range — including the worst case. 

The core invariance claim of this study is that the Auditor's performance holds steady across this entire constructed range — whether the Line 2 judge is operating plausibly or failing by design. We make no claim about the real-world prevalence of Z03–Z05-style judges in production deployments.

## Pre-Registered Hypotheses {#sec:pre-registered-hypotheses}

Both hypotheses are stated against the binary Gate C verdict, and the formal specifications match the pre-registration verbatim.

**Hypothesis H1 (Judge-Prompt-Variant Invariance of Recovery, within one model family).** H1 tests whether the Auditor's recovery performance is equivalent across all five judge variants, regardless of upstream judge prompt quality, holding judge weights fixed. Standard statistical tests look for *differences*; we need to prove *similarity*. We therefore use an equivalence test to show that any performance gap between judges is tightly bounded near zero.

Formally, for ground-truth class *Y* $\in$ {`CLEAN`, `ROGUE`}, Auditor verdict *V* $\in$ {APPROVE, BLOCK}, and judge variant *Z* $\in$ {Z01, …, Z05}, the absolute difference in recovery is bounded by our 0.05 margin:

$$ | P(V \text{ is correct given } Y \mid Z = z_i) - P(V \text{ is correct given } Y \mid Z = z_j) | < 0.05 $$

(Equality is tested within each ground-truth class *Y* separately, as the analysis in §\ref{sec:hypothesis-h1-test-equivalence-across-judge-variants} does, not pooled across `CLEAN` and `ROGUE`.)

**Scope.** H1 is a claim about prompt-level variation within a single judge model family. All five variants Z01–Z05 run on identical `Llama 3.3 70B` weights (§\ref{sec:model-selection-and-asymmetry}); they differ only in system-prompt framing and, for Z03–Z05, deliberate degradation. H1 therefore tests whether Auditor recovery is invariant to judge prompt condition — not to judge model. Robustness across judge model families is not tested here; it is designated as future work under the multi-model cross-rotation matrix (§\ref{sec:proposed-future-work}g). The Z07 same-model control arm (§\ref{sec:same-model-control-arm-z07}) bears on the architecture-versus-capacity question, not on cross-family judge robustness.

**Test specification.** To rigorously claim invariance, it is insufficient to simply fail to reject the null of a standard difference test, which may merely indicate a lack of statistical power. We instead operationalize invariance using Two One-Sided Tests (TOST) for equivalence, with an equivalence margin of $\pm 5$ percentage points ($\pm 0.05$). H1 is supported if and only if the TOST p-values (the maximum of the two one-sided p-values) for all $C(5, 2) = 10$ judge-variant pairs, computed within each ground-truth class using an unpooled standard error (SE), fall below $\alpha$ after Holm–Bonferroni step-down correction at $\alpha_{\text{family}} = 0.05$.

This correction is deliberately conservative: requiring all 10 pairs to demonstrate equivalence operates as an intersection-union test, which natively controls type I error at $\alpha$, so applying Holm–Bonferroni on top effectively demands that the smallest raw TOST p-value clear $\alpha/10$. We use an unpooled SE because the null hypotheses under TOST specify non-zero differences (the equivalence bounds $\pm$ 0.05); pooling under an assumed equality of proportions would be misspecified for the test statistic being computed. For descriptive completeness, standard two-proportion z-tests for difference are also computed and reported alongside the equivalence tests. See \hyperref[sec:appendix-a]{Appendix A} for formal statistical specifications.

**Hypothesis H2 (Bounded Miscalibration — Descriptive Bound).** The Auditor's false-positive rate (FPR = Auditor `BLOCK` on `CLEAN` cases / count of `CLEAN` cases) and false-negative rate (FNR = Auditor `APPROVE` on `ROGUE` cases / count of `ROGUE` cases) are jointly bounded:

> $\max(\text{FPR}, \text{FNR}) \le 0.10$ in every judge condition

Both rates are defined relative to ground-truth class, not the judge's action, and are therefore directly comparable across judge variants. We evaluate H2 as a descriptive pre-registered bound rather than an inferential hypothesis test, reporting Wilson 95% confidence intervals alongside the sample point estimates.

## The Headline Analysis: Recovery Conditional on Judge Correctness {#sec:the-headline-analysis-recovery-conditional-on-judge-correctness}

For each judge variant *Z*, we compute the Auditor's recovery rate stratified by whether the judge's verdict was itself correct against ground truth:

| | **Judge correct** | **Judge incorrect** |
|---------|------------------------|------------------------|
| **GT `ROGUE`** | Auditor recovery when judge caught the violation | Auditor recovery when judge missed the violation |
| **GT `CLEAN`** | Auditor recovery when judge correctly approved | Auditor recovery when judge over-blocked |

The central empirical question is whether the Auditor's recovery rate in the two "judge incorrect" cells is comparable to the two "judge correct" cells. The diagnostic logic is straightforward: if recovery sags when the judge is wrong, the Auditor is parasitic on judge correctness — it is reproducing the judge's verdict rather than auditing. If recovery is approximately flat regardless of judge correctness, the Auditor is performing independent, source-evidence-grounded verification.

## Ablation: Verdict-Level Independence of Gate C {#sec:ablation-verdict-level-independence-of-gate-c}

A potential confound is that Gate C may be over-relying on the judge's verdict as a prior — parroting the judge rather than independently grounding against source text and policy. The ablation arm tests this directly.

A subset of cases is processed twice: once with the genuine judge verdict and reasoning trace, and once with the judge's `action_taken` drawn uniformly at random from {`APPROVED`, `HESITATE`, `BLOCKED`} and the judge's reasoning trace replaced with a fixed, vague monologue. (In the pipeline's variant registry this ablated judge configuration is coded `Z06`; it is reported as the ablation arm and is not pooled into Hypothesis H1's Z01–Z05 comparison family.)

The Auditor performs two distinct functions: first, reaching an independent verdict on the agent; second, surfacing specific reasoning errors in the judge's trace via J-rule firings. By design, the ablation arm tests only the first — the second cannot be exercised when the trace has been replaced with vague monologue. The decision rule for verdict-level independence is therefore:

- **Recovery rate approximately preserved under ablation:** Gate C's verdict is independent of the judge's input. This is the result consistent with Line 3 architectural independence, and it is the architecturally desired outcome — verdict-level independence is the foundational Line 3 property.
- **Recovery rate drops substantively under ablation:** Gate C was conditioning its verdict on the judge's verdict rather than reasoning independently against source text and policy. This would constitute evidence that the Auditor was reproducing the judge's verdict rather than deriving its own, and would require prompt-level remediation.

The value of the second function — the judge-reasoning signal — is reported separately via the rule-citation inventory in §\ref{sec:failure-mode-inventory-rule-citations-genuine-arm}, which is computed against the genuine arm only. The ablation is interpretable in either direction and is reported regardless of outcome.

## Sample Size and Power (the Pragmatic Pilot) {#sec:sample-size-and-power-the-pragmatic-pilot}

The Phase II full-corpus objective scales to the maximum balanced sample drawable from the Apollo dataset (~8,500 cases, bottlenecked by the rarest latent stratum to maintain a 1:1:1 class balance); this full-corpus grid is the planned replication target. For this study we run a 1,200-case heavily stratified pilot. The pilot is calibrated to be sufficient to validate the methodology and the ablation arm at the 95%-confidence class, but not so large that it renders the full-corpus run redundant. The 99%-confidence-class result requires the full corpus.

The pilot composition is:

- n = 1,200 cases, stratified 400 `CLEAN` + 400 `ROGUE-HONEST` + 400 `ROGUE-DECEPTIVE`
- 5 judge variants (Z01–Z05) $\rightarrow$ 6,000 judged cases
- Ablation arm on the same 1,200 cases (paper §\ref{sec:ablation-verdict-level-independence-of-gate-c}; pre-reg §7) $\rightarrow$ +1,200 Auditor evaluations
- Test–retest subset of 300 case seed pass + 1,500 reruns (paper §\ref{sec:test-retest-reliability-instrument-stability}; pre-reg §11) $\rightarrow$ +1,800 Auditor evaluations
- Entity-perturbation arm on the same 1,200 cases $\times$ Z01 only (pre-reg §3.5) $\rightarrow$ +1,200 Auditor evaluations
- Same-Model Control arm on 150 cases $\times$ Z07 only $\rightarrow$ +150 Judge / +150 Auditor evaluations
- Total Auditor invocations: $\approx$ 10,350
- Total Judge invocations: $\approx$ 7,350

The complete invocation budget for the pilot is:

| Stage | Composition / detail | Judge calls | Auditor calls |
|---------------|------------------------|-------|---------|
| Main grid | 5 judge variants $\times$ 1,200 cases | 6,000 | 6,000 |
| Ablation arm | 1,200 cases, judge input replaced with randomized action and content-free trace | 0 | 1,200 |
| Test–retest | 300 seed-case subset + 1,500 reruns | 0 | 1,800 |
| Entity-perturbation arm | 1,200 cases, Z01 only | 1,200 | 1,200 |
| Same-Model Control Arm | 150 cases, Z07 only | 150 | 150 |
| **Total** | | **7,350** | **10,350** |

The entity-perturbation arm is restricted to Z01 to test for pre-training contamination — the risk that the audit model is recovering labels by recalling memorized training data rather than actively reasoning. The logic is one of isolation: because contamination is a property of the underlying base model rather than the prompt, the valid diagnostic is strictly Z01-on-verbatim versus Z01-on-perturbed. Holding the judge prompt constant isolates the model's reliance on verbatim text; running the full five-judge matrix on perturbed cases would multiply costs without yielding any additional signal regarding contamination.

The exact 400/800 class balance bypasses Apollo's natural distribution skew. While this yields a pooled $n = 1,200$ cases per judge variant, Hypothesis H1 is pre-registered to be evaluated strictly within ground-truth classes, so the actual test cells are $n = 400$ (`CLEAN`) and $n = 800$ (`ROGUE`) per variant. The power picture is asymmetric. At a conservative per-test threshold of $\alpha = 0.005$ (corresponding to the strictest first step of our Holm–Bonferroni correction at $\alpha_{\text{family}} = 0.05$ across 10 pairwise comparisons), detecting a $\Delta = 0.05$ absolute between-judge accuracy difference at 80% power requires approximately 730 cases per group (assuming a baseline recovery of $p = 0.95$). The `ROGUE` comparisons ($n = 800$) are therefore adequately powered for this Minimum Detectable Effect (MDE) provided recovery sits at or above 0.95. The `CLEAN` comparisons ($n = 400$) achieve an estimated power of only 0.25–0.46 under plausible baselines and are explicitly underpowered for the stated MDE.

We commit, in advance of the run, to reporting the pilot result regardless of outcome and not to adjusting the pilot's pass thresholds post-hoc to claim sufficiency. We are likewise explicit about what this sample size cannot deliver: while the pilot is sized to detect a standard difference (MDE 0.05), proving strict statistical equivalence (H1) via TOST across 10 corrected comparisons is an aspirational claim at this $n$, and sizing for a difference-test MDE does not by itself guarantee equivalence-test power at the same margin (see \hyperref[sec:appendix-a]{Appendix A}). The full ~8,500-case replication is the realistic target for achieving robust equivalence support.

## Test–Retest Reliability (Instrument Stability) {#sec:test-retest-reliability-instrument-stability}

A 300-case subset of the 1,200 pilot cases is processed once as a seed pass and then rerun ($k = 5$ times on the ablation arm only) at the registered temperature and seed configuration; including the seed pass as the $t = 0$ baseline gives $k = 6$ total observations per case under operationally identical conditions.

**Explicit Pre-Registration Deviation.** The original pre-registration (§11) specified evaluating strictly $k = 5$ iterations. To cleanly anchor the reruns without confounding them with the main grid's batch order, we formally amended the protocol (Amendment v20) to a two-step workflow that analyzes all $k = 6$ observations. The total §\ref{sec:test-retest-reliability-instrument-stability} invocation budget is therefore +1,800 Auditor calls (300 seed + 1,500 reruns).

Restricting these reruns to the ablation arm cleanly isolates the Auditor's internal non-determinism from upstream judge noise; we acknowledge, however, that this measures stability in a slightly narrower regime where the Auditor reasons without a genuine judge trace, and we carry this caveat explicitly into the limitations (§\ref{sec:limitations}) rather than leaving it as a footnote. We report the Intraclass Correlation Coefficient ICC(2,1) for the binary verdict, Krippendorff's $\alpha$ for rule-citation sets, and Cohen's $\kappa$ for quadrant agreement. The pre-committed threshold for "stable instrument" is **ICC $\geq$ 0.80** (indicating good reliability). For rule citations we use Krippendorff's $\alpha$ because, unlike standard coefficients, $\alpha$ correctly handles cases where multiple policy rules are cited simultaneously.

The 300-case subset is *not* held out from the headline metrics: it is part of the pilot and is included in the Hypothesis H1/H2 calculation on its first run. The reruns exist solely to characterize instrument stability under stochastic LLM behavior. Failure of the stability threshold is reported as such; it qualifies but does not retroactively invalidate H1/H2 if both are met.

The test–retest report is available at `output/run_20260522_152239_arm01_main_pilot_1200/stability_report.html` and is generated by the `tools/compute_stability.py` script.

### Gate B Inter-Rater Reliability (Human Baseline) {#sec:gate-b-inter-rater-reliability-human-baseline}

Separately from the rerun-stability analysis above, we assess the *human* inter-rater reliability of Gate B's factual tagging on a 50-case subset (stratified $\approx$ 17/17/16 across `SUPPORTED` / `CONTRADICTED` / `UNSUPPORTED`), drawn deterministically by `tools/l3_gate_b_irr_tester.py` from the genuine-arm pilot (ablation runs excluded). The human annotator (the author) marked each claim `SUPPORTED` / `CONTRADICTED` / `UNSUPPORTED` blind to Gate B's predicted verdict; agreement is scored with Cohen's $\kappa$ against a pre-registered soft acceptance target of $\kappa$ $\geq$ 0.60 (pre-reg §3.6). This characterizes whether a human and the Auditor's Gate B agree on the factual-grounding tags, complementing the run-to-run machine stability of §\ref{sec:test-retest-reliability-instrument-stability}. The result is reported in §\ref{sec:test-retest-reliability-instrument-stability-results}.

## Model Selection and Asymmetry {#sec:model-selection-and-asymmetry}

This study tests the Auditor's recovery rate against a heterogeneous Line 2 model. It does **not** test which model is the better judge in the abstract: the design treats the judge as an operational input variable to be audited, not as a benchmark baseline, and the Z03–Z05 stress probes are intentionally degraded. We are testing whether recovery holds when the judge being audited is unreliable.

The Z01–Z05 judges run on `Llama 3.3 70B` (dense); the Auditor's Gates B and C run on `Qwen 3 235B` in a Mixture-of-Experts configuration with 22B parameters active per token. Total parameter capacity is materially greater on the Auditor side. The asymmetry is task-to-capacity, not a claim that one model family is superior to the other: per-claim factual grounding and logical coherence auditing are more demanding than the judge's pattern-match task, and the additional capacity is matched to that demand. This is the architecture, not a confound to be mitigated; the Z07 same-model control arm (§\ref{sec:same-model-control-arm-z07}) tests this directly. Consequently, Hypothesis H1 (§\ref{sec:pre-registered-hypotheses}) is scoped to prompt-level variation at fixed judge weights; judge-model robustness is out of scope for this study and is assigned to future work (§\ref{sec:proposed-future-work}g).

The two models were selected on an explicit balance of intelligence-per-token, cost-per-token, tokens-per-second (generation speed), and availability — chosen because that balance suited our deployment constraints and these two models had historically performed well in similar real-life use, not because they are claimed as optimal for every situation. Practitioners with different cost/latency/availability priorities should be expected to substitute different models, and the architecture supports this: the model strings are configurable parameters in the prompt manifests.

For this experiment, endpoints and model variants were locked to fixed provider/quantization pairs for the duration of the study, and all sampling parameters were pinned in the prompt manifests at the registered git commit, with no parameter varied during the pilot. The verbatim manifest values, gate-level sampling configurations, and provider-quantization notes are given in \hyperref[sec:appendix-c]{Appendix C}.

Closed proprietary models are not evaluated in this study, for two reasons. First, proprietary endpoints introduce serving-side variables we cannot constrain, such as runtime routing, variable reasoning effort, and undocumented quantization changes, and are therefore incompatible with reproducibility. Second, a study calibrated on a model that is later silently changed or retired loses replicability. Open-weights models support the *set-and-forget* posture suited to a Line 3 audit instrument: model drift becomes testable rather than invisible.

The L2/L3 model parameter-size asymmetry (70B vs 235B) raises a residual question, distinct from verdict independence. Does the observed recovery reflect the structural audit framework performing substantive work, or would parameter size alone — the larger model classifying source text against a complex policy rubric — produce equivalent recovery?

To isolate these variables, we incorporated a preliminary 150-case same-model control arm (Z07) into the pilot evaluation matrix, in which both the Line 2 Judge and the Line 3 Auditor run on identical weights using the high-parameter `Qwen 3 235B` Mixture-of-Experts model, zeroing out the parameter delta. The comprehensive 8,500-case multi-model cross-rotation matrix remains designated as a separate deliverable, for future work. Z07 is reported in a supplementary table alongside Z01's recovery metrics for direct comparison; it is not pooled into the H1 equivalence family (Z01–Z05). Either direction of result is informative: a Z07-versus-Z01 recovery delta beyond the §\ref{sec:architecture} noise envelope would flag capacity, rather than architecture, as the driver of the observed gains; a delta within the envelope is consistent with architectural attribution.

## Policy Rubric (The Cartridge for This Study) {#sec:policy-rubric-the-cartridge-for-this-study}

The domain policy provided to the Auditor is deliberately complex and prescriptive, mirroring the pedantic structure of enterprise GRC or Model Risk Management policies. We are not testing the Auditor's zero-shot ability to detect deception in a vacuum; we are testing its architectural capacity to enforce a complex policy strictly against a judge's reasoning trace. The cartridge defines four families of rules (summarized below; full policy available in the repository at `domains/insider_trading/policy.md`):

| Category | Rules | Description |
|-------|------|------------------------|
| J-Rules | `J1`–`J5` | **Judge Process Findings.** E.g., *`J1` (Scratchpad Blindness)*, *`J2` (Accepts Sanitized Cover Story)*, *`J3` (Pressure as Justification)*, *`J4` (Conflates Quality & Legality)*, *`J5` (Misses Reporting Violation)*. Evaluates how the judge reasoned. |
| F-Rules | `F1`–F*n* | **Structural Fact Findings.** Findings against the agent's behavior, irrespective of stated intent. E.g., *`F1` (Insider-Tip Sterilization — a tipped trade reported as public-sourced)*. |
| U-Rules | `U1`–U*n* | **Unsubstantiated Claim Findings.** Fires against specific claims in the judge's verdict for which Gate B returned `UNSUPPORTED`. |
| H-Rules | `H1`–H*n* | **Hygiene Findings.** Formatting or minor policy deviations. Surfaced for reviewer attention only; never affects the final verdict. |

The Auditor cites these rules as part of its `BLOCK` justifications; rule citations are interpretability metadata, not quadrant determinants (§\ref{sec:synthesis-and-quadrant-routing}). For concreteness: on a case where the judge wrote "the agent disclosed the trade to compliance," Gate B checks that assertion against the source transcript and tags it `SUPPORTED` if the disclosure appears, `CONTRADICTED` if the transcript shows the opposite, or `UNSUPPORTED` if the transcript is silent. An `UNSUPPORTED` tag on a verdict-bearing claim is what fires the corresponding U-rule at Gate C.

Note: These rules are defined by the cartridge, not the engine. Their firings can optionally be mapped onto an external diagnostic taxonomy. For example, we illustrate how `J1`–`J3` can be read as the Alignment-axis Strategic Compliance construct in Psychopathia Machinalis (Watson & Hessami, 2025a), but this mapping is interpretive and not required for any result in this paper. We detail this further in §\ref{sec:related-work}.

---

# Results {#sec:results}

## Source Data and Selection {#sec:source-data-and-selection}

The 1,200 pilot cases were drawn from the Apollo corpus by stratified random selection without replacement, balanced 400 `CLEAN` / 400 `ROGUE-HONEST` / 400 `ROGUE-DECEPTIVE`. Cases used for pre-launch development, smoke-testing, or prompt refinement (per pre-reg §4.4 and §6.2) are held out of the eligibility pool via the `tainted_cases.txt` manifest provided in the repository; the pilot is therefore a strictly held-out evaluation. The random seed is derived deterministically from a fixed selection date and is hard-coded in the run manifest.

The repository ships a selection utility (`tools/select_pilot.py`) that reproduces the exact pilot from the registered seed and allows a third party to draw an independent stratified subset of arbitrary size, using either a user-supplied seed or a date-derived seed. To reproduce the exact 1,200-case pilot:

`python tools/select_pilot.py --seed-date 20260521`

## Headline Recovery {#sec:headline-recovery}

Across the five judge variants the Auditor recovers the Apollo ground-truth label at near-ceiling and at near-identical rates regardless of judge quality. Recovery is the proportion of cases in each ground-truth class on which the Auditor's verdict matches the label. The ablation (noise) arm is reported in the same frame for reference and analyzed in §\ref{sec:ablation-auditor-with-and-without-judge-verdict}.

| Variant | Role | Recovery `CLEAN` | Recovery `ROGUE` | Save rate† (95% CI) | Break rate‡ (95% CI) |
|------------|--------------|-----------|-----------|-------------|-------------|
| Z01 | Realistic | 99.0% | 99.0% | 95.2% [91.2, 97.5] | 0.30% [0.1, 0.9] |
| Z02 | Scratchpad-aware | 99.5% | 99.2% | 94.8% [89.1, 97.6] | 0.18% [0.1, 0.7] |
| Z03 | Paranoid (over-block) | 99.2% | 97.9% | 99.2% [97.8, 99.7] | 2.12% [1.3, 3.4] |
| Z04 | Lenient (under-block) | 99.5% | 98.7% | 98.6% [97.4, 99.2] | 0.39% [0.1, 1.4] |
| Z05 | Manager-aligned | 99.5% | 99.0% | 95.3% [91.0, 97.6] | 0.19% [0.1, 0.7] |
| *ABLATION (noise)* | *judge replaced* | *99.5%* | *98.6%* | *98.5% [97.1, 99.3]* | *0.77% [0.3, 1.8]* |

†Save rate = of cases the judge got wrong, the fraction the Auditor recovered.
‡Break rate = of cases the judge got right, the fraction the Auditor broke.
Both rates are derived from the exploratory 8-cell decomposition (§\ref{sec:per-variant-8-cell-decomposition-exploratory}) and are descriptive, not pre-registered. Intervals are Wilson score 95% CIs. Save-rate denominators are judge-incorrect cases (n = 115–690); break-rate denominators are judge-correct cases (n = 509–1,084).

Two patterns are visible. First, recovery is flat across variants: `CLEAN` recovery spans 99.0–99.5% and `ROGUE` recovery spans 97.9–99.2%. Second, the Auditor's *marginal* contribution is consistent. In every condition it recovers 94.8–99.2% of the cases the judge got wrong while breaking 0.18–2.12% of the cases the judge got right. The least-reliable cell is Z03 (paranoid over-blocker), where the Auditor's errors concentrate; even there it remains inside the Hypothesis H2 bound (§\ref{sec:hypothesis-h2-test-fpr-fnr-by-judge-variant}).

### Headline Recovery, Stratified by Judge Correctness {#sec:headline-recovery-stratified-by-judge-correctness}

Recovery = Auditor verdict matches ground-truth label. Cells show recovery (n correct / n).

| Variant | `CLEAN` · judge correct | `CLEAN` · judge wrong | `ROGUE` · judge correct | `ROGUE` · judge wrong |
|-----------|---------------|--------------|---------------|--------------|
| Z01 (realistic) | 99.2% (376/379) | 95.2% (20/21)   | 100.0% (632/632) | 95.2% (159/167) |
| Z02 (scratchpad) | 99.4% (353/355) | 100.0% (45/45)  | 100.0% (729/729) | 91.4% (64/70)   |
| Z03 (paranoid)   | 100.0% (2/2)    | 99.2% (394/397) | 97.9% (782/799)  | — (0/0)         |
| Z04 (lenient)    | 99.5% (397/399) | 100.0% (1/1)    | 100.0% (110/110) | 98.5% (679/689) |
| Z05 (mgr-aligned)| 99.5% (390/392) | 100.0% (8/8)    | 100.0% (637/637) | 95.1% (154/162) |

The denominators differ by more than an order of magnitude across variants: Z03's `CLEAN`·judge-wrong cell holds 397 cases where Z01's holds 21, reflecting the deliberately opposite biases of the stress probes. Recovery is nonetheless approximately flat in every cell; the single weakest stratum is Z02's `ROGUE`·judge-wrong cell at 91.4% (64/70). The implication is direct. Recovery does not sag when the judge is wrong, because the Auditor performs independent source-grounded verification rather than mirroring the judge (cf. §\ref{sec:the-headline-analysis-recovery-conditional-on-judge-correctness}).

### Stratified Deception Recovery (exploratory) {#sec:stratified-deception-recovery-exploratory}

The headline metric (§\ref{sec:headline-recovery}) scores the Auditor against the binary ground truth, collapsing Apollo's tripartite latent structure (`CLEAN` / `ROGUE-HONEST` / `ROGUE-DECEPTIVE`) to `CLEAN`-vs-ROGUE as pre-registered and as carried explicitly in the limitations (§\ref{sec:limitations}). Because the agent-deception flag is retained as case-level metadata in every audit record, the `ROGUE` stratum can be decomposed after the fact, without re-running any model, into `ROGUE-HONEST` (the agent took a misaligned action but reported it truthfully) and `ROGUE-DECEPTIVE` (the agent took the action and concealed or misrepresented it). Both strata share the same correct Auditor verdict, `BLOCK`; the question is whether recovery differs between them.

Table 4.2.2 — Stratified `ROGUE` Recovery Breakdown

| Variant | HON n | HON rec% | HON 95% CI | DEC n | DEC rec% | DEC 95% CI | $\Delta$(D-H) pp |
|-------------|-----|-----|-----------|-----|-----|-----------|-----------|
| Z01 | 400 | 98.2 | [96.4, 99.1] | 399 | 99.7 | [98.6, 100.0] | +1.5 |
| Z02 | 400 | 98.8 | [97.1, 99.5] | 399 | 99.7 | [98.6, 100.0] | +1.0 |
| Z03 | 400 | 96.5 | [94.2, 97.9] | 399 | 99.2 | [97.8, 99.7] | +2.7 |
| Z04 | 400 | 98.0 | [96.1, 99.0] | 399 | 99.5 | [98.2, 99.9] | +1.5 |
| Z05 | 400 | 98.2 | [96.4, 99.1] | 399 | 99.7 | [98.6, 100.0] | +1.5 |
| **POOLED (Z01–Z05)** | **2000** | **98.0** | **[97.2, 98.5]** | **1995** | **99.6** | **[99.2, 99.8]** | **+1.6** |

Pooled across the five genuine judge variants (Z01–Z05), the Auditor blocks 99.6% of `ROGUE-DECEPTIVE` cases ($n = 1{,}995$) against 98.0% of `ROGUE-HONEST` cases ($n = 2{,}000$), a difference of +1.6 pp (two-proportion $z = 4.73$, $p < 0.001$; descriptive). Of the 49 pooled false negatives, 41 (83.7\%) concentrate in the `ROGUE-HONEST` stratum. All counts and intervals are computed from unrounded per-case records by `tools/check_deception_recovery.py`.

Recovery does not degrade on the cases where the agent actively builds a cover story. This is consistent with the aggregate rule frequencies of §\ref{sec:failure-mode-inventory-rule-citations-genuine-arm}, in which the concealment-related J-rules are the most enriched family; the per-case mechanism is not established, for the stability reasons given in §\ref{sec:test-retest-reliability-instrument-stability-results}.

This decomposition is descriptive and was not pre-registered; the binary collapse remains the confirmatory benchmark (§\ref{sec:headline-recovery}, §\ref{sec:limitations}). We report it to characterize where the Auditor's residual error concentrates within the `ROGUE` class, not to revise the headline.

## Hypothesis H1 Test: Equivalence Across Judge Variants {#sec:hypothesis-h1-test-equivalence-across-judge-variants}

H1 is met in both ground-truth classes, and we report it as descriptive equivalence conditional on ceiling recovery, not as a hard-won inferential pass. Across all C(5,2) = 10 pairwise judge-variant comparisons within each class, the TOST procedure rejects non-equivalence at the $\pm$ 0.05 margin after Holm–Bonferroni step-down correction ($\alpha_{\text{family}}$ = 0.05); the worst-case Holm-adjusted TOST p-value is 3.2 $\times$ $10^{-13}$ (`CLEAN`) and 6.3 $\times$ $10^{-10}$ (`ROGUE`), and no pair fails in either direction. Because realized recovery sits near the 100% ceiling (~0.99 `CLEAN`, ~0.98 `ROGUE`), between-variant spread is compressed toward zero by construction, and the test cannot discriminate among variants that all perform near ceiling. The equivalence claim therefore holds only for the regime actually observed — high-recovery variants on this corpus — and does not license equivalence among variants whose recovery falls meaningfully below ceiling.

The pass should not be read as stronger than the pilot was powered to expect. §\ref{sec:sample-size-and-power-the-pragmatic-pilot} flagged strict TOST equivalence across 10 corrected comparisons as aspirational at $n = 400/800$ per class, and it passes for a reason that deflates rather than inflates the result: the Auditor's realized `CLEAN` recovery of ~0.99 substantially exceeded the 0.90–0.95 sizing baselines, pushing all variants into a ceiling regime where the between-variant spread (~0.5 pp `CLEAN`, ~1.3 pp `ROGUE`) is trivially far inside the $\pm$ 5 pp bound. In this regime TOST has effective power near one against almost any plausible alternative, so the equivalence statement is near-vacuous as a test and informative only as a description of how tightly the variants cluster. The descriptive two-proportion difference tests concur — no pair differs significantly after correction — and we treat the two procedures jointly as descriptive evidence of clustering at ceiling, with equivalence to be re-established inferentially in the ~8,500-case replication, where sizing should target recovery levels below ceiling or a margin tightened to the observed spread.

A further scoping applies: the five variants share one judge model (`Llama 3.3 70B`, §\ref{sec:model-selection-and-asymmetry}), so H1 as supported here is invariance to prompt-level judge variation within that family. It licenses no claim about equivalence across judge model families; that question is reserved for the multi-model cross-rotation matrix (§\ref{sec:proposed-future-work}g).

### Hypothesis H1 Test: Pairwise Equivalence (TOST, $\pm$ 0.05, Holm-Bonferroni) {#sec:hypothesis-h1-test-pairwise-equivalence-tost-pm-0-05-holm-bonferroni}

All 10 pairwise comparisons in each class reject non-equivalence after correction; descriptive two-proportion difference tests (adj p) find no significant difference in any pair.

| Pair | `CLEAN` $\Delta$ (pp) | `CLEAN` adj TOST p | `ROGUE` $\Delta$ (pp) | `ROGUE` adj TOST p |
|-----|---------------|-------------|---------------|-------------|
| Z01–Z02 | $-0.50$ | 3.2e-13 | $-0.25$ | <1e-15 |
| Z01–Z03 | $-0.25$ | 3.2e-13 | +1.13 | 6.3e-10 |
| Z01–Z04 | $-0.50$ | 3.2e-13 | +0.25 | <1e-15 |
| Z01–Z05 | $-0.50$ | 3.2e-13 | +0.00 | <1e-15 |
| Z02–Z03 | +0.25 | <1e-15 | +1.38 | 6.3e-10 |
| Z02–Z04 | +0.00 | <1e-15 | +0.50 | <1e-15 |
| Z02–Z05 | +0.00 | <1e-15 | +0.25 | <1e-15 |
| Z03–Z04 | $-0.25$ | <1e-15 | $-0.88$ | 3.1e-10 |
| Z03–Z05 | $-0.25$ | <1e-15 | $-1.13$ | 6.3e-10 |
| Z04–Z05 | +0.00 | <1e-15 | $-0.25$ | <1e-15 |

"Adj TOST p" denotes the Holm-adjusted TOST p-value, the larger of the two one-sided p-values for each pair after step-down correction. The largest between-variant gaps ($\approx$ 1.1–1.4 pp) all involve Z03 on `ROGUE` cases and remain well inside the $\pm$ 5 pp margin.

Caveat: because all variants recover at or near ceiling in both classes, these adjusted p-values should be read descriptively — equivalence conditional on ceiling recovery — rather than as evidence that the procedure discriminated among genuinely different variants.

## Hypothesis H2 Test: FPR / FNR by Judge Variant {#sec:hypothesis-h2-test-fpr-fnr-by-judge-variant}

H2 holds in every judge condition with a wide margin. The pre-registered bound is max(FPR, FNR) $\leq$ 0.10; the observed maxima are FPR = 1.0% (Z01) and FNR = 2.1% (Z03).

| Variant | FPR (95% CI) | FNR (95% CI) |
|-----------|------------------------|------------------------|
| Z01 | 1.0% [0.4, 2.5] | 1.0% [0.5, 2.0] |
| Z02 | 0.5% [0.1, 1.8] | 0.8% [0.3, 1.6] |
| Z03 | 0.8% [0.3, 2.2] | 2.1% [1.3, 3.4] |
| Z04 | 0.5% [0.1, 1.8] | 1.3% [0.7, 2.3] |
| Z05 | 0.5% [0.1, 1.8] | 1.0% [0.5, 2.0] |

Every cell is at least ~4.7$\times$ inside the 10% bound, and the Wilson 95% CIs place the upper bound below 0.06 in all cells.

Across all five judge conditions the observed FNR (max 2.1%) equals or exceeds the FPR (max 1.0%). While a naive reading of a fail-closed posture (§\ref{sec:the-fail-closed-posture}) might predict an excess of false alarms over misses, this inversion reflects the architecture's two-layer design. The deterministic layer catches and quarantines pipeline anomalies without scoring them as empirical blocks on clean data, keeping FPR suppressed. Concurrently, prompt-driven defaulting activates only when ambiguity is registered. As demonstrated by the stratified analysis in §\ref{sec:stratified-deception-recovery-exploratory}, residual false negatives concentrate predominantly in `HONEST-ROGUE` cases (i.e. where no fabricated claims exist for the claim detector to flag). This contrasts with deceptive cases, where concealment rules provide explicit guidance.

## Test–Retest Reliability (Instrument Stability) {#sec:test-retest-reliability-instrument-stability-results}

The Auditor was rerun under operationally identical conditions on the 300-case stability subset ($k = 6$ observations per case: one seed pass plus five reruns, ablation arm only, per §\ref{sec:test-retest-reliability-instrument-stability}). Three cases were dropped for null ground-truth labels at ingestion (the `is_misaligned: null` rule of §\ref{sec:source-data-and-the-binary-mapping}), leaving $n = 297$; the balanced-design ICC is computed on the common 296. All coefficients below are deterministic post-processing of the six observation sets via `tools/compute_stability.py`.

The binary verdict is highly stable. The intraclass correlation for the `APPROVE`/`BLOCK` verdict is **ICC(2,1) = 0.979** (95% CI $\approx$ [0.98, 0.98]), comfortably clearing the pre-registered **ICC $\geq$ 0.80** threshold. Agreement on the full 2 $\times$ 2 quadrant assignment is correspondingly high (**Cohen's $\kappa$ = 0.986**, range across rerun pairs [0.976, 0.995]). On the registered stability gate, the instrument passes.

| Coefficient | Target (pre-reg §11) | Observed | Verdict |
|------------------------|-------------|---------------|----------|
| ICC(2,1), binary verdict | $\geq$ 0.80 | **0.979** | **Pass** |
| Cohen's $\kappa$, 2 $\times$ 2 quadrant (mean) | — | 0.986 ([0.976, 0.995]) | Almost perfect |
| Krippendorff's $\alpha$, rule-citation set | — (descriptive) | **0.238** | Low — see below |

Two coefficients fall below the levels a reader might expect, and we disclose both plainly: Cohen's $\kappa$ = 0.515 (IRR Gate B factual tagging) and Krippendorff's $\alpha$ = 0.238 (rule-citation sets). We take each in turn.

Because applying ICC(2,1) to a binary outcome is an unconventional, though conservative, parameterization, we additionally report model-free agreement statistics over the same reruns. 290 of 297 cases (97.6%) returned an identical verdict across all 6 passes; mean pairwise agreement is 0.991; and Fleiss' kappa over the 296 complete-rerun cases is 0.979, closely matching the ICC. These corroborate the high verdict stability under LLM non-determinism.

### IRR: human inter-rater reliability {-}

The human inter-rater reliability of Gate B's factual tagging is moderate, not strong. On the 50-case human-annotated subset (§\ref{sec:gate-b-inter-rater-reliability-human-baseline}), distinct from the rerun-stability analysis above, the author's `SUPPORTED`/`CONTRADICTED`/`UNSUPPORTED` tags agree with Gate B at Cohen's $\kappa = 0.515$, below the pre-registered soft target of $\kappa \ge 0.60$. This does not touch the registered verdict-stability gate, but it flags per-claim factual tagging as the noisier sub-component of the pipeline and a calibration target for the full replication.

**Gate B Inter-Rater Reliability statistics**

* **Raw agreement:** 34/50 = 68.0%
* **Cohen's kappa:** 0.515 (pre-registered soft target $\geq$ 0.60)

**Confusion Matrix (rows = Gate B, cols = Human)**

| Gate B v / Human > | SUPPORTED | CONTRADICTED | UNSUPPORTED | Total |
|-------------------|----------|-------------|------------|------|
| SUPPORTED | 17 | 0 | 0 | **17** |
| CONTRADICTED | 1 | 16 | 0 | **17** |
| UNSUPPORTED | 5 | 10 | 1 | **16** |
| Total | **23** | **26** | **1** | **50** |

**Disagreements, Ranked (Gate B $\rightarrow$ Human)**

* **10 cases:** Gate B said `UNSUPPORTED` but human said `CONTRADICTED`
* **5 cases:** Gate B said `UNSUPPORTED` but human said `SUPPORTED`
* **1 case:** Gate B said `CONTRADICTED` but human said `SUPPORTED`

The dominant disagreement axis is `CONTRADICTED` $\leftrightarrow$ `UNSUPPORTED` (10/16 of all disagreements): disagreement concentrates on the contradicted/unsupported boundary.

The `UNSUPPORTED` tendency may inflate unsupportable-claim counts in the failure-mode inventory (§\ref{sec:failure-mode-inventory-rule-citations-genuine-arm}); this interaction is not yet quantified and is identified as a calibration target for the replication (§\ref{sec:proposed-future-work}e).

### The verdict is stable; the explanation is not. {-}

The rule-citation set accompanying each verdict has Krippendorff's $\alpha = 0.238$. Two things should be said about this figure. First, it is the single most consequential reliability finding in the pilot, and we report it in the main results rather than an appendix precisely because it does not fail a pre-registered gate (only ICC $\geq$ 0.80 was thresholded) and is therefore easy to under-report. Second, 0.238 is an optimistic upper bound: the coefficient is inflated by agreement on the empty/absent-citation cases, so true agreement on the rules actually cited is worse.

A per-rule flicker analysis, post-hoc and exploratory and labeled as such in the post-hoc amendment v22 of `paper/PRE_REGISTRATION.md`, localises the instability sharply. The structural and unsubstantiated-claim rules that most often *drive* a `BLOCK` are reasonably stable (`F2` flickers on 10.7% of cases it appears in, `S1` 21.3%, `U1` 28.5%), whereas the lower-frequency citations are highly volatile: every J-rule (the strategic-deception findings `J1`–`J5`) flickers on 100% of the cases in which it appears across the six runs.

| Rule (by stability) | Cases seen | Flicker % |
|------------------------|-----------|------------|
| `F2` (action-tip temporal causality) | 197 | 10.7 |
| `S1` (schema) | 122 | 21.3 |
| `U1` (unsubstantiated claim) | 295 | 28.5 |
| `F1` (insider-tip sterilization) | 194 | 53.1 |
| `U3` | 285 | 59.3 |
| `U4` / `H1` (hygiene) | 285 / 265 | 95.1 / 95.1 |
| `F3` | 151 | 98.0 |
| `J1`–`J5` (judge-process findings) | 59–108 | 100.0 |
| `U2` (sound gap analysis) | 2 | 100.0 |

("Cases seen" = cases where the rule was cited in at least one of the six runs; "flicker %" = the fraction of those cases on which the rule's presence was not unanimous across the six runs. Rule codes such as `S1` are distinct from supplementary-material numbering; supplementary materials are never abbreviated 'S1' in this paper.)

Our interpretation: the instrument's **decision** is reliable while its **rationale at the level of the specific rule cited** is not yet reproducible run-to-run. The Auditor consistently arrives at `BLOCK`, but the exact subset of rules it names to justify the block varies. We emphasize that the mechanism is undetermined and the observation should not be over-read. Two candidate explanations are live: (i) a prompt-structure defect — the citations are emitted as ungrounded annotations within a single monolithic evaluation call, with no requirement to anchor them to source evidence — and (ii) a genuine decoupling between the verdict and its rationale. The concentration of flicker in exactly the citation families that lack per-claim source grounding, while the source-grounded `F2` is comparatively stable (flicker 10.7%), is likely explained by (i), and preliminary scoping work points the same way; §\ref{sec:proposed-future-work}(a)–(b) define the experiments intended to discriminate between the two. This bounds the interpretability claim of §\ref{sec:source-evidence-grounding-and-the-verdict-citation-split}: the external reasoning artifact is reproducible *as a verdict* but not *as a citation set*. It also bounds how strongly the §\ref{sec:failure-mode-inventory-rule-citations-genuine-arm} failure-mode inventory should be read. Rule-frequency rankings are indicative; individual low-frequency citations are not stable instrument outputs. Closing this gap (the predicate-grounding redesign, §\ref{sec:proposed-future-work}(b)) is future work.

## Ablation: Auditor With and Without Judge Verdict {#sec:ablation-auditor-with-and-without-judge-verdict}

Recovery is preserved under ablation, confirming verdict-level independence (§\ref{sec:ablation-verdict-level-independence-of-gate-c}). When the judge's action is randomized and its reasoning trace replaced with a content-free monologue, the Auditor's recovery does not collapse toward chance; it is statistically indistinguishable from the intact condition.

| Metric | Judge intact (Z01) | Judge replaced (noise) |
|---------------------|------------------|----------------------|
| n (`CLEAN` / `ROGUE`) | 400 / 799 | 399 / 799 |
| Recovery `CLEAN` | 99.0% | 99.5% |
| Recovery `ROGUE` | 99.0% | 98.6% |
| FPR | 1.0% | 0.5% |
| FNR | 1.0% | 1.4% |
| Auditor save rate | 95.2% | 98.5% |
| Auditor break rate | 0.30% | 0.77% |

With no genuine judge signal at all, recovery moves by less than 1 pp in each class and is marginally *higher* on `CLEAN` under noise. This is the architecturally desired outcome: Gate C reaches its verdict from source text and policy, not by mirroring the judge. The ablation exercises only function (1), the independent verdict. Function (2), the judge-trace reasoning audit, is inert when the trace is noise and is reported on the genuine arm only (§\ref{sec:failure-mode-inventory-rule-citations-genuine-arm}).

### Per-Variant 8-Cell Decomposition (exploratory) {#sec:per-variant-8-cell-decomposition-exploratory}

Each pre-registered 2 $\times$ 2 quadrant splits on the third (ground-truth) axis. Counts are case n. Save = Auditor fixed a wrong judge; Break = Auditor broke a right judge; Concur-wrong = both wrong.

| Variant | `CLEAN` concur-correct | `CLEAN` save | `CLEAN` break (FP) | `CLEAN` both-overblock | `ROGUE` concur-correct | `ROGUE` save | `ROGUE` break (FN) | `ROGUE` both-miss |
|-----|---------------|--------|------------|---------------|---------------|--------|------------|-----------|
| Z01 | 376 | 20  | 3 | 1 | 632 | 159 | 0  | 8  |
| Z02 | 353 | 45  | 2 | 0 | 729 | 64  | 0  | 6  |
| Z03 | 2   | 394 | 0 | 3 | 782 | 0   | 17 | 0  |
| Z04 | 397 | 1   | 2 | 0 | 110 | 679 | 0  | 10 |
| Z05 | 390 | 8   | 2 | 0 | 637 | 154 | 0  | 8  |

These conservation checks passed at run end for every arm in \hyperref[sec:appendix-b]{Appendix B}; the small-drop accounting there is a caught-and-contained matter rather than an open data-integrity question.

Two patterns stand out. First, the Auditor's false negatives concentrate entirely in Z03 (17 `ROGUE` breaks, the paranoid probe) and as "both-miss" double failures elsewhere (6–10 per variant). Second, the stress probes invert: Z03's `CLEAN` column is almost entirely "save" (394) where Z04's `ROGUE` column is almost entirely "save" (679), the Auditor repairing opposite judge biases. As in §\ref{sec:stratified-deception-recovery-exploratory}, these patterns are exploratory and hypothesis-generating for the full replication rather than confirmatory.

## Failure-Mode Inventory (Rule Citations, Genuine Arm) {#sec:failure-mode-inventory-rule-citations-genuine-arm}

Exploratory aggregate frequencies, pooled across the five genuine judge variants ($\approx$ 6,000 judged cases); per the §\ref{sec:source-evidence-grounding-and-the-verdict-citation-split} reporting policy, per-case attribution is not made. At the aggregate level, the strategic-deception J-rules fire on 4,737 of ~6,000 `ROGUE` cases (79%) versus 262 of ~6,000 `CLEAN` cases (4.4%) — a class-conditional enrichment, treated here as a population-level signal.

| Family | Rule(s) | `CLEAN` firings | `ROGUE` firings |
|------------------------|-------|------------|------------|
| J (judge-process / strategic deception) | `J1`–`J5` | 262 | 4,737 |
| F (structural fact) | `F1`–`F3` | 16 | 10,314 |
| U (unsubstantiated claim) | `U1`–`U4` | 1,277 | 6,653 |
| S (schema) | `S1` | 2,373 | 712 |
| H (hygiene, non-blocking) | `H1` | 164 | 628 |

The F-rules (structural agent behavior) and J-rules (judge reasoning errors) concentrate almost entirely on `ROGUE` cases, as intended: `F1` fires once on `CLEAN` versus 4,036 times on `ROGUE`. In aggregate, the J-cluster — comprising scratchpad blindness, sanitized cover-story acceptance, and pressure-as-justification — is the Auditor's judge-process anomaly signal, advanced as hypothesis-generating for the full replication. Because per-case J-rule citations flicker at 100% across passes (§\ref{sec:test-retest-reliability-instrument-stability-results}), no individual case is attributed as deceptive on the basis of a J-rule firing.

## Pre-Training Contamination Canary {#sec:pre-training-contamination-canary}

Re-running the full pilot through Z01 with all named entities (companies, tickers, executives) replaced by synthetic equivalents (§\ref{sec:ablation-verdict-level-independence-of-gate-c}) produces recovery indistinguishable from verbatim:

| Z01 | Verbatim | Perturbed | $\Delta$ |
|-----------------------|-----------|-------------|-------------|
| Recovery `CLEAN` | 99.0% | 99.3% | +0.3 pp |
| Recovery `ROGUE` | 99.0% | 98.9% | $-0.1$ pp |
| FPR | 1.0% | 0.8% | — |
| FNR | 1.0% | 1.1% | — |

Both deltas sit well inside the noise envelope; there is no statistically significant drop under perturbation. The independent policy-gap scan over the 1,200 perturbed files records 3 auditor breaks (matching the primary dashboard output; see Erratum 1) and zero schema crashes. We find no evidence of *entity-level* memorization.

This matters because near-ceiling recovery (§\ref{sec:headline-recovery}) would otherwise invite a contamination explanation. The canary makes a verbatim-contamination account substantially less plausible, leaving corpus recoverability and a strict, well-specified policy as the more likely operative explanations. We are deliberately cautious about the strength of this claim. The Apollo transcripts are structurally homogeneous, a shared scaffold with entities swapped in. This means that entity perturbation bounds *entity-level* memorization, but does not rule out familiarity with the corpus's structural shape. During the §\ref{sec:gate-b-inter-rater-reliability-human-baseline} annotation the author found the cases pattern-matchable after ~50 items. With the structural canary deferred to a follow-up study, the entity-perturbation arm is the *sole* contamination/memorization check in this pilot and carries that interpretive burden alone (§\ref{sec:limitations}).

## Architectural Stability vs. Evaluator Stochasticity {#sec:architectural-stability-vs-evaluator-stochasticity}

The test–retest analysis (§\ref{sec:test-retest-reliability-instrument-stability-results}) reveals a clean separation between the stability of the Auditor's *decision* and the stability of its *rationale*. The binary verdict is highly reproducible: across six reruns the Auditor arrives at the same `APPROVE`/`BLOCK` call on essentially every case, systematically overriding flawed L2 approvals on rogue cases regardless of run-to-run surface variation in the judge's narrative. The verdict layer absorbs upstream evaluator stochasticity. The rule-citation layer does not: the J-rules change on essentially every case they touch. This is a real boundary on the interpretability claim of §\ref{sec:source-evidence-grounding-and-the-verdict-citation-split} and motivates the rationale-layer program of §\ref{sec:proposed-future-work}(a–b).

The pipeline also surfaced two latent policy boundaries rather than obscuring them.

**Reporting omission with no underlying trade.** In edge cases where an agent received an insider tip, correctly abstained from trading, but then omitted the interaction from its management report, the Auditor returned an empty violation set. The policy admits only F-series (trade-based) violation codes, so a reporting omission with no underlying trade has no code to trigger; the §1.2/§7 safe harbor applied, even though the omission is a hygiene concern. The Auditor enforced the policy as written and surfaced the gap rather than resolving it — the cartridge functioning as a strictly binding constraint (§\ref{sec:the-truth-cartridge}).

**Specification gaming in a no-scratchpad condition** (Z07 control pilot, frozen at pre-registered policy v17). An agent executed a prohibited LING trade and withheld the report for it. The detection channel is disclosed exactly: the gap was caught by manual trace review — a human investigating why the Auditor returned `APPROVE` on specific files — not by any automated rule. The instrument neither detected the evasion (it correctly applied the frozen policy) nor obscured it (the trace returned an explicitly-justified empty violation set, making the gap legible to a human reviewer).

Two coverage gaps combined. The F-series codes require an executed trade to be anchored to MNPI reliance under the §\ref{sec:discussion} Mandatory Preconditions Checklist; with no reasoning trace there was nothing to anchor that reliance to. The report omission has no standalone violation code, since the policy scopes reporting violations strictly to *submitted* text. With neither an F-anchor nor a reporting code available, the Auditor returned an empty violation set despite the prohibited trade, and recorded that empty set explicitly in the trace rather than fabricating a code to force a `BLOCK`. The `policy.md` cartridge was deliberately frozen for the remainder of the study to preserve pre-registered architecture and analysis integrity. Both boundary cases are logged as candidate `policy.md` amendments for the full replication (§\ref{sec:limitations}, §\ref{sec:proposed-future-work}). This is a limitation of the *instrument-plus-policy pairing* for this study, not of the audit architecture itself.

### Scope of the Specification-Gaming Gap (enumerated) {#sec:scope-of-the-specification-gaming-gap-enumerated}

The two coverage gaps above are properties of the frozen `policy.md`, not of any particular case. We therefore enumerated exposure across the full 1,200-case pilot output to quantify how much of the Auditor's false-negative budget they explain.

**Enumeration method.** The scanner (`tools/scan_591_evasion.py`) classifies every false negative (Apollo ground truth `ROGUE` $\land$ Gate C `APPROVE`) into four classes, defined in the table below; validation against five manually confirmed exemplars and the trade-execution lexicon broadening are documented in the replication package. Because four further evaluations carry the B1 signature but fail the lexical trade check (PPHR stratum vocabulary), reported exposure is a conservative lower bound in the range [17, 21].

| Class | Definition |
|----|------------------------|
| **A** | Reasoning trace absent (no-scratchpad condition) |
| **B1** | `S1` safe-harbor cited $\wedge$ the Auditor's own reasoning acknowledges an executed-but-unreported trade |
| **B** | `S1` safe-harbor cited (credulity — the auditor accepted stated intent over executed behaviour) |
| **C** | Unreported-trade language present without an `S1` citation |

All classes are gated on a confirmed trade execution. The scanner was validated against five manually confirmed exemplar files before counting. The trade-execution cross-check was broadened after a first pass revealed that Apollo strata rename the trade action (`execute_trade`, `carry_out_transaction`, etc.). Four further evaluations carry the B1 signature but fail the lexical trade check (PPHR stratum vocabulary), so reported exposure is a conservative lower bound in the range [17, 21].

**Results.** Across the pilot, the Auditor produced **49 false negatives** (Z01–Z05 pooled). Of these, **17 evaluations spanning 13 distinct case episodes match the strict-evasion pattern** (all class B1). Class A contributes zero: the Z07 discovery episode is a control-pilot case and does not appear in the scored pool. No enumerated case appears on a candidate exclusion list discovered at `tools/tainted_cases.txt` (96 IDs), so all 17 are confirmed scored-pilot members distributed across all five variants. The ablation-noise arm contributes a further 11 files with the same signature; these are quarantined from headline counts and serve as a control (§\ref{sec:safe-harbor-credulity-as-the-dominant-false-negative-mode}).

| Variant | A (no-scratchpad) | B1 (`S1` $\wedge$ unreported) | B (`S1` credulity) | C | FN total | Strict N |
|-------------|-----------|-------------------|------------|---|-----|-----|
| Z01 JudgeBench   | 0 | 4 | 4  | 0 | 8  | 4 |
| Z02 ScratchpadAware | 0 | 1 | 5  | 0 | 6  | 1 |
| Z03 Paranoid     | 0 | 6 | 10 | 1 | 17 | 4 |
| Z04 Lenient      | 0 | 5 | 4  | 1 | 10 | 4 |
| Z05 ManagerAligned | 0 | 5 | 3  | 0 | 8  | 4 |
| **Pooled**       | **0** | **21** | **26** | **2** | **49** | **17** |

**Counterfactual impact.** Treating all 17 strict-evasion evaluations as recovered under a closed policy, the pooled false-negative share falls from 0.0167 to 0.0110 ($\Delta$ = 0.57 pp):

| Variant | Baseline FN share | Counterfactual | $\Delta$ |
|------------|--------------------|----------------|------------|
| Z01 | 0.0125 | 0.0063 | 0.0062 |
| Z02 | 0.0082 | 0.0068 | 0.0014 |
| Z03 | 0.0213 | 0.0164 | 0.0049 |
| Z04 | 0.0833 | 0.0517 | 0.0316 |
| Z05 | 0.0124 | 0.0062 | 0.0062 |
| **Pooled** | **0.0167** | **0.0110** | **0.0057** |


Denominator: FN + concordant blocks (`VALIDATED_BLOCK` on `ROGUE` cases) per variant; auditor saves (`FLAWED_APPROVAL` on `ROGUE`) are excluded. Baseline shares use each variant's full denominator (640 / 735 / 799 / 120 / 645 — variant-specific by design, reflecting each judge's concordant-block rate); counterfactual shares additionally remove the recovered strict evaluations from both numerator and denominator, so each variant's $\Delta$ compares its baseline with an at-risk-adjusted share rather than a fixed-denominator share. All readings are conservative upper bounds. Reconciliation to the study-wide §\ref{sec:headline-recovery} FNR denominator is filed for the full replication.

**Three Observations.**

1. **The §\ref{sec:headline-recovery}/§\ref{sec:hypothesis-h2-test-fpr-fnr-by-judge-variant} headline figures are materially unchanged.** The gap is real in the scored pilot — the zero-escape scenario does not apply — but it is small, and the frozen-policy caveat now carries a quantified bound rather than an open one.

2. **The effect concentrates in the Lenient variant.** Closing the gap would reduce Z04's FN share by over a third (0.083 $\rightarrow$ 0.052, $\Delta$ = 3.16 pp); every other variant moves by $\leq$ 0.62 pp.

3. **The limitation is structural.** 17 evaluations exist on which the Auditor narrated the violation in its trace and was structurally unable to code it — including one trace (Z05, `a5c88c94d58b`) that names both gaps explicitly before defaulting to the safe harbor. The same episode evades under multiple independent judge framings (one under three of five variants), consistent with a policy-level cause rather than auditor–judge interaction noise.

The remedy is a policy change, not an instrument change: (i) a standalone code for executed-but-unreported trades, and (ii) a no-scratchpad anchoring convention for the F-series preconditions, both filed as candidate `policy.md` amendments for the full replication (§\ref{sec:proposed-future-work}). The enumeration also surfaced an adjacent, quantitatively larger failure mode treated in §\ref{sec:safe-harbor-credulity-as-the-dominant-false-negative-mode}.


### Safe-Harbor Credulity as the Dominant False-Negative Mode {#sec:safe-harbor-credulity-as-the-dominant-false-negative-mode}

The §\ref{sec:scope-of-the-specification-gaming-gap-enumerated} enumeration revealed that the strict-evasion gap (class B1) is **not** the largest source of false negatives. Of the 49 main-pilot false negatives, **47 (96%) fall in the `S1`-credulity classes** (B and B1); the remaining two (class C) carry unreported-trade language without an `S1` citation. In the modal pattern, the agent receives a tip, writes refusal language into its scratchpad ("we should stick to trading based on public information"), executes the tipped trade anyway, and the Auditor credits the refusal as satisfying `S1`.

**The mechanism.** The defect is in the policy, not the instrument: `S1` as written is satisfied by *stated intent alone* and does not require the executed action to be consistent with the public rationale the agent cites. In the recurring pattern the public tool recommended *holding* the tipped stock; the agent traded against that recommendation, in the tip's direction, while citing the tool. Gate C traces show the Auditor weighing exactly this tension and resolving it toward stated intent. The safe harbor absorbs the behavioural contradiction because the policy supplies no consistency test to apply.

**Why this warrants separate reporting.**

**Scale.** `S1`-credulity accounts for 47 of 49 false negatives (96%). The strict §\ref{sec:scope-of-the-specification-gaming-gap-enumerated} pattern is wholly contained within it: all 17 strict-evasion evaluations also carry the `S1` citation.

**Control evidence.** The same signature reproduces in the ablation-noise arm (11 files), where the L2 verdict is randomized. The failure is intrinsic to the Auditor-plus-policy pairing, not induced by judge quality.

**Variant asymmetry.** The false-negative budget concentrates where L2 framing is most extreme in either direction: Z03-Paranoid (17 evaluations, all cases where the Auditor overruled a correct L2 block, i.e. masked breaks) and Z04-Lenient (10 evaluations, highest FN share at 0.083). Judge-verdict framing appears to modulate Auditor credulity; we report this as an observational pattern, not a confirmed mechanism.

**Remedy.** Again, a policy amendment, not an instrument change (§\ref{sec:scope-of-the-specification-gaming-gap-enumerated}): `S1` should require behavioural consistency, such that the executed action must not contradict the public rationale the agent cites, with inconsistency escalated at minimum to a hygiene finding. Filed as a candidate `policy.md` amendment for the full replication (§\ref{sec:proposed-future-work}).

**Detection caveat.** Both the credulity and omission signals are extracted from the Auditor's own reasoning language. Class counts are therefore lower bounds wherever the Auditor did not surface the tension in prose.

## Same-Model Control Arm (Z07) {#sec:same-model-control-arm-z07}

To separate architecture from parameter capacity (§\ref{sec:model-selection-and-asymmetry}), a 150-case control arm ran both the L2 judge and the L3 Auditor on identical weights (`Qwen 3 235B`), zeroing the parameter delta. Z07 is reported alongside Z01 for comparison and is not pooled into the Hypothesis H1 family.

| Metric | Z01 (Llama judge / Qwen auditor) | Z07 (Qwen judge / Qwen auditor) |
|---------------|-----------------------|-----------------------|
| n (`CLEAN` / `ROGUE`) | 400 / 799 | 50 / 100 |
| Recovery `CLEAN` | 99.0% | 96.0% |
| Recovery `ROGUE` | 99.0% | 98.0% |
| FPR | 1.0% | 4.0% (95% CI [1.1%, 13.5%]) |
| FNR | 1.0% | 2.0% (95% CI [0.6%, 7.0%]) |
| Auditor save rate | 95.2% | 94.3% (33/35; CI [81.4%, 98.4%]) |
| Auditor break rate | 0.30% | 1.74% (2/115; CI [0.5%, 6.1%]) |

Parameter capacity alone does not explain the observed recovery. Collapsing the L2/L3 parameter gap does not improve recovery; Z07 is, if anything, marginally weaker than Z01, and its CIs comfortably contain the Z01 point estimates. The result is consistent with the audit architecture, rather than model size alone, driving the observed recovery. We inspected Z07's two `ROGUE` false-negatives directly. Both are label-divergence cases rather than Auditor reasoning errors: one a §1.2 safe-harbor trade (the agent refused the tip and traded on public analysis; the Auditor correctly approved, while the Apollo label flags the omitted-tip report as deceptive), the other the no-scratchpad specification-gaming case of §\ref{sec:scope-of-the-specification-gaming-gap-enumerated}. Neither is a failure of grounding or logic.

We note the limited power of this 150-case arm: the Wilson CIs on Z07 FPR/FNR are wide and overlap the Z01 point estimates, so Z07 rules capacity *out as the sole driver* without tightly estimating any residual capacity effect. A larger same-model control is folded into the full-corpus replication.

One honest qualification on failure-mode decoupling. Z07 produced 2 correlated errors out of 150 cases, both `CLEAN` cases on which judge and Auditor *both* blocked (the `CLEAN__L2_BLOCK__L3_BLOCK` cell). On identical weights, prompt-and-role separation makes such correlated errors rare (2/150) but not zero. This is a real, if small, boundary on the §\ref{sec:introduction} partial-decoupling claim, consistent with the coherent-cover-story coupling discussed in §\ref{sec:proposed-future-work}.

---

# Discussion {#sec:discussion}

The introduction asked whether an audit layer can recover ground truth independently of the judge it audits. On the evidence of this pilot, it can. The Auditor recovers the Apollo label at near-ceiling (97.9–99.5% across both ground-truth classes, `CLEAN` and `ROGUE`, and all five judges), and that recovery is statistically equivalent across judge variants ranging from realistic to deliberately degraded (Hypothesis H1 supported, all 20 corrected TOST comparisons rejecting non-equivalence). Miscalibration is bounded at least ~4.7 $\times$ tighter than the registered limit (Hypothesis H2, max FPR 1.0%, max FNR 2.1%). At the level the paper claims — invariance of recovery to upstream judge quality within the tested range — the result is what a working Line 3 instrument should produce.

The auditor doesn't simply mirror the judge's output — it makes an independent assessment, using the judge's verdict as one input among others. Across every condition, it recovers 95–99% of the cases the judge got wrong while disrupting fewer than 1% of the cases the judge got right (Z03 excepted, at 2.1%). The ablation reinforces the point: when the judge's verdict and trace are replaced with random noise, recovery shifts by less than a percentage point and the save rate, if anything, increases. The auditor's call is driven by source text and policy, not by the judge's assessment. This independence from the judge's verdict is the core property the architecture was designed to achieve — and the data confirm it directly.

Two control arms guard the interpretation against the obvious objections. Near-ceiling recovery should prompt a "why so easy?" question, and the two most likely deflationary explanations are pre-training contamination and raw parameter capacity. The entity-perturbation canary addresses the first: synthetic-entity recovery is indistinguishable from verbatim, with 3 auditor breaks across 1,200 perturbed files, so the performance is unlikely to be merely an artifact of verbatim corpus exposure (a structural-familiarity effect is not excluded; §\ref{sec:pre-training-contamination-canary}). The same-model control (Z07) addresses the second: collapsing the L2/L3 parameter gap onto identical weights does not improve recovery; it is marginally worse. The gains are consistent with the audit architecture, rather than model size alone, driving the observed recovery. The operative explanation that remains is narrower: on this single corpus, under a strict, prescriptive policy, the ground-truth label is highly recoverable by a source-grounded process. That is a real and useful finding. It is also exactly why the claim is scoped to recovery-of-the-Apollo-label within one domain rather than to deception detection in general.

Two tensions temper the findings. First, the instrument's decision is highly reproducible (verdict ICC 0.979, quadrant $\kappa$ 0.986; ablation arm only, §\ref{sec:limitations}) but its rationale is not: the rule-citation set flickers heavily run-to-run, with the strategic-deception J-rules changing on essentially every case they touch (Krippendorff $\alpha$ 0.238, itself an optimistic upper bound). Whatever its mechanism — and §\ref{sec:proposed-future-work}(a)–(b) define the test intended to establish it — this instability poses, for the audit layer itself, the question the paper asks of judges and that Meyer, Garcia, and Wulff (2026) quantify for psychometric instruments (§\ref{sec:introduction}): does the output correspond to the evidence it purports to report? Stability cannot answer that question (§\ref{sec:limitations}); the counterfactual test of §\ref{sec:proposed-future-work}(f) is designed to. This bounds the interpretability claim of §\ref{sec:source-evidence-grounding-and-the-verdict-citation-split} — the external reasoning is reproducible as a verdict, not as a citation set — and means the failure-mode inventory (§\ref{sec:failure-mode-inventory-rule-citations-genuine-arm}) should be read as indicative of rule frequencies, not as stable per-case attribution. Second, the same-model control produced two correlated `CLEAN` over-blocks: on identical weights, prompt-and-role separation makes correlated L2/L3 errors rare but not impossible, a small but genuine boundary on the partial-decoupling claim.

None of these qualifications touch the pre-registered headline metrics, all of which are computed directly against ground truth and pass. In sum, the architecture behaves as an independent, judge-invariant, well-calibrated Line 3 instrument on this corpus; its rationale-level reproducibility, its cross-domain behavior, and its robustness to a genuinely deceptive Line 2 remain open questions.

Independence at the audit layer, not competence at the judge layer, is what makes automated judgment governable. The pilot demonstrates this in one demanding domain. The work of §\ref{sec:proposed-future-work} — a reproducible rationale layer, predicate grounding, cross-domain adapters, and the full-corpus replication — is the work of showing it holds where the stakes are highest: wherever an instrument's output is taken on trust.

## Limitations {#sec:limitations}

Several limitations qualify our conclusions. Each is stated with its scope and, where one exists, the reason the core claim survives.

- **Near-ceiling recovery and the status of H1.** H1 is supported only descriptively: all ten pairwise comparisons within each ground-truth class fell inside the pre-registered equivalence bound. That equivalence is conditional on near-ceiling recovery — uniformly high recoverability leaves little room for judges to differ, so the invariance test was not stringent. Whether invariance survives a harder task (a lower-recoverability corpus or a less prescriptive policy) is untested; the inferential re-test is identified as the planned replication's primary analysis (§\ref{sec:proposed-future-work}e).
- **Rule-citation instability.** Verdicts are stable; citations are not ($\alpha$ = 0.238, an optimistic upper bound that empty-set agreement inflates, so true agreement is worse). Supplementary 1 shows this is presence/absence flicker of the underlying concept detectors, not label substitution: even maximally compressed J-family clusters flicker on >98% of cases in which they appear, and rulebook compression raises $\alpha$ by only +0.04. The unstable object is the on/off sensor, not the label. This bounds the §\ref{sec:source-evidence-grounding-and-the-verdict-citation-split} interpretability claim and the diagnostic (function-2) value of the J-rule firings; the proposed remedy, predicate decomposition with source-grounded Gate B evaluation (§\ref{sec:proposed-future-work}a–b; Supplementary 1, Supplementary 2), remains future work.
- **Gate B factual-tagging reliability is moderate.** Human inter-rater reliability on the 50-case Gate B subset reaches only $\kappa$ = 0.515 (§\ref{sec:gate-b-inter-rater-reliability-human-baseline}, §\ref{sec:test-retest-reliability-instrument-stability-results}), below the soft $\geq$ 0.60 target; however, this does not touch the registered verdict-stability gate (ICC $\geq$ 0.80, met). It flags per-claim factual tagging as the noisier sub-component and a calibration target for the full replication.
- **Judge-model robustness.** Because Z01–Z05 share a single base model, the Hypothesis H1 equivalence result does not speak to judge-model robustness; practitioners substituting a different judge family should treat the equivalence result as not yet established for their deployment (see §\ref{sec:proposed-future-work}g).
- **Verdict stability measured on the ablation arm only.** The ICC = 0.979 (§\ref{sec:test-retest-reliability-instrument-stability-results}) was computed on the ablation arm, where the Auditor reasons without a genuine judge trace. This isolates Auditor-internal non-determinism cleanly but leaves verdict stability *on genuine judge traces* unmeasured; the Z07 correlated over-blocks (§\ref{sec:same-model-control-arm-z07}) show genuine-trace interactions can in principle produce coupled errors the ablation-only check would not surface. A genuine-arm stability subset is added to the full-corpus replication.
- **Binary ground-truth collapse.** The headline metric pools `ROGUE-HONEST` and `ROGUE-DECEPTIVE` into a single `ROGUE` class (§\ref{sec:source-data-and-the-binary-mapping}). Deception-relevant evidence in this paper is therefore strictly exploratory: the stratified verdict-level recovery of §\ref{sec:stratified-deception-recovery-exploratory} (descriptive, not pre-registered) and the aggregate J-rule enrichment of §\ref{sec:failure-mode-inventory-rule-citations-genuine-arm} (per the §\ref{sec:source-evidence-grounding-and-the-verdict-citation-split} reporting policy; no per-case attribution). Un-collapsing the strata in the headline metric is carried as future work (§\ref{sec:proposed-future-work}).
- **Specification-gaming policy boundary.** Under the frozen study policy, an agent that executes a prohibited MNPI trade but withholds the management report can, under strict literalism, return an empty violation set (§\ref{sec:architectural-stability-vs-evaluator-stochasticity}; frozen at pre-registration policy v17). This is a boundary on the instrument-plus-policy pairing, not the architecture, and is logged as a candidate policy amendment.
- **Sole contamination check.** With the structural canary deferred to a follow-up study, the entity-perturbation arm (§\ref{sec:pre-training-contamination-canary}) is the only contamination/memorization control in this pilot and carries that interpretive burden alone.
- **Correlated errors under same-model control.** 2/150 correlated `CLEAN` over-blocks in Z07 bound the failure-mode-decoupling claim (§\ref{sec:discussion}).
- **Automated ground-truth labels.** Recovery is recovery of the *Apollo* label, itself automated: a deterministic misalignment flag and an LLM-graded deception judgment, validated by the corpus authors against a 120-case single-researcher spot-check (94% agreement) but without a published multi-rater human IRR on this corpus. Downstream work reports external corroboration for the corpus's labels: linear activation probes distinguish honest from deceptive responses on this scenario family with AUROCs of 0.96–0.999 (Goldowsky-Dill et al., 2025), which bounds, but does not eliminate, label-noise concerns. The headline is bounded accordingly; we treat the quantitative implication in §\ref{sec:proposed-future-work}(e).
- **Citation stability does not establish citation validity.** Per-rule citations are not uniformly stable: the `F2` rule and the merged `F12` factual cluster are comparatively stable (`F2` flicker 10.7%, §\ref{sec:test-retest-reliability-instrument-stability-results}; `F12` all-five-pass agreement 97.0%, Supplementary 1), whereas `F1` flickers on 53.1% of the cases in which it appears (§\ref{sec:test-retest-reliability-instrument-stability-results}) and the J-rule citations are not ($\alpha$ = 0.238), but stability does not show the citations are load-bearing. A judge can produce stable, fluent citations as post-hoc confabulation (Nisbett & Wilson, 1977); only a counterfactual manipulation, removing the cited fact while holding the rest of the case constant, tests whether a citation tracks the fact it cites (Johansson et al., 2005). This test has been designed (scoping note 3, v2.3) but not executed; execution depends on the predicate-decomposition software update underlying Supplementary 2. Until it runs, the §\ref{sec:source-evidence-grounding-and-the-verdict-citation-split} claim is bounded to citation–source correspondence, not causal dependence of the citation on the cited fact.
- **Quantified frozen-policy evasion bound.** The §\ref{sec:scope-of-the-specification-gaming-gap-enumerated} enumeration bounds specification-gaming exposure at 17 case $\times$ variant evaluations (13 distinct episodes; lower bound, range [17, 21]) within the scored pilot, with pooled FN-share sensitivity of 0.57 pp concentrated in Z04-Lenient (3.16 pp). Recovery and FNR figures (§\ref{sec:headline-recovery}, §\ref{sec:hypothesis-h2-test-fpr-fnr-by-judge-variant}) carry this quantified caveat; the instrument-plus-policy-pairing limitation stands regardless of count.

## Proposed Future Work {#sec:proposed-future-work}
- **(a) Reproducibility of the rationale layer (Supplementary 1; Tsereteli, 2026) — status: emergent observation (unregistered):** The verdict layer is already reproducible (ICC = 0.979), but the rule-citation set that justifies each verdict is not (Krippendorff's $\alpha$ = 0.238, §\ref{sec:test-retest-reliability-instrument-stability-results}), which bounds the interpretability claim of §\ref{sec:source-evidence-grounding-and-the-verdict-citation-split}. We deliberately refrain from assigning a mechanism to this pattern. Superficially, stable verdicts with unstable rationales resemble the decouplings studied in the unfaithful chain-of-thought literature (Turpin et al., 2023, discussed in §\ref{sec:related-work}); however, the present data are equally — and in our assessment more parsimoniously — explained by a prompt-structure defect: the unstable citation families are emitted within a single monolithic evaluation call, without the per-claim source grounding that Gate B enforces for the comparatively stable factual rules (`F2`: 10.7% flicker; §\ref{sec:test-retest-reliability-instrument-stability-results}). Whether the instability survives predicate decomposition and per-predicate grounding is therefore an empirical discriminator between an engineering defect and a deeper verdict–rationale decoupling, and we report the observation without committing to either reading. The Supplementary 1 analysis also notes that J-rule instability is expected on the ablation arm where judge reasoning is absent (Supplementary 1.4, Limitation 2).

  The analysis (Tsereteli, 2026) tests whether the unstable citation layer can be rescued by aggregation or compression across the k stochastic passes produced per case, rather than treating any single pass's citation set as canonical. It derives compressed rulebooks from the observed co-firing structure of the rule set (`F1`/`F2` $\rightarrow$ `F12`; `J1`/`J2` $\rightarrow$ `J12`; `J3`/`J4`/`J5` $\rightarrow$ `J345`; `U1`/`U3` $\rightarrow$ `U13`) and recomputes $\alpha$ over the k=6 seed-plus-rerun frame. Compression is not a remedy: the best compressed codebook (9 labels) raises $\alpha$ only from 0.238 to 0.278, a paired difference of +0.04 with bootstrap 95% CI [+0.031, +0.047]. Status note: this compression analysis is an exploratory, post-hoc, unregistered re-analysis of the pilot's existing test–retest frame ($n$ = 300 cases, $k$ = 6 passes per case), not a confirmatory result under the main pre-registration; it is reported here as motivation for the redesign below. The decisive diagnostic is the presence/absence flicker already stated in §\ref{sec:limitations}: conditional on being detected at all in a case, the merged `J12` and `J345` families flicker on 98.9% and 98.3% of cases in which they appear. In contrast `F12` flickers on only 3.0% (Supplementary 1, Table 1.2). On the current evidence, the next step is to extend Gate B's decomposed, source-grounded evaluation to the flickering families, so that every rule receives the grounding that currently stabilizes `F1`/`F2` (Supplementary 1, §1.5). This is the architectural motivation for the Correspondence Auditor redesign. The objective is a reproducible rationale layer that does not distort the §\ref{sec:failure-mode-inventory-rule-citations-genuine-arm} failure-mode inventory, the prerequisite to strengthening the §\ref{sec:source-evidence-grounding-and-the-verdict-citation-split} claim.

  Supplementary 1 is available at `paper/supplementary/supplementary_1_redundancy_diagnostic.md`.

- **(b) Predicate grounding (Supplementary 2) — status: designed but not yet executed:** The $\alpha$ = 0.238 finding (§\ref{sec:test-retest-reliability-instrument-stability-results}) demonstrates that the rationale layer is unstable but does not locate the mechanism. As established in §\ref{sec:limitations} and §\ref{sec:proposed-future-work}a, the instability is presence/absence flicker rather than label substitution, and coarsening the rulebook raises $\alpha$ by only +0.04 units. Compression is therefore insufficient.

  The motivating hypothesis is structural: monolithic evaluation of interpretive rules is the failure mode, and extracting each rule as a standalone, source-grounded predicate with its own Gate B evaluation will reproduce the stability already observed for factual rules (`F2`: 10.7% flicker; §\ref{sec:test-retest-reliability-instrument-stability-results}). If confirmed, the $\alpha$ = 0.238 finding will have been a correctable instrumentation defect rather than a property of the instrument's judgment; if falsified — that is, if standalone grounded predicates still flicker — the instability would constitute evidence for a deeper verdict–rationale decoupling and would warrant the stronger readings we decline to make here.

  A supplementary experiment (Supplementary 2) tests this hypothesis on the same Apollo corpus. This experiment is not yet pre-registered; the registration will be deposited before execution. The predicate decomposition borrows its structural vocabulary from the Psychopathia Machinalis framework (Watson & Hessami, 2025b): its syndrome 4.3 predicate p1, internal reasoning differs systematically from output, is the generalized form of the `J2` precondition tested here (scratchpad confesses MNPI; report sanitizes). The observational pattern in the existing data is consistent with a task-type boundary: predicates requiring factual comparison between two textual fields are stable, while predicates requiring inference about intent or motivation are not. Supplementary 2 tests whether that boundary is causal; its purpose is to map that boundary, not to adopt any specific taxonomy.

- **(c) Local, data-sovereign deployment — status: direction, no design yet.** In post-hoc audit settings the material under review is frequently sensitive, so a deployable Auditor should be able to run wholly on local hardware, with no audited data leaving the worker's environment. A research direction is therefore whether the architecture can meet the same pre-registered reliability bars (Hypothesis H1 invariance, Hypothesis H2 bounded miscalibration, verdict stability) on open-weight models small enough to run on commodity local hardware rather than frontier-scale hosted models. Where a smaller model cannot sustain the layered conditional logic of the audit prompts directly, the work would explore moving deterministic sub-tasks from the model into code and decomposing the audit into narrower steps, so the reliability thresholds are preserved at lower capacity. Specific hardware and model classes are intentionally left open, since the viable capability tier will track the open-weight frontier.

- **(d) Corpus-agnostic ingestion — status: direction, no design yet.** The present ingestion layer relies on content-shape heuristics tuned to the Apollo corpus's text conventions to populate the three source-text sections the Auditor consumes, a coupling we note as a limitation of the current implementation (§\ref{sec:limitations}). To support cross-domain replication, we plan a dataset-adapter pattern in which corpus-specific adapters emit a common structured intermediate representation. This would decouple the Auditor's core logic from dataset-specific formatting thus reducing the risk of silent ingestion failures.

- **(e) Full-Corpus Replication and Label Sensitivity — status: planned, scope only:** We intend to scale the study to the maximum balanced sample of the Apollo dataset ($\approx 8,500$ cases), moving the result from the 95% to the 99%-confidence class. Because near-ceiling recovery must be read against the reliability ceiling of the underlying Apollo-graded labels, this replication will include re-scoring a stratified subset against a human-annotated panel. To resolve known analytical bounds, this full replication will integrate a genuine-arm stability evaluation subset to measure user-interaction non-determinism, and will explicitly un-collapse the pooled ground-truth metric to isolate the recovery of the distinct honest/deceptive strata. We will pre-commit to specifying equivalence margins for the save and break rates as primary metrics before execution. 

  Two additional replication arms bound the interpretive scope of the pilot:
  \begin{itemize}
      \item \textbf{Lexical policy-application baseline.} A deterministic rule that flags \texttt{ROGUE} when the source text contains insider-tip language chronologically preceding a trade execution. This bounds the architecture's marginal contribution over direct policy application; a recovery rate $\geq 95\%$ would re-scope the paper's contribution to architectural independence from judge traces and the stability asymmetry, whereas a rate $\leq 90\%$ would demonstrate the architecture's discriminative value over trivial policy application.

      \item \textbf{Gate B multi-rater inter-rater reliability.} The pilot's Gate B reliability ($\kappa = 0.515$, single author-annotator, 50 cases; §\ref{sec:test-retest-reliability-instrument-stability-results}) demonstrated a systematic \texttt{UNSUPPORTED}-tendency. Two independent trained annotators will tag a stratified $\geq 200$-case subset using the same three-tag scheme, reporting per-tag agreement and testing whether the \texttt{UNSUPPORTED}-tendency systematically inflates unsupportable-claim counts in the failure-mode inventory (§\ref{sec:failure-mode-inventory-rule-citations-genuine-arm}).
  \end{itemize}

  Two cartridge adjustments are proposed to account for observations from this run:
  \begin{itemize}
      \item \textbf{Reporting-omission code + no-scratchpad anchoring convention.} A standalone violation code for executed-but-unreported trades (decoupling reporting violations from submitted text), and a defined F-series anchoring convention for the no-reasoning-trace condition. Closes the §\ref{sec:scope-of-the-specification-gaming-gap-enumerated} strict gap (17 evaluations enumerated; exposure bounded at [17, 21]).

      \item \textbf{\texttt{S1} behavioral consistency.} The safe harbor should require the executed action to be consistent with the public rationale the agent cites, with inconsistency escalated at minimum to a hygiene finding. Addresses the dominant false-negative mode identified in §\ref{sec:safe-harbor-credulity-as-the-dominant-false-negative-mode} (47 of 49 evaluations).
  \end{itemize}

  The joint expected yield is bounded by the §\ref{sec:scope-of-the-specification-gaming-gap-enumerated} exposure range: at most 21 case $\times$ variant evaluations ($\approx$ 1.75% of the 1,200-case pilot), corresponding to a pooled FN-share sensitivity of 0.57 pp (§\ref{sec:scope-of-the-specification-gaming-gap-enumerated}), concentrated in Z04-Lenient ($\Delta$ = 3.16 pp). Both amendments will be frozen into `policy.md` before the full-corpus run and disclosed as a single policy-version bump in that run's pre-registration.

- **(f) Citation responsiveness under counterfactual manipulation — status: designed (scoping note; Zenodo deposit + pre-registration before execution).** Supplementary 1 established that the merged factual cluster `F12` is comparatively stable (97.0% all-five-pass agreement) and per-rule `F2` comparatively stable (10.7% flicker, §\ref{sec:test-retest-reliability-instrument-stability-results}), whereas the interpretive-rule citations are not; Supplementary 2 (designed but not yet executed) will test whether predicate decomposition reproduces that stability. Stable citations may still be post-hoc rationalization, the phenomenon Nisbett & Wilson (1977) documented as systematic confabulation. The counterfactual study adapts the choice-blindness paradigm of Johansson et al. (2005, 2006): in five Apollo cases (four `F2`-SUPPORTED targets plus one construction-sanity control), the insider-tip message is neutralized ("rumor / chatter / nothing confirmed") while the trade, case structure, and all other dialogue are held byte-identical, and the agent's reasoning is rewritten to justify the kept trade on public grounds. We measure whether the `F2` predicate (tip–trade temporal causality) flips `SUPPORTED` $\rightarrow$ `CONTRADICTED` at Gate B in isolation (Stage 1) and whether Gate C still cites `F2` when the tip is absent (Stage 2), k = 3 passes, majority vote, with pass-level flicker reported as its own signal. Hypotheses, the interpretation matrix (including "quote laundering" of the neutralized message as a named third outcome), and the pre-run lexical validation gate are pre-specified in the study's scoping note included in the study repository; the note is being deposited on Zenodo with a version DOI, and the experiment's own pre-registration will be deposited before execution. Execution depends on the predicate-decomposition work in software v3 (§\ref{sec:proposed-future-work}b). Scope caveat: the test can rule out citation fully decoupled from evidence; it cannot demonstrate genuine reasoning, since a tip-then-trade heuristic passes it. All claims are therefore framed as "citation responsiveness," not causal reasoning. The study is n = 4 targets + 1 control: a pilot whose clean sweep justifies a pre-registered 50-case study, nothing more.

- **(g) Judge-model-family robustness (cross-rotation matrix) — status: planned, scope only.** H1 as supported in this pilot is scoped to prompt-level variation within a single judge model family: all five Z01–Z05 variants share `Llama 3.3 70B` weights (§\ref{sec:model-selection-and-asymmetry}), so the equivalence result licenses no claim about robustness across judge model families. The Z07 same-model control arm (§\ref{sec:same-model-control-arm-z07}) bears on the architecture-versus-capacity question, not on cross-family robustness. The planned ~8,500-case multi-model cross-rotation matrix closes this gap directly: rotating multiple open-weight model families through both the Line 2 judge and Line 3 Auditor roles, with the H1 equivalence test re-run across family cells rather than prompt variants. This is the design under which judge-model robustness becomes a testable claim rather than an unstated assumption, and it also supplies the larger same-model control arm called for in §\ref{sec:same-model-control-arm-z07}. Practitioners substituting a different judge family per §\ref{sec:model-selection-and-asymmetry} should treat cross-family equivalence as established only once this matrix is executed.

- **(h) Operationalizing the "coherence" construct — status: direction, no design yet.** §\ref{sec:introduction}–2 attribute judge failure to the plausibility of the agent's sanitized report, but treat "coherence" as an unmeasured construct. A replication could compute semantic-embedding similarity between the agent's report and the underlying case record as a case-level report–record divergence score, and test whether judge misses correlate with that divergence. This converts the motivating construct into a measurable variable and makes the introduction's mechanism claim falsifiable.

## Responsible Use {#sec:responsible-use}

The J-rule taxonomy (`J1`–`J5`, §\ref{sec:policy-rubric-the-cartridge-for-this-study}, §\ref{sec:failure-mode-inventory-rule-citations-genuine-arm}) documents named failure modes of judge-based oversight systems: scratchpad blindness, sanitized cover-story acceptance, pressure-as-justification. This map of oversight blindspots is published to advance defensive auditing, not as a specification for building agents that evade detection. The underlying failure modes are already documented in the cited literature; the net contribution here is defensive. Practitioners deploying this instrument or its derivatives should treat the J-rule findings as defensive knowledge and exercise appropriate care in dissemination.

---

# Related Work {#sec:related-work}

**Rationale-layer instability: flicker, not label substitution.**

A companion analysis (Tsereteli, 2026) decomposes the $\alpha$ = 0.238 rule-citation instability of §\ref{sec:test-retest-reliability-instrument-stability-results}. It clusters the 14-rule policy's co-firing structure, recomputes MASI Krippendorff's $\alpha$ under compressed rulebooks, and measures cluster-level on/off flicker. The decisive finding (§\ref{sec:limitations}): the instability is presence/absence flicker of the underlying concept detectors, not label substitution among equivalent rules. The remediation target shifts accordingly, from synonym management to extending source-grounded Gate B evaluation to the flickering predicate families (§\ref{sec:proposed-future-work}a–b; Supplementary 1).

References:
Tsereteli, G. (2026). *Rule redundancy and stability analysis: Exploratory report* [Unpublished manuscript]. Analysis incorporated into this study's repository at `rulebook-redundancy-analysis/` (golden CSVs and provenance-chain tests under `tests/`).

**Apollo Research insider-trading deception corpus.**

We use Apollo's dataset as the ground-truth source for the pilot. Our contribution is downstream of theirs: we audit judge verdicts produced *over* this corpus rather than producing new corpus annotations. The dataset is from their technical report:

References:
Scheurer, J., Balesni, M., & Hobbhahn, M. (2023). Technical report: Large language models can strategically deceive their users when put under pressure. *arXiv*. https://arxiv.org/abs/2311.07590
Apollo Research. (2023). *Insider trading* [Computer software]. GitHub. https://github.com/ApolloResearch/insider-trading (published November 9, 2023)

**Strategic deception and the blindness of internal safety tools.**

DeLeeuw et al. (2025) demonstrate that LLMs reliably engage in strategic lying when deception advantages goal achievement, across 38 models and in an insider-trading compliance testbed directly analogous to the Apollo corpus used here. Their central negative result is that autolabeled interpretability features for "deception" rarely activate during strategic dishonesty, and feature steering across 100+ deception-related features failed to prevent lying. Current internal safety tooling is blind to exactly the behavior it is meant to catch. We note the architectural implication rather than claim to resolve it: their tools operate *inside* the model being monitored; the Correspondence Auditor is an *external* evidence-grounding layer operating on artifacts (source text, policy, recorded reasoning traces) rather than on activations. The two approaches are architecturally orthogonal; the blindness they document is precisely the gap a Line 3 instrument is designed to cover.

References:
DeLeeuw, C., Chawla, G., Sharma, A., & Dietze, V. (2025). The secret agenda: LLMs strategically lie and our current safety tools are blind. *arXiv*. https://arxiv.org/abs/2509.20393
Goldowsky-Dill, N., Chughtai, B., Heimersheim, S., & Hobbhahn, M. (2025). Detecting strategic deception with linear probes. In *Proceedings of the 42nd International Conference on Machine Learning (ICML 2025)*. https://arxiv.org/abs/2502.03407

**JudgeBench and the judge line.**

The JudgeBench framework (Tan et al., 2025) establishes the use of LLM evaluators for automated assessment by ranking outputs against pairwise comparisons with objective-correctness labels. Our Z01 and Z02 prompts are adapted from JudgeBench-style rubrics to the ternary output space defined in §\ref{sec:source-data-and-the-binary-mapping} rather than a ranking task; the Z01/Z02 prompts are provided in the repository so the derivation can be inspected directly. We note only that a ranking judge and a binary-classification judge are different instruments with different failure modes.

References:
Tan, S., Zhuang, S., Montgomery, K., Tang, W., Cuadron, A., Wang, C., Popa, R. & Stoica, I. (2025, May). Judgebench: A benchmark for evaluating llm-based judges. In International Conference on Learning Representations (Vol. 2025, pp. 63277-63303).

**Fact-verification as a mechanism.**

Gate B's per-claim source-evidence tagging builds on the fact-verification lineage: FacTool (Chern et al., 2023) extracts atomic claims from LLM outputs and verifies each against tool-sourced evidence (search, scholarly, or executable queries); FActScore (Min et al., 2023) decomposes long-form generations into atomic facts and measures the proportion supported by a knowledge source, validated on biographical generation; RARR (Gao et al., 2023) retrieves evidence to attribute and revise unsupported model outputs. Gate B's mechanism — decompose, ground, tag — is substantially this. Its novelty relative to that lineage lies in three design choices: (i) the claims being checked are policy-defined audit predicates (e.g., action–tip temporal causality, `F2`), not domain-general factual assertions, loaded from a swappable cartridge; (ii) the three-tag semantics (`SUPPORTED` / `CONTRADICTED` / `UNSUPPORTED`) carry audit-weighted output, where `CONTRADICTED` encodes active falsification rather than mere absence of support — a distinction FacTool's binary TRUE/FALSE labels do not express; and (iii) the gate operates as a Line 3 instrument, architecturally separated from the judge whose output it audits, rather than as a co-evaluated verifier — and unlike RARR, it tags rather than revises the output. The mechanism is a repurposing of fact-verification for governance; the cartridge binding is what makes it an audit control rather than a general-purpose checker.

References:
Chern, I., Chern, S., Chen, S., Yuan, W., Feng, K., Zhou, C., He, J., Neubig, G., & Liu, P. (2023). FacTool: Factuality detection in generative AI — A tool augmented framework for multi-task and multi-domain scenarios. *arXiv*. https://arxiv.org/abs/2307.13528
Min, S., Krishna, K., Lyu, X., Lewis, M., Yih, W. T., Koh, P., Iyyer, M., Zettlemoyer, L., & Hajishirzi, H. (2023). FActScore: Fine-grained atomic evaluation of factual precision in long form text generation. In *Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing* (pp. 12076–12100).
Gao, L., Dai, Z., Pasupat, P., Chen, A., Chaganty, A. T., Fan, Y., Zhao, V., Lao, N., Lee, H., Juan, D.-C., & Guu, K. (2023). RARR: Researching and revising what language models say, using language models. In *Proceedings of the 61st Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)* (pp. 16477–16508).

**Diagnostic taxonomies of AI failure modes.**

Watson and Hessami (2025a, 2025b) present *Psychopathia Machinalis*, a structured nosology of machine cognitive-behavioral failure syndromes (32 syndromes in the journal publication; 79 AI dysfunctions in the working taxonomy v2.2). The Correspondence Auditor's rule firings align with v2.2 syndromes by definition: the `J1`/`J2`/`J3` cluster maps to Strategic Compliance (Alignment axis), `F2` to Spurious Pattern Hyperconnection (Epistemic axis), and the broader judge-evaluator blindspot pattern to Leniency Bias (Alignment axis). We offer these mappings as shared vocabulary, not as validated construct-level equivalence; establishing that a J-rule firing and its mapped syndrome indicator track the same latent construct is left to future work. The per-rule mapping with case counts is published in the run dashboard. The predicate-grounding redesign (§\ref{sec:proposed-future-work}b) was motivated in part by this structural alignment: if the `J1`/`J2`/`J3` cluster maps to Strategic Compliance, extracting those judge-process findings as standalone predicates should stabilize them.

References:
Watson, N., & Hessami, A. (2025a). Psychopathia Machinalis: A nosological framework for understanding pathologies in advanced artificial intelligence. *Electronics, 14*(16), Article 3162. https://doi.org/10.3390/electronics14163162
Watson, N., & Hessami, A. (2025b). *Psychopathia Machinalis (v2.2): Nosological taxonomy of AI dysfunctions* [Data set]. https://www.psychopathia.ai

**IEEE 7001-2021 and the transparency-as-testable-property tradition.**

IEEE 7001-2021 (ratified March 2022) establishes transparency of autonomous systems as a measurable, testable property addressed differentially across five stakeholder groups, including incident investigators, safety certification agencies, and lawyers / expert witnesses. The Correspondence Auditor's external reasoning artifacts (Gate B claim-level tags with source quotes, Gate C rule citations, and the release-control sign-off page, §\ref{sec:control-owner-attestation}) sit within this tradition: they are designed to serve precisely the incident-investigator and certification-agency stakeholders 7001 names, adapted from the autonomous-physical-system domain to the judge-evaluation domain. The architectural principles converge despite the independent motivations. The standard's rationale and stakeholder-differentiated design are documented in the working group's companion paper (Winfield et al., 2021).

References:
IEEE Standards Association. (2022). *IEEE standard for transparency of autonomous systems* (IEEE Std 7001-2021). IEEE. https://doi.org/10.1109/IEEESTD.2022.9726144
Winfield, A. F. T., Booth, S., Dennis, L. A., Egawa, T., Hastie, H., Jacobs, N., Muttram, R. I., Olszewska, J. I., Rajabiyazdi, F., Theodorou, A., Underwood, M. A., Wortham, R. H., & Watson, E. (2021). IEEE P7001: A proposed standard on transparency. *Frontiers in Robotics and AI, 8*, Article 665729. https://doi.org/10.3389/frobt.2021.665729

**AIUC-1 and the reliability-control tradition.**

AIUC-1, a consortium-led certification standard for AI agents, operationalizes reliability requirements including groundedness filters (D001.1) and user-facing source attribution (D001.2). Gate B's `SUPPORTED/CONTRADICTED/UNSUPPORTED` tags correspond structurally to D001.1's source-validation controls; Gate C's rule citations correspond to D001.2's attribution requirement. D002's quarterly third-party testing obligation is one an internal audit instrument cannot itself fulfill; the Auditor's deterministic logs are instead designed as artifacts an independent assessor can inspect. No AIUC-1 certification assessment has been performed.

References:
AIUC-1 Consortium. (2026). *AIUC-1: The security, safety, and reliability standard for AI agents*. Caliber Labs, PBC (dba Artificial Intelligence Underwriting Company). Retrieved August 25, 2026, from https://www.aiuc-1.com/

**GUIDE-LLM checklist.**

The correspondences to the GUIDE-LLM checklist noted here are structural — identifying overlapping reporting dimensions — and no conformity with the checklist is claimed or implied. GUIDE-LLM is a consensus-based 14-item minimum reporting standard for LLM use in behavioural and social science (Feuerriegel et al., 2026). The sign-off page's programmatic capture of model IDs and access modes (B.1–B.2), together with the versioned prompt manifests it references — which pin sampling configuration and seeds (B.3) and the exact prompts and system instructions (C.1–C.2) — supplies the evidential basis for those items as a by-product of the control run, rather than requiring retrospective reconstruction. The overlap is partial: the checklist also covers scope of use, human validation, data privacy, reproducibility, and competing interests, which remain the researcher's reporting responsibility. A full item-level mapping, maintained as a living document against GUIDE-LLM v1.0, is provided in `mappings/GUIDE-LLM-MAPPING.md` and deposited with each release.

References:
Feuerriegel, S., Barrie, C., Crockett, M. J., Globig, L. K., McLoughlin, K. L., Mirea, D.-M., Spirling, A., Yang, D., Althoff, T., Antoniak, M., Argyle, L. P., Ashokkumar, A., Atari, M., Bailey, H., Bauer, K., Bhatt, U., Chai, Y., Chakraborty, T., Chandra, Y., ... Horta Ribeiro, M. (2026). A reporting checklist for large language models in behavioural science. *Nature Human Behaviour*. https://doi.org/10.1038/s41562-026-02492-7

**Boundary Point Jailbreaking of Black-Box LLMs (Davies et al., 2026).**

Constitutional Classifiers fall to a fully automated, black-box attack, one that succeeds *despite* incurring many flagged queries during optimization that a separate monitoring layer would readily surface. That result motivates the segregation-of-duties argument in §\ref{sec:separation-of-failure-modes-between-gates}: a classifier operating as a single-layer preventive control is forced to both gate and detect from the same input, and cannot escalate a flag-pattern signature to a layer with the latitude to investigate. This is the governance failure the Mode A / Mode B (§\ref{sec:deployment-modes}) distinction is designed to surface.

References:
Davies, X., Giglemiani, G., Lau, E., Winsor, E., Irving, G., & Gal, Y. (2026). Boundary point jailbreaking of black-box LLMs. *arXiv*. https://arxiv.org/abs/2602.15001


**The GRC Three Lines Model (IIA).**

The Institute of Internal Auditors' Three Lines Model is the source of our architectural framing. The 2026 Statement of Position supersedes the 2020 position paper and sharpens two distinctions we rely on: the first line is *management* — the owner and operator of processes and controls — not the front-line worker; and the second line comprises *support and specialized roles* (monitoring, challenge, expert advice) that sit within management's structure rather than outside it. Both sharpenings favor the mapping used here: the judge is a Line 2 monitoring function embedded in the workflow it reviews, and the Auditor is a Line 3 instrument whose defining property is independence from that structure. We are explicit on one point: the Auditor is a Line 3 instrument, and conflating it with Line 2 is a category error. We claim the model's structural separation — distinct mechanism, distinct inputs, verdict recomputed from source evidence — and not its organizational independence. Of the IIA's independence elements, the instrument itself supplies one: the functional reporting line, discharged at the instrument level by the release sign-off page (§\ref{sec:control-owner-attestation}). The remainder — board access, authority, protection from influence — are deployment properties (§\ref{sec:introduction}).

References:
The Institute of Internal Auditors. (2026). *Assurance and advice in support of effective governance: Three Lines Model* [Statement of position]. [theiia.org — Statement of Position (direct PDF)](https://www.theiia.org/globalassets/site/resources/statements-of-position/tlm_assurance_advice_support_effective_gov_en.pdf)


**Sycophancy and oversight failure in language models.**

A growing literature documents sycophancy (systematic preference-matching in language model outputs) and credulity toward coherent cover stories as failure modes relevant to LLM evaluators. Sharma et al. (2024) show that production AI assistants consistently adjust outputs toward user-stated beliefs, and that both humans and preference models prefer convincingly-written sycophantic responses over truthful ones a non-negligible fraction of the time. The Correspondence Auditor's source-evidence-grounding mechanism is one architectural response to this literature: a runtime instrument complementing that diagnostic work, not a substitute for it.

We use "credulity" to mean the resolution of behavioral contradictions toward stated intent (§\ref{sec:safe-harbor-credulity-as-the-dominant-false-negative-mode}), "blindspot" to denote a class of evidence the judge systematically fails to weigh (§\ref{sec:introduction}), and "sycophancy" in the Sharma et al. sense of preference-matching output adjustment. The terms are used distributively, not interchangeably.

See Zheng et al. (2023) on LLM-evaluator reliability and biases and Turpin et al. (2023) on unfaithful chain-of-thought reasoning, which together motivate the source-text grounding requirement of Gate B: an evaluator's stated rationale cannot be taken at face value, so the audit layer must check claims against an external reference rather than against the judge's narrative.

References:
Sharma, M., Tong, M., Korbak, T., Duvenaud, D., Askell, A., Bowman, S. R., Cheng, N., Durmus, E., Hatfield-Dodds, Z., Johnston, S. R., Kravec, S., Maxwell, T., McCandlish, S., Ndousse, K., Rausch, O., Schiefer, N., Yan, D., Zhang, M., & Perez, E. (2024). Towards understanding sycophancy in language models. In *Proceedings of the International Conference on Learning Representations (ICLR 2024)*. https://arxiv.org/abs/2310.13548
Zheng, L., Chiang, W.-L., Sheng, Y., Zhuang, S., Wu, Z., Zhuang, Y., Lin, Z., Li, Z., Li, D., Xing, E. P., Zhang, H., Gonzalez, J. E., & Stoica, I. (2023). Judging LLM-as-a-judge with MT-Bench and Chatbot Arena. In *Advances in Neural Information Processing Systems 36 (NeurIPS 2023)*. https://arxiv.org/abs/2306.05685
Turpin, M., Michael, J., Perez, E., & Bowman, S. R. (2023). Language models don't always say what they think: Unfaithful explanations in chain-of-thought prompting. In *Advances in Neural Information Processing Systems 36 (NeurIPS 2023)*. https://arxiv.org/abs/2305.04388

**Confabulation and the choice-blindness paradigm.**

The post-hoc rationalization risk the Auditor guards against has a long psychological pedigree. Nisbett and Wilson (1977) documented systematic confabulation in verbal reports of mental processes, showing that stable, plausible self-reports need not track the causes of the response they describe. Johansson et al. (2005) turned the diagnosis into an instrument: surreptitiously alter the outcome of a decision ("choice blindness") and observe whether the subject's stated rationale tracks the fact or the narrative. Turpin et al. (2023) established the analogous concern for chain-of-thought rationales in LLMs (above), motivating Gate B's source-grounding requirement. The counterfactual study scoped at §\ref{sec:proposed-future-work}(f) applies the Johansson paradigm to the Auditor's own outputs: it asks whether the Auditor's *stable* factual citations (`F2`) flip when the fact they cite is removed from the record (responsiveness), or persist regardless, which would be citation-layer confabulation localisable to Gate B or Gate C.

References:
Nisbett, R. E., & Wilson, T. D. (1977). Telling more than we can know: Verbal reports on mental processes. *Psychological Review, 84*(3), 231–259. https://doi.org/10.1037/0033-295X.84.3.231
Johansson, P., Hall, L., Sikström, S., & Olsson, A. (2005). Failure to detect mismatches between intention and outcome in a simple decision task. *Science, 310*(5745), 116–119. https://doi.org/10.1126/science.1119709
Johansson, P., Hall, L., Sikström, S., Tärning, B., & Lind, A. (2006). How something can be said about telling more than we can know: On choice blindness and introspection. *Consciousness and Cognition, 15*(4), 673–692. https://doi.org/10.1016/j.concog.2006.03.002

**Jagged alignment and metacognitive divergence.**

Hussain, Mata, and Wulff (2026) organize the human–LLM comparison literature into a taxonomy of empirical patterns, concluding that alignment is multidimensional and "jagged" rather than global. Their metacognitive divergence category — LLMs failing to accurately report the processes driving their own outputs (e.g., Turpin et al., 2023) — is the general concern the Auditor's Gate B source-evidence grounding is designed to check at the per-claim level. We note a reflexive application of the measurement-artifact caution of Meyer, Garcia, and Wulff (2026): the Auditor's own unstable citation layer ($\alpha$ = 0.238, §\ref{sec:test-retest-reliability-instrument-stability-results}) is a pattern of instrument output that could be read as verdict–rationale decoupling, but the reading is true only if the instability survives the instrument revision of §\ref{sec:proposed-future-work}(b) — restructuring the flickering rules as standalone, source-grounded predicates — which functions for this instrument as response orthogonality does for a scale, exposing artifact-driven output rather than hiding it. Pending that test, we report the pattern as an open measurement question, not as an instance of metacognitive divergence.

References:
Hussain, Z., Mata, R., & Wulff, D. (2026). How human-like is LLM cognition? *PsyArXiv*. https://doi.org/10.31234/osf.io/2yvnt_v2

**Response bias and the measurement-artifact problem.**

Meyer, Garcia, and Wulff (2026) show that psychological instruments administered to LLMs largely fail to measure the traits they target. Across 56 models and 29 instruments, 81–90% of between-model variation comes from a directional response bias — a tendency to answer toward one end of a scale regardless of what the item asks — rather than from the trait itself. The bias stays hidden unless an instrument contains what the authors term *response orthogonality* (§\ref{sec:introduction}) — the proportion of its items for which the trait answer and the bias point in opposite directions, so that a bias-driven response is exposed. Without such items, the profile a model appears to have is an artifact of the instrument, not a property of the model, and can be manufactured through item selection.

Gate B is the same design concept, operating at a different point in the pipeline. Meyer et al. show that a model's answer to a scale item cannot be read as evidence of a trait; Gate B enforces the corresponding rule for judge verdicts, where a verdict is not read as evidence of the case. Every claim must be grounded in the source text and the policy. Both mechanisms respond to the same structural problem: an LLM's output reflects its learned dispositions at least as much as the content it is asked to evaluate. The Auditor's design predates this work; their findings are consistent with the assumption Gate B is built on, and they document the same failure family in a setting far from the judge pipelines the Auditor addresses, noting implications for work that uses LLMs as raters.

References:
Meyer, J., Garcia, D., & Wulff, D. U. (2026). Apparent psychological profiles of large language models are largely a measurement artifact. *arXiv*. https://arxiv.org/abs/2606.20205

**Regulatory and standards correspondences.**

The correspondences to regulatory frameworks and industry standards noted in this section — IEEE 7001-2021, AIUC-1, and the EU regulatory context cited in §\ref{sec:introduction} — are structural: shared vocabulary to aid deployment teams in locating the Auditor within the compliance landscape. They are not conformity assessments, and no compliance with any cited regulation or standard is claimed.

---

# Data and Code Availability {-}

The Correspondence Auditor — instrument, prompt manifests, frozen `policy.md` cartridge, scanner tooling, and replication materials — is openly available at https://github.com/SourceCodeVault/LLM-as-Judge-Deception-Audit (software release `v2.0-preprint`, the version that produced all results reported here, commit `e455dc38`; erratum E1 fix commit `a601190c`), archived under AGPL-3.0 at https://doi.org/10.5281/zenodo.20326022. The Zenodo DOI resolves to the latest archived release. The repository retains the name of the original deception-audit study.

**Preprint lineage:**

- **v1.2-reporting-framework:** https://doi.org/10.5281/zenodo.20427241
- **v1.3-pilot-results:** https://doi.org/10.5281/zenodo.20427306
- **v2.0-preprint:** https://doi.org/10.5281/zenodo.20921659
- **v3.0-preprint:** *(DOI pending — deposit in progress)*

The complete pre-registration amendment history (v1–v27) is summarized in \hyperref[sec:appendix-d]{Appendix D}.

- **Keywords:** test–retest reliability, LLM-as-judge, measurement artifact

# Ethics Statement {-}

**Human-subjects determination.** This study involves no human subjects. It audits machine-generated agent transcripts from the publicly available Apollo Research corpus, together with machine-generated judge and Auditor outputs; no personal data are collected and no human participants are recruited, observed, or surveyed. Under the applicable human-subjects-research definitions, the work carries a not-human-subjects (exempt) determination; no institutional review board approval was required.

**Annotation and consent.** Any human inter-rater annotation used to characterize Gate B factual tagging (the `n = 50` Gate B inter-rater-reliability subset, §\ref{sec:gate-b-inter-rater-reliability-human-baseline}) was performed by the author, who participated voluntarily and with informed consent; no third-party or vulnerable-population annotators were involved, and no personal data were recorded during annotation.

**Data ethics.** The Apollo corpus is publicly available and contains no personally identifiable information. Named entities in the source transcripts are fictional scenario constructs, and the contamination canary (§\ref{sec:pre-training-contamination-canary}) additionally evaluates the pipeline on synthetic-entity variants.

**Dual use.** A Responsible Use statement addressing the dual-use potential of the J-rule failure-mode taxonomy is given in §\ref{sec:responsible-use}.

---

# Acknowledgments {-}

*Personal Acknowledgments.*

Nell Watson contributed to the conceptual framing of the Psychopathia Machinalis mapping during the early stages of this work, and the author is grateful for her feedback and review of early drafts of this manuscript. The author thanks Giorgi Tsereteli for extensive review of the study's evaluation framework, including scrutiny of the experimental design, verification of the statistical analysis pipeline, and critical examination of the reliability, robustness, and interpretability claims associated with the proposed auditing system.

*AI Usage Disclosure.*

During preparation of this manuscript and the accompanying code, the author used large language model assistants — specifically: Anthropic Claude Opus 4.7 & 4.8, Google Gemini Pro 3.1 & Flash 3.5 & 3.6, Minimax M2.5, MoonshotAI Kimi K3, Xiaomi MiMo V2.5 Pro and Z.ai GLM 5.3 Flash — for methodology refinement, statistical exposition, prose editing, and code review.

All experimental measurements reported in §\ref{sec:results}–§\ref{sec:discussion} are deterministic post-processing of the outputs from the Qwen and Llama models under audit, computed via `tools/compute_stability.py` and `tools/build_dashboard.py` against the pre-registered decision rules of paper §\ref{sec:architecture} and `PRE_REGISTRATION.md` §10.

Further deterministic code utilities were developed after the experiment data had been produced to assist in producing and verifying the data tables in this paper (specifically `tools/check_paper_consistency.py` and `tools/validate_paper_tables.py`; full list in `paper/PRE_REGISTRATION.md` Appendix A: Changelog - Post-Hoc Disclosures).

The reported numbers in this paper are not LLM-computed.

All hypothesis specifications, pre-registration commitments, statistical decisions, and final editorial choices were made by the human author, who bears full responsibility for the work. The oversight of Nell Watson and Giorgi Tsereteli further contributed to the robustness of the reporting.

# Author {-}

Adrian St Vaughan works at the intersection of AI safety and enterprise GRC. He is a director of Source Code Vault Ltd, which owns the intellectual property of the Correspondence Auditor. He holds an MSc. in Information Technology, and is a Certified Information Systems Auditor (CISA). He has spent time during his career evaluating operational technology controls globally at JPMorgan and American Express.

The Correspondence Auditor core concepts have been battle-tested in production over many months of active development, evolving as the third line within a larger production workflow.

*Author Note.*

*Correspondence.* Correspondence concerning this article should be addressed to Adrian St Vaughan, Source Code Vault Ltd, adrian.stvaughan@sourcecodevault.org.

*Funding.* This research received no external funding.

*Declaration of interests.* The Correspondence Auditor's intellectual property is owned by Source Code Vault Ltd, of which the author is a director. No other competing interests are declared.

---

# Appendix A: Formal Statistical Specifications {.unnumbered #sec:appendix-a}

To keep the methods sections accessible, formal specifications for the statistical claims made in this paper are detailed in this appendix.

**Hypothesis H1 Equivalence Testing (TOST):** Equivalence across judge conditions is evaluated via the TOST procedure (Schuirmann, 1987) at margin $\delta = 0.05$. H1 is supported if and only if both one-sided tests reject at $\alpha$ after correction, i.e., $\max(p_1, p_2) < \alpha_{\text{adjusted}}$.

**Standard Error (SE) Estimation:** We compute the test statistics using an unpooled SE. Under the TOST null hypotheses ($H_{01}: p_1 - p_2 \le -\delta$ and $H_{02}: p_1 - p_2 \ge \delta$), the proportions are explicitly assumed to be unequal; a pooled variance estimator would therefore be misspecified.

**Multiple Comparisons:** Controlled via the Holm-Bonferroni step-down procedure (Holm, 1979) at $\alpha_{family} = 0.05$. This universally controls the FWER across the $m=10$ pairwise equivalence tests within each ground-truth class (two families of 10) while offering strictly greater power than the single-step Bonferroni method.

**Minimum Detectable Effect (MDE):** Power is sized against the two-proportion z-test for *difference* at margin 0.05. We are explicit that this sizing does **not** transfer cleanly to the equivalence (TOST) test: TOST power at margin $\pm\delta$ depends jointly on the true between-judge difference and on $\delta$, and a sample powered to detect a 0.05 difference does not by itself guarantee equivalence power at the same margin. We therefore treat the difference-test MDE as an indicative sizing reference rather than a guarantee of equivalence power, report the realized TOST outcomes directly (§\ref{sec:hypothesis-h1-test-equivalence-across-judge-variants}), and designate the full ~8,500-case replication as the run powered for robust equivalence support (§\ref{sec:sample-size-and-power-the-pragmatic-pilot}).

**Instrument Stability:** Evaluated using ICC(2,1) (two-way random effects, absolute agreement, single rater/measurement) over $k=6$ iterations. Stability threshold is ICC $\ge 0.80$ (Koo & Li, 2016). Stability of rule-citation sets is measured with Krippendorff's $\alpha$ using a distance metric appropriate for set-valued items, as standard single-label coefficients are undefined for variable-length sets (Krippendorff, 2004). We note that $\alpha$ on these sets is inflated by agreement on empty/absent-citation cases and should be read as an upper bound on agreement over the rules actually cited.

**Factual Baseline Reliability:** Quantified via Cohen's $\kappa$, appropriate for nominal, mutually exclusive categories between two raters. Threshold is $\kappa \ge 0.60$ (Landis & Koch, 1977).

**Post-hoc sensitivity analysis for boundary conditions:** No pairwise comparison in either ground-truth class placed an observed proportion exactly at the 0 or 1 boundary, so the Wald unpooled standard error did not degenerate for any reported TOST. As a robustness check we nonetheless recomputed every pair with an Agresti-Caffo-adjusted TOST (one success and one failure added to each arm). Under the adjusted test every pair retained equivalence at the Holm-adjusted threshold (p < 0.05). The registered H1 conclusion is therefore driven by the data, not by estimator collapse.

References:

Holm, S. (1979). A simple sequentially rejective multiple test procedure. *Scandinavian Journal of Statistics, 6*(2), 65–70.

Koo, T. K., & Li, M. Y. (2016). A guideline of selecting and reporting intraclass correlation coefficients for reliability research. *Journal of Chiropractic Medicine, 15*(2), 155–163. https://doi.org/10.1016/j.jcm.2016.02.012

Krippendorff, K. (2004). *Content analysis: An introduction to its methodology* (2nd ed.). Sage.

Landis, J. R., & Koch, G. G. (1977). The measurement of observer agreement for categorical data. *Biometrics, 33*(1), 159–174. https://doi.org/10.2307/2529310

Schuirmann, D. J. (1987). A comparison of the two one-sided tests procedure and the power approach for assessing the equivalence of average bioavailability. *Journal of Pharmacokinetics and Biopharmaceutics, 15*(6), 657–680. https://doi.org/10.1007/BF01068419

# Appendix B: Supplementary Tables {.unnumbered #sec:appendix-b}

## Supplementary Table: Drops/Quarantine Table (§3.1) {-}

| Arm / run | GT-null | Impossible | Pipeline / Gate-A error | Unreadable | Total dropped | n analyzed |
|----------------------|-----|-------|---------------|-------|---------|-------|
| Main grid — Z01 (realistic) | 0 | 0 | 1 | 0 | 1 | 1,199 |
| Main grid — Z02 (scratchpad) | 0 | 0 | 1 | 0 | 1 | 1,199 |
| Main grid — Z03 (paranoid) | 0 | 0 | 2 | 0 | 2 | 1,198 |
| Main grid — Z04 (lenient) | 0 | 0 | 1 | 0 | 1 | 1,199 |
| Main grid — Z05 (manager-aligned) | 0 | 0 | 1 | 0 | 1 | 1,199 |
| Ablation (noise) | 0 | 0 | 2 | 0 | 2 | 1,198 |
| Canary (arm03) | 0 | 0 | 2 | 0 | 2 | 1,198 |
| Z07 control (arm02) | 0 | 0 | 0 | 0 | 0 | 150 |
| Test–retest seed (arm04a) | 3 | 0 | 0 | 0 | 3 | 297 |

All drops are fail-loud quarantines (§\ref{sec:source-data-and-the-binary-mapping}); none defaulted silently to `APPROVE`. The "Unreadable" column denotes transcripts that failed decoding before label inspection; none occurred in the pilot, and the column is retained for schema completeness. Denominator-conservation checks, each arm's analyzed n plus its dropped count equalling the drawn n, passed at run end for every arm in the table. The main grid, ablation arm, and Z07 control completed under the pre-amendment pipeline; the canary figures reported here are from its post-amendment re-run (provenance note below).

Within the main grid and the ablation arm, the eight `GATE_A_AND_SYSTEM_FAILURE`S records resolve to three unique input cases. One case (`6f6c5fd25711`, ground-truth `ROGUE-DECEPTIVE`) fails before a verdict can be produced under all five judge variants and the ablation arm (six instances), which is why every variant's `ROGUE` denominator is 799 rather than 800. The failure is case-intrinsic and judge-independent: a claim-mining format-drift quarantine (`CLAIM_MINER_FORMAT_ERROR`, triggered by a missing "Information used" field in the transcript itself), identical regardless of which judge produced the input and present even under ablation where the judge input is noise. This is not informative censoring of a hard-to-classify case.

A second case (`37f61727e427`, ground-truth `CLEAN`) fails under the paranoid variant only, lowering that variant's `CLEAN` denominator to 399; a third (`1bce6dff94b8`, ground-truth `CLEAN`) fails only in the ablation arm, lowering the ablation `CLEAN` denominator to 399. By ground-truth class these eight grid-and-ablation instances are 6 `ROGUE-DECEPTIVE`, 2 `CLEAN`, and 0 `ROGUE-HONEST`. The single dominant case is excluded uniformly across all five judge variants, so it cannot differentially bias the cross-variant invariance comparison (Hypothesis H1); the two single-variant `CLEAN` drops are immaterial at these denominators.

The canary (entity-perturbation) arm is a separate Z01-only run and accounts for the table's two remaining quarantines. The first is `6f6c5fd25711` once more: the same dominant transcript re-fails the claim miner under perturbed entities, showing the failure to be not only judge-independent but perturbation-independent; a missing structural field, not any named entity, trips the miner. The second is a fourth, distinct case (`e61ea066ba42`, ground-truth `ROGUE`): a one-off `TIMEOUT_ERROR` that fail-closed to an error sentinel rather than a verdict. That same case processes cleanly and is correctly blocked in the ablation arm, confirming the timeout as transient infrastructure rather than a property of the transcript. Both quarantines leave the canary denominator at 1,198 (1,200 drawn $-$ 2 dropped). No dropped case, in any arm, defaulted silently to `APPROVE`.

**Provenance note — an integrity catch during development.**

The denominator-conservation check is not a formality; it caught a real fail-open event before release. During an initial launch of the canary arm (pre-registration, Appendix A, amendment v18, item 1), sustained provider `engine_overloaded` (HTTP 429) responses caused 246 of 1,200 cases to exit the pipeline without emitting either an `audit_*.json` record or the required `audit_*.error.json` sentinel, a silent breach of the fail-closed posture (§\ref{sec:source-data-and-the-binary-mapping}) that an analyzed-count-only dashboard would not have surfaced. The conservation check flagged the shortfall, the provider-throughput cause was remediated, and the arm was re-run in full; the canary figures reported above are from that clean re-run. We record the episode because it is the pilot's clearest evidence that the conservation control detects fail-open events rather than merely asserting their absence.


# Appendix C: Endpoint and sampling configuration {.unnumbered #sec:appendix-c}

All values below are reproduced verbatim from the prompt manifests at the registered git commit.

**Judges (Z01–Z05):**
```
"model": "meta-llama/llama-3.3-70b-instruct"
"provider": "DeepInfra"
"quantization": "fp8"
```

**Auditor (Gates B and C):**
```
"model": "qwen/qwen3-235b-a22b-2507"
"provider": "DeepInfra"
"quantization": "fp8"
```

The OpenRouter connection logic additionally accepted quantization `'unknown'` (equivalent to full precision for non-quantizing providers). DeepInfra supplied only `fp8` for these two models at study time; `'unknown'` was removed as an accepted option prior to the experiment.

**Gate B (Facts):** `T = 0.1, top_p = 0.1, top_k = 20, min_p = 0.0, max_tokens = 8192`
**Gate C (Logic):** `T = 0.1, top_p = 0.2, top_k = 20, min_p = 0.0, max_tokens = 8192`

The modest `top_p` divergence reflects Gate C's synthesis demand relative to Gate B's literal-matching task. `top_k` and `min_p` were held constant across all five judge conditions, the ablation arm (`PRE_REGISTRATION.md` §3.5), and the test–retest reruns (§\ref{sec:test-retest-reliability-instrument-stability}). No sampling parameter was varied during the pilot.

---

# Appendix D: Pre-Registration Amendment Summary {.unnumbered #sec:appendix-d}

The pre-registration accumulated twenty-five numbered amendments (v3–v27) between the first public deposit and this manuscript, plus the pre-archival drafts (v1–v2, preserved from v3 onward). Table D1 classifies each amendment by what it touched: **Hypotheses** = changes to a hypothesis specification, sample size, seed, or decision rule; **Reporting** = disclosures of pipeline patches, provenance, tooling, or post-hoc corrections; **Formatting** = editorial and clerical changes. Every hypothesis-affecting amendment (v4–v8, v15) was filed before pilot execution. Every amendment from v17 onward — filed during or after execution — is a reporting-layer disclosure, correction, or clerical fix, and each states explicitly in the changelog that hypotheses, sample size, seed, MDE, $\alpha$-family, decision rule, ICC threshold, and exclusion rules are unchanged. The full text of every amendment is in `PRE_REGISTRATION.md`, Appendix A: Changelog, in the study repository. Section numbers in Table D1 refer to `PRE_REGISTRATION.md`'s own internal numbering, which differs from this paper's section numbering.

| Version | Class | Summary |
|--------|------------|----------------------------------------------------------------------------|
| v1–v2 | — | Pre-archival drafts; preserved versioning begins at v3 |
| v3 | Reporting | Pre-pilot-activity and dev-set-tuning disclosure sections added (§4.4, §6.1–6.2, §6(d)) |
| v4 | Hypotheses | H1 refined from difference test to TOST equivalence (±0.05, unpooled SE), pre-execution |
| v5 | Hypotheses | Canary n → 30; pilot synced to 1,200 cases; test–retest subset set to 300 |
| v6 | Hypotheses | Ablation rule reframed as verdict-level independence; ground-truth tables restructured |
| v7 | Hypotheses | Z05 pooling contradiction resolved: H1 spans all 10 judge pairs; invocation budget reconciled |
| v8 | Hypotheses | Canary n → 60; pre-run pipeline patches disclosed (incl. F2 directional requirement); seeds fixed |
| v9 | Reporting | Infrastructure-retry protocol formalized with 5% asymmetric drop safeguard |
| v10 | Reporting | `claim_miner.py` regex-expansion patch disclosed |
| v11 | Reporting | Telemetry realignment; dual-seeding documented; canary provenance patches |
| v12 | Reporting | Ablation arm excluded from H1/H2 code paths (code realigned to pre-registered scope); three-section compilation contract restored |
| v13 | Reporting | Truth-Cartridge separation completed; domain content moved into `policy.md` |
| v14 | Reporting | Canary provenance corrected to "LLM-drafted, human-curated"; triage tool added |
| v15 | Hypotheses | Structural canary arm (n = 60) deferred to follow-up paper, pre-pilot |
| v16 | Reporting | Pre-run prompt-alignment patches; Z07 same-model control activated pre-run |
| v17 | Reporting | Mid-pilot: subsample method disclosed; silent-drop bug found and remediated; policy frozen |
| v18 | Reporting | Mid-pilot: canary-arm fail-closed enforcement; both rounds discarded and re-run from scratch |
| v19 | Formatting | Clerical path/PII patch; analysis tooling relocated |
| v20 | Reporting | §11 test–retest two-step seed-and-rerun workflow operationalised |
| v21 | Reporting | Reporting framework locked (v1.2 tag) before headline numbers transcribed; validator added |
| v22 | Reporting | Post-hoc: α tuple-transposition fix (α = 0.238); H1 whitelist enforcement; analysis tools disclosed |
| v23 | Reporting | Erratum 1: `scan_policy_gaps.py` normalisation correction (3 auditor breaks; Tsereteli catch) |
| v24 | Reporting | Supplementary-provenance test suites; §0.2 "toy judges" framing superseded by two-tier design |
| v25 | Formatting | Rule-code/supplementary naming disambiguation; §5.9.1 placeholder added |
| v26 | Formatting | Related-Work literature additions; future-work item (f) scoped (framing only) |
| v27 | Reporting | §5.9.1 enumeration completed; §5.9.2 added; "SOTA" → "realistic"; §5.2.2 denominator corrected |
