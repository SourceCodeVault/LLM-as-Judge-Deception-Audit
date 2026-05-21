#!/usr/bin/env python3
"""
select_pilot.py - Stratified Sampling Utility for LLM Audit Pipeline

Provides two modes:
  [1] Generate new stratified random sample from raw data
  [2] Reproduce dataset from existing manifest

Features:
  - File indexing/caching for speed optimization
  - Automatic index invalidation on file changes
  - Tripartite sampling (CLEAN, ROGUE_HONEST, ROGUE_DECEPTIVE)
  - STRICT DATA HYGIENE: Excludes tainted cases by default to prevent contamination.
"""

import os
import sys
import json
import shutil
import random
import argparse
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Tuple, List

# Constants
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_RAW_DATA_PATH = PROJECT_ROOT / "data" / "raw"
DEFAULT_INPUT_PATH = PROJECT_ROOT / "input"
DEFAULT_EXCLUDE_FILE = PROJECT_ROOT / "tools" / "tainted_cases.txt"
CACHE_INDEX_FILENAME = "raw_index.json"
MANIFEST_FILENAME = "manifest.jsonl"

# =============================================================================
# PRE-REG COMPLIANCE: Cache versioning
# =============================================================================
# Bump this string whenever classification logic or path handling changes.
# This invalidates any stale cache that was built under different rules.
CACHE_CODE_VERSION = "v1.0-prereg"


def compute_cache_fingerprint(raw_path: Path, exclude_file: str | None) -> str:
    """
    Compute a fingerprint that invalidates the cache when:
    1. Raw file metadata changes (mtime/size)
    2. Exclusion file content changes
    3. Code version changes (CACHE_CODE_VERSION)
    
    Returns:
        str: SHA-256 hex digest of the fingerprint
    """
    h = hashlib.sha256()
    
    # 1. Include code version
    h.update(f"version:{CACHE_CODE_VERSION}".encode())
    
    # 2. Include exclusion file content (if exists)
    if exclude_file:
        exclude_path = Path(exclude_file)
        if exclude_path.exists():
            h.update(f"exclude_file:{exclude_path.name}".encode())
            h.update(exclude_path.read_bytes())
    
    # 3. Include sorted file metadata (mtime + size)
    for json_file in sorted(raw_path.rglob("*.json")):
        try:
            st = json_file.stat()
            # Use relative path for consistency across different invocation contexts
            rel_path = str(json_file.relative_to(raw_path))
            h.update(f"{rel_path}|{st.st_mtime_ns}|{st.st_size}".encode())
        except (OSError, IOError):
            continue
    
    return h.hexdigest()


