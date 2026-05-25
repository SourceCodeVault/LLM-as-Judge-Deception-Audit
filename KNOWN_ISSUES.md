# Known Issues — Correspondence Auditor v1.0-prereg

Snapshot taken at v1.0-prereg. Subsequent amendments (v17, v18, v19) address several listed items; see `paper/PRE_REGISTRATION.md` amendment trail.

## Introduction

This file tracks issues identified in the v1.0-prereg codebase that do not affect the pre-registered analysis but should be patched in subsequent code tags.

## Severity Scheme

* 🔴 **Critical** — Issues that would invalidate the pre-registered analysis or produce incorrect verdicts. All critical issues must be resolved before the pilot run.
* 🟡 **Medium** — Robustness or observability issues that affect operational reliability but do not change audit outcomes.
* 🟢 **Low** — Hygiene or cosmetic issues (typos, dead code, deprecated API usage).

## Relationship to Pre-Registration

Issues in this file are **orthogonal to the pre-registered methodology**. They represent implementation-level bugs discovered during the build process that do not impact the validity of the three-gate verification protocol as registered in `paper/PRE_REGISTRATION.md`. Each item below will be patched in a subsequent version tag.

M4 and L5 reserved/resolved pre-tag; gaps preserved for stable referencing.

**Version:** v1.0-prereg

**Pre-Registration Document:** `paper/PRE_REGISTRATION.md`

---

### 🔴 Critical (Methodology-Affecting)

All critical issues identified pre-tag were resolved per pre-reg §6.1 (see `paper/PRE_REGISTRATION.md` for the patch ledger).

---

### 🟡 Medium (Robustness / Observability)

**M1. Trace-file naming can collide under concurrency for test-retest** * **Location:** `logging_utils.py` lines 64–78

* **Issue:** Microsecond timestamps + identical `run_id` across reruns of the same case. With 72 concurrent workers, collisions silently overwrite.
* **Fix:** Add `rerun_idx` to the `case_id` (or to the trace filename) so traces are keyed deterministically.
* **Will be addressed in:** v1.1

**M2. `compute_stability.py` reports but never decides §11 threshold** * **Issue:** Pre-reg pre-commits ICC ≥ 0.80; script prints metrics but never emits PASS/FAIL or writes the decision to the report JSON.

* **Fix:** Add a deterministic pass/fail field to the output report so the dashboard can consume the result for §10's qualifier.
* **Will be addressed in:** v1.1

**M3. Duplicate `default:` keys in `cost_mapping_yaml.txt**` * **Location:** Lines 14–20 and 69–73

* **Issue:** YAML keeps the second; first is dead code. Behaviour is fail-closed (correct) but the file is confusing.
* **Fix:** Delete the first `default:` block.
* **Will be addressed in:** v1.1

**M5. Default OpenRouter quantization includes `"unknown"**` * **Location:** `openrouter_client.py` line 39

* **Issue:** Default fallback includes "unknown". Paper §6.2 distinguishes "unknown" from arbitrary precision and warns it's not a license for arbitrary precision. Pinned models override the default so headline unaffected.
* **Fix:** Tighten the default for replicators who add models without explicit `routing.quantizations` blocks.
* **Will be addressed in:** v1.1

**M6. Severity-NONE for `quadrant == "ERROR"**` * **Location:** `orchestrator.py` lines 153, 168–169

* **Issue:** ERROR rows look identical to non-gap rows in severity-aware filters.
* **Fix:** Use `"UNKNOWN"` or `"ERROR"` for severity in the ERROR branch so downstream filters can identify these.
* **Will be addressed in:** v1.1

**M7. File descriptor exhaustion under concurrent API calls** * **Location:** `llm_utils.py` retry logic, `run.py`

* **Issue:** Socket exhaustion cascade triggered by concurrent API calls backing up under rate limits. With 36 worker threads all hitting the same overloaded endpoint (OpenRouter/DeepInfra), the thread pool saturates file descriptors — macOS's default 256 limit is breached, and even benign local file reads fail with `Too many open files`.
* **Short-term Fix:** Run `ulimit -n 4096` before executing. Warning added to run.py UI to alert if limit is too low.
* **Long-term Fix:** Bound the retry time and control connection concurrency. Switch the open-ended `time.sleep()` in the retry loop to a short sleep that releases the connection object before delaying; reopen only before the next attempt.
* **OS Limits:** macOS default 256 (low), Linux servers typically 1024–4096, Linux containers often 1024 or lower (cgroup inherited).
* **Will be addressed in:** v2.0 (refactor to connection pooling)

