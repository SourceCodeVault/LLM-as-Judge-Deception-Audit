#!/usr/bin/env python3
import json
import hashlib
from pathlib import Path

# run from project root
# python tools/backfill_manifest_v19.py

# Set up paths dynamically based on the script's location in tools/
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Point to your specific dataset
DATASET_DIR = PROJECT_ROOT / "input" / "dataset_20260521_192859"

MANIFEST = DATASET_DIR / "manifest.jsonl"
BACKUP = DATASET_DIR / "manifest.jsonl.pre_v19"
OUT = DATASET_DIR / "manifest.jsonl.new"

def backfill_manifest():
    print(f"🔄 Starting backfill for: {MANIFEST.name}")

    # 1. Back up the original file safely
    if not BACKUP.exists():
        BACKUP.write_bytes(MANIFEST.read_bytes())
        print(f"📦 Created backup at: {BACKUP.name}")
    else:
        print(f"ℹ️ Backup already exists at: {BACKUP.name}")

    # 2. Read, transform, write
    processed_count = 0
    with open(MANIFEST, 'r', encoding='utf-8') as src, open(OUT, 'w', encoding='utf-8') as dst:
        for line in src:
            if not line.strip(): continue
            rec = json.loads(line)
            
            # Derive case_id from the new_path's location inside dataset folder
            new_path_abs = Path(rec["new_path"])
            
            # The slug logic must match run.py exactly
            if new_path_abs.is_absolute():
                rel_inside_dataset = new_path_abs.relative_to(DATASET_DIR)
            else:
                rel_inside_dataset = Path(rec["new_path"]).relative_to(Path("input") / DATASET_DIR.name)
                
            flat_slug = rel_inside_dataset.with_suffix("").as_posix().replace("/", "__")
            case_id = hashlib.sha256(flat_slug.encode()).hexdigest()[:12]
            
            # Scrub PII to repo-relative paths
            if Path(rec["original_path"]).is_absolute():
                safe_original = str(Path(rec["original_path"]).relative_to(PROJECT_ROOT))
            else:
                safe_original = rec["original_path"]
                
            if Path(rec["new_path"]).is_absolute():
                safe_new = str(Path(rec["new_path"]).relative_to(PROJECT_ROOT))
            else:
                safe_new = rec["new_path"]
            
            # Construct new record: case_id goes first
            new_rec = {"case_id": case_id}
            
            # Add existing keys (except the ones we are replacing)
            for k, v in rec.items():
                if k not in ("original_path", "new_path", "case_id"):
                    new_rec[k] = v
            
            # Add the scrubbed safe paths
            new_rec["original_path"] = safe_original
            new_rec["new_path"] = safe_new
            
            dst.write(json.dumps(new_rec) + "\n")
            processed_count += 1

    # 3. Atomic swap: replace the old manifest with the new one
    OUT.replace(MANIFEST)
    print(f"✅ Successfully backfilled {processed_count} records.")
    print(f"   Original untouched manifest preserved at {BACKUP.name}")

if __name__ == "__main__":
    backfill_manifest()