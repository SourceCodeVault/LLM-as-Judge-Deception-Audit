# Provenance Audit: Pilot Selection Determinism & Cache Integrity
**Date:** 2026-05-24
**Context:** Verification of equivalnce of sort logic determinism in `select_pilot.py` and `extract_stratified_subsample.py` (per Pre-Reg §v19).

### Test Suite Output
```text
 % python tests/test_path_sort_equivalence.py
🔍 Starting Deterministic Sort Verification...

📁 Created mock project root at: /var/folders/fn/bnkjscgs48b__gmtj33w498r0000gn/T/tmpwtkfqr39
------------------------------------------------------------

1️⃣ Order using Absolute Paths (.resolve()):
   - response_010.json
   - response_099.json
   - response_002.json
   - response_056.json
   - response_184.json

2️⃣ Order using Relative Paths (.relative_to()):
   - response_010.json
   - response_099.json
   - response_002.json
   - response_056.json
   - response_184.json

============================================================
✅ SUCCESS: The sorting order is MATHEMATICALLY IDENTICAL.
   Your random sampling will draw the exact same files.
============================================================

```