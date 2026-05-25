import json
import hashlib
from pathlib import Path

# Dynamically find the project root (since this script is now in tools/)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Point this to your specific input dataset folder using the dynamic root
INPUT_DIR = PROJECT_ROOT / "input" / "dataset_20260521_192859"

# Save the output mapping to the project root (or change to SCRIPT_DIR if you want it inside tools/)
OUTPUT_MAPPING_PATH = PROJECT_ROOT / "hash_mapping.json"

lookup_table = {}

# Replicate the exact rglob scan from run.py (Lines 141-146)
for f in sorted(INPUT_DIR.rglob("*.json")):
    if f.name.startswith("_"): 
        continue
        
    try:
        # This is exactly how run.py calculates the flat_slug
        flat_slug = f.relative_to(INPUT_DIR).with_suffix("").as_posix().replace("/", "__")
    except Exception:
        flat_slug = f"{f.parent.name}___{f.stem}"

    # Generate the 12-character hex hash
    case_hash = hashlib.sha256(flat_slug.encode()).hexdigest()[:12]
    
    # Store the path relative to the dataset's parent folder to prevent PII leaks
    # This will result in: dataset_20260521_192859/...
    safe_relative_path = f.relative_to(INPUT_DIR.parent).as_posix()

    lookup_table[case_hash] = {
        "flat_slug": flat_slug,
        "input_path": safe_relative_path
    }

with open(OUTPUT_MAPPING_PATH, 'w', encoding='utf-8') as out_f:
    json.dump(lookup_table, out_f, indent=2)

print(f"✅ Successfully generated safe mapping for {len(lookup_table)} cases directly from the file system.")