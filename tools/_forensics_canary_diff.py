#!/usr/bin/env python3
"""
Forensics Canary Diff — Extract raw L2 action frequency table.
Used as a standalone reproducibility artifact for the erratum.
"""

import json
from collections import Counter
from pathlib import Path
import os

def main():
    run_dir = os.environ.get("AUDIT_RUN_DIR")
    if not run_dir:
        print("❌ Set AUDIT_RUN_DIR environment variable")
        return
    
    run_path = Path(run_dir)
    if not run_path.exists():
        print(f"❌ Run directory not found: {run_dir}")
        return
    
    all_files = list(run_path.rglob("audit_*.json"))
    print(f"Found {len(all_files)} audit files")
    
    action_counts = Counter()
    for f in all_files:
        try:
            with open(f, 'r') as fh:
                data = json.load(fh)
            # Correct path: compliance_gap.l2_judge_action
            gap = data.get("compliance_gap") or {}
            l2_action = (gap.get("l2_judge_action") 
                        or gap.get("watcher_action") 
                        or "UNKNOWN").upper()
            action_counts[l2_action] += 1
        except Exception as e:
            print(f"⚠️  Error processing {f.name}: {e}")
            continue
    
    print("\n📊 Raw L2 Action Frequency Table:")
    print("=" * 40)
    for action, count in sorted(action_counts.items()):
        print(f"{action:>20}: {count:>4} files")
    print("=" * 40)
    print(f"Total files processed: {sum(action_counts.values())}")

if __name__ == "__main__":
    main()