"""Source Compiler — assembles the full prompt_dialogue for the Fact Checker  source_text.

The decision rules:

role == "system" → [SYSTEM_CONTEXT]
role == "user" + content starts with "Output:" or "Message:" → [EXTERNAL_EVIDENCE]
Everything else (assistant turns, date markers, ambient user turns) → [AGENT_TRANSCRIPT]
response field → appended to [AGENT_TRANSCRIPT] as ASSISTANT_FINAL

Unlike the Sanitization Adapter, this is INTENTIONALLY un-sanitized:
Gate B's job is to compare cover-story claims against ground truth, so
it MUST see the scratchpad.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

def _has_real_content(dialogue: list, final: str) -> bool:
    """Check if dialogue turns or final response contain non-whitespace content."""
    for turn in dialogue:
        if (turn.get("content") or "").strip():
            return True
    return bool(final.strip())

def _is_external_evidence(turn: dict) -> bool:
    """A user turn qualifies as external evidence if any of its segments
    is a tool output or inbound message. Apollo conventions: each segment
    begins with 'Output:' or 'Message:', delimited by paragraph breaks.
    A turn may bundle a 'Date:' scaffolding marker alongside evidence,
    so the prefix can appear at content start or after a paragraph break."""
    if turn.get("role") != "user":
        return False
    content = turn.get("content", "")
    return bool(re.search(r'(^|\n\n)\s*(Output|Message):', content))

def compile_source_text(response_path: Path) -> str | None:
    data = json.loads(response_path.read_text(encoding="utf-8"))
    dialogue = data.get("prompt_dialogue", [])
    final = (data.get("response") or "").strip()

    if not _has_real_content(dialogue, final):
        return None

    # --- Defensive sentinel: detect evidence-shaped content that the
    # --- heuristic failed to route to EXTERNAL_EVIDENCE. This is the
    # --- cure for silent dataset-quirk failures.
    suspicious = []
    for i, turn in enumerate(dialogue):
        if turn.get("role") != "user":
            continue
        content = turn.get("content", "")
        looks_like_evidence = ("Output:" in content or "Message:" in content)
        will_route_correctly = _is_external_evidence(turn)
        if looks_like_evidence and not will_route_correctly:
            suspicious.append({
                "turn_index": i,
                "content_preview": content[:120].replace("\n", " ⏎ ")
            })

    if suspicious:
        import sys
        print(f"⚠️  COMPILER_QUIRK in {response_path.name}: "
              f"{len(suspicious)} user turn(s) contain 'Output:' or 'Message:' "
              f"but failed to route to [EXTERNAL_EVIDENCE]. "
              f"Inspect for unhandled dataset shape: {suspicious}",
              file=sys.stderr)
        # Optional, stronger: raise an exception to halt the run.
        raise ValueError(f"Compiler quirk detected in {response_path.name}")

    sections: dict[str, list[str]] = {
        "SYSTEM_CONTEXT": [],
        "AGENT_TRANSCRIPT": [],
        "EXTERNAL_EVIDENCE": [],
    }

    # Process each turn in the dialogue
    for i, turn in enumerate(dialogue):
        role = turn.get("role", "unknown").upper()
        content = turn.get("content", "")

        if role == "SYSTEM":
            # System prompt goes to [SYSTEM_CONTEXT]
            sections["SYSTEM_CONTEXT"].append(content)
        elif role == "USER" and _is_external_evidence(turn):
            # Tool outputs and inbound messages go to [EXTERNAL_EVIDENCE]
            sections["EXTERNAL_EVIDENCE"].append(
                f"--- Turn {i:02d} [{role}] ---\n{content}"
            )
        else:
            # Everything else (assistant, date markers, etc.) goes to [AGENT_TRANSCRIPT]
            sections["AGENT_TRANSCRIPT"].append(
                f"--- Turn {i:02d} [{role}] ---\n{content}"
            )

    # Add final assistant response to [AGENT_TRANSCRIPT]
    if final:
        sections["AGENT_TRANSCRIPT"].append(
            f"--- Turn {len(dialogue):02d} [ASSISTANT_FINAL] ---\n{final}"
        )

    # Build the output with proper section markers
    output_parts: list[str] = []

    if sections["SYSTEM_CONTEXT"]:
        output_parts.append("[SYSTEM_CONTEXT]")
        output_parts.append("\n\n".join(sections["SYSTEM_CONTEXT"]))
        output_parts.append("[/SYSTEM_CONTEXT]")

    if sections["AGENT_TRANSCRIPT"]:
        output_parts.append("[AGENT_TRANSCRIPT]")
        output_parts.append("\n\n".join(sections["AGENT_TRANSCRIPT"]))
        output_parts.append("[/AGENT_TRANSCRIPT]")

    if sections["EXTERNAL_EVIDENCE"]:
        output_parts.append("[EXTERNAL_EVIDENCE]")
        output_parts.append("\n\n".join(sections["EXTERNAL_EVIDENCE"]))
        output_parts.append("[/EXTERNAL_EVIDENCE]")

    return "\n\n".join(output_parts)