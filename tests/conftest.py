import pytest
from pathlib import Path

@pytest.fixture
def target_folder():
    """Discover the first valid input folder for sort-parity tests."""
    input_dir = Path(__file__).parent.parent / "input"
    if not input_dir.exists():
        pytest.skip("input/ directory not found")
    folders = [
        f for f in input_dir.iterdir()
        if f.is_dir()
        and not f.name.startswith("_")
        and (f / "manifest.jsonl").exists()
    ]
    if not folders:
        pytest.skip("No valid input folders with manifest.jsonl found")
    return folders[0]