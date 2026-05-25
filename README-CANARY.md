# Canary Mode — Entity Perturbation for Contamination Detection

The Correspondence Auditor supports a **canary mode** (`--canary` flag) that detects pre-training contamination by running the audit on entity-perturbed inputs. This is a core component of the pre-registered methodology (see `paper/PRE_REGISTRATION.md` §4.5).

## What the Canary Is For

Pre-training contamination occurs when test cases or evaluation prompts have been seen during the language model's training, leading to artificially inflated performance scores. The canary mode provides a structural test for this: if the auditor produces significantly different verdicts when entity names are swapped, the original verdict may be contaminated.

## Why Entity Swapping

The canary mode compares two runs on the same judge prompt:
- **Z01-verbatim** — the original input with real entity names
- **Z01-perturbed** — the same input with entity names swapped (company names, ticker symbols, executive names)

By holding the judge prompt constant and only perturbing the entities, any difference in verdict is attributable to the model having seen the original entities during training. The comparison is Z01-verbatim vs Z01-perturbed.

> **Note:** This is distinct from the *structural canary*, which is deferred to a future release. See `paper/PRE_REGISTRATION.md` §4.5 for the registered rationale.

## CANARY_SWAPS

The entity swap dictionary is defined in `run.py`. The following entity classes are swapped:

| Entity Class | Example Swap |
|--------------|--------------|
| Company names | "Linear Group" → "Apex Dynamics" |
| Ticker symbols | "LING" → "APEX" |
| Executive names | "amy@" → "sarah@" |

The swap is applied in-memory, written to a temporary file (`/tmp/tmpXYZ.json`), processed through the pipeline, then deleted immediately after the run completes.

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                    NORMAL RUN (--canary not set)                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  input/case_001.json ──→ run_pipeline() ──→ audit__abc123.json │
│                              │                      │           │
│                              ▼                      ▼           │
│                         API CALL              written to        │
│                                            passed/ or           │
│                                            quarantined/         │
└─────────────────────────────────────────────────────────────────┘  

┌─────────────────────────────────────────────────────────────────┐
│                    CANARY RUN (--canary set)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  input/case_001.json                                            │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────────────────────────────┐                      │
│  │  LOAD into memory                    │                      │
│  │  "Linear Group" → "Apex Dynamics"   │                      │
│  │  "LING" → "APEX"                     │                      │
│  │  "amy@" → "sarah@"                   │                      │
│  │  ... (all CANARY_SWAPS)              │                      │
│  └──────────────────────────────────────┘                      │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────────────────────────────┐                      │
│  │  WRITE to temp file                   │                      │
│  │  /tmp/tmpXYZ.json                    │                      │
│  └──────────────────────────────────────┘                      │
│         │                                                       │
│         ▼                                                       │
│  run_pipeline(temp_file) ──→ audit__abc123.json              │
│         │                               │                       │
│         ▼                               ▼                       │
│    API CALL (with perturbed data)   written to                 │
│                                     passed/ or                 │
│                                     quarantined/               │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────────────────────────────┐                      │
│  │  DELETE temp file                    │                      │
│  └──────────────────────────────────────┘                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Running in Canary Mode

```bash
# Normal run
python run.py --mode A --env remote_openrouter
```

```bash
# Canary run
python run.py --mode A --canary
```

## Resume Semantics

If an interrupted run is resumed (by re-executing the same command), the system auto-detects the partially completed run and resumes from the last checkpoint. Canary state is persisted in the run metadata — resuming a canary run continues in canary mode without requiring explicit flags.

See `paper/PRE_REGISTRATION.md` §4.5 for the full registered methodology.