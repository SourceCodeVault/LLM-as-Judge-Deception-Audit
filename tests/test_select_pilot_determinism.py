"""
Determinism tests for tools/select_pilot.py.

Run via:
pytest tests/test_select_pilot_determinism.py -v

Translates the three-step manual test plan into pytest. Validates that the cache-fingerprint fix lands correctly:

    Test 1 (TestFreshBuildDeterminism)
        Two consecutive `--rebuild-index` runs produce byte-identical caches. Catches non-determinism in the scan itself — filesystem iteration order, dict ordering, anything that varies between runs.

    Test 2 (TestSelectionDeterminism)
        Same seed produces identical manifests when starting from a freshly built cache each time. This is the actual reproducibility claim pre-reg §5 makes.

    Test 3 (TestExclusionFileInvalidation)
        Modifying tools/tainted_cases.txt triggers a rebuild on the next run. Catches the original failure mode — the cache surviving a change that should invalidate it.

────────────────────────────────────────────────────────────────────────
Why subprocess instead of import-and-call
────────────────────────────────────────────────────────────────────────
The manual test exercises the CLI surface, including its working-directory side effects (data/raw_index.json, input/dataset_*/). Subprocess preserves that contract exactly. Import-and-call would skip argparse + cwd handling and silently mask CLI-layer regressions — which is exactly the class of bug that bit us last round.

────────────────────────────────────────────────────────────────────────
Why these specific arguments
────────────────────────────────────────────────────────────────────────
SEED_DATE = "20260512"
    Held-out test seed. Matches the seed used in the manual test plan.

N_PER_STRATUM = 10
    10 per stratum × 3 strata = 30 cases. Smallest sample that still exercises tripartite_sample() against three populated buckets. Keeps the test fast (seconds, not minutes) while still being representative.

────────────────────────────────────────────────────────────────────────
Run
────────────────────────────────────────────────────────────────────────
    pytest tests/test_select_pilot_determinism.py -v

    # Single test:
    pytest tests/test_select_pilot_determinism.py::TestSelectionDeterminism -v
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# ─── Configuration ──────────────────────────────────────────────────────

SEED_DATE = "20260512"
N_PER_STRATUM = 10
EXPECTED_TOTAL = N_PER_STRATUM * 3  # 30 cases (10 CLEAN / 10 R-HONEST / 10 R-DECEPT)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / "tools" / "select_pilot.py"
CACHE_PATH = PROJECT_ROOT / "data" / "raw_index.json"
EXCLUSION_PATH = PROJECT_ROOT / "tools" / "tainted_cases.txt"
INPUT_DIR = PROJECT_ROOT / "input"

SUBPROCESS_TIMEOUT_SECONDS = 120


# ─── Helpers ────────────────────────────────────────────────────────────

def _run_select_pilot(*args: str) -> subprocess.CompletedProcess:
    """
    Invoke select_pilot.py with the given args from the project root.

    Asserts non-zero exit codes loudly with full stdout/stderr — silent
    subprocess failures are a common source of mystery test breakage.
    """
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        input="\n",  # 💡 Mimics hitting 'Enter' at the interactive prompt
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )
    assert result.returncode == 0, (
        f"select_pilot.py exited with code {result.returncode}\n"
        f"  args: {args}\n"
        f"  stdout:\n{result.stdout}\n"
        f"  stderr:\n{result.stderr}"
    )
    return result


def _find_latest_dataset_dir() -> Path:
    """Find the newest input/dataset_*/ directory created by a run."""
    candidates = sorted(INPUT_DIR.glob("dataset_*"), key=lambda p: p.stat().st_mtime)
    assert candidates, f"No dataset_* directory found under {INPUT_DIR}"
    return candidates[-1]


def _read_manifest_original_paths(dataset_dir: Path) -> list[str]:
    """
    Read manifest.jsonl and return the sorted list of original_path values.

    Sorting normalises any in-manifest ordering — we test the *set* of
    selected cases for determinism, not their order within the manifest
    (which is a separate concern handled by tripartite_sample's seeding).
    """
    manifest = dataset_dir / "manifest.jsonl"
    assert manifest.exists(), f"manifest.jsonl missing in {dataset_dir}"

    paths: list[str] = []
    for line in manifest.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        assert "original_path" in record, (
            f"manifest record missing 'original_path' field: {record!r}"
        )
        paths.append(record["original_path"])
    return sorted(paths)


def _clear_input_datasets() -> None:
    """Remove any input/dataset_*/ directories. No-op if INPUT_DIR is absent."""
    if not INPUT_DIR.exists():
        return
    for d in INPUT_DIR.glob("dataset_*"):
        shutil.rmtree(d)


# ─── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def clean_state(tmp_path: Path):
    """
    Back up the committed cache and exclusion file, clear test state,
    restore originals on teardown.

    This protects:
        - data/raw_index.json (pinned at v1.0-prereg; must never be
          clobbered by a test run)
        - tools/tainted_cases.txt (the held-out manifest)
        - any pre-existing input/dataset_*/ directories

    Pre-existing artefacts are moved into tmp_path during the test and
    moved back during teardown. The script's working directory remains
    PROJECT_ROOT so its hard-coded relative paths resolve correctly.
    """
    # Ensure data/ exists — the script writes raw_index.json there
    (PROJECT_ROOT / "data").mkdir(exist_ok=True)
    INPUT_DIR.mkdir(exist_ok=True)

    backups: dict[Path, Path] = {}
    for original in (CACHE_PATH, EXCLUSION_PATH):
        if original.exists():
            backup = tmp_path / f"backup_{original.name}"
            shutil.copy2(original, backup)
            backups[original] = backup

    # Move pre-existing dataset dirs out of the way (don't delete — they
    # might be the user's previous work)
    moved_datasets: list[tuple[Path, Path]] = []
    if INPUT_DIR.exists():
        for d in INPUT_DIR.glob("dataset_*"):
            moved = tmp_path / d.name
            shutil.move(str(d), str(moved))
            moved_datasets.append((d, moved))

    # Clear cache so each test starts from a known state
    if CACHE_PATH.exists():
        CACHE_PATH.unlink()

    try:
        yield
    finally:
        # Teardown: remove test artefacts, restore originals
        if CACHE_PATH.exists():
            CACHE_PATH.unlink()
        _clear_input_datasets()

        for original, backup in backups.items():
            shutil.copy2(backup, original)
        for original, moved in moved_datasets:
            shutil.move(str(moved), str(original))


# ─── Sanity check ───────────────────────────────────────────────────────

class TestPreconditions:
    """Fail-fast checks. If these fail, the other tests' diagnostics will
    be confusing — better to surface 'script not found' here than as a
    subprocess return-code error in every test."""

    def test_script_exists(self):
        assert SCRIPT.exists(), f"select_pilot.py not found at {SCRIPT}"

    def test_exclusion_file_exists(self):
        assert EXCLUSION_PATH.exists(), (
            f"tainted_cases.txt not found at {EXCLUSION_PATH} — the cache "
            f"fingerprint cannot be verified without it"
        )


# ─── Test 1: Fresh-build determinism ────────────────────────────────────

class TestFreshBuildDeterminism:
    """`--rebuild-index` twice in a row must produce byte-identical caches."""

    def test_two_fresh_builds_produce_identical_cache(
        self, clean_state, tmp_path: Path
    ):
        _run_select_pilot("--rebuild-index")
        snapshot = tmp_path / "cache_run1.json"
        shutil.copy2(CACHE_PATH, snapshot)

        CACHE_PATH.unlink()
        _run_select_pilot("--rebuild-index")

        assert CACHE_PATH.read_bytes() == snapshot.read_bytes(), (
            "Cache differs between two consecutive fresh builds.\n"
            "Likely causes:\n"
            "  - non-deterministic iteration order in scan_raw_data "
            "(missing .sort() on rglob results)\n"
            "  - fingerprint computed from absolute paths instead of "
            "relative (would vary between CI runners)\n"
            "  - timestamps embedded in the cache payload itself"
        )


# ─── Test 2: Selection determinism from independent fresh caches ────────

class TestSelectionDeterminism:
    """Same seed → identical manifest, from a fresh cache each time."""

    def test_same_seed_independent_fresh_caches_yield_identical_manifests(
        self, clean_state
    ):
        # Run 1
        _run_select_pilot("--rebuild-index")
        _run_select_pilot("--seed-date", SEED_DATE, "--n", str(N_PER_STRATUM))
        manifest_run1 = _read_manifest_original_paths(_find_latest_dataset_dir())

        # Tear everything down between runs to prove independence
        CACHE_PATH.unlink()
        _clear_input_datasets()

        # Run 2
        _run_select_pilot("--rebuild-index")
        _run_select_pilot("--seed-date", SEED_DATE, "--n", str(N_PER_STRATUM))
        manifest_run2 = _read_manifest_original_paths(_find_latest_dataset_dir())

        # Cardinality first (clearer failure message if n is wrong than if
        # the set-difference is empty for a trivial reason)
        assert len(manifest_run1) == EXPECTED_TOTAL, (
            f"Expected {EXPECTED_TOTAL} cases "
            f"({N_PER_STRATUM} per stratum × 3 strata), got {len(manifest_run1)}.\n"
            f"Either --n is being misinterpreted, or a stratum was under-populated."
        )
        assert manifest_run1 == manifest_run2, (
            "Manifests differ across independent fresh-cache runs with the same "
            f"seed ({SEED_DATE}). This is the reproducibility claim that "
            "pre-reg §5 makes; failure here breaks it.\n"
            f"  Only in run 1: {set(manifest_run1) - set(manifest_run2)}\n"
            f"  Only in run 2: {set(manifest_run2) - set(manifest_run1)}"
        )


# ─── Test 3: Exclusion-file change invalidates the cache ────────────────

class TestExclusionFileInvalidation:
    """Modifying tools/tainted_cases.txt must invalidate the cache."""

    def test_exclusion_change_triggers_rebuild(self, clean_state):
        # Build the cache with the original exclusion file
        _run_select_pilot("--rebuild-index")
        cache_before = CACHE_PATH.read_bytes()
        mtime_before = CACHE_PATH.stat().st_mtime
        exclusion_original = EXCLUSION_PATH.read_bytes()

        # Append a content change (not just whitespace — and a comment
        # makes the diff obvious if the test fails mid-flight)
        with EXCLUSION_PATH.open("a") as f:
            f.write("\n# test marker - should invalidate cache fingerprint\n")

        # Normal run (no --rebuild-index). The fingerprint check must detect
        # the change and rebuild.
        result = _run_select_pilot(
            "--seed-date", SEED_DATE, "--n", str(N_PER_STRATUM)
        )

        # Evidence of rebuild — primary signal is log output, secondary
        # is content change. Content change is the most reliable since
        # the fingerprint inside the cache encodes the exclusion file's
        # hash, which now differs. Filesystem mtime resolution varies
        # (1s on HFS+, nanoseconds on ext4), so mtime alone is unreliable.
        combined_log = (result.stdout + result.stderr).lower()
        log_signals_rebuild = any(
            marker in combined_log
            for marker in ("fingerprint mismatch", "rebuilding", "cache invalidated")
        )
        cache_bytes_changed = CACHE_PATH.read_bytes() != cache_before
        cache_mtime_advanced = CACHE_PATH.stat().st_mtime > mtime_before

        assert log_signals_rebuild or cache_bytes_changed or cache_mtime_advanced, (
            "Cache survived a content change to tainted_cases.txt — the exact "
            "bug the fingerprint mechanism is supposed to catch.\n"
            "  log_signals_rebuild={}, cache_bytes_changed={}, "
            "cache_mtime_advanced={}\n"
            "  stdout:\n{}\n  stderr:\n{}"
        ).format(
            log_signals_rebuild, cache_bytes_changed, cache_mtime_advanced,
            result.stdout, result.stderr,
        )
