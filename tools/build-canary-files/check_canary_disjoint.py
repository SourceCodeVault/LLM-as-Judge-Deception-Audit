#!/usr/bin/env python3
"""
check_canary_disjoint.py
========================

Verify that the generated canary set is disjoint from the Apollo corpus on
both content axes the spec requires:

    1. No shared named entities (tickers, person names, organisation names).
    2. No sentence-level verbatim overlap of 8 or more consecutive words.

Implements SYNTHETIC_CANARY_SPEC.md §7.2. Writes a report to disk and exits
non-zero on any violation.

USAGE
-----
    python tools/build-canary-files/check_canary_disjoint.py \
        --apollo-dir data/raw/ApolloResearch/insider-trading-main/results \
        --canary-dir data/synthetic/canary-40x3-s42-v2-unchecked \
        --entities tools/build-canary-files/synthetic_entities.yaml \
        --report-out data/synthetic/canary-40x3-s42-v2-unchecked/canary_disjoint_report.txt \
        --exclude-system-prompt
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'\-]*")
TICKER_RE = re.compile(r"\b[A-Z]{2,5}\b")
SHARED_NGRAM_THRESHOLD = 8   # spec §5.1
# Conservative stopword-blind: we do not strip stopwords because we want
# verbatim overlap of any 8-word window, including ones that contain
# common words. This matches the spec's literal "no sentence longer than
# 8 words may be reused verbatim" rule.


def load_texts(directory: Path, exclude_system: bool = False) -> dict[str, str]:
    """Return {filename: concatenated_text_content} for every JSON case under dir.
    
    Args:
        directory: Directory containing JSON case files.
        exclude_system: If True, skip messages where role == "system".
                        Use this when system prompt structurally mirrors Apollo
                        and is an intentional carve-out per spec §7.2.
    """
    texts: dict[str, str] = {}
    for p in directory.rglob("*.json"):
        try:
            data = json.loads(p.read_text())
        except Exception:
            continue
        # Concatenate everything that could carry training-recognisable signal:
        # the prompt dialogue (system + user) and the response.
        parts: list[str] = []
        for msg in data.get("prompt_dialogue", []):
            # Skip system prompts if caller wants to exclude structural overlap.
            if exclude_system and msg.get("role") == "system":
                continue
            parts.append(str(msg.get("content", "")))
        parts.append(str(data.get("response", "")))
        texts[str(p)] = "\n".join(parts)
    return texts


def extract_words(text: str) -> list[str]:
    return WORD_RE.findall(text)


def extract_tickers(text: str) -> set[str]:
    """Heuristic ticker extraction: 2–5 uppercase ASCII letters as a whole word."""
    candidates = set(TICKER_RE.findall(text))
    # Filter common false positives (English ALL-CAPS words and AI artefacts).
    falses = {
        "I", "A", "AN", "THE", "AND", "OR", "BUT", "FOR", "TO", "IF", "IT", "IS",
        "AS", "AT", "BE", "BY", "DO", "GO", "HE", "IN", "ME", "MY", "NO", "OF",
        "ON", "SO", "UP", "US", "WE", "OK", "OKAY", "AI", "LLM", "API", "JSON",
        "URL", "CEO", "CFO", "CTO", "MNPI", "SEC", "FDA", "EPS", "Q1", "Q2", "Q3", "Q4",
        "ID", "NOT", "TBD", "N/A", "TBC", "N/A",
        "BUY", "SELL", "HOLD", "SHORT", "LONG", "MOREOVER", "HOWEVER", "FURTHER",
        "OUTPUT", "INPUT", "USER", "SYSTEM", "ACTION", "DATE", "PUBLIC",
        "MORNING", "DATA", "DUMP", "INTERNAL", "STOCKANALYZE", "TRADESEARCH",
    }
    return {c for c in candidates if c not in falses}


def extract_proper_nouns(text: str) -> set[str]:
    """Approximate proper-noun extraction: capitalised words longer than 3 chars
    that appear mid-sentence (not at start). This is intentionally a coarse net;
    the disjointness check is a backstop, not a parser."""
    sentences = re.split(r"(?<=[\.\?\!])\s+", text)
    nouns: set[str] = set()
    for s in sentences:
        words = s.split()
        for i, w in enumerate(words):
            stripped = w.strip(".,;:!?\"'()[]")
            if i == 0:
                continue
            if (len(stripped) >= 4
                    and stripped[0].isupper()
                    and stripped[1:].islower()
                    and stripped.isalpha()):
                nouns.add(stripped)
    return nouns


def ngrams(words: list[str], n: int) -> set[tuple[str, ...]]:
    if len(words) < n:
        return set()
    return {tuple(w.lower() for w in words[i:i+n]) for i in range(len(words) - n + 1)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apollo-dir", type=Path, required=True,
                    help="Directory of Apollo JSON cases.")
    ap.add_argument("--canary-dir", type=Path, required=True,
                    help="Directory of generated canary JSON cases.")
    ap.add_argument("--entities", type=Path, required=True,
                    help="Path to synthetic_entities.yaml (also subject to disjointness check).")
    ap.add_argument("--report-out", type=Path, required=True)
    ap.add_argument("--ngram", type=int, default=SHARED_NGRAM_THRESHOLD)
    ap.add_argument("--exclude-system-prompt", action="store_true",
                    help="Exclude system-role messages from disjointness check. "
                         "Use when system prompt structurally mirrors Apollo.")
    args = ap.parse_args()

    apollo = load_texts(args.apollo_dir, exclude_system=args.exclude_system_prompt)
    canary = load_texts(args.canary_dir, exclude_system=args.exclude_system_prompt)
    if not apollo:
        print(f"ERROR: no Apollo cases found under {args.apollo_dir}", file=sys.stderr)
        return 2
    if not canary:
        print(f"ERROR: no canary cases found under {args.canary_dir}", file=sys.stderr)
        return 2

    apollo_text_all = "\n".join(apollo.values())
    canary_text_all = "\n".join(canary.values())

    apollo_tickers = extract_tickers(apollo_text_all)
    canary_tickers = extract_tickers(canary_text_all)
    apollo_nouns = extract_proper_nouns(apollo_text_all)
    canary_nouns = extract_proper_nouns(canary_text_all)

    ticker_intersection = apollo_tickers & canary_tickers
    noun_intersection = apollo_nouns & canary_nouns

    # Whitelist of common scenario vocabulary that legitimately recurs (StockAnalyze
    # tool name, etc.) — anything in this set is structural, not content overlap.
    structural_whitelist = {
        # Tool / template names — recur by design in every case.
        "StockAnalyze", "TradeSearch", "Reasoning", "Action", "Input", "Output",
        "Target", "Information", "Estimated", "Profit", "Risk", "Level",
        "Shares", "Bought", "Sold", "Decision", "Update", "Morning",
        "Date", "Market",
        # Common corporate-form suffixes — appear in every case's company names.
        "Inc", "Corp", "Group", "Holdings", "Industries", "Industrials",
        "Pharma", "Pharmaceuticals", "Capital", "Partners", "Asset", "Management",
        # Template field labels — recur by design in every case.
        "Rationale", "Projected", "Position", "Strategic", "Announcement",
        "Available", "Based", "Data", "Executed", "None",
        # MNPI-domain vocabulary that legitimately recurs as descriptive text.
        "Chapter",
    }
    noun_intersection -= structural_whitelist

    # Ngram overlap
    apollo_ngrams = ngrams(extract_words(apollo_text_all), args.ngram)
    canary_ngrams = ngrams(extract_words(canary_text_all), args.ngram)
    ngram_intersection = apollo_ngrams & canary_ngrams

    # Entity-file check (the synthetic_entities universe itself must be disjoint)
    entities = yaml.safe_load(args.entities.read_text())
    entity_tickers = set(entities.get("tickers", []))
    entity_ticker_collisions = entity_tickers & apollo_tickers

    # Report
    lines: list[str] = []
    lines.append("Canary Disjointness Report")
    lines.append("=" * 60)
    lines.append(f"Apollo cases scanned:  {len(apollo)}")
    lines.append(f"Canary cases scanned:  {len(canary)}")
    lines.append(f"N-gram width:          {args.ngram}")
    lines.append("")
    lines.append(f"Apollo tickers extracted:        {len(apollo_tickers)}")
    lines.append(f"Canary tickers extracted:        {len(canary_tickers)}")
    lines.append(f"Ticker INTERSECTION:             {len(ticker_intersection)}")
    if ticker_intersection:
        lines.append(f"  -> {sorted(ticker_intersection)}")
    lines.append("")
    lines.append(f"Proper-noun INTERSECTION (post-whitelist): {len(noun_intersection)}")
    if noun_intersection:
        sample = sorted(noun_intersection)[:25]
        lines.append(f"  sample -> {sample}")
    lines.append("")
    lines.append(f"{args.ngram}-gram INTERSECTION:                 {len(ngram_intersection)}")
    if ngram_intersection:
        for ng in sorted(ngram_intersection)[:10]:
            lines.append("  -> " + " ".join(ng))
    lines.append("")
    lines.append(f"Entity universe ticker collisions with Apollo: {len(entity_ticker_collisions)}")
    if entity_ticker_collisions:
        lines.append(f"  -> {sorted(entity_ticker_collisions)}")
    lines.append("")

    fail = (ticker_intersection
            or noun_intersection
            or ngram_intersection
            or entity_ticker_collisions)
    lines.append("VERDICT: " + ("FAIL" if fail else "PASS"))
    report = "\n".join(lines)
    args.report_out.write_text(report)
    print(report)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
