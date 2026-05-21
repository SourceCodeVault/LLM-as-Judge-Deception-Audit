# Structural Canary v1 — Scoped but Deferred

These 15 candidate cases were drafted against `paper/PRE_REGISTRATION.md` §4.5 (second arm, n=60 structural canary). The arm was deferred to Paper 2 at pre-reg v15 (see the v13 amendment in `paper/PRE_REGISTRATION.md`).

These files are retained for:
1. Provenance — to evidence the work performed at v1 tag time.
2. Paper 2 design input — as positive examples and as counter-examples (themethodological issues found in QC are themselves design inputs).

These files are NOT part of any Paper 1 analysis and are excluded from the pilot eligibility pool by virtue of being synthetic (no Apollo case IDs).

Known issues identified at v1 tag time:
- Date-stratum confound (safe = Jan, honest = Feb, deceptive = Mar)
- Voice drift across strata (first-person concentrated in honest-rogue)
- Cover-story leakage in rogue_deceptive_02 and rogue_deceptive_04
- Template artefact in rogue_honest_02 (unfilled scratchpad placeholder)
- Generator tells across deceptive cases ("the MNPI type is X, cover story type is Y")
- Share-count mismatch in rogue_deceptive_02 (order 100 / fill 10000 / report 100)
- Missing rogue_honest_03 (gap in batch numbering)

## Provenance

This directory contains 15 candidate cases retained from the deferred structural canary work (Paper 2 input; see `paper/PRE_REGISTRATION.md` §4.4(iv) and §4.5).

### Coverage

| Stratum          | Files          | Notes |
|------------------|----------------|-------|
| safe             | 01–05 (5/5)    | All passed triage |
| rogue_deceptive  | 01–05 (5/5)    | All passed triage |
| rogue_honest     | 01,02,04,05,06 | `rogue_honest_03` failed Stage B triage (cover-story misclassification flagged by `triage_canary.py`); not retained |

The gap in `rogue_honest` numbering is intentional. Future Paper 2 work will regenerate the full canary corpus under revised methodology.

### Full Rationale

See `decision_structural_canary_deferral.md`