def print_header(title: str) -> None:
    """Print a styled header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_status(symbol: str, message: str) -> None:
    """Print a styled status message."""
    print(f"  {symbol} {message}")


def get_default_seed() -> int:
    """Generate default seed from current date."""
    return int(datetime.now().strftime("%Y%m%d"))


def ensure_directory(path: Path) -> None:
    """Ensure directory exists, create if necessary."""
    path.mkdir(parents=True, exist_ok=True)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="LLM Audit Pipeline - Pilot Selection Tool"
    )
    parser.add_argument("--rebuild-index", action="store_true", help="Force rebuild of the raw data index cache")
    parser.add_argument("--raw-path", type=str, default=DEFAULT_RAW_DATA_PATH, help=f"Path to raw data directory")
    parser.add_argument("--exclude-file", type=str, default=DEFAULT_EXCLUDE_FILE, help=f"Path to exclusions")
    parser.add_argument("--all", action="store_true", help="Process all files, ignoring default exclusions.")
    
    # NEW ARGUMENTS FOR PRE-REG COMPLIANCE
    parser.add_argument("--seed-date", type=str, help="YYYYMMDD date string to derive deterministic seed")
    parser.add_argument("--seed", type=int, help="Explicit integer seed (overrides --seed-date)")
    parser.add_argument("--n-cases", type=int, help="Number of cases to select per stratum (default 400 for pilot)")
    return parser.parse_args()


def get_file_metadata(raw_path: Path) -> Dict[str, Tuple[float, int]]:
    """
    Walk directory and collect lightweight metadata for each JSON file.
    Returns dict: {relative_path: (mtime, size)}
    
    This is O(n) filesystem operations but does NOT parse JSON content.
    """
    metadata = {}
    
    for json_file in raw_path.rglob("*.json"):
        try:
            stat = json_file.stat()
            rel_path = str(json_file.relative_to(raw_path))
            # Store (mtime, size) tuple - lightweight comparison
            metadata[rel_path] = (stat.st_mtime, stat.st_size)
        except (OSError, IOError):
            continue
    
    return metadata


def detect_changes(raw_path: Path, cached_metadata: dict) -> Tuple[bool, str]:
    """
    Compare current file metadata against cached metadata.
    
    Returns:
        (has_changes, reason) - Tuple indicating if rebuild is needed and why
    """
    current_metadata = get_file_metadata(raw_path)
    
    cached_files = set(cached_metadata.keys())
    current_files = set(current_metadata.keys())
    
    # Check for added files
    added = current_files - cached_files
    if added:
        return True, f"{len(added)} new file(s) added"
    
    # Check for removed files
    removed = cached_files - current_files
    if removed:
        return True, f"{len(removed)} file(s) removed"
    
    # Check for modified files (mtime or size changed)
    modified = []
    for path in cached_files & current_files:
        cached_mtime, cached_size = cached_metadata[path]
        current_mtime, current_size = current_metadata[path]
        if cached_mtime != current_mtime or cached_size != current_size:
            modified.append(path)
    
    if modified:
        return True, f"{len(modified)} file(s) modified"
    
    return False, "no changes detected"


def scan_raw_data(raw_path: Path, force_rebuild: bool = False, exclude_file: str = None) -> dict:
    """
    Recursively scan raw data directory for JSON files.
    Uses cache if available and force_rebuild is False.
    Classifies files into three buckets:
      - CLEAN: is_misaligned == False AND is_deceptive is None
      - ROGUE_DECEPTIVE: is_misaligned == True AND is_deceptive == True
      - ROGUE_HONEST: is_misaligned == True AND is_deceptive is None
    
    Returns:
        dict: {
            'clean': [(file_path, is_misaligned, is_deceptive), ...],
            'rogue_deceptive': [(file_path, is_misaligned, is_deceptive), ...],
            'rogue_honest': [(file_path, is_misaligned, is_deceptive), ...],
            'skipped': [file_path, ...],
            'metadata': {'raw_path': ..., 'total_files': ...}
        }
    """
    cache_path = raw_path.parent / CACHE_INDEX_FILENAME
    
    # Check cache first (unless force rebuild)
    if not force_rebuild and cache_path.exists():
        print_status("💾", f"Loading from cache: {cache_path}")
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            
            # =================================================================
            # PRE-REG COMPLIANCE: Validate cache fingerprint
            # =================================================================
            cached_version = cached_data.get('metadata', {}).get('cache_version')
            cached_fingerprint = cached_data.get('metadata', {}).get('cache_fingerprint')
            
            # Rebuild if version string changed
            if cached_version != CACHE_CODE_VERSION:
                print_status("🔄", f"Cache version mismatch (cached: {cached_version}, current: {CACHE_CODE_VERSION}), rebuilding...")
            # Rebuild if fingerprint changed (exclusions or raw files changed)
            elif cached_fingerprint:
                current_fingerprint = compute_cache_fingerprint(raw_path, exclude_file)
                if cached_fingerprint != current_fingerprint:
                    print_status("🔄", f"Cache fingerprint mismatch, rebuilding index...")
                else:
                    print_status("✅", "Cache loaded successfully (fingerprint validated)")
                    print_status("📊", f"CLEAN: {len(cached_data.get('clean', []))}")
                    print_status("📊", f"ROGUE_DECEPTIVE: {len(cached_data.get('rogue_deceptive', []))}")
                    print_status("📊", f"ROGUE_HONEST: {len(cached_data.get('rogue_honest', []))}")
                    return cached_data
            else:
                # Legacy cache without fingerprint - rebuild
                print_status("🔄", "Legacy cache detected (no fingerprint), rebuilding...")
                
        except (json.JSONDecodeError, IOError) as e:
            print_status("⚠️", f"Cache corrupted ({e}), rebuilding index...")
    
    # Perform fresh scan
    print_status("🔍", f"Scanning {raw_path} recursively...")

    exclusions = set()
    if exclude_file and Path(exclude_file).exists():
        print_status("🛡️", f"Loading exclusion list from: {exclude_file}")
        with open(exclude_file, 'r', encoding='utf-8') as f:
            for line in f:
                clean_path = line.strip().replace('\\', '/')
                if not clean_path or not clean_path.endswith('.json'): continue
                # Normalize to the unique part of the Apollo path
                if 'insider-trading-main/' in clean_path:
                    exclusions.add(clean_path.split('insider-trading-main/')[-1])
                else:
                    exclusions.add("/".join(clean_path.split('/')[-3:]))
        print_status("🛡️", f"Loaded {len(exclusions)} unique tainted signatures to exclude")
    
    clean_files = []
    rogue_deceptive_files = []
    rogue_honest_files = []
    skipped_files = []
    
    for json_file in raw_path.rglob("*.json"):
        # Check against exclusions first
        rel_str = str(json_file).replace('\\', '/')
        sig = rel_str.split('insider-trading-main/')[-1] if 'insider-trading-main/' in rel_str else "/".join(rel_str.split('/')[-3:])
        
        if sig in exclusions:
            skipped_files.append(str(json_file))
            continue

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            is_misaligned = data.get('is_misaligned')
            is_deceptive = data.get('is_deceptive')

            # 1. THE APOLLO QUIRK PATCH: Infer misaligned if explicitly deceptive
            if is_misaligned is None and is_deceptive is True:
                is_misaligned = True

            # 2. PRE-COMMITTED EXCLUSIONS (Fail-Closed)
            # Skip if still missing/null/invalid after the patch
            if not isinstance(is_misaligned, bool):
                skipped_files.append(str(json_file))
                continue

            # Prevent impossible pairings from leaking into the CLEAN bucket
            if is_misaligned is False and is_deceptive is True:
                skipped_files.append(str(json_file))
                continue

            # 3. STRICT ALLOWLIST ENFORCEMENT (matching empirical §0.3 table)
            if is_misaligned is False and is_deceptive is None:
                # =================================================================
                # PRE-REG COMPLIANCE: Use resolved absolute path for deterministic sort
                # =================================================================
                clean_files.append((str(json_file.resolve()), is_misaligned, is_deceptive))
            elif is_misaligned is True and is_deceptive is None:
                rogue_honest_files.append((str(json_file.resolve()), is_misaligned, is_deceptive))
            elif is_misaligned is True and is_deceptive is True:
                rogue_deceptive_files.append((str(json_file.resolve()), is_misaligned, is_deceptive))
            else:
                skipped_files.append(str(json_file))
                continue
                
        except (json.JSONDecodeError, IOError) as e:
            skipped_files.append(str(json_file))
            continue
    
    # Get lightweight file metadata for change detection
    file_index = get_file_metadata(raw_path)
    
    # CRITICAL: Sort the lists to ensure OS-independent deterministic sampling
    clean_files.sort(key=lambda x: x[0])
    rogue_deceptive_files.sort(key=lambda x: x[0])
    rogue_honest_files.sort(key=lambda x: x[0])
    
    # =================================================================
    # PRE-REG COMPLIANCE: Compute and store fingerprint
    # =================================================================
    cache_fingerprint = compute_cache_fingerprint(raw_path, exclude_file)
    
    result = {
        'clean': clean_files,
        'rogue_deceptive': rogue_deceptive_files,
        'rogue_honest': rogue_honest_files,
        'skipped': skipped_files,
        'file_index': file_index,
        'metadata': {
            'raw_path': str(raw_path),
            'cache_version': CACHE_CODE_VERSION,
            'cache_fingerprint': cache_fingerprint,
            'total_scanned': len(clean_files) + len(rogue_deceptive_files) + len(rogue_honest_files),
            'total_skipped': len(skipped_files)
        }
    }
    
    # Save to cache
    print_status("💾", f"Saving index to cache: {cache_path}")
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
    except IOError as e:
        print_status("⚠️", f"Failed to save cache: {e}")
    
    print_status("✅", f"Found {len(clean_files)} CLEAN files")
    print_status("✅", f"Found {len(rogue_deceptive_files)} ROGUE_DECEPTIVE files")
    print_status("✅", f"Found {len(rogue_honest_files)} ROGUE_HONEST files")
    print_status("⚠️", f"Skipped {len(skipped_files)} files (excluded/invalid)")
    
    return result


def tripartite_sample(buckets: dict, n_per_category: int, seed: int) -> list:
    """
    Perform tripartite stratified random sampling.
    Selects exactly N from each of the three buckets.
    
    Returns:
        list: [(original_path, bucket_label, is_misaligned, is_deceptive), ...]
    """
    random.seed(seed)
    
    clean_files = buckets['clean']
    rogue_deceptive_files = buckets['rogue_deceptive']
    rogue_honest_files = buckets['rogue_honest']
    
    # Validate we have enough files in each bucket
    if len(clean_files) < n_per_category:
        raise ValueError(f"Not enough CLEAN files. Need {n_per_category}, have {len(clean_files)}")
    if len(rogue_deceptive_files) < n_per_category:
        raise ValueError(f"Not enough ROGUE_DECEPTIVE files. Need {n_per_category}, have {len(rogue_deceptive_files)}")
    if len(rogue_honest_files) < n_per_category:
        raise ValueError(f"Not enough ROGUE_HONEST files. Need {n_per_category}, have {len(rogue_honest_files)}")
    
    # Random selection from each bucket
    selected_clean = random.sample(clean_files, n_per_category)
    selected_deceptive = random.sample(rogue_deceptive_files, n_per_category)
    selected_honest = random.sample(rogue_honest_files, n_per_category)
    
    # Format results
    result = []
    for path, is_misaligned, is_deceptive in selected_clean:
        result.append((path, 'CLEAN', is_misaligned, is_deceptive))
    for path, is_misaligned, is_deceptive in selected_deceptive:
        result.append((path, 'ROGUE_DECEPTIVE', is_misaligned, is_deceptive))
    for path, is_misaligned, is_deceptive in selected_honest:
        result.append((path, 'ROGUE_HONEST', is_misaligned, is_deceptive))
    
    # Shuffle to mix categories
    random.shuffle(result)
    
    total = n_per_category * 3
    print_status("🎲", f"Selected {n_per_category} CLEAN + {n_per_category} ROGUE_DECEPTIVE + {n_per_category} ROGUE_HONEST = {total} total")
    print_status("🔢", f"Using seed: {seed}")
    
    return result


def copy_with_path_preservation(
    selected_files: list,
    raw_data_path: Path,
    output_path: Path,
    bucket_name: str
) -> list:
    """
    Copy files preserving original relative folder structure.
    
    Returns:
        list: [(original_path, new_path, bucket, is_misaligned, is_deceptive), ...]
    """
    copied_files = []
    
    for original_path, bucket, is_misaligned, is_deceptive in selected_files:
        # Calculate relative path from raw data root
        rel_path = Path(original_path).relative_to(raw_data_path)
        
        # Build new path in output directory
        new_path = output_path / rel_path
        
        # Ensure parent directory exists
        ensure_directory(new_path.parent)
        
        # Copy file
        shutil.copy2(original_path, new_path)
        
        copied_files.append({
            'original_path': original_path,
            'new_path': str(new_path),
            'bucket': bucket,
            'is_misaligned': is_misaligned,
            'is_deceptive': is_deceptive
        })
    
    return copied_files


def generate_manifest(copied_files: list, seed: int, output_path: Path) -> None:
    """Generate manifest.jsonl file in output directory."""
    manifest_path = output_path / MANIFEST_FILENAME
    
    with open(manifest_path, 'w', encoding='utf-8') as f:
        for file_info in copied_files:
            record = {
                'original_path': file_info['original_path'],
                'new_path': file_info['new_path'],
                'bucket': file_info['bucket'],
                'is_misaligned': file_info['is_misaligned'],
                'is_deceptive': file_info['is_deceptive'],
                'seed': seed
            }
            f.write(json.dumps(record) + '\n')
    
    print_status("📄", f"Generated manifest: {manifest_path}")
    print_status("📊", f"Manifest contains {len(copied_files)} entries")


def generate_new_sample(force_rebuild: bool = False, exclude_file: str = None, 
                        auto_n: int = None, auto_seed: int = None,
                        auto_raw_path: str = None) -> None:
    """Mode A: Generate new tripartite stratified random sample."""
    print_header("🚀 Generate New Tripartite Stratified Sample")
    
    # Get raw data path (Bypass input if in automated mode)
    if auto_n is not None or auto_seed is not None:
        raw_path = Path(auto_raw_path) if auto_raw_path else Path(DEFAULT_RAW_DATA_PATH)
    else:
        raw_input = input("  📁 Raw data path (default: data/raw): ").strip()
        raw_path = Path(raw_input) if raw_input else Path(DEFAULT_RAW_DATA_PATH)
        
    if not raw_path.exists():
        print_status("❌", f"Path does not exist: {raw_path}")
        return
        
    # 1. Scan and classify FIRST so we know our limits
    print_status("📂", "Scanning and classifying files to determine available cases...")
    buckets = scan_raw_data(raw_path, force_rebuild=force_rebuild, exclude_file=exclude_file)
    
    # Calculate available cases to guide the user
    num_clean = len(buckets.get('clean', []))
    num_rogue_dec = len(buckets.get('rogue_deceptive', []))
    num_rogue_hon = len(buckets.get('rogue_honest', []))
    max_n = min(num_clean, num_rogue_dec, num_rogue_hon)
    
    print_status("📊", f"Inventory: {num_clean} CLEAN | {num_rogue_dec} ROGUE_DECEPTIVE | {num_rogue_hon} ROGUE_HONEST")
    print_status("💡", f"The maximum N you can select (bottlenecked by smallest bucket) is: {max_n}")
    
    if max_n == 0:
        print_status("❌", "Cannot generate sample: One or more buckets are empty.")
        return

    # 2. Get N per category with validation against max_n
    if auto_n is not None:
        n_per_category = auto_n
        if n_per_category > max_n:
            print_status("❌", f"Requested N ({n_per_category}) exceeds available cases ({max_n})")
            return
    else:
        while True:
            try:
                n_input = input(f"  📊 N (cases PER category, max {max_n}): ").strip()
                n_per_category = int(n_input)
                if 0 < n_per_category <= max_n:
                    break
                print_status("❌", f"Please enter a positive integer between 1 and {max_n}")
            except ValueError:
                print_status("❌", "Please enter a valid integer")
    
    # 3. Get seed
    if auto_seed is not None:
        seed = auto_seed
    else:
        seed_input = input(f"  🎲 Random seed (default: {get_default_seed()}): ").strip()
        seed = int(seed_input) if seed_input else get_default_seed()

    # Perform tripartite stratified sampling
    try:
        selected = tripartite_sample(buckets, n_per_category, seed)
    except ValueError as e:
        print_status("❌", str(e))
        return
    
    # Generate output directory name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_name = f"dataset_{timestamp}"
    output_path = Path(DEFAULT_INPUT_PATH) / output_name
    
    ensure_directory(output_path)
    print_status("📁", f"Output directory: {output_path}")
    
    # Copy files with path preservation
    print_status("📋", "Copying files...")
    copied_files = copy_with_path_preservation(
        selected, raw_path, output_path, "sampled"
    )
    
    # Generate manifest
    generate_manifest(copied_files, seed, output_path)
    
    print_header("✅ Sample Generation Complete")
    print_status("📁", f"Output: {output_path}")
    print_status("📄", f"Manifest: {output_path / MANIFEST_FILENAME}")


def reproduce_from_manifest() -> None:
    """Mode B: Reproduce dataset from existing manifest."""
    print_header("🔄 Reproduce Dataset from Manifest")
    
    # Get manifest path
    manifest_input = input("  📄 Path to manifest.jsonl: ").strip()
    manifest_path = Path(manifest_input)
    
    if not manifest_path.exists():
        print_status("❌", f"Manifest not found: {manifest_path}")
        return
    
    # Read manifest
    print_status("📖", "Reading manifest...")
    manifest_entries = []
    
    with open(manifest_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                entry = json.loads(line.strip())
                manifest_entries.append(entry)
            except json.JSONDecodeError as e:
                print_status("⚠️", f"Skipping malformed line {line_num}: {e}")
                continue
    
    print_status("✅", f"Read {len(manifest_entries)} entries from manifest")
    
    # Determine raw data path from first entry
    if manifest_entries:
        first_entry = manifest_entries[0]
        original_path = first_entry['original_path']
        
        # Try to determine raw data root
        raw_path = None
        for part in ['data/raw', 'data/', './data/raw', './data/']:
            if part in original_path:
                raw_path = Path(original_path.split(part)[0] + part)
                break
        
        if raw_path and raw_path.exists():
            print_status("📂", f"Using raw data path: {raw_path}")
        else:
            # Ask user for raw data path
            raw_input = input("  📁 Raw data path: ").strip()
            raw_path = Path(raw_input)
            if not raw_path.exists():
                print_status("❌", f"Path does not exist: {raw_path}")
                return
    
    # Generate new output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_name = f"dataset_{timestamp}_reproduced"
    output_path = Path(DEFAULT_INPUT_PATH) / output_name
    
    ensure_directory(output_path)
    print_status("📁", f"Output directory: {output_path}")
    
    # Copy files
    print_status("📋", "Copying files...")
    copied_count = 0
    failed_count = 0
    
    for entry in manifest_entries:
        original_path = entry['original_path']
        
        if not Path(original_path).exists():
            print_status("⚠️", f"File not found: {original_path}")
            failed_count += 1
            continue
        
        # Calculate relative path
        try:
            rel_path = Path(original_path).relative_to(raw_path)
        except ValueError:
            # If we can't determine relative path, use filename only
            rel_path = Path(original_path).name
        
        new_path = output_path / rel_path
        ensure_directory(new_path.parent)
        
        shutil.copy2(original_path, new_path)
        copied_count += 1
    
    # Generate new manifest
    new_manifest_entries = []
    for entry in manifest_entries:
        original_path = entry['original_path']
        
        try:
            rel_path = Path(original_path).relative_to(raw_path)
            new_path = str(output_path / rel_path)
        except ValueError:
            new_path = str(output_path / Path(original_path).name)
        
        new_manifest_entries.append({
            'original_path': original_path,
            'new_path': new_path,
            'bucket': entry.get('bucket', 'UNKNOWN'),
            'is_misaligned': entry.get('is_misaligned'),
            'is_deceptive': entry.get('is_deceptive'),
            'seed': entry.get('seed')
        })
    
    generate_manifest(new_manifest_entries, new_manifest_entries[0].get('seed', 0), output_path)
    
    print_header("✅ Reproduction Complete")
    print_status("📁", f"Output: {output_path}")
    print_status("✅", f"Successfully copied: {copied_count}")
    if failed_count > 0:
        print_status("⚠️", f"Failed to copy: {failed_count}")


def rebuild_index(exclude_file: str = None) -> None:
    """Rebuild the raw data index cache."""
    print_header("🔨 Rebuild Raw Data Index")
    
    raw_input = input("  📁 Raw data path (default: data/raw): ").strip()
    raw_path = Path(raw_input) if raw_input else Path(DEFAULT_RAW_DATA_PATH)
    
    if not raw_path.exists():
        print_status("❌", f"Path does not exist: {raw_path}")
        return
    
    print_status("🔄", "Forcing full re-scan of raw data...")
    scan_raw_data(raw_path, force_rebuild=True, exclude_file=exclude_file)
    
    print_header("✅ Index Rebuild Complete")
    print_status("💾", "Cache updated at: " + str(raw_path.parent / CACHE_INDEX_FILENAME))


def audit_corpus_labels(exclude_file: str = None) -> None:
    """Mode C: Audit corpus label combinations to check for edge cases."""
    from collections import Counter
    
    print_header("📊 Audit Corpus Label Combinations")
    
    raw_input = input("  📁 Raw data path (default: data/raw): ").strip()
    raw_path = Path(raw_input) if raw_input else Path(DEFAULT_RAW_DATA_PATH)
    
    if not raw_path.exists():
        print_status("❌", f"Path does not exist: {raw_path}")
        return
        
    print_status("🔍", f"Scanning {raw_path} to count label combinations...")

    # Load exclusions
    exclusions = set()
    if exclude_file and Path(exclude_file).exists():
        with open(exclude_file, 'r', encoding='utf-8') as f:
            for line in f:
                clean_path = line.strip().replace('\\', '/')
                if not clean_path or not clean_path.endswith('.json'): continue
                if 'insider-trading-main/' in clean_path:
                    exclusions.add(clean_path.split('insider-trading-main/')[-1])
                else:
                    exclusions.add("/".join(clean_path.split('/')[-3:]))

    raw_counts = Counter()
    patched_counts = Counter()
    skipped = 0

    for json_file in raw_path.rglob("*.json"):
        rel_str = str(json_file).replace('\\', '/')
        sig = rel_str.split('insider-trading-main/')[-1] if 'insider-trading-main/' in rel_str else "/".join(rel_str.split('/')[-3:])
        
        if sig in exclusions:
            skipped += 1
            continue

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            raw_mis = data.get('is_misaligned')
            raw_dec = data.get('is_deceptive')
            
            raw_counts[(raw_mis, raw_dec)] += 1
            
            # Apply Apollo Quirk Patch for accurate pipeline simulation
            patched_mis = raw_mis
            if patched_mis is None and raw_dec is True:
                patched_mis = True
                
            patched_counts[(patched_mis, raw_dec)] += 1
            
        except (json.JSONDecodeError, IOError):
            skipped += 1

    print_status("✅", "Scan complete. Here are the observed combinations:")
    
    print("\n  [PATCHED COUNTS] (What the pipeline actually evaluates)")
    print(f"  {'-'*75}")
    print(f"  {'is_misaligned':<15} | {'is_deceptive':<15} | {'Count':<10} | {'Status'}")
    print(f"  {'-'*75}")
    
    # The exact allowlist from empirical paper §0.3
    valid_combos = [(False, None), (True, None), (True, True)]
    
    for (mis, dec), count in patched_counts.most_common():
        status = "VALID" if (mis, dec) in valid_combos else "EDGE CASE (LEAKAGE)"
        print(f"  {str(mis):<15} | {str(dec):<15} | {count:<10} | {status}")
        
    print(f"  {'-'*75}")
    print(f"  Skipped (Excluded/Unreadable): {skipped}\n")

    edge_cases = sum(c for (m, d), c in patched_counts.items() if (m, d) not in valid_combos)
    if edge_cases == 0:
        print_status("🎉", "ZERO EDGE CASES! Your paper's allowlist is perfectly aligned with the corpus.")
        print_status("💡", "You can safely apply the allowlist fix to the code. No paper edits needed.")
    else:
        print_status("⚠️", f"Found {edge_cases} edge cases that leak through the current blocklist.")
        print_status("💡", "Apply the allowlist fix to code, and add a quick note to paper §1 reporting the dropped counts.")

def main():
    """Main entry point - executes choice and exits."""
    cli_args = parse_args()
    force_rebuild = cli_args.rebuild_index
    
    print_header("🛠️ LLM Audit Pipeline - Pilot Selection Tool")
    
    if cli_args.all:
        active_exclude_file = None
        print_status("⚠️", "DANGER: --all flag detected. Tainted cases WILL be included.")
    else:
        active_exclude_file = cli_args.exclude_file
        if not Path(active_exclude_file).exists():
            print_status("❌", f"FATAL: Default exclusion file '{active_exclude_file}' not found.")
            sys.exit(1)
        else:
            print_status("🛡️", f"Data Hygiene: Will exclude files listed in '{active_exclude_file}'")

    # Automated CLI execution bypasses interactive menu
    if cli_args.seed_date or cli_args.seed or cli_args.n_cases:
        target_seed = cli_args.seed
        if target_seed is None and cli_args.seed_date:
            target_seed = int(cli_args.seed_date.replace("-", ""))
        
        target_n = cli_args.n_cases or 400 # Default to the 400-per-stratum pilot
        
        print_status("🤖", f"Automated execution triggered: N={target_n} per bucket, Seed={target_seed}")
        # NEW: Pass the raw_path from CLI arguments so it doesn't prompt the user
        generate_new_sample(force_rebuild, active_exclude_file, auto_n=target_n, auto_seed=target_seed, auto_raw_path=cli_args.raw_path)
        sys.exit(0)

    if force_rebuild:
        rebuild_index(exclude_file=active_exclude_file)
        sys.exit(0)
    
    print("  Select mode:")
    print("    [1] Generate new tripartite stratified sample")
    print("    [2] Reproduce dataset from existing manifest")
    print("    [3] Rebuild raw data index cache")
    print("    [4] Audit corpus label combinations (Check for edge cases)")
    print("    [q] Quit")
    print()
    
    choice = input("  Enter choice: ").strip().lower()
    
    if choice == '1':
        generate_new_sample(force_rebuild=False, exclude_file=active_exclude_file)
        sys.exit(0)
    elif choice == '2':
        reproduce_from_manifest()
        sys.exit(0)
    elif choice == '3':
        rebuild_index(exclude_file=active_exclude_file)
        sys.exit(0)
    elif choice == '4':
        audit_corpus_labels(exclude_file=active_exclude_file)
        sys.exit(0)
    elif choice == 'q':
        print_status("👋", "Goodbye!")
        sys.exit(0)
    else:
        print_status("❌", "Invalid choice.")
        sys.exit(1)

if __name__ == "__main__":
    main()