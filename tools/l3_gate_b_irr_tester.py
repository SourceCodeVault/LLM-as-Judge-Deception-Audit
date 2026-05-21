import json
import random
import csv
import re
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
NUM_CLAIMS = 50

# Fixed seed for reproducibility — committed at v1.0-prereg tag
RNG_SEED = "gate_b_irr_v1"

# Target stratum sizes (§4.6)
STRATUM_TARGETS = {
    "SUPPORTED": 17,
    "CONTRADICTED": 17,
    "UNSUPPORTED": 16,
}

# Explicit allow-list of keys known to hold the agent transcript.
PROVENANCE_TEXT_KEYS = ("source_text", "agent_transcript", "transcript", "text")
AUDIT_TEXT_KEYS = ("source_text", "agent_transcript", "transcript", "target_response")

# Arm detection: runs containing "ablation" in name are excluded per §4.6
ABLATION_PATTERN = re.compile(r"ablation", re.IGNORECASE)


def select_run() -> Path | None:
    if not OUTPUT_DIR.exists():
        print(f"❌ output/ directory not found at {OUTPUT_DIR}")
        return None
        
    runs = sorted([d for d in OUTPUT_DIR.iterdir() if d.is_dir() and d.name.startswith("run_")], reverse=True)
    
    if not runs:
        print("❌ No runs found in output/.")
        return None
    if len(runs) == 1:
        return runs[0]

    recent = runs[:9]
    print("\n📊 Select a run for manual annotation:")
    for i, d in enumerate(recent, 1):
        is_ablation = "ABLATION" if ABLATION_PATTERN.search(d.name) else "GENUINE"
        print(f"  [{i}] {d.name} [{is_ablation}]")
        
    while True:
        choice = input(f"\nEnter choice (1–{len(recent)}) or 'q': ").strip()
        if choice.lower() == "q":
            return None
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(recent):
                return recent[idx]
        except ValueError:
            pass
        print("❌ Invalid choice; try again.")


def is_genuine_arm(run_path: Path) -> bool:
    """Check if run is genuine arm (not ablation). Per §4.6, ablation is excluded."""
    return not ABLATION_PATTERN.search(run_path.name)


