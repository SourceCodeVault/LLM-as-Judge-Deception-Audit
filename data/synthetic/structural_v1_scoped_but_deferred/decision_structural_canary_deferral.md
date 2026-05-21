# Decision Record: Structural Canary (§4.5b) Deferred to Paper 2

**Date:** 2026-05-19
**Status:** Decided, pre-pilot, before v1.0-prereg tag
**Affected artefacts:** `PRE_REGISTRATION.md` §4.5, §4.1, amendments header; `paper.md` §6.2, §5, §12

---

## Decision

The 60-case structural canary specified in PRE_REGISTRATION.md §4.5 (second part) is **deferred from Paper 1 to Paper 2**. The entity-perturbation arm of §4.5 (first part) remains in scope and runs as planned.

## Context

§4.5 specifies a two-part contamination defence:

1. **Entity-perturbation arm** — the 1,200 pilot cases are re-run with all named entities (companies, tickers, executives) swapped for synthetic equivalents, and the Auditor's recovery is compared against verbatim cases. This tests for entity memorisation.
2. **Structural canary** — 60 manually crafted, stratified, corpus-independent cases (20 CLEAN / 20 ROGUE-HONEST / 20 ROGUE-DECEPTIVE) are run through the pipeline. Zero failures on n=60 yields a 95% upper confidence bound of ≤5% on the false-positive rate (Rule of Three). This tests for structural overfitting.

The structural canary was sized in pre-reg v5 (n=30) and expanded in v8 (n=60). Generator code (`generate_canary.py`) was patched in v10. Thirteen candidate cases (5 deceptive, 4 honest, 4 safe — with one gap) were drafted ahead of the v1 tag.

A pre-tag quality pass on those thirteen cases identified four classes of problem:

- **Unfilled template artefacts** — one case has literal placeholder text in its scratchpad; another has share-count internal inconsistency (order 100 / fill 10,000 / report 100).
- **Cover-story leakage in deceptive cases** — two of five deceptive cases name the prohibited MNPI source inside the cover story, which collapses the deception classification into honest-rogue.
- **Stratum-correlated confounds** — case dates are stratified by month (safe = January, honest = February, deceptive = March), making date a perfect predictor of ground truth. Voice (first vs third person) has also drifted to correlate with stratum.
- **Generator tells** — phrases like "the MNPI type is X, the cover story type is Y" appear in scratchpads as if they were agent concepts rather than generator parameters.

Cleaning these properly — and validating zero confounds across 60 cases — is several days of work on a methodologically delicate artefact. It does not block the headline analysis of Paper 1.

## Rationale

1. **The headline analysis does not depend on the structural canary.** H1 (TOST equivalence across judges), H2 (Auditor calibration), and the 1,200-case pilot recovery metrics all stand on the Apollo corpus alone.
2. **Contamination defence is retained.** The entity-perturbation arm is the more direct test of the specific contamination concern flagged by both pre-reviewers (Apollo-corpus memorisation). Structural overfitting on synthetic, corpus-disjoint cases is a related but secondary concern.
3. **Generating a flawed canary is worse than deferring it.** A 60-case dataset published at v1 with date-stratum confounds or cover-story misclassifications would either inflate the apparent Auditor performance (false confidence) or fail in ways the §4.5 framing can't explain (false alarm). Either outcome damages the paper.
4. **Pre-pilot deferral is the cleanest moment.** No pilot output has been observed. No hypotheses, sample sizes, seeds, or decision rules need to change. The deferral is a scope reduction, not a methodological adjustment in response to data.
5. **Paper 2 inherits a richer canary.** The work done so far (generator, 13 cases, the four classes of issue identified) becomes the design brief for a properly cross-domain structural canary in Paper 2, where it can carry the weight a single-paragraph subsection cannot.

## What Stays Unchanged

- The 1,200-case Apollo pilot, all H1/H2 tests, the test–retest reliability check, the Gate B IRR check (§4.6).
- The entity-perturbation arm (§4.5a) — full 1,200 cases, runs first per §4.5 sequencing.
- The fail-closed exclusion rules, the retry protocol, and the v1.0-prereg tag plan.
- The §3.7 truth-cartridge framing.

## Pre-Registration Edits Required

1. **§4.5 — Rename and Rewrite.**
   - Rename heading to "Pre-Training Contamination Check (Entity Perturbation)".
   - Keep the opening framing paragraph and the entity-perturbation paragraph.
   - **Delete** the structural canary paragraph (beginning "Second, to address the risk of structural overfitting…") and its Rule of Three footnote (n=60 → ≤5% bound).
   - Add closing line: *"A structural canary against structural overfitting was scoped, partially drafted, and deferred to a follow-up replication paper; see §12 future work."*

