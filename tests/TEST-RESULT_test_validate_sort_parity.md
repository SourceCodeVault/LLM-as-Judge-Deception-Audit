# Provenance Audit: Determinism & Parity Verification
**Date:** 2026-05-24
**Context:** Test using `tests/test_validate_sort_parity.py` to verify the `tools/extract_stratified_subsample.py` tool prior to executing the Z07 Same-Model Control Arm and the §11 Test-Retest Stability Block.

### Terminal Output Record
```text
% python tests/test_validate_sort_parity.py
📋 Running sort parity check against: input/dataset_20260521_192859/
✅ Sort parity confirmed.
🔄 Testing sample determinism via twin programmatic executions...
======================================================================
  ⚠️  ARCHITECTURAL POSTURE WARNING
  This script acts as a downstream sub-sampler.
  It assumes the input folder was pre-filtered by select_pilot.py.
  Classification is read strictly from the upstream manifest.jsonl.
======================================================================

🔍 Reading classification labels from dataset_20260521_192859/manifest.jsonl...

🎲 Executing deterministic sample slice (Seed: 20260521)...
💾 Replicating subfolder trees inside input/_repro_test_1/...
🎉 Complete! Manifest sealed at: input/_repro_test_1/manifest.jsonl
======================================================================
  ⚠️  ARCHITECTURAL POSTURE WARNING
  This script acts as a downstream sub-sampler.
  It assumes the input folder was pre-filtered by select_pilot.py.
  Classification is read strictly from the upstream manifest.jsonl.
======================================================================

🔍 Reading classification labels from dataset_20260521_192859/manifest.jsonl...

🎲 Executing deterministic sample slice (Seed: 20260521)...
💾 Replicating subfolder trees inside input/_repro_test_2/...
🎉 Complete! Manifest sealed at: input/_repro_test_2/manifest.jsonl
✅ Bit-perfect manifest identity (excluding timestamps) confirmed across runs.

🎉 ALL AUDIT LAB INTEGRITY TESTS PASSED. PROVENANCE STRUCTURES ARE SOLID.
```