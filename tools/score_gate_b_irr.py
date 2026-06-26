"""
score_gate_b_irr.py — Gate B inter-rater-reliability scorer.

python score_gate_b_irr.py --key gate_b_answer_key.csv --human gate_b_human_annotations_FINAL.csv

The generator (`l3_gate_b_irr_tester.py`) only builds the blind annotation task and the
answer key; it never scored agreement, so the *location* of disagreement was never surfaced.
This companion reads the answer key (Gate B's predicted status) plus the human's filled-in
annotations, then reports:

  - Cohen's kappa (3-class: SUPPORTED / CONTRADICTED / UNSUPPORTED)
  - the full 3x3 confusion matrix (Gate B rows x Human columns)
  - the off-diagonal (disagreement) cells ranked by count, so you can state in §5.5
    exactly where the κ = 0.515 disagreements concentrated.

INPUTS (CSV, joined on the `ID` column, e.g. "Q1".."Q50"):
  --key    gate_b_answer_key.csv          (cols: ID, Case ID, Claim, AI_Status, Source File)
  --human  gate_b_human_annotations.csv   (cols: ID, human_label[, ...])
           OR a single merged CSV that already contains both AI_Status and human_label,
           passed to --key (then --human can be omitted).

Status values are normalised case-insensitively to {SUPPORTED, CONTRADICTED, UNSUPPORTED}.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

LABELS = ["SUPPORTED", "CONTRADICTED", "UNSUPPORTED"]
_ALIASES = {
    "SUPPORTED": "SUPPORTED", "SUPPORT": "SUPPORTED", "S": "SUPPORTED",
    "CONTRADICTED": "CONTRADICTED", "CONTRADICT": "CONTRADICTED", "C": "CONTRADICTED",
    "UNSUPPORTED": "UNSUPPORTED", "UNSUPPORT": "UNSUPPORTED", "U": "UNSUPPORTED",
}


def _norm(value: str) -> str | None:
    if value is None:
        return None
    key = value.strip().upper().replace(" ", "").replace("-", "")
    return _ALIASES.get(key)


def _find_col(fieldnames: list[str], *candidates: str) -> str | None:
    lower = {f.lower().strip(): f for f in fieldnames}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    # loose contains-match fallback
    for want in candidates:
        for f in fieldnames:
            if want.lower() in f.lower():
                return f
    return None


def _read_csv(path: Path) -> tuple[list[dict], list[str]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return rows, (reader.fieldnames or [])


def load_pairs(key_path: Path, human_path: Path | None) -> tuple[list[tuple[str, str]], list[str]]:
    """Return (pairs, warnings) where each pair is (gate_b_status, human_label)."""
    warnings: list[str] = []
    key_rows, key_fields = _read_csv(key_path)
    id_col = _find_col(key_fields, "ID", "Q", "Question")
    ai_col = _find_col(key_fields, "AI_Status", "Gate_B_Status", "AI", "Predicted", "Status")
    if id_col is None or ai_col is None:
        sys.exit(f"❌ Could not locate ID / AI_Status columns in {key_path.name} "
                 f"(found: {key_fields})")

    ai_by_id: dict[str, str] = {}
    for r in key_rows:
        gid = (r.get(id_col) or "").strip()
        ai = _norm(r.get(ai_col))
        if gid and ai:
            ai_by_id[gid] = ai

    # Human answers: either a second file, or merged into the key file.
    human_by_id: dict[str, str] = {}
    if human_path is not None:
        h_rows, h_fields = _read_csv(human_path)
        h_id = _find_col(h_fields, "ID", "Q", "Question")
        h_col = _find_col(h_fields, "human_label", "Human", "Annotation", "Verdict", "Status")
        if h_id is None or h_col is None:
            sys.exit(f"❌ Could not locate ID / human_label columns in {human_path.name} "
                     f"(found: {h_fields})")
        for r in h_rows:
            gid = (r.get(h_id) or "").strip()
            hv = _norm(r.get(h_col))
            if gid and hv:
                human_by_id[gid] = hv
    else:
        h_col = _find_col(key_fields, "human_label", "Human", "Annotation", "Verdict")
        if h_col is None:
            sys.exit("❌ No --human file given and no human_label column in the key file.")
        for r in key_rows:
            gid = (r.get(id_col) or "").strip()
            hv = _norm(r.get(h_col))
            if gid and hv:
                human_by_id[gid] = hv

    pairs: list[tuple[str, str]] = []
    for gid, ai in ai_by_id.items():
        if gid in human_by_id:
            pairs.append((ai, human_by_id[gid]))
        else:
            warnings.append(f"no human annotation for {gid}")
    for gid in human_by_id:
        if gid not in ai_by_id:
            warnings.append(f"human annotation {gid} has no answer-key row")
    return pairs, warnings


def cohens_kappa(pairs: list[tuple[str, str]]) -> float:
    n = len(pairs)
    if n == 0:
        return float("nan")
    po = sum(1 for a, b in pairs if a == b) / n
    a_counts = Counter(a for a, _ in pairs)
    b_counts = Counter(b for _, b in pairs)
    pe = sum((a_counts.get(l, 0) / n) * (b_counts.get(l, 0) / n) for l in LABELS)
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1.0 - pe)


def confusion(pairs: list[tuple[str, str]]) -> dict[tuple[str, str], int]:
    m: dict[tuple[str, str], int] = defaultdict(int)
    for a, b in pairs:
        m[(a, b)] += 1
    return m


def report(pairs: list[tuple[str, str]], warnings: list[str]) -> None:
    n = len(pairs)
    print("\n=== Gate B Inter-Rater Reliability ===")
    print(f"Paired claims scored: {n}")
    for w in warnings:
        print(f"  ⚠️  {w}")
    if n == 0:
        return

    k = cohens_kappa(pairs)
    agree = sum(1 for a, b in pairs if a == b)
    print(f"\nRaw agreement: {agree}/{n} = {agree / n:.1%}")
    print(f"Cohen's kappa: {k:.3f}   (pre-registered soft target ≥ 0.60)")

    m = confusion(pairs)
    width = max(len(l) for l in LABELS)
    print("\nConfusion matrix  (rows = Gate B, cols = Human):")
    header = " " * (width + 2) + "".join(f"{l[:4]:>8}" for l in LABELS) + f"{'tot':>8}"
    print(header)
    for a in LABELS:
        row = f"{a:<{width}}  " + "".join(f"{m.get((a, b), 0):>8}" for b in LABELS)
        row += f"{sum(m.get((a, b), 0) for b in LABELS):>8}"
        print(row)
    foot = f"{'tot':<{width}}  " + "".join(
        f"{sum(m.get((a, b), 0) for a in LABELS):>8}" for b in LABELS
    )
    print(foot)

    # Off-diagonal ranking — this is the "where did disagreement concentrate" answer.
    off = sorted(
        (((a, b), c) for (a, b), c in m.items() if a != b),
        key=lambda kv: kv[1], reverse=True,
    )
    print("\nDisagreements, ranked (Gate B → Human):")
    if not off:
        print("  (none — perfect agreement)")
    else:
        for (a, b), c in off:
            print(f"  {c:>3}  Gate B said {a:<12} but human said {b}")
        top = off[0]
        # group disagreements by the unordered category pair to name the dominant axis
        axis = Counter()
        for (a, b), c in off:
            axis[frozenset((a, b))] += c
        dom = axis.most_common(1)[0]
        pair = sorted(dom[0])
        print(f"\nDominant disagreement axis: {pair[0]} ↔ {pair[1]} "
              f"({dom[1]}/{n - agree} of all disagreements).")
        print("Paste-ready: \"disagreement concentrated on the "
              f"{pair[0].lower()}/{pair[1].lower()} boundary"
              f" ({dom[1]} of {n - agree} disagreements).\"")


def main() -> None:
    ap = argparse.ArgumentParser(description="Score Gate B IRR (kappa + confusion matrix).")
    ap.add_argument("--key", required=True, type=Path,
                    help="answer key CSV (AI_Status), or merged CSV with both columns")
    ap.add_argument("--human", type=Path, default=None,
                    help="human annotations CSV (ID, human_label); omit if merged into --key")
    args = ap.parse_args()
    if not args.key.exists():
        sys.exit(f"❌ key file not found: {args.key}")
    if args.human is not None and not args.human.exists():
        sys.exit(f"❌ human file not found: {args.human}")
    pairs, warnings = load_pairs(args.key, args.human)
    report(pairs, warnings)


if __name__ == "__main__":
    main()
