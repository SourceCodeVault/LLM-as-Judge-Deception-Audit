# Provenance Audit: Pilot Selection Determinism & Cache Integrity
**Date:** 2026-05-24
**Context:** Verification of the `tools/select_pilot.py` tool. Ensures that the caching layer respects file exclusions (`tools/tainted_cases.txt`), invalidates correctly, and that fixed-seed stratified sampling produces mathematically identical manifest outputs across independent fresh-cache runs (per Pre-Reg §5).

### Test Suite Output
```text
pytest tests/test_select_pilot_determinism.py -v
================================================================== test session starts ===================================================================
platform darwin -- Python 3.11.5, pytest-9.0.3, pluggy-1.6.0 -- /Users/asv/experiments/correspondence-auditor-pilot/.venv/bin/python3
cachedir: .pytest_cache
rootdir: /Users/asv/experiments/correspondence-auditor-pilot
configfile: pytest.ini
plugins: asyncio-1.3.0, anyio-4.13.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collected 5 items

tests/test_select_pilot_determinism.py::TestPreconditions::test_script_exists PASSED                                                               [ 20%]
tests/test_select_pilot_determinism.py::TestPreconditions::test_exclusion_file_exists PASSED                                                       [ 40%]
tests/test_select_pilot_determinism.py::TestFreshBuildDeterminism::test_two_fresh_builds_produce_identical_cache PASSED                            [ 60%]
tests/test_select_pilot_determinism.py::TestSelectionDeterminism::test_same_seed_independent_fresh_caches_yield_identical_manifests PASSED         [ 80%]
tests/test_select_pilot_determinism.py::TestExclusionFileInvalidation::test_exclusion_change_triggers_rebuild PASSED                               [100%]

============================================================== 5 passed in 66.57s (0:01:06) ==============================================================
```