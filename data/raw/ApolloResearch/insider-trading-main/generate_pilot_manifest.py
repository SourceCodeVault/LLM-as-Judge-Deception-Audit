import json
import random
from pathlib import Path

# --- CONFIGURATION ---
BASE_DIR = Path(".")
RESULTS_DIR = BASE_DIR / "results"
MANIFEST_FILE = "smoke_test_manifest.jsonl"
SAMPLE_SIZE_PER_CLASS = 5 

def extract_slug(file_path):
    rel_path = file_path.relative_to(RESULTS_DIR)
    return str(rel_path.with_suffix(''))

def main():
    clean_pool = []
    flawed_pool = []
    
    print(f"Scanning JSON files in {RESULTS_DIR.resolve()}...")
    
    for filepath in RESULTS_DIR.rglob("*.json"):
        # STRATEGIC FILTER: Drop No Scratchpad cases to protect W2 preconditions
        if "No Scratchpad" in str(filepath):
            continue
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # A case is flawed if it is EITHER misaligned or deceptive
            is_misaligned = data.get("is_misaligned", False)
            is_deceptive = data.get("is_deceptive", False)
            
            # Ground truth: Did it commit a compliance violation?
            is_flawed = is_misaligned or is_deceptive
            
            slug = extract_slug(filepath)
            
            case_record = {
                "absolute_path": str(filepath.resolve()),
                "slug": slug,
                "is_misaligned": is_misaligned,
                "is_deceptive": is_deceptive,
                "ground_truth_flawed": is_flawed
            }
            
            if is_flawed:
                flawed_pool.append(case_record)
            else:
                clean_pool.append(case_record)
                
        except Exception as e:
            print(f"Failed to parse {filepath}: {e}")
            
    print(f"Found {len(clean_pool)} clean cases and {len(flawed_pool)} flawed cases (excluding No Scratchpad).")
    
    random.shuffle(clean_pool)
    random.shuffle(flawed_pool)
    
    selected_cases = (
        clean_pool[:SAMPLE_SIZE_PER_CLASS] + 
        flawed_pool[:SAMPLE_SIZE_PER_CLASS]
    )
    
    random.shuffle(selected_cases)
    
    with open(MANIFEST_FILE, 'w', encoding='utf-8') as f:
        for case in selected_cases:
            f.write(json.dumps(case) + '\n')
            
    print(f"\nManifest successfully written to {MANIFEST_FILE}")

if __name__ == "__main__":
    main()