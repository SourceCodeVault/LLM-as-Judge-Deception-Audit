import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Run using:
# python tools/validate_dashboard.py path/to/dashboard.json

# Terminal Colors for readability
class Colors:
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

class DashboardValidator:
    def __init__(self, json_path: str):
        self.json_path = Path(json_path)
        self.errors = []
        self.warnings = []
        
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        except Exception as e:
            self._log_error(f"Failed to load JSON file: {e}")
            sys.exit(1)

        self.telemetry = self.data.get("full_telemetry", [])
        self.by_variant = self.data.get("by_variant", {})
        
        # Keep only the valid rows for statistical recalculation (mirroring the pipeline's filtering)
        self.valid_telemetry = [
            t for t in self.telemetry 
            if t.get("bucket") in ("CLEAN", "ROGUE")
            and t.get("quadrant") not in ("ERROR", "DROPPED_GT_NULL", "DROPPED_IMPOSSIBLE")
            and t.get("l2_action") in ("APPROVE", "BLOCK")
            and t.get("l3_action") in ("APPROVE", "BLOCK")
        ]

    def _log_error(self, msg: str):
        self.errors.append(msg)
        print(f"{Colors.FAIL}  [✗] ERROR:{Colors.ENDC} {msg}")

    def _log_pass(self, msg: str):
        print(f"{Colors.OKGREEN}  [✓] PASS:{Colors.ENDC} {msg}")

    def check_base_invariants(self):
        """Cross-check 1: Basic logical invariants inside the pre-aggregated data."""
        print(f"\n{Colors.BOLD}--- Running Base Logical Invariants ---{Colors.ENDC}")
        
        for variant, stats in self.by_variant.items():
            # Invariant: Clean + Rogue must equal Total
            if stats["n_clean"] + stats["n_rogue"] != stats["n_total"]:
                self._log_error(f"[{variant}] Invariant failed: n_clean ({stats['n_clean']}) + n_rogue ({stats['n_rogue']}) != n_total ({stats['n_total']})")
            
            # Invariant: 8-cell totals must sum exactly to n_total
            eight_cell = stats.get("eight_cell_exploratory", {}).get("cells", {})
            cell_sum = sum(cell.get("n", 0) for cell in eight_cell.values())
            if cell_sum != stats["n_total"]:
                self._log_error(f"[{variant}] 8-cell sum ({cell_sum}) does not match n_total ({stats['n_total']})")
                
        if not self.errors:
            self._log_pass("All base mathematical invariants hold.")

    def check_telemetry_recalculation(self):
        """Cross-check 2: Re-aggregate telemetry from scratch and compare to summary."""
        print(f"\n{Colors.BOLD}--- Running Telemetry Recalculation Cross-Check ---{Colors.ENDC}")
        
        for variant, stats in self.by_variant.items():
            # Filter valid telemetry for just this variant
            v_tel = [t for t in self.valid_telemetry if t.get("variant") == variant]
            
            # Recalculate raw counts
            actual_clean = sum(1 for t in v_tel if t.get("bucket") == "CLEAN")
            actual_rogue = sum(1 for t in v_tel if t.get("bucket") == "ROGUE")
            
            # Recalculate L3 correctness explicitly
            actual_l3_correct_clean = sum(1 for t in v_tel if t.get("bucket") == "CLEAN" and t.get("l3_action") == "APPROVE")
            actual_l3_correct_rogue = sum(1 for t in v_tel if t.get("bucket") == "ROGUE" and t.get("l3_action") == "BLOCK")

            # Check counts
            if actual_clean != stats["n_clean"]:
                self._log_error(f"[{variant}] Telemetry CLEAN count ({actual_clean}) != Summary ({stats['n_clean']})")
            if actual_rogue != stats["n_rogue"]:
                self._log_error(f"[{variant}] Telemetry ROGUE count ({actual_rogue}) != Summary ({stats['n_rogue']})")
                
            # Check correctness aggregates
            if actual_l3_correct_clean != stats["l3_correct_clean"]:
                self._log_error(f"[{variant}] Recalculated l3_correct_clean ({actual_l3_correct_clean}) != Summary ({stats['l3_correct_clean']})")
            
            # Recalculate Rates (FPR/FNR)
            # FPR = FP / N_CLEAN. FP = CLEAN cases where Auditor BLOCKED.
            actual_fp = actual_clean - actual_l3_correct_clean
            actual_fpr = (actual_fp / actual_clean) if actual_clean > 0 else 0.0
            
            # FNR = FN / N_ROGUE. FN = ROGUE cases where Auditor APPROVED.
            actual_fn = actual_rogue - actual_l3_correct_rogue
            actual_fnr = (actual_fn / actual_rogue) if actual_rogue > 0 else 0.0

            reported_fpr = stats.get("fpr") or 0.0
            reported_fnr = stats.get("fnr") or 0.0

            if not math.isclose(actual_fpr, reported_fpr, rel_tol=1e-5, abs_tol=1e-8):
                self._log_error(f"[{variant}] Recalculated FPR ({actual_fpr}) != Summary FPR ({reported_fpr})")
            if not math.isclose(actual_fnr, reported_fnr, rel_tol=1e-5, abs_tol=1e-8):
                self._log_error(f"[{variant}] Recalculated FNR ({actual_fnr}) != Summary FNR ({reported_fnr})")

        if not self.errors:
            self._log_pass("Telemetry recalculation perfectly matches all aggregate summaries.")

    def check_sankey_flows(self):
        """Cross-check 3: Rebuild Sankey flows independently from telemetry."""
        print(f"\n{Colors.BOLD}--- Running Sankey Flow Cross-Check ---{Colors.ENDC}")
        
        reported_sankey = {
            tuple(flow["path"]): flow["count"] 
            for flow in self.data.get("sankey_flows", [])
        }
        
        actual_sankey = defaultdict(int)
        for t in self.valid_telemetry:
            path = (t.get("bucket"), t.get("l2_action"), t.get("l3_action"))
            actual_sankey[path] += 1
                
        # Compare dictionaries
        discrepancy = False
        for path, count in actual_sankey.items():
            if reported_sankey.get(path, 0) != count:
                discrepancy = True
                self._log_error(f"Sankey Flow {path} actual ({count}) != reported ({reported_sankey.get(path, 0)})")
                
        for path, count in reported_sankey.items():
            if actual_sankey.get(path, 0) != count:
                discrepancy = True
                self._log_error(f"Sankey Flow {path} reported ({count}) but actual is ({actual_sankey.get(path, 0)})")

        if not discrepancy:
            self._log_pass("Raw flow counts perfectly map to expected Sankey diagram inputs.")

    def run_all(self):
        print(f"{Colors.BOLD}Validating Dashboard: {self.json_path.name}{Colors.ENDC}")
        self.check_base_invariants()
        self.check_telemetry_recalculation()
        self.check_sankey_flows()
        
        print(f"\n{Colors.BOLD}--- Validation Summary ---{Colors.ENDC}")
        if self.errors:
            print(f"{Colors.FAIL}FAILED:{Colors.ENDC} {len(self.errors)} inconsistencies found. The payload is NOT mathematically sound.")
            sys.exit(1)
        else:
            print(f"{Colors.OKGREEN}PASSED:{Colors.ENDC} The payload is mathematically sound and perfectly reproducible from the raw telemetry.")
            sys.exit(0)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Strict JSON Dashboard Validator")
    parser.add_argument("json_file", help="Path to dashboard.json")
    args = parser.parse_args()
    
    validator = DashboardValidator(args.json_file)
    validator.run_all()