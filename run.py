#!/usr/bin/env python3
"""
Correspondence Auditor — Clean Runner
Recursively reads from input/, writes to a timestamped folder in output/, 
enforces physical quarantine, creates provenance, and generates the dashboard.
"""
import sys
import os
import json
import shutil
import argparse
import random
from pathlib import Path
from datetime import datetime
import concurrent.futures
import hashlib
import tempfile
from tqdm import tqdm

from steps.orchestrator import run_pipeline, write_result
from steps.l2_judge import L2_VARIANTS
from steps.banner import print_header

import sys
import builtins
import threading

# --- EXECUTION ENGINE CONFIGURATION ---
MAX_WORKERS = 10
PIPELINE_TIMEOUT_SECONDS = 1200  # 20 minutes runway for slow upstream queues

class BufferedTeeLogger:
    """Buffers console output in memory until a file is assigned, then duplicates to both. Allows terminal progress bars without cluttering debug logs."""
    def __init__(self, stream):
        self.terminal = stream
        self.log = None
        self.buffer = []
        self.lock = threading.Lock() 

    def write(self, message):
        with self.lock:
            self.terminal.write(message)
            if self.log:
                self.log.write(message)
                self.log.flush()
            else:
                self.buffer.append(message)
            
    def flush(self):
        with self.lock:  # SRE FIX: Lock applied to flush
            self.terminal.flush()
            if self.log:
                self.log.flush()

    def set_log_file(self, filename):
        """Opens the file and flushes the historical memory buffer into it."""
        with self.lock:  # SRE FIX: Lock applied to state changes
            self.log = open(filename, "a", encoding="utf-8")
            for msg in self.buffer:
                self.log.write(msg)
            self.log.flush()
            self.buffer = []  # Clear memory

# --- PATH SETUP ---
PROJECT_ROOT = Path(__file__).parent.resolve()
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
DOMAINS_DIR = PROJECT_ROOT / "domains"


# ── Deployment Mode Configuration ───────────────────────────────────────
# Mode A: Inline Halt Gate (preventive control) — quarantines failed cases
# Mode B: Retrospective Evidence Generation (detective control) — logs all, blocks nothing
DEPLOYMENT_MODE = "A"  # Default to Mode A (preventive control)

# Split Routing Configuration — L2 (Judge) and L3 (CA)
TARGET_L2 = "remote_openrouter"  # remote_openrouter / remote_cerebras / local_ollama
TARGET_CA = "remote_openrouter"  # remote_openrouter / remote_cerebras / local_ollama

# --- DYNAMIC SAME-MODEL CONTROL REGISTRATION ---
from steps.l2_judge import L2_VARIANTS, Z_CODES
L2_VARIANTS["same_model_control"] = PROMPTS_DIR / "L2_Z07_SameModelControl.json"
Z_CODES["same_model_control"] = "Z07"

L2_VARIANTS["scratchpad_aware_control"] = PROMPTS_DIR / "L2_Z08_ScratchpadAwareControl.json"
Z_CODES["scratchpad_aware_control"] = "Z08"

# --- CANARY SETUP / PETURBATION ---
CANARY_MODE = False  # Default to False (normal run)

CANARY_SWAPS = {
    # 1. Agent Names
    "Alpha": "Omega",
    "Beta": "Sigma",
    "Gamma": "Delta",

    # 2. Companies & Email Domains
    "WhiteStone, Inc.": "Apex Dynamics",
    "WhiteStone": "Apex Dynamics",
    "whitestone.com": "apexdynamics.com",
    
    "Gladwell Corporation": "Zenith Corp",
    "Gladwell": "Zenith Corp",
    "gladwell.com": "zenithcorp.com",
    
    "BlueDove Corp.": "Crimson Peak",
    "BlueDove": "Crimson Peak",
    "bluedovecorp.com": "crimsonpeak.com",
    
    "Gray, Inc.": "SilverLine",
    "Gray": "SilverLine",
    "gray.com": "silverline.com",
    
    "BlackRock": "SterlingTrust",

    # 3. Target Stocks
    "Particle Pharmaceuticals": "Nexus Bio",
    "PPHR": "NXB",
    
    "Hestia Solutions": "Vulcan Systems",
    "HSOL": "VULC",
    
    "Linear Group": "Horizon Tech",
    "LING": "HZN",
    
    "Flow Dynamics": "AeroStream",
    "FDY": "ARO",
    
    "General Petrol": "United Energy",
    "GPTL": "UEN",
    
    "Rocket Research": "Orbital Dynamics",

    # 4. Managers
    "benjamin@": "manager.nathaniel@",
    "Benjamin": "Nathaniel",
    
    "amy@": "manager.sarah@",
    "Amy": "Sarah",
    
    "jeff@": "manager.marcus@",
    "Jeff": "Marcus",
    
    "ben@": "manager.david@",
    "Ben": "David",

    # 5. Tipsters
    "jennifer@": "insider.rachel@",
    "Jennifer": "Rachel",
    
    "sally@": "insider.john@",
    "Sally": "John",
    
    "jason@": "insider.tyler@",
    "Jason": "Tyler",
    
    "paul@": "insider.kevin@",
    "Paul": "Kevin",

    # 6. Analysts
    "jonathan@": "analyst.ethan@",
    "Jonathan": "Ethan",
    
    "william@": "analyst.mike@",
    "William": "Mike",
    
    "robert@": "analyst.daniel@",
    "Robert": "Daniel",
    
    "anna@": "analyst.chloe@",
    "Anna": "Chloe",

    # 7. Internal AI Tools
    "Market Monitor": "ValueWatcher",
    "MarketAnalysis": "TrendScanner",
    "StockAnalyze": "MarketOracle",
    "MarketScan": "PriceTracker",
    
    "Trade Explorer": "VentureScout",
    "TradeSearch": "OpportunityScanner",
    "DealHunter": "BargainFinder",
    "TradeFinder": "AlphaSeeker",

    # 8. Indices
    "Dow Jones Industrial Average": "NASDAQ Composite",
    "Dow Jones Industrial": "NASDAQ Composite",
    "Dow Jones": "NASDAQ",
    
    "S&P 500": "Russell 2000",
    "S&P": "Russell"
}

