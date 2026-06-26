"""
analyze_rule_bundles.py — bundled-flicker analysis (EXPLORATORY, not pre-registered).

§5.5 shows individual rule citations are unstable run-to-run (Krippendorff α = 0.238; J-rules
flicker on ~100% of the cases they touch). The open question for the Psychopathia mapping is:
when individually-jittery rules are grouped into diagnostic *bundles* (e.g. "scratchpad blindness"
= J1 ∪ J2 ∪ J5), does the BUNDLE stabilise even though its members do not?

This reads the k=6 stability reruns and, for each case, asks per observation whether each
individual rule fired and whether each bundle fired (bundle = ANY member fired, by default).
"Flicker" = fraction of cases (among cases where the rule/bundle appeared in ≥1 of the 6 runs)
on which presence was NOT unanimous across the 6 runs. Lower flicker = more stable.

This does NOT modify any locked pipeline code; it only reads outputs.

INPUT: a stability run directory containing the k=6 rerun audit files. Each audit JSON must carry a
case identifier and the rules cited that pass. The loader is permissive about layout: it scans all
`audit_*.json` under --run, groups by case_id, and treats each file as one of the (up to 6)
observations for that case. It reads rules from `logic_auditor_verdict.rules_fired`,
`rules_fired`, or `compliance_gap.rules_fired` (whichever is present).

Usage:
  python tools/analyze_rule_bundles.py --run output/run_..._test_retest_300
  python tools/analyze_rule_bundles.py --run <dir> --bundles bundles.json
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

# Default diagnostic bundles. Edit, or pass --bundles a JSON {name: [rules]}.
DEFAULT_BUNDLES: dict[str, list[str]] = {
    "scratchpad_blindness (J1,J2,J5)": ["J1", "J2", "J5"],
    "strategic_compliance (J1,J2,J3)": ["J1", "J2", "J3"],
    "all_J (judge-process)": ["J1", "J2", "J3", "J4", "J5"],
    "all_F (structural fact)": ["F1", "F2", "F3"],
    "all_U (unsubstantiated)": ["U1", "U2", "U3", "U4"],
}


def _extract_rules(obj) -> list[str]:
    """Pull a rule list out of an audit record, accumulating from all locations."""
    if not isinstance(obj, dict):
        return []
    
    found_rules = set()
    
    # We added 'judge_diagnostic_observations' and 'metadata/rules_fired'
    for path in (
        ("logic_auditor_verdict", "rules_fired"),
        ("logic_auditor_verdict", "agent_policy_violations"),
        ("logic_auditor_verdict", "judge_diagnostic_observations"),
        ("compliance_gap", "rules_fired"),
        ("metadata", "rules_fired")
    ):
        cur = obj
        ok = True
        for k in path:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                ok = False
                break
        if ok and isinstance(cur, list):
            found_rules.update([str(r).strip().upper() for r in cur if str(r).strip()])
            
    if isinstance(obj.get("rules_fired"), list):
        found_rules.update([str(r).strip().upper() for r in obj["rules_fired"] if str(r).strip()])
        
    return list(found_rules)

    
def _case_id(obj, fallback: str) -> str:
    if isinstance(obj, dict):
        cid = obj.get("case_id") or (obj.get("metadata") or {}).get("case_id")
        if cid:
            return str(cid)
    return fallback


def load_observations(run: Path) -> dict[str, list[set[str]]]:
    """case_id -> list of rule-sets (one per rerun observation)."""
    obs: dict[str, list[set[str]]] = defaultdict(list)
    files = [f for f in run.rglob("audit_*.json")
             if not any(p.startswith("_") for p in f.relative_to(run).parts[:-1])]
    for f in sorted(files):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        cid = _case_id(data, f.stem)
        obs[cid].append(set(_extract_rules(data)))
    return obs


def flicker(present_per_obs: list[bool]) -> float | None:
    """Among cases seen at least once, 1.0 if presence not unanimous, else 0.0."""
    if not any(present_per_obs):
        return None  # never appeared for this case; not counted
    return 0.0 if all(present_per_obs) else 1.0


def summarise(obs: dict[str, list[set[str]]], bundles: dict[str, list[str]]) -> None:
    n_cases = len(obs)
    k_runs = max((len(v) for v in obs.values()), default=0)
    print(f"\nCases: {n_cases}   max observations/case: {k_runs}")
    incomplete = sum(1 for v in obs.values() if len(v) != k_runs)
    if incomplete:
        print(f"⚠️  {incomplete} case(s) have fewer than {k_runs} observations "
              f"(partial reruns) — counted on the observations present.")

    all_rules = sorted({r for sets in obs.values() for s in sets for r in s})

    def line(label: str, members: list[str] | None) -> str:
        seen = 0
        flick = 0
        for sets in obs.values():
            if members is None:  # single rule, label is the rule
                present = [label in s for s in sets]
            else:
                present = [any(m in s for m in members) for s in sets]
            fl = flicker(present)
            if fl is not None:
                seen += 1
                flick += fl
        pct = (100.0 * flick / seen) if seen else float("nan")
        return f"  {label:<34} seen {seen:>4}   flicker {pct:5.1f}%"

    print("\n── Individual rules ──")
    indiv = []
    for r in all_rules:
        s = line(r, None)
        indiv.append((r, s))
        print(s)

    print("\n── Bundles (member ∪; 'fired' = any member fired) ──")
    for name, members in bundles.items():
        present_members = [m for m in members if m in all_rules]
        if not present_members:
            print(f"  {name:<34} (no members observed in this run)")
            continue
        print(line(name, members))

    print("\nReading: if a bundle's flicker is markedly lower than the mean flicker of its members,")
    print("the diagnostic-group signal is stable even though individual rule citations are not —")
    print("which is the level at which the Psychopathia syndrome mapping should be read.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Bundled rule-citation flicker (exploratory).")
    ap.add_argument("--run", required=True, type=Path, help="stability rerun directory")
    ap.add_argument("--bundles", type=Path, default=None,
                    help="optional JSON {bundle_name: [rules]}; defaults to built-in groups")
    args = ap.parse_args()
    if not args.run.exists():
        raise SystemExit(f"❌ run directory not found: {args.run}")
    bundles = DEFAULT_BUNDLES
    if args.bundles and args.bundles.exists():
        bundles = json.loads(args.bundles.read_text(encoding="utf-8"))
    obs = load_observations(args.run)
    if not obs:
        raise SystemExit("❌ no audit_*.json observations found under --run")
    summarise(obs, bundles)


if __name__ == "__main__":
    main()
