#!/usr/bin/env python3
"""
Correspondence Auditor — Stratified Subsample Extractor (Defensible Edition)
Operates down-stream of select_pilot.py folder structures. Generates structured 
manifest artifacts capturing absolute cryptographic provenance.

WARNING: This script assumes the input directory has already been processed
by select_pilot.py and contains a valid manifest.jsonl.
"""
import os
import sys
import json
import shutil
import random
import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
INPUT_DIR = PROJECT_ROOT / "input"

def get_self_hash() -> str:
    """Computes the SHA-256 hash of this script file to record in the manifest provenance."""
    hasher = hashlib.sha256()
    with open(__file__, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()

def parse_arguments():
    """Parses CLI arguments to support headless/CI operations."""
    parser = argparse.ArgumentParser(description="Deterministic Stratified Sub-Sampler")
    parser.add_argument("--input-folder", type=str, help="Name of the source directory inside input/")
    parser.add_argument("--n-cases", type=int, help="Number of cases to sample per stratum")
    parser.add_argument("--seed", type=int, default=20260521, help="Randomization seed")
    parser.add_argument("--output-suffix", type=str, help="Suffix for the created output folder")
    parser.add_argument("--force", action="store_true", help="Force overwrite if target folder contains a manifest.jsonl")
    return parser.parse_known_args()[0]

def interactive_menu(folders, default_seed):
    """Fallback menu for interactive manual execution."""
    print("\n📊 Select Stratified Subsample Allocation Profile:")
    print("  [1] 50-50-50   = 150 Cases (Z07 & Z08 Control Arm Work)")
    print("  [2] 100-100-100 = 300 Cases (Line 3 Test-Retest Stability Block)")
    print("  [3] Custom N per Stratum")
    track = input("> ").strip()
    
    if track == "1":
        n, suffix = 50, "z07_z08_stratified_150"
    elif track == "2":
        n, suffix = 100, "test_retest_stratified_300"
    elif track == "3":
        try:
            n = int(input("Enter desired case count per stratum: ").strip())
            if n <= 0: raise ValueError()
        except ValueError:
            print("❌ Invalid target allocation size.")
            sys.exit(1)
        suffix = f"custom_stratified_{n * 3}"
    else:
        print("❌ Unknown allocation profile selection.")
        sys.exit(1)
        
    print("\nSelect Pre-Curated Dataset Folder to Sample From:")
    for i, f in enumerate(folders):
        print(f"  [{i + 1}] {f.name}")
    try:
        f_idx = int(input("> ").strip()) - 1
        source_folder = folders[f_idx]
    except (ValueError, IndexError):
        print("❌ Invalid directory choice.")
        sys.exit(1)

    seed_input = input(f"\n🎲 Enter Randomization Seed [default {default_seed}]: ").strip()
    seed = int(seed_input) if seed_input else default_seed
        
    return source_folder, n, suffix, seed

def main():
    args = parse_arguments()
    script_hash = get_self_hash()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    print("=" * 70)
    print("  ⚠️  ARCHITECTURAL POSTURE WARNING")
    print("  This script acts as a downstream sub-sampler.")
    print("  It assumes the input folder was pre-filtered by select_pilot.py.")
    print("  Classification is read strictly from the upstream manifest.jsonl.")
    print("=" * 70)

    # Find candidate directories inside input/
    eligible_folders = sorted([f for f in INPUT_DIR.iterdir() if f.is_dir() and not f.name.startswith("_")], 
                              key=lambda f: f.stat().st_mtime, reverse=True)
    
    # Route via CLI or interactive menu
    if args.input_folder and args.n_cases and args.output_suffix:
        source_folder = INPUT_DIR / args.input_folder
        n_per_category = args.n_cases
        folder_suffix = args.output_suffix
        seed = args.seed
    else:
        if not eligible_folders:
            print(f"❌ No dataset folders found in {INPUT_DIR}")
            sys.exit(1)
        source_folder, n_per_category, folder_suffix, seed = interactive_menu(eligible_folders, args.seed)

    # --- STRUCTURAL VERIFICATION GUARDRAIL ---
    upstream_manifest = source_folder / "manifest.jsonl"
    if not upstream_manifest.exists():
        print(f"\n❌ CRITICAL POSTURE EXCLUSION:")
        print(f"   Directory 'input/{source_folder.name}/' lacks an authentic 'manifest.jsonl'.")
        print(f"   Aborting to prevent non-sanitized or tainted data contamination.")
        sys.exit(1)

    random.seed(seed)
    
    # Gather target files and build a dictionary lookup keyed by Absolute Path Resolution
    # This prevents basename collisions across subdirectories.
    target_files = []
    for f in sorted(source_folder.rglob("*.json")):
        if f.name.startswith("_") or f.name == "manifest.json": continue
        target_files.append((f, f.relative_to(source_folder)))
        
    target_lookup = {f_path.resolve(): (f_path, rel_path) for f_path, rel_path in target_files}

    # Python >= 3.7 guarantees dict iteration order matches insertion order.
    # Initializing in this specific order guarantees deterministic downstream slicing.
    pool = {"CLEAN": [], "ROGUE_HONEST": [], "ROGUE_DECEPTIVE": []}
    
    print(f"\n🔍 Reading classification labels from {source_folder.name}/manifest.jsonl...")
    
    with open(upstream_manifest, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip(): continue
            record = json.loads(line)
            raw_bucket = record.get("bucket", "").upper().replace("-", "_")
            
            # Map robustly by resolving the original saved path
            f_key = Path(record.get("new_path", "")).resolve()
            
            if f_key in target_lookup:
                f_path, rel_path = target_lookup[f_key]
                if raw_bucket in pool:
                    pool[raw_bucket].append((f_path, rel_path))

    # CRITICAL: Sort each pool by absolute path string to guarantee deterministic sampling
    for bucket in pool:
        pool[bucket].sort(key=lambda x: str(x[0].resolve()))

    output_target_dir = INPUT_DIR / folder_suffix

    print(f"\n🎲 Executing deterministic sample slice (Seed: {seed})...")
    
    # 1. VERIFY ALL POOLS FIRST
    for b_type, items in pool.items():
        if len(items) < n_per_category:
            print(f"❌ CRITICAL ERROR: Category pool [{b_type}] only contains {len(items)} items. Cannot slice {n_per_category}.")
            sys.exit(1)
            
    # 2. SAFE TO ALTER FILESYSTEM (WITH OVERWRITE PROTECTION)
    if output_target_dir.exists():
        if (output_target_dir / "manifest.jsonl").exists() and not args.force:
            print(f"\n❌ CRITICAL EXCLUSION: Directory 'input/{output_target_dir.name}' already contains a tracked manifest.jsonl.")
            print(f"   Pass --force via CLI to intentionally overwrite this provenance anchor.")
            sys.exit(1)
        print(f"  🧹 Folder input/{output_target_dir.name} already exists. Cleaving historical data...")
        shutil.rmtree(output_target_dir)
        
    output_target_dir.mkdir(parents=True, exist_ok=True)
    
    # 3. EXECUTE THE SLICE
    sampled_records = []
    print(f"💾 Replicating subfolder trees inside input/{output_target_dir.name}/...")
    
    for b_type, items in pool.items():
        selection = random.sample(items, n_per_category)
        for source_path, rel_path in selection:
            dest_path = output_target_dir / rel_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, dest_path)
            
            sampled_records.append({
                "case_id": hashlib.sha256(rel_path.with_suffix("").as_posix().replace("/", "__").encode()).hexdigest()[:12],
                "original_path": str(source_path.resolve().relative_to(PROJECT_ROOT)),
                "new_path": str(dest_path.resolve().relative_to(PROJECT_ROOT)), 
                "bucket": b_type,
                "seed": seed,
                "script_self_hash": script_hash,
                "input_source_folder": source_folder.name,
                "timestamp_utc": timestamp
            })

    # Write the output manifest anchor file
    sampled_records.sort(key=lambda x: x["case_id"])
    manifest_out = output_target_dir / "manifest.jsonl"
    with open(manifest_out, "w", encoding="utf-8") as mp:
        for entry in sampled_records:
            mp.write(json.dumps(entry) + "\n")

    print(f"🎉 Complete! Manifest sealed at: input/{folder_suffix}/manifest.jsonl")

if __name__ == "__main__":
    main()