def get_source_text(data: dict, target_run: Path, log_name: str) -> tuple[str, bool]:
    """
    Strict resolution of the agent transcript.

    Returns (text, found). If found is False, the caller MUST exclude this
    case from the annotation sample. No silent fallback to arbitrary strings
    in the audit file — those are model-generated and would create circular
    human-vs-AI validation.
    """
    m = re.search(r"__(.*?)(?:\.error)?\.json$", log_name)
    file_hash = m.group(1) if m else "unknown"

    # 1. Provenance file (preferred — this is where transcripts live by design)
    prov_dir = target_run / "_provenance" / "inputs"
    if prov_dir.exists():
        for match in prov_dir.glob(f"*{file_hash}*.json"):
            try:
                with open(match, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                for key in PROVENANCE_TEXT_KEYS:
                    val = s_data.get(key) if isinstance(s_data, dict) else None
                    if isinstance(val, str) and val.strip():
                        return val, True
            except Exception:
                continue  # try next match

    # 2. Explicit transcript keys inside the audit JSON itself
    for key in AUDIT_TEXT_KEYS:
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val, True
        ctx = data.get("input_context") or {}
        if isinstance(ctx, dict):
            val = ctx.get(key)
            if isinstance(val, str) and val.strip():
                return val, True

    # No legitimate source found — caller will exclude this case.
    return f"[SOURCE TEXT NOT RESOLVED for hash {file_hash} — case excluded]", False


def stratify_sample(claims: list[dict], rng: random.Random) -> list[dict]:
    """
    Stratified sampling by ai_status to ensure non-degenerate κ.
    Per §4.6: target ~17/17/16 split. Deficits taken from SUPPORTED.
    """
    # Group by status
    strata = defaultdict(list)
    for claim in claims:
        strata[claim["ai_status"]].append(claim)

    # Verify we have all three classes
    missing = set(STRATUM_TARGETS.keys()) - set(strata.keys())
    if missing:
        print(f"⚠️  Missing strata in data: {missing}")
        print(f"   Available: {dict((k, len(v)) for k, v in strata.items())}")

    sample = []
    deficits = []

    for status, target in STRATUM_TARGETS.items():
        available = strata.get(status, [])
        if len(available) >= target:
            selected = rng.sample(available, target)
        else:
            # Deficit: take all available, record deficit
            selected = available
            deficits.append((status, target - len(available)))
            print(f"   ⚠️ {status} stratum undersized: {len(available)} < {target}")

        sample.extend(selected)

    # If we have deficits, take them from SUPPORTED (per §4.6)
    if deficits:
        supported_pool = strata.get("SUPPORTED", [])
        # Remove already-sampled SUPPORTED claims
        already_sampled = {id(c) for c in sample if c["ai_status"] == "SUPPORTED"}
        remaining = [c for c in supported_pool if id(c) not in already_sampled]
        
        for _, deficit in deficits:
            if remaining:
                take = min(deficit, len(remaining))
                picked = rng.sample(remaining, take)
                sample.extend(picked)
                picked_ids = {id(c) for c in picked}
                remaining = [c for c in remaining if id(c) not in picked_ids]

    rng.shuffle(sample)
    return sample


def generate_test():
    target_run = select_run()
    if not target_run:
        return

    # Arm filter: reject ablation runs per §4.6
    if not is_genuine_arm(target_run):
        print(f"❌ Run {target_run.name} is an ablation arm.")
        print("   §4.6 requires genuine arm only. Aborting.")
        return

    print(f"\n📂 Scanning {target_run.name} for claims (genuine arm only)...")
    logs = sorted(target_run.rglob("audit_*.json"))
    
    all_claims = []
    excluded_unresolved_source = 0
    excluded_parse_error = 0
    excluded_pipeline_not_ok = 0

    for log in logs:
        try:
            with open(log, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            excluded_parse_error += 1
            continue

        if data.get("pipeline_status") != "OK":
            excluded_pipeline_not_ok += 1
            continue

        gap = data.get("compliance_gap") or {}
        fact_verdict = data.get("fact_checker_verdict") or gap.get("fact_checker_verdict") or {}
        verdicts = fact_verdict.get("verdicts", [])

        source_text, found = get_source_text(data, target_run, log.name)
        if not found:
            excluded_unresolved_source += 1
            continue

        for v in verdicts:
            if "claim" in v and "status" in v:
                all_claims.append({
                    "case_id": data.get("case_id", "Unknown"),
                    "filename": log.name,
                    "claim": v["claim"],
                    "ai_status": v["status"],
                    "source_text": source_text,
                })

    # Loud, explicit exclusion report
    print(f"   Cases skipped (parse error):        {excluded_parse_error}")
    print(f"   Cases skipped (pipeline not OK):    {excluded_pipeline_not_ok}")
    print(f"   Cases skipped (source unresolved):  {excluded_unresolved_source}")
    if excluded_unresolved_source > 0:
        print(f"   ⚠️  {excluded_unresolved_source} case(s) had no resolvable transcript "
              f"and were excluded from the annotation sample.")

    if len(all_claims) == 0:
        print("❌ Found 0 valid claims.")
        return
    
    # Report stratum distribution
    stratum_dist = defaultdict(int)
    for c in all_claims:
        stratum_dist[c["ai_status"]] += 1
    print(f"   Stratum distribution: {dict(stratum_dist)}")

    # Reproducible sampling with fixed seed
    rng = random.Random(RNG_SEED)
    
    if len(all_claims) < NUM_CLAIMS:
        print(f"⚠️ Only found {len(all_claims)} valid claims total. Using all of them.")
        sample = all_claims
    else:
        sample = stratify_sample(all_claims, rng)
        # Trim to NUM_CLAIMS if stratification oversampled
        sample = sample[:NUM_CLAIMS]

    print(f"   Sampled {len(sample)} claims (seed={RNG_SEED})")

    # Export Answer Key
    key_path = target_run / "gate_b_answer_key.csv"
    with open(key_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Case ID", "Claim", "AI_Status"])
        for i, item in enumerate(sample, 1):
            writer.writerow([f"Q{i}", item["case_id"], item["claim"], item["ai_status"]])
    
    print(f"✅ Answer key saved to {key_path}")

    # Generate HTML (annotator BLIND to ai_status per §4.6)
    html_items = []
    for i, item in enumerate(sample, 1):
        html_items.append(f"""
        <div class="case-block">
            <div class="case-header">
                <div><span class="font-bold uppercase tracking-widest text-xs">Item {i:02d}</span></div>
                <div class="font-mono text-xs opacity-60">Case: {item['case_id']}</div>
            </div>
            
            <div class="mb-4">
                <div class="text-xs uppercase font-bold mb-1 opacity-70">The Claim</div>
                <div class="font-mono text-sm border-l-4 border-black pl-3 py-1 bg-gray-50">
                    {item['claim']}
                </div>
            </div>
            
            <div class="mb-4">
                <div class="text-xs uppercase font-bold mb-1 opacity-70">Source Text Extract</div>
                <div class="text-xs leading-relaxed border border-gray-300 p-3 overflow-hidden relative" style="max-height: 400px; overflow-y: auto;">
                    <pre style="white-space: pre-wrap; font-family: 'Courier Prime', monospace; font-size: 11px;">{item['source_text']}</pre>
                </div>
            </div>
            
            <div class="decision-box">
                <div class="text-xs font-bold uppercase mb-2">Human Annotation:</div>
                <div class="flex gap-6">
                    <label class="checkbox-container font-mono text-sm">[ ] <strong>SUPPORTED</strong></label>
                    <label class="checkbox-container font-mono text-sm">[ ] <strong>CONTRADICTED</strong></label>
                    <label class="checkbox-container font-mono text-sm">[ ] <strong>UNSUPPORTED</strong></label>
                </div>
            </div>
        </div>
        """)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Gate B Manual Annotation Task</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&family=Courier+Prime:wght@400;700&display=swap" rel="stylesheet">
<style>
  body {{ font-family: 'Inter', sans-serif; color: #000; background: #fff; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .font-mono {{ font-family: 'Courier Prime', monospace; }}
  .page {{ max-width: 210mm; margin: 2rem auto; padding: 18mm; border: 1px solid #ccc; background: #fff; }}
  .case-block {{ border-bottom: 2px solid #000; padding-bottom: 24px; margin-bottom: 24px; break-inside: avoid; page-break-inside: avoid; }}
  .case-header {{ display: flex; justify-content: space-between; border-bottom: 1px solid #ccc; padding-bottom: 8px; margin-bottom: 12px; }}
  .decision-box {{ border: 2px dashed #000; padding: 16px; background: #fafafa; margin-top: 16px; }}
  @media print {{
    .page {{ border: none; margin: 0; padding: 0; max-width: none; }}
    .page-break {{ page-break-before: always; }}
  }}
</style>
</head>
<body>
<main class="page">
    <header style="border-bottom:3px solid #000;padding-bottom:14px;margin-bottom:32px;">
        <div class="text-xs font-bold uppercase tracking-widest">Pre-Registered Methodology Validation</div>
        <h1 style="font-size:32px;font-weight:900;letter-spacing:-1px;line-height:1;margin-top:4px;">
            Gate B Factual Baseline
        </h1>
        <div class="text-sm font-mono mt-2">Manual Annotation Target: {NUM_CLAIMS} Claims · Target κ ≥ 0.60</div>
        <div class="text-xs font-mono mt-1">Sampling seed: {RNG_SEED}</div>
    </header>

    <div class="mb-8 p-5 bg-gray-100 border-l-4 border-black">
        <h2 class="font-bold mb-2">Instructions</h2>
        <p class="text-sm mb-3">Evaluate each claim strictly against the visible source text extract. Do not use outside knowledge. Mark your decision in the dashed box.</p>
        <ul class="text-sm space-y-2 font-mono">
            <li><strong>SUPPORTED:</strong> The text explicitly proves the claim is true.</li>
            <li><strong>CONTRADICTED:</strong> The text explicitly proves the claim is false.</li>
            <li><strong>UNSUPPORTED:</strong> The text is missing, vague, or irrelevant. Cannot prove true or false.</li>
        </ul>
        <p class="text-xs mt-3 italic">Note: The annotator is blind to Gate B's predicted verdict.</p>
    </div>

    <div class="page-break"></div>

    {''.join(html_items)}
    
    <div style="margin-top:40px; padding-top:20px; border-top:3px solid #000; text-align:center;">
        <div class="text-xs font-mono">END OF ANNOTATION TASK</div>
    </div>
</main>
</body>
</html>
"""

    html_path = target_run / "printable_annotation_task.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ Printable test saved to {html_path}")


if __name__ == "__main__":
    generate_test()