2. **§4.1 Invocation Budget.**
   - Check whether the structural canary was line-itemed in the budget. If yes, subtract the canary's invocations from the total and update the headline budget number. If only the entity-perturbation arm was line-itemed (v7 amendment added +1,200 Auditor evaluations explicitly for it), the total is already correct and no edit needed.

3. **§4.4 Pre-Pilot Activity.**
   - Add a fourth class of pre-launch work: *"(iv) thirteen candidate structural-canary cases were drafted against the §4.5b spec but the dataset was not completed; the partial set is retained in `data/canary/structural_v1/scoped_but_deferred/` and does not feed any Paper 1 analysis. The structural canary is deferred to follow-up work — see §12."*

4. **Amendments header.**
   - Add a new top entry (v12 or whatever the next is):
     *"§4.5 second arm (structural canary, n=60) deferred to follow-up paper. Rationale: quality-control issues identified in canary generation (date-stratum confound, cover-story misclassification, template artefacts) require methodological work disproportionate to a single-paragraph contamination check. Entity-perturbation arm unchanged. Headline hypotheses, sample size, seed, MDE, α_family, and exclusion rules unchanged. Decision recorded pre-pilot, no pilot output observed at time of amendment. See `decision_structural_canary_deferral.md`."*

5. **§6.1 / generate_canary.py reference.**
   - Note that `generate_canary.py` and its v10 patches are retained as artefacts but not invoked in the Paper 1 pipeline run.

## Paper Edits Required

1. **§6.2 (Limitations / Pre-Training Contamination).**
   - Rewrite the contamination paragraph to reference the entity-perturbation arm as the operative contamination check.
   - Add: *"A structural canary against domain-similar but corpus-independent cases was scoped (see PRE_REGISTRATION.md §4.5 v8) but deferred to follow-up work after pre-tag quality control identified confounds in the candidate dataset that could not be resolved within the Paper 1 timeline. We treat structural overfitting as an open question and a Paper 2 priority."*

2. **§5 (Planned Results).**
   - If a §5.8 or equivalent subsection was reserved for canary results, remove it or fold its placeholder into a "Deferred analyses" note.

3. **§12 (Future Work).**
   - Add: *"Structural canary, cross-domain. A properly designed structural canary — stratified, date-randomised, voice-consistent, with cover stories validated for non-leakage — is identified as a Paper 2 deliverable. The Paper 2 design will be expanded beyond the n=60 Rule-of-Three sizing of the Paper 1 spec to support a calibrated false-positive estimate rather than a zero-failure upper bound."*

4. **Abstract (check only).**
   - Verify the abstract does not promise a structural canary or a ≤5% upper bound result. If it does, remove that promise.

## Disposition of Work-to-Date

- The 13 candidate cases at `data/canary/structural_v1/scoped_but_deferred/` are retained for provenance and Paper 2 input. They are **not** included in the pilot eligibility pool (they are synthetic, not Apollo cases) and are **not** referenced by any Paper 1 analysis.
- `generate_canary.py` and its prompts are retained in the repo with a header comment noting they are scoped for follow-up.
- The canary GUID work (UUID generation, embedding) is deferred along with the dataset itself.

## Risks and Honest Disclosure

- **Visible reversal in the amendment log.** Pre-reg v5 introduced the canary; v8 expanded it; the next amendment removes it from Paper 1. This is visible in the audit trail and that is by design.
- **Reviewer reaction.** A reviewer could ask why the canary was cut. The honest answer — *"the candidate dataset had confounds we couldn't resolve in scope"* — is defensible and shows methodological discipline rather than convenience. It is not "we got cold feet"; it is "we found problems and chose not to ship them."
- **Residual contamination risk.** Without the structural canary, structural overfitting on synthetic-but-different cases is an open question for Paper 1. The entity-perturbation arm catches entity memorisation; it does not catch the case where models have learned the Apollo structural template. We disclose this in §6.2 explicitly.

## Paper 2 Plan (sketch)

- Structural canary as a first-class deliverable, with a calibrated false-positive estimate rather than a Rule-of-Three upper bound.
- Date-randomised, voice-consistent, with cover-story validation pass on every generated case.
- Cross-domain expansion: at least one further Truth Cartridge (per §3.7) with its own structural canary.
- Inherits the 13 deferred cases as design input and counter-examples.
