# Stub — Logging utilities for LLM call telemetry.
# In production this writes to a structured log/datalake.
# Stubbed here so the audit workflow runs standalone.

import json
import os
import threading
from pathlib import Path
from datetime import datetime

# Global lock for thread-safe file appending
_log_lock = threading.Lock()

def _get_log_dir() -> Path:
    if "AUDIT_RUN_DIR" in os.environ:
        return Path(os.environ["AUDIT_RUN_DIR"]) / "_provenance"
    return Path(__file__).parent.parent / "output" / "_logs"

def log_llm_call(log_data: dict):
    """Thread-safe append to JSONL log file."""
    try:
        _get_log_dir().mkdir(parents=True, exist_ok=True)
        log_file = _get_log_dir() / "llm_calls.jsonl"
        
        # Acquire lock to prevent interleaved writes from different threads
        with _log_lock:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_data, default=str) + "\n")
    except Exception:
        pass


def log_json_extraction_failure(run_id, calling_tool, model_id, raw_text, attempts):
    """Record a JSON extraction failure for debugging."""
    try:
        _get_log_dir().mkdir(parents=True, exist_ok=True)
        log_file = _get_log_dir() / "json_failures.jsonl"
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "run_id": run_id,
            "calling_tool": calling_tool,
            "model_id": model_id,
            "raw_text_len": len(raw_text) if raw_text else 0,
            "attempts": attempts,
        }
        
        # Acquire lock to prevent interleaved writes
        with _log_lock:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, default=str) + "\n")
    except Exception:
        pass


def save_raw_trace(run_id, model_id, raw_content, thinking_content="",
                   prompt_messages=None, provider_id="N/A", alias="Unknown",
                   params=None, execution_target="unknown",
                   wire_payload=None, wire_headers=None, 
                   wire_raw_body=None, openrouter_generation=None,
                   l2_variant=None, l2_manifest_filename=None): 
    try:
        trace_dir = _get_log_dir() / "traces"
        trace_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%H%M%S_%f") 
        safe_run = run_id.replace("/", "_").replace(":", "_")
        
        # Extract Zxx variant from manifest filename if available
        variant_suffix = ""
        if l2_manifest_filename:
            import re
            match = re.search(r"(Z\d+)", l2_manifest_filename)
            if match:
                variant_suffix = f"_L2_{match.group(1)}"
        
        trace_file = trace_dir / f"{safe_run}{variant_suffix}_{ts}.json"
        
        # Note: No lock needed here because each trace gets a unique filename
        trace_file.write_text(json.dumps({
            "run_id": run_id,
            "model_id": model_id,
            "provider_id": provider_id,
            "alias": alias,
            "execution_target": execution_target,
            "params": params or {},
            "wire_payload": wire_payload, 
            "wire_headers": wire_headers,
            "wire_raw_body": wire_raw_body,
            "openrouter_generation": openrouter_generation,
            "prompt_messages": prompt_messages or [],
            "raw_content": raw_content[:5000],
            "thinking_content": (thinking_content or "")[:5000],
        }, indent=2, default=str), encoding="utf-8")
    except Exception:
        pass