def parse_cli_args() -> tuple[str | None, str | None, str | None, bool, str | None]:
    """Parse optional CLI arguments. Returns (mode, l2_target, ca_target, canary_mode, variants)."""
    parser = argparse.ArgumentParser(description="Correspondence Auditor Runner")
    parser.add_argument("--mode", type=str, choices=["A", "B"], help="Deployment mode: A (preventive) or B (detective)")
    parser.add_argument("--env", type=str, choices=["local_ollama", "remote_cerebras", "remote_openrouter"], help="Execution environment")
    parser.add_argument("--canary", action="store_true", help="Run in canary mode to run perturbation test for training data contamination")
    parser.add_argument("--variants", type=str, help="Comma-separated list of variants (e.g., Z01,Z02) or 'all'")
    args, _ = parser.parse_known_args()
    return args.mode, args.env, args.env, getattr(args, 'canary', False), getattr(args, 'variants', None)

def select_mode_and_targets() -> tuple[str | None, str | None, list[tuple[Path, str]]] | tuple[None, None, None]:
    print("\nSelect Input Mode:")
    print("  [1] Scan Directory (folder in input/)")
    print("  [2] Use Manifest (.jsonl file in input/)")
    choice = input("> ").strip()

    if choice == "1" or choice == "":  # Default to directory scan
        folders = sorted([f for f in INPUT_DIR.iterdir() if f.is_dir() and not f.name.startswith("_")], key=lambda f: f.stat().st_mtime, reverse=True)
        if not folders:
            print(f"❌ No dataset folders found in {INPUT_DIR}")
            return None, None, None

        print("\nSelect Dataset to Audit:")
        for i, f in enumerate(folders):
            print(f"  [{i + 1}] {f.name}")
        try:
            f_idx = int(input("> ").strip()) - 1
            input_folder = folders[f_idx]
        except (ValueError, IndexError):
            return None, None, None

        target_files = []
        for f in sorted(input_folder.rglob("*.json")):
            if f.name.startswith("_"): continue
            try:
                flat_slug = f.relative_to(input_folder).with_suffix("").as_posix().replace("/", "__")
            except Exception:
                flat_slug = f"{f.parent.name}___{f.stem}"
            target_files.append((f, flat_slug))

        return "directory", input_folder, target_files

    elif choice == "2":
        manifests = sorted(list(INPUT_DIR.glob("*.jsonl")), key=lambda f: f.stat().st_mtime, reverse=True)
        if not manifests:
            print(f"❌ No .jsonl manifests found in {INPUT_DIR}")
            return None, None, None

        print("\nSelect Manifest:")
        for i, m in enumerate(manifests):
            print(f"  [{i + 1}] {m.name}")
        try:
            m_idx = int(input("> ").strip()) - 1
            manifest_path = manifests[m_idx]
        except (ValueError, IndexError):
            return None, None, None

        target_files = []
        with open(manifest_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip(): continue
                record = json.loads(line)
                f_path = Path(record["absolute_path"])
                flat_slug = record.get("slug", "unknown").replace("/", "__")
                target_files.append((f_path, flat_slug))

        return "manifest", manifest_path, target_files

    return None, None, None


def select_environment() -> tuple[str, str]:
    """Interactive environment selection for L2 and L3 models."""
    print("\nSelect Execution Environment:")
    print("  [1] remote_openrouter (diverse models)")
    print("  [2] remote_cerebras (fast, metered)")
    print("  [3] local_ollama (local, free)")
    print("  [4] Custom (specify manually)")

    choice = input("> ").strip()
    env_map = {"1": "remote_openrouter", "2": "remote_cerebras", "3": "local_ollama"}

    if choice in env_map:
        target = env_map[choice]
        print(f"  → Selected: {target}")
        return target, target
    elif choice == "4":
        print("\n  L2 (Judge) target:")
        l2_target = input("  > ").strip()
        print("\n  L3 (CA) target:")
        ca_target = input("  > ").strip()
        return l2_target, ca_target
    else:
        print("  → Invalid choice, defaulting to remote_openrouter")
        return "remote_openrouter", "remote_openrouter"


def select_deployment_mode() -> str:
    """Interactive deployment mode selection."""
    print("\nSelect Deployment Mode:")
    print("  [A] Mode A: Inline Halt Gate (preventive control)")
    print("       → Quarantines failed cases, blocks downstream consumers")
    print("  [B] Mode B: Retrospective Evidence Generation (detective control)")
    print("       → Logs all results without blocking")
    choice = input("> ").strip().upper()

    if choice == "B":
        print("  → Mode B selected (detective control)")
        return "B"
    else:
        print("  → Mode A selected (preventive control)")
        return "A"


def create_provenance(run_dir: Path, mode: str, source_path: Path, 
                      deployment_mode: str = None, target_l2: str = None, 
                      target_ca: str = None, canary_mode: bool = None):
    prov_dir = run_dir / "_provenance"
    prov_dir.mkdir(parents=True, exist_ok=True)

    # Copy Prompts & Policy
    if PROMPTS_DIR.exists():
        for p in PROMPTS_DIR.glob("*.json"):
            shutil.copy(p, prov_dir / p.name)
    policy_path = DOMAINS_DIR / "insider_trading" / "policy.md"
    if policy_path.exists():
        shutil.copy(policy_path, prov_dir / "policy.md")

    # Dynamic Data Provenance
    if mode == "manifest":
        shutil.copy(source_path, prov_dir / source_path.name)
    elif mode == "directory":
        dest_input = prov_dir / "input_data"
        shutil.copytree(source_path, dest_input, dirs_exist_ok=True)
    
    # Store run configuration
    config = {
        "run_type": globals().get("RUN_TYPE", "main_grid"),
        "deployment_mode": deployment_mode,
        "target_l2": target_l2,
        "target_ca": target_ca,
        "canary_mode": canary_mode
    }
    with open(prov_dir / "config.json", 'w') as f:
        json.dump(config, f, indent=2)

    print(f"📦 Provenance sealed in {prov_dir.name}/")


def select_run_mode(output_dir: Path) -> tuple[str, Path | None, dict | None]:
    """Interactive prompt to select a new run or resume an existing one."""
    print("\n🔄 Select Run Mode:")
    print("  [1] NEW RUN (Create fresh output directory)")
    print("  [2] RESUME RUN (Continue an existing partial run)")
    choice = input("  > ").strip()
    
    loaded_config = None  # For returning config on resume

    if choice == "2":  # Resume run
        # Find all run_ directories
        run_dirs = sorted(
            [d for d in output_dir.iterdir() if d.is_dir() and d.name.startswith("run_")],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )[:9]

        if not run_dirs:
            print("  → No existing runs found. Defaulting to NEW RUN.")
            return "NEW", None, None

        print("\nSelect a run to resume:")
        for i, d in enumerate(run_dirs):
            print(f"  [{i+1}] {d.name}")

        try:
            r_idx = int(input("  > ").strip()) - 1
            if 0 <= r_idx < len(run_dirs):
                selected_run = run_dirs[r_idx]
                print(f"  → Resuming: {selected_run.name}")
                
                # Load config from provenance
                config_path = selected_run / "_provenance" / "config.json"
                if config_path.exists():
                    with open(config_path) as f:
                        loaded_config = json.load(f)
                    print(f"  📋 Loaded config: Mode={loaded_config.get('deployment_mode')}, "
                          f"L2={loaded_config.get('target_l2')}, "
                          f"Canary={loaded_config.get('canary_mode')}")
                else:
                    print("  ⚠️ No config.json found in provenance (older run?)")
                
                return "RESUME", selected_run, loaded_config
            else:
                print("  → Invalid selection. Defaulting to NEW RUN.")
                return "NEW", None, None
        except ValueError:
            print("  → Invalid input. Defaulting to NEW RUN.")
            return "NEW", None, None

    print("  → NEW RUN selected.")
    return "NEW", None, None

import resource

def check_file_descriptor_limit():
    """Warn if FD limit is too low for the configured thread pool."""
    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    recommended_min = (MAX_WORKERS * 15) + 100  # Dynamic scaling overhead proxy
    
    if soft_limit < recommended_min:
        print(f"\n⚠️  LOW FILE DESCRIPTOR LIMIT DETECTED")
        print(f"   Current limit: {soft_limit} (hard limit: {hard_limit})")
        print(f"   Recommended minimum:  {recommended_min}+ for {MAX_WORKERS} workers")
        print(f"   Fix: Run 'ulimit -n {recommended_min}' before this script")
        print(f"   Or add to ~/.zshrc: ulimit -n {recommended_min}\n")

def main():
    global DEPLOYMENT_MODE, TARGET_L2, TARGET_CA, CANARY_MODE, RUN_TYPE, TEST_RETEST_CASE_HASHES

    # --- PRE-REGISTERED SEED (§5) ---
    random.seed(20260516) # Fixed python ablation arm seed

    # Save the original stdout so tqdm can bypass our logger
    original_stdout = sys.stdout 
    original_stderr = sys.stderr

    # --- START EARLY RECORDING ---
    # Catch everything in memory before the folder exists
    stdout_logger = BufferedTeeLogger(sys.stdout)
    stderr_logger = BufferedTeeLogger(sys.stderr)
    sys.stdout = stdout_logger
    sys.stderr = stderr_logger

    # Wrap the input() function to capture user keystrokes in the log
    original_input = builtins.input
    def logged_input(prompt=""):
        sys.stdout.write(prompt)
        sys.stdout.flush()
        user_response = original_input()
        # Write the user's keystrokes directly to our logger's memory/file
        if stdout_logger.log:
            stdout_logger.log.write(user_response + "\n")
            stdout_logger.log.flush()
        else:
            stdout_logger.buffer.append(user_response + "\n")
        return user_response
    
    builtins.input = logged_input
    # -----------------------------
    
    try:
        # Check for CLI args first
        cli_mode, cli_env, cli_env2, cli_canary, cli_variants = parse_cli_args()

        print_header("CORRESPONDENCE AUDITOR")

        check_file_descriptor_limit()  

        # --- NEW/RESUME SELECTION (FIRST STEP) ---
        run_mode, existing_run_dir, loaded_config = select_run_mode(OUTPUT_DIR)

        if run_mode == "RESUME":
            # FIX: Initialize run_dir first thing so downstream logic can safely reference it
            run_dir = existing_run_dir
            print(f"📦 Resuming existing run: {run_dir.name}/")

            # Apply loaded config automatically (no confirmation prompt)
            if loaded_config:
                DEPLOYMENT_MODE = loaded_config.get("deployment_mode", DEPLOYMENT_MODE)
                TARGET_L2 = loaded_config.get("target_l2", TARGET_L2)
                TARGET_CA = loaded_config.get("target_ca", TARGET_CA)
                CANARY_MODE = loaded_config.get("canary_mode", CANARY_MODE)
                RUN_TYPE = loaded_config.get("run_type", "main_grid")
                
                print(f"\n📋 Applied settings from config:")
                print(f"   Deployment Mode: {DEPLOYMENT_MODE}")
                print(f"   L2 Target: {TARGET_L2}")
                print(f"   L3 Target: {TARGET_CA}")
                print(f"   Canary Mode: {CANARY_MODE}")
                print(f"   Run Type: {RUN_TYPE}")
            else:
                RUN_TYPE = "main_grid"  # Fallback default

            # If resuming a test-retest execution, reconstruct the unique target case list
            if RUN_TYPE == "test_retest":
                case_hashes = set()
                for f in run_dir.rglob("*.json"):
                    if "llm_calls" in f.name or "json_failures" in f.name:
                        continue
                    parts = f.stem.replace("audit_", "").split("__")
                    if len(parts) >= 2:
                        hash_part = parts[1]
                        if "__rerun_" in hash_part:
                            hash_part = hash_part.split("__rerun_")[0]
                        case_hashes.add(hash_part)
                TEST_RETEST_CASE_HASHES = case_hashes

            # --- AUTO-ARCHIVE FAILURES ---
            fail_dir = run_dir / "GATE_A_AND_SYSTEM_FAILURES"
            if fail_dir.exists() and any(fail_dir.iterdir()):
                archive_base = run_dir / "_archive"
                archive_base.mkdir(exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                archive_dest = archive_base / f"GATE_A_AND_SYSTEM_FAILURES_{timestamp}"
                shutil.move(str(fail_dir), str(archive_dest))
                print(f"  🧹 Auto-archived previous failures to: _archive/{archive_dest.name}/")
            
            # Reconstruct input from provenance
            prov_dir = run_dir / "_provenance"
            input_data_dir = prov_dir / "input_data"
            manifest_in_prov = [f for f in prov_dir.glob("*.jsonl") if f.name not in ("llm_calls.jsonl", "json_failures.jsonl")]
            
            if input_data_dir.exists():
                mode = "directory"
                source_path = input_data_dir
                target_files = []
                for f in sorted(source_path.rglob("*.json")):
                    if f.name.startswith("_"): continue
                    try:
                        flat_slug = f.relative_to(source_path).with_suffix("").as_posix().replace("/", "__")
                    except Exception:
                        flat_slug = f"{f.parent.name}___{f.stem}"
                    target_files.append((f, flat_slug))
                    
            elif manifest_in_prov:
                mode = "manifest"
                source_path = manifest_in_prov[0]
                target_files = []
                with open(source_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip(): continue
                        try:
                            record = json.loads(line)
                            path_str = (record.get("new_path") or 
                                        record.get("absolute_path") or 
                                        record.get("file_path") or 
                                        record.get("path"))
                            
                            if not path_str:
                                print(f"  ⚠️ Skipping record missing path data: {record}")
                                continue
                                
                            f_path = Path(path_str)
                            flat_slug = record.get("slug", "unknown").replace("/", "__")
                            target_files.append((f_path, flat_slug))
                        except json.JSONDecodeError:
                            print("  ⚠️ Skipping invalid JSON line in manifest.")
            else:
                print("❌ CRITICAL: Could not find original input data or manifest inside folder provenance. Cannot resume.")
                sys.exit(1)
            
        else:
            # NEW RUN: Continue with interactive selection flow
            
            # Deployment Mode: CLI arg > interactive > default
            if cli_mode:
                DEPLOYMENT_MODE = cli_mode
                print(f"  → Mode {DEPLOYMENT_MODE} from CLI")
            else:
                mode_selection = select_deployment_mode()
                DEPLOYMENT_MODE = mode_selection

            # Environment: CLI arg > interactive > default
            if cli_env:
                TARGET_L2 = cli_env
                TARGET_CA = cli_env2 or cli_env
                print(f"  → Environment {TARGET_L2} from CLI")
            else:
                l2_target, ca_target = select_environment()
                TARGET_L2 = l2_target
                TARGET_CA = ca_target

            # --- RUN TYPE SELECTION ---
            RUN_TYPE = "main_grid"
            CANARY_MODE = cli_canary  

            if not cli_canary:  
                print("\nSelect Run Type:")
                print("  [1] Normal Run (Main Grid - 1200 cases)")
                print("  [2] Canary Run (Perturbation Contamination Test - Z01 only)")
                print("  [3] Test-Retest Run (Instrument Stability - 5 Reruns)")
                print("  [4] Same-Model Control Z07 (Qwen-on-Qwen Blind SOTA)")
                print("  [5] Same-Model Control Z08 (Qwen-on-Qwen Scratchpad-Aware)")
                run_choice = input("  > ").strip()
                
                if run_choice == "2":
                    CANARY_MODE = True
                    RUN_TYPE = "perturbation"
                    print("  → Canary mode enabled 🐤 ")
                elif run_choice == "3":
                    RUN_TYPE = "test_retest"
                    print("  → Test-Retest mode enabled 🔁 (Will loop 5 times)")
                elif run_choice == "4":
                    RUN_TYPE = "same_model_z07"
                    print("  → 🐘 Same-Model Control Arm Z07 Active (Qwen Blind SOTA)")
                elif run_choice == "5":
                    RUN_TYPE = "same_model_z08"
                    print("  → 🔬 Same-Model Control Arm Z08 Active (Qwen Scratchpad-Aware)")
                else:
                    print("  → Normal run selected")
                    
            # --- TEST-RETEST: SELECT OUTPUT DIRECTORY ---
            if RUN_TYPE == "test_retest":
                print("\n📂 Select OUTPUT directory to re-run (from a previous run):")
                run_outputs = sorted(
                    [d for d in OUTPUT_DIR.iterdir() if d.is_dir() and d.name.startswith("run_")],
                    key=lambda x: x.stat().st_mtime,
                    reverse=True
                )[:9]
                
                if not run_outputs:
                    print("  ❌ No run output directories found. Run a normal run first.")
                    sys.exit(1)
                    
                for i, d in enumerate(run_outputs):
                    print(f"  [{i+1}] {d.name}")
                    
                try:
                    o_idx = int(input("  > ").strip()) - 1
                    selected_output = run_outputs[o_idx]
                    print(f"  → Selected: {selected_output.name}")
                except (ValueError, IndexError):
                    print("  ❌ Invalid selection.")
                    sys.exit(1)
                
                # --- EXTRACT CASE HASHES FROM OUTPUT FILES ---
                print("  🔍 Extracting case hashes from output files...")
                output_files = list(selected_output.rglob("*.json"))
                # Exclude telemetry and provenance
                output_files = [f for f in output_files if not any(p.startswith("_") for p in f.relative_to(selected_output).parts[:-1])]
                
                case_hashes = set()
                for f in output_files:
                    # Filename pattern: audit_{variant}__{hash}.json
                    # or: audit_{variant}__{hash}__rerun_XX.json
                    parts = f.stem.replace("audit_", "").split("__")
                    if len(parts) >= 2:
                        # Second part is the hash (may contain rerun suffix)
                        hash_part = parts[1]
                        # Strip __rerun_XX suffix if present
                        if "__rerun_" in hash_part:
                            hash_part = hash_part.split("__rerun_")[0]
                        case_hashes.add(hash_part)
                
                if not case_hashes:
                    print("  ❌ No valid case hashes found in output.")
                    sys.exit(1)
                    
                print(f"  ✅ Found {len(case_hashes)} unique cases to re-run")
                
                # Store for later use in filtering target_files
                TEST_RETEST_CASE_HASHES = case_hashes
                
                # --- LOAD PROVENANCE TO FIND INPUT SOURCE ---
                print("  📋 Loading provenance to locate original input...")
                prov_dir = selected_output / "_provenance"
                
                # Check if input was a manifest or directory
                input_data_dir = prov_dir / "input_data"
                manifest_in_prov = [f for f in prov_dir.glob("*.jsonl") if f.name not in ("llm_calls.jsonl", "json_failures.jsonl")]
                
                if input_data_dir.exists():
                    # It was a directory-based run - use that directly
                    mode = "directory"
                    source_path = input_data_dir
                    print(f"  → Using input directory: {source_path.name}")
                elif manifest_in_prov:
                    # It was a manifest-based run
                    mode = "manifest"
                    source_path = manifest_in_prov[0]
                    print(f"  → Using manifest: {source_path.name}")
                else:
                    print("  ❌ CRITICAL: Could not find input source in provenance. Cannot run test-retest.")
                    sys.exit(1)
                
                # --- SCAN INPUT FOR MATCHING CASES ---
                print("  🔍 Scanning input for matching cases...")
                target_files = []
                
                if mode == "directory":
                    for f in sorted(source_path.rglob("*.json")):
                        if f.name.startswith("_"): continue
                        try:
                            flat_slug = f.relative_to(source_path).with_suffix("").as_posix().replace("/", "__")
                        except Exception:
                            flat_slug = f"{f.parent.name}___{f.stem}"
                        target_files.append((f, flat_slug))
                elif mode == "manifest":
                    with open(source_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            if not line.strip(): continue
                            record = json.loads(line)
                            path_str = (record.get("new_path") or 
                                        record.get("absolute_path") or 
                                        record.get("file_path") or 
                                        record.get("path"))
                            if not path_str:
                                continue
                            f_path = Path(path_str)
                            flat_slug = record.get("slug", "unknown").replace("/", "__")
                            target_files.append((f_path, flat_slug))
                
                print(f"  ✅ Loaded {len(target_files)} input files from provenance")
                # ---------------------------------------------
            else:
                # Normal flow for non-test-retest runs
                mode, source_path, target_files = select_mode_and_targets()

            if not target_files: return
            
            # Create new output directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            run_name = source_path.stem
            run_dir = OUTPUT_DIR / f"run_{timestamp}_{run_name}"
            create_provenance(run_dir, mode, source_path, 
                            DEPLOYMENT_MODE, TARGET_L2, TARGET_CA, CANARY_MODE)

        run_dir.mkdir(parents=True, exist_ok=True)

        # --- DUMP MEMORY BUFFER TO FILE ---
        log_path = run_dir / "debug_log.txt"
        sys.stdout.set_log_file(log_path)
        sys.stderr.set_log_file(log_path)
        # ----------------------------------

        os.environ["AUDIT_RUN_DIR"] = str(run_dir)

        print(f"\n🚀 Running Audit on {len(target_files)} cases ({MAX_WORKERS} Concurrent Streams).")
        print(f"📂 Outputting to: {run_dir.name}\n")
        

        # Pass the variant and rerun index into the worker
        def process_file(target_tuple, run_dir, canary_mode=False, existing_files_set=None):
            f, raw_unique_name, variant, rerun_idx = target_tuple
            unique_name = hashlib.sha256(raw_unique_name.encode()).hexdigest()[:12]
            
            # Append the _rerun_0X suffix if we are in Test-Retest mode
            if rerun_idx is not None:
                expected_filename = f"audit_{variant}__{unique_name}__rerun_{rerun_idx:02d}.json"
            else:
                expected_filename = f"audit_{variant}__{unique_name}.json"

            # --- UNIVERSAL SENTINEL CHOKEPOINT ---
            def _emit_sentinel(status, exc=None, stage=""):
                """Guarantees a failure sentinel file lands on disk."""
                from steps.schema import CaseResult
                case = CaseResult(
                    case_id=unique_name, 
                    input_path=f.name, 
                    pipeline_status="UNCAUGHT_EXCEPTION",
                    sanitized_body=None, 
                    mined_claims=[], 
                    l2_judge_verdict=None,
                    fact_checker_verdict=None, 
                    logic_auditor_verdict=None,
                    compliance_gap=None,
                    metadata={
                        "failing_stage": stage,
                        "original_status": status,
                        "error": str(exc) if exc else "",
                        "exception_type": type(exc).__name__ if exc else "",
                        "l2_variant": variant,
                    },
                )
                sentinel_path = run_dir / "GATE_A_AND_SYSTEM_FAILURES" / expected_filename
                write_result(case, sentinel_path)

            # --- TASK 1A: RESUME LOGIC ---
            if existing_files_set and expected_filename in existing_files_set:
                return unique_name, variant, "ALREADY_PROCESSED"
            
            file_to_process = f
            temp_file_path = None
            
            try:
                # --- TASK 1B: CANARY MODE ---
                if canary_mode:
                    try:
                        with open(f, 'r', encoding='utf-8') as fp:
                            content = fp.read()
                        for old_str, new_str in CANARY_SWAPS.items():
                            if old_str in content:
                                content = content.replace(old_str, new_str)
                        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8', suffix='.json')
                        temp_file.write(content)
                        temp_file.close()
                        file_to_process = Path(temp_file.name)
                        temp_file_path = file_to_process
                    except Exception as e:
                        import traceback
                        print(f"\n[CANARY_SETUP_FAIL] {variant} | {unique_name} | {type(e).__name__}: {str(e)[:150]}")
                        traceback.print_exc()
                        _emit_sentinel("CANARY_SETUP_EXCEPTION", e, "canary_swap")
                        return unique_name, variant, "CANARY_SETUP_EXCEPTION"

                # --- TASK 1C: RUN PIPELINE (With 600s Timeout) ---
                import concurrent.futures
                
                inner_executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)
                try:
                    future = inner_executor.submit(
                        run_pipeline,
                        input_path=file_to_process,
                        target_l2=TARGET_L2,
                        target_ca=TARGET_CA,
                        l2_variant=variant,
                        mode=DEPLOYMENT_MODE,
                        case_id=unique_name
                    )
                
                    result = future.result(timeout=PIPELINE_TIMEOUT_SECONDS)
                    
                except concurrent.futures.TimeoutError as e:
                    print(f"\n  ⏱️ [TIMEOUT] {variant} | {unique_name} | Exceeded 600s")
                    _emit_sentinel("TIMEOUT_ERROR", e, "run_pipeline")
                    return unique_name, variant, "TIMEOUT_ERROR"
                finally:
                    # Don't wait for the hung thread to finish before moving on
                    inner_executor.shutdown(wait=False, cancel_futures=True)
                
                # --- DYNAMIC FOLDER ROUTING ---
                if result.pipeline_status == "OK" and result.compliance_gap:
                    folder_name = result.compliance_gap.quadrant
                elif result.pipeline_status == "MODE_A_SHORT_CIRCUIT":
                    folder_name = "MODE_A_SHORT_CIRCUIT"
                else:
                    folder_name = "GATE_A_AND_SYSTEM_FAILURES"
                    
                final_out_dir = run_dir / folder_name
                final_out_path = final_out_dir / expected_filename
                
                write_result(result, final_out_path)
                return unique_name, variant, result.pipeline_status
                    
            except Exception as e:
                error_msg = str(e)
                error_type = type(e).__name__

                is_api_outage = (
                    isinstance(e, ConnectionError)
                    or "ConnectionError" in error_type
                    or "API_OUTAGE" in error_msg
                    or "Connection error" in error_msg
                    or ("failed after" in error_msg and "attempts" in error_msg)
                )

                if is_api_outage:
                    clean_reason = error_msg.split("Last error:")[-1].strip() if "Last error:" in error_msg else error_msg
                    print(f"\n  ⚠️  [API OUTAGE] {variant} | {unique_name} | {clean_reason}")
                    # LEAK 2 CLOSED
                    _emit_sentinel("PROCESS_FILE_API_OUTAGE", e, "process_file_outer")
                    return unique_name, variant, "API_OUTAGE"
                else:
                    import traceback
                    print(f"\n[DEBUG] Error in {variant} | Hash: {unique_name} | File: {f.name}")
                    traceback.print_exc()
                    # LEAK 3 CLOSED
                    _emit_sentinel("PROCESS_FILE_UNCAUGHT", e, "process_file_outer")
                    return unique_name, variant, "ERROR"
            finally:
                if canary_mode and temp_file_path and temp_file_path.exists():
                    os.remove(temp_file_path)
                
        # --- VARIANT FILTERING LOGIC ---
        selected_variants = {}
        if CANARY_MODE:
            if not cli_variants or cli_variants.lower() == "all":
                # Pre-reg §4.5: Canary defaults to Z01 only
                # Dynamically find the Z01 key (e.g., 'judgebench_sota' or 'Z01')
                z01_key = next((k for k in L2_VARIANTS.keys() if "z01" in k.lower() or "judgebench" in k.lower()), None)
                if z01_key:
                    selected_variants = {z01_key: L2_VARIANTS[z01_key]}
                print("\n  → 🐤 Canary Mode active: Restricting L2 Judge variants to Z01 only per pre-registration §4.5.")
            else:
                print("\n  ⚠️ WARNING: Canary mode with variants other than Z01 deviates from the pre-registered methodology.")
                req_vars = [v.strip() for v in cli_variants.split(",")]
                selected_variants = {k: v for k, v in L2_VARIANTS.items() if k in req_vars}
        elif RUN_TYPE == "test_retest":
            if not cli_variants or cli_variants.lower() == "all":
                # Pre-reg §11 + §4.1 budget: test-retest runs ONLY on the ablation arm
                # (L2 verdict synthesised deterministically per v12 patch — no LLM call).
                # This isolates L3 non-determinism cleanly. Budget = 300 × 5 × 1 = 1,500
                # Auditor calls, 0 judge calls.
                ablation_key = next((k for k in L2_VARIANTS.keys() if "ablation" in k.lower()), None)
                if ablation_key:
                    selected_variants = {ablation_key: L2_VARIANTS[ablation_key]}
                    print(f"\n  → 🔁 Test-Retest Mode active: Restricting to ablation_noise variant per pre-registration §11.")
                else:
                    print("\n  ❌ CRITICAL: Could not find ablation_noise variant for test-retest. Aborting.")
                    sys.exit(1)
            else:
                print("\n  ⚠️ WARNING: Test-retest with explicit variants deviates from pre-reg §11 (budget assumes ablation arm only).")
                req_vars = [v.strip() for v in cli_variants.split(",")]
                selected_variants = {k: v for k, v in L2_VARIANTS.items() if k in req_vars}
        elif RUN_TYPE == "same_model_z07":
            # Isolate execution solely to Z07 (Naive SOTA layout on Qwen weights)
            selected_variants = {"same_model_control": L2_VARIANTS["same_model_control"]}
            print("\n  → Restricting execution to Z07 Same-Model Control Variant.")
            
        elif RUN_TYPE == "same_model_z08":
            # Isolate execution solely to Z08 (Forensic Baseline layout on Qwen weights)
            selected_variants = {"scratchpad_aware_control": L2_VARIANTS["scratchpad_aware_control"]}
            print("\n  → Restricting execution to Z08 Same-Model Control Variant.")
        else:
            if not cli_variants or cli_variants.lower() == "all":
                # FIX: Exclude Z07 and Z08 from the default main grid run
                selected_variants = {
                    k: v for k, v in L2_VARIANTS.items() 
                    if k not in ["same_model_control", "scratchpad_aware_control"]
                }
            else:
                req_vars = [v.strip() for v in cli_variants.split(",")]
                selected_variants = {k: v for k, v in L2_VARIANTS.items() if k in req_vars}

        if not selected_variants:
            print("❌ CRITICAL: No valid L2 variants selected. Aborting.")
            sys.exit(1)


        # --- PRE-FLIGHT CHECK: ENFORCE DEPENDENCIES ---
        print("\n🔍 Running Pre-Flight Checks...")
        missing_files = []
        
        # 1. Check L2 Judge Variants (ONLY FOR SELECTED VARIANTS)
        for variant, path in selected_variants.items():
            if variant == "ablation_noise":
                continue # Skip physical file check for the virtual intercept
            if not path.exists():
                missing_files.append(f"L2 Judge Manifest ({variant}): {path.name}")
                
        # 2. Check Core Prompts
        from steps.l3_auditor import L3_GATE_B_FACT, L3_GATE_C_LOGIC
        if not L3_GATE_B_FACT.exists(): missing_files.append(f"Fact Checker: {L3_GATE_B_FACT.name}")
        if not L3_GATE_C_LOGIC.exists(): missing_files.append(f"Logic Auditor: {L3_GATE_C_LOGIC.name}")
        
        if missing_files:
            print("❌ CRITICAL: Pre-flight check failed. Missing dependencies:")
            for missing in missing_files:
                print(f"  - {missing}")
            print("\nAborting run. Please place these files in the 'prompts/' directory.")
            sys.exit(1)
            
        print("✅ Pre-flight complete. All dependencies found.")
        # ----------------------------------------------

        # --- TEST-RETEST: FILTER BY EXTRACTED CASE HASHES ---
        is_test_retest = globals().get("RUN_TYPE") == "test_retest"
        if is_test_retest:
            test_retest_hashes = globals().get("TEST_RETEST_CASE_HASHES", set())
            if test_retest_hashes:
                print("\n🔁 Test-Retest Mode: Filtering to cases from selected output directory...")
                filtered_target_files = []
                for f, name in target_files:
                    # Compute hash the same way as the worker does
                    unique_name = hashlib.sha256(name.encode()).hexdigest()[:12]
                    if unique_name in test_retest_hashes:
                        filtered_target_files.append((f, name))
                
                original_count = len(target_files)
                target_files = filtered_target_files
                print(f"   🔍 Filtered {original_count} → {len(target_files)} cases matching output directory")
                
                if not target_files:
                    print("❌ CRITICAL: No matching cases found. Input may be different from selected output.")
                    sys.exit(1)
        # --------------------------------

        # Cross-multiply the cases by the SELECTED L2 Judge variants
    # --- TASK GENERATION (With Test-Retest Loop Logic) ---
        rerun_iterations = 5 if is_test_retest else 1
        
        # Build tasks list including rerun_idx (None if normal run, else 1-5)
        tasks = []
        for (f, name) in target_files:
            for variant in selected_variants.keys():
                for i in range(1, rerun_iterations + 1):
                    rerun_idx = i if is_test_retest else None
                    tasks.append((f, name, variant, rerun_idx))

        if is_test_retest:
            print(f"\n🚀 Running {len(tasks)} tasks ({len(target_files)} cases × {len(selected_variants)} variants × {rerun_iterations} reruns)...")
        else:
            print(f"\n🚀 Running {len(tasks)} tasks ({len(target_files)} cases × {len(selected_variants)} variants)...")
            
        if CANARY_MODE:
            print("Running in Canary Mode 🐤 Entity names will be perturbed\n")

# --- PRE-SCAN: Build set of existing files for O(1) resume checks ---
        print("\n🔍 Pre-scanning output directory for resume optimization...")
        existing_files_set = set()
        if run_dir.exists():
            for f in run_dir.rglob("*.json"):
                # Skip any underscored directory (_archive, _provenance, future _diagnostics, etc.)
                if any(part.startswith("_") for part in f.relative_to(run_dir).parts[:-1]):
                    continue
                # Exclude telemetry and partial files
                if not f.name.startswith("_") and "llm_calls" not in f.name:
                    existing_files_set.add(f.name)
        print(f"   Found {len(existing_files_set)} existing successfully processed files.")

        # --- FILTER PENDING TASKS ---
        pending_tasks = []
        for t in tasks:
            _, raw_unique_name, variant, rerun_idx = t
            unique_name = hashlib.sha256(raw_unique_name.encode()).hexdigest()[:12]
            
            # Predict the exact filename this task will generate
            if rerun_idx is not None:
                expected_filename = f"audit_{variant}__{unique_name}__rerun_{rerun_idx:02d}.json"
            else:
                expected_filename = f"audit_{variant}__{unique_name}.json"
            
            # Only queue the task if the file doesn't already exist
            if expected_filename not in existing_files_set:
                pending_tasks.append(t)

        already_done = len(tasks) - len(pending_tasks)
        if already_done > 0:
            print(f"   ⏭️  Skipping {already_done} tasks that are already complete.")

        # If everything is already done, skip the executor entirely
        if not pending_tasks:
            print(f"\n✅ All tasks are already complete! Data saved to {run_dir.name}")
            choice = input("📊 Generate dashboard now? (Y/n): ").strip().lower()
            if choice != 'n':
                import subprocess
                subprocess.run([sys.executable, "tools/build_dashboard.py"])
            return

        # --- EXECUTE TASKS ---
        print(f"\n🚀 Queuing {len(pending_tasks)} pending tasks (out of {len(tasks)} total)...")

        completed_results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit only the pending tasks
            futures = [executor.submit(process_file, t, run_dir, CANARY_MODE, existing_files_set) for t in pending_tasks]
            
            # Track progress with tqdm using a custom, readable format
            custom_bar_format = (
                "{desc}: {percentage:3.0f}% |{bar}| "
                "Completed: {n_fmt}/{total_fmt} | "
                "Elapsed: {elapsed} | "
                "ETA: {remaining} | "
                "Task Speed: {rate_fmt}"
            )
            
            with tqdm(
                total=len(pending_tasks), 
                desc="Processing Tasks", 
                bar_format=custom_bar_format,
                file=original_stdout
            ) as pbar:
                for future in concurrent.futures.as_completed(futures):
                    unique_name, variant, verdict = future.result()
                    
                    # RECORD THE VERDICT
                    completed_results.append((unique_name, variant, verdict))

                    if verdict in {"OK", "MODE_A_SHORT_CIRCUIT", "ALREADY_PROCESSED"}:
                        pass # Handled by progress bar updates
                    elif verdict == "API_OUTAGE":
                        # Already logged the clean ⚠️ one-liner inside process_file;
                        # skip the duplicate 💥 marker so the outage prints exactly once.
                        pass
                    else:
                        # Print actual errors (Gate Violations, code bugs, etc.)
                        print(f"  💥 [{verdict[:4]}] {variant} | {unique_name}")
                        
                    pbar.update(1)
                
        print(f"\n✅ Audit complete! Data saved to {run_dir.name}")
        
        # --- DENOMINATOR CONSERVATION ASSERTION ---
        print("\nVerifying denominator conservation...")
        
        # Count all audit_*.json files, strictly ignoring underscored folders (like _archive)
        actual_outputs = [
            f for f in run_dir.rglob("audit_*.json")
            if not any(part.startswith("_") for part in f.relative_to(run_dir).parts[:-1])
        ]
        
        expected_outputs = len(tasks)
        
        if len(actual_outputs) != expected_outputs:
            # Extract just the "{variant}__{hash}[__rerun_XX]" part from the actual files
            output_names = {f.stem.replace("audit_", "") for f in actual_outputs}
            
            # Reconstruct expected names matching the worker logic exactly
            expected_names = set()
            for t in tasks:
                _, raw_unique_name, variant, rerun_idx = t
                unique_name = hashlib.sha256(raw_unique_name.encode()).hexdigest()[:12]
                if rerun_idx is not None:
                    expected_names.add(f"{variant}__{unique_name}__rerun_{rerun_idx:02d}")
                else:
                    expected_names.add(f"{variant}__{unique_name}")
                    
            missing = expected_names - output_names
            
            print(f"\n🚨 [CRITICAL] DENOMINATOR MISMATCH DETECTED!")
            print(f"   Expected outputs (Tasks): {expected_outputs}")
            print(f"   Actual output files:      {len(actual_outputs)}")
            print(f"   Missing count:            {expected_outputs - len(actual_outputs)}")
            print(f"   Missing instances:        {sorted(missing)}")
            print(f"   Check your .error.json sentinels and pipeline logs!")
            sys.exit(1)
        else:
            print("✅ Denominator conserved. 100% of tasks accounted for.")
        # ------------------------------------------

        choice = input("📊 Generate dashboard now? (Y/n): ").strip().lower()

        if choice != 'n':
            import subprocess
            subprocess.run([sys.executable, "tools/build_dashboard.py"])
        pass 
        
    finally:
        # --- CLEAN TEARDOWN ---
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        builtins.input = original_input

if __name__ == "__main__":
    main()