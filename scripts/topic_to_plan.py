#!/usr/bin/env python3
"""Deterministically turn a Telegram topic into a PptxGenJS slide plan.

No model, network, credentials or external facts are used. The output is a
topic-only starter deck: every slide is editable and every message is safe.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Ali\presentation-agent")

PALETTES = [
    {"name": "editorial-teal", "bg": "F7F8F5", "ink": "12212B", "accent": "0E7C7B", "accent2": "E8B44A", "muted": "5B6B73", "panel": "E6EFEC"},
    {"name": "editorial-indigo", "bg": "F6F6FA", "ink": "1B1B35", "accent": "4B4EAC", "accent2": "D98A3D", "muted": "6A6A7D", "panel": "E8E9F4"},
    {"name": "editorial-rust", "bg": "F8F5F0", "ink": "2E2118", "accent": "A8502F", "accent2": "3F6C63", "muted": "73685F", "panel": "F0E5DA"},
]


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:42] or "topic")


def readable(topic: str) -> str:
    topic = " ".join(topic.split())
    if topic.islower():
        return topic.title()
    return topic[:90]


def build(topic: str) -> Path:
    digest = hashlib.sha1(topic.encode("utf-8")).hexdigest()[:8]
    style = PALETTES[int(digest[:2], 16) % len(PALETTES)]
    title = readable(topic)
    plan = {
        "title": title,
        "shortTitle": "DECK",
        "topic": topic,
        "author": "Deck-only Telegram pipeline",
        "font": "Aptos",
        "palette": {k: v for k, v in style.items() if k != "name"},
        "sources": [],
        "slides": [
            {
                "layout": "cover",
                "kicker": "Topic deck / generated",
                "title": title,
                "subtitle": "A clean, editable starting point built from your topic. No external facts were added.",
                "footer": "Deck-only pipeline | 7 slides",
                "notes": "Open with the topic exactly as sent; do not claim outside knowledge.",
            },
            {
                "layout": "statement",
                "kicker": "Frame",
                "title": "Start with one clear question",
                "stat": "01",
                "statLabel": "One topic. One main message per slide.",
                "bullets": [
                    "What is being claimed or explained?",
                    "Who needs to understand it, and why?",
                    "What should they remember tomorrow?",
                ],
                "notes": "This slide sets the frame without adding facts.",
            },
            {
                "layout": "compare",
                "kicker": "Lenses",
                "title": "Two lenses to hold at once",
                "columns": [
                    {"head": "What is known", "items": ["Agree on the basic definition", "Separate facts from interpretation", "Use an example to make it concrete"]},
                    {"head": "What is open", "items": ["Name the unanswered questions", "State the limits plainly", "Show where evidence would help"]},
                ],
                "notes": "Keep this conceptual; no unsupported numbers.",
            },
            {
                "layout": "process",
                "kicker": "Method",
                "title": "A simple path from topic to story",
                "steps": [
                    {"head": "Define", "body": "Say what the topic is in one sentence."},
                    {"head": "Select", "body": "Choose the three points that matter most."},
                    {"head": "Arrange", "body": "Put them in an order a reader can follow."},
                    {"head": "State", "body": "End with one takeaway or next action."},
                ],
                "notes": "This is a reusable thinking structure.",
            },
            {
                "layout": "quote",
                "quote": "A good deck does not cover everything. It makes one thing impossible to miss.",
                "attribution": "Deck design principle",
                "notes": "Synthesis, not a quotation from an outside source.",
            },
            {
                "layout": "summary",
                "kicker": "Conclusion",
                "title": "Leave them with one next step",
                "bullets": [
                    "Open with the definition, not the detail.",
                    "Use one visual idea per slide.",
                    "Close with a single action or question.",
                ],
                "calloutHead": "Remember",
                "callout": "Structure beats decoration.",
                "notes": "End cleanly; invite the next question in chat, not on the slide.",
            },
            {"layout": "sources", "notes": "Explains that no outside facts were used."},
        ],
    }
    out_dir = ROOT / "output" / "telegram" / "plans"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{slugify(topic)}-{digest}.json"
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/topic_to_plan.py <topic>")
        return 2
    path = build(sys.argv[1])
    print(f"PLAN:{path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
