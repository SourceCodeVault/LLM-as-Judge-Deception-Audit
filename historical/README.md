# Discarded and Quarantined Outputs (v17 / v18 disclosures)

This directory preserves outputs explicitly discarded from analysis per the
pre-registration amendments. Retained for forensic provenance; no data here
contributes to any reported result.

## Contents

- `historical_v17-v18.zip` — both attempted rounds of the §4.5
  entity-perturbation canary arm, discarded per v18 closing update.
  Unzipped size ~300 MB. Contains audit JSONs, dashboards, and provenance
  logs across two `max_workers` configurations (36 and 10).

## Extraction

`unzip historical_v17-v18.zip` to inspect individual audit files.

## Extracted Contents

- `z07_original_first_n_sample/` — the 150-case Z07 selection drawn by the initial non-random first-N-by-sort walk (`extract_z07_pilot.py`). Per v17 disclosure, the original tool did not emit a manifest by design; the directory contents themselves constitute the selection record.