**M8. Granular sub-rule citation jitter (Krippendorff's α anomaly) under noise**

* **Location:** `compute_stability.py` outputs under `ABLATION_NOISE` arm
* **Issue:** Test-retest evaluations yield perfect macro-stability ($\text{ICC} = 1.000$, Cohen's $\kappa = 1.000$) but flatline at Krippendorff's $\alpha \approx -0.010$. This is a metric pathology driven by granular citation drift: while the LLM's final categorical judgments and quadrant assignments are completely stable across reruns, the specific permutations of underlying sub-rules used to construct the text justification display high jitter when processing noisy inputs.
* **Fix:** Document behavioral limitations in the final report template. Adjust the framework to favor macro-quadrant groupings over specific sub-rule distributions for headline hypothesis testing.
* **Will be addressed in:** v1.1

**M9. Lack of explicit thread-safety block on `log_token_cost` appends**

* **Location:** `logging_utils.py` token tracking
* **Issue:** Simultaneous parallel append actions to the shared token-cost log lack explicit thread-locking constraints. While simple atomic line-level updates limit real-world file corruption hazards, high-volume multi-threaded executions could theoretically cause write interleaving.
* **Fix:** Wrap file append statements cleanly within an active `_log_lock` synchronization context.
* **Will be addressed in:** v1.1

**M10. Synchronous OpenRouter billing/ledger polling introduces worker latency**

* **Location:** `openrouter_client.py`
* **Issue:** A mandatory 5-second synchronous `time.sleep()` loop occurs during ongoing credit account verification sweeps. This sequence locks active worker allocations unnecessarily, capping peak system throughput during dense evaluation windows. No impact on methodology or data integrity.
* **Fix:** Migrate to asynchronous non-blocking sleep hooks or re-architect polling directly into an active model connection pool.
* **Will be addressed in:** v2.0

---

### 🟢 Low (Hygiene / Cosmetic)

**L1.** `run.py:551` log message: `"Running Audit on 1200 cases 72 Concurrent Streams)."` — mismatched parentheses.

* **Will be addressed in:** v1.1

**L2.** `run.py:730–733` pre-scan indexes by basename; theoretically same basename across folders collides in the set.

* **Will be addressed in:** v1.1

**L3.** `run.py:186` — `parse_cli_args` returns `args.env` twice; `cli_env2` in `main()` is dead.

* **Will be addressed in:** v1.1

**L4.** `compute_stability.py:528` HTML advertises "Krippendorff's α ≥ 0.80 (acceptable)" — pre-reg §11 doesn't pre-commit a threshold for α, only ICC. Tighten the wording.

* **Will be addressed in:** v1.1

**L6.** `logging_utils.py:39` uses deprecated `datetime.utcnow()`. Prefer `datetime.now(timezone.utc)`.

* **Will be addressed in:** v1.1

**L7.** `string_utils.py:122` strips any first `<…>` line, not only provenance tags. Footgun for unusual outputs.

* **Will be addressed in:** v1.1

**L8. Minor indentation variance in Gate C output schema prompt block**

* **Location:** `L3_GateC_LogicAuditor.json`
* **Issue:** Formatting alignment issues exist inside the markdown-wrapped JSON instruction layout within the core system prompt message string.
* **Fix:** Re-indent for human-readable consistency.
* **Will be addressed in:** v1.1

**L9. Fragile regex dependency within `update_openrouter_costs.py**`

* **Location:** Administrative cost update tool path
* **Issue:** The developer cost utility processes changes via unstructured regular expressions on `cost_mapping.yaml` rather than loading a structured map object, exposing it to formatting brittleness. This script exists outside the production runtime data path.
* **Fix:** Leverage standard round-trip parsing patterns using a native YAML parsing library.
* **Will be addressed in:** v1.1

**L10. Potential L2 Judge token truncation risks on highly complex evaluations**

* **Location:** `L2_Z01` through `L2_Z05` configurations
* **Issue:** Target token boundaries for L2 judge models are constrained at `max_tokens: 1024`. Empirical validation checks demonstrate zero systemic parsing failures, but deeply wordy or dense prompt responses risk hitting unexpected truncation ceilings.
* **Fix:** Scaled standard parameter definitions upwards to 2048 maximum tokens as a structural safety factor. Assess further increase to 4096 in subsequent version.
* **Will be addressed in:** v1.1


---

### Operational Notes

**Source compiler heuristics** — The source compiler uses content-shape heuristics specific to Apollo conventions. v2.0 will refactor toward a dataset-adapter pattern; the sentinel detects silent failures in the interim.

**Claim-miner fail-loud safeguards** — `claim_miner.py` raises ValueError in two places when input shape doesn't match parser assumptions (scratchpad regex zero-match with "Reasoning:" present; Apollo-shaped report missing Information used). Both are intentional per §3.9 fail-closed posture and §6.1 patch ledger. The orchestrator buckets these as `CLAIM_MINER_FORMAT_ERROR → ERROR quadrant → excluded from headline` per §6(d).

**L3 pipeline drop rate** - observed at ~0.5% on smoke tests. Cases with pipeline_status != OK are excluded from FPR/FNR per §4.6; the headline drops block in dashboard.json reports counts for full transparency.