#!/usr/bin/env python3
"""Generate a topic-specific PptxGenJS plan with a Hermes model.

The model is used only for slide *content*. The layout, palette, schema and
fallback content come from the deterministic planner, so a bad model reply
cannot break rendering. On any failure this script exits non-zero and the bot
uses the deterministic plan instead.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Ali\presentation-agent")
HERMES = "hermes"
PROFILE = "testad"
MODEL = os.environ.get("DECK_PLAN_MODEL", "free")
LAYOUTS = ["cover", "statement", "compare", "process", "quote", "summary", "sources"]

PROMPT = """You write slide CONTENT for a fixed 7-slide PowerPoint generator.
The user's topic is: {topic}
Respond in the SAME LANGUAGE as the topic.

Return ONLY one JSON object. No markdown, no commentary. Use exactly this shape:
{{
  "title": "short specific deck title",
  "subtitle": "one sentence saying what this deck covers",
  "slides": [
    {{"kicker":"...","title":"...","subtitle":"...","footer":"..."}},
    {{"kicker":"...","title":"...","stat":"...","statLabel":"...","bullets":["...","...","..."]}},
    {{"kicker":"...","title":"...","columns":[{{"head":"...","items":["...","...","..."]}},{{"head":"...","items":["...","...","..."]}}]}},
    {{"kicker":"...","title":"...","steps":[{{"head":"...","body":"..."}},{{"head":"...","body":"..."}},{{"head":"...","body":"..."}},{{"head":"...","body":"..."}}]}},
    {{"quote":"...","attribution":"..."}},
    {{"kicker":"...","title":"...","bullets":["...","...","..."],"calloutHead":"...","callout":"..."}},
    {{"note":"one sentence about sources or scope"}}
  ]
}}

Rules:
- Every line must be specific to THIS topic. Generic filler is forbidden.
- Use short phrases, not paragraphs. Max 12 words per bullet or step body.
- Do NOT invent statistics, dates, names, citations, prices or percentages.
- The quote slide must be an original line you write, not a quotation from a real person.
- If the user included instructions (language, slide count, tone, audience), obey them.
- The 7 slide objects correspond to: cover, statement, compare, process, quote, summary, sources.
- Keep the JSON valid and compact.
"""


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start:end + 1])


def _merge(topic: str, data: dict) -> dict:
    from topic_to_plan import build as deterministic_build

    plan = json.loads(deterministic_build(topic).read_text(encoding="utf-8"))
    plan["title"] = str(data.get("title") or plan["title"])[:90]
    if data.get("subtitle"):
        plan["subtitle"] = str(data["subtitle"])[:300]
    gen = data.get("slides") or []
    if len(gen) != len(LAYOUTS):
        raise ValueError("expected 7 slide objects")

    for i, (slide, source) in enumerate(zip(plan["slides"], gen)):
        if slide["layout"] != LAYOUTS[i]:
            raise ValueError("slide layout order mismatch")
        if not isinstance(source, dict):
            raise ValueError("slide content must be an object")
        for key, value in source.items():
            if key == "note":
                slide["notes"] = str(value)
            elif key in ("columns", "steps"):
                if not isinstance(value, list) or len(value) not in (2, 4):
                    raise ValueError(f"{key} must be a list")
                for item in value:
                    if not isinstance(item, dict):
                        raise ValueError(f"{key} items must be objects")
                    for subkey, subvalue in item.items():
                        if subkey == "items" and isinstance(subvalue, list):
                            item[subkey] = [str(x)[:180] for x in subvalue if isinstance(x, str)]
                        elif isinstance(subvalue, str):
                            item[subkey] = subvalue[:300]
                slide[key] = value
            elif isinstance(value, list):
                if not all(isinstance(x, str) for x in value):
                    raise ValueError("expected list of strings")
                slide[key] = [str(x)[:180] for x in value]
            elif isinstance(value, dict):
                slide[key] = value
            elif isinstance(value, str):
                slide[key] = value[:500]
    words = [w for w in re.findall(r"[^\W_]+", topic.lower()) if len(w) >= 4][:6]
    dump = json.dumps(plan, ensure_ascii=False).lower()
    if not any(w in dump for w in words):
        raise ValueError("topic not reflected in plan")
    return plan


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python scripts/llm_topic_to_plan.py <topic> <output.json>")
        return 2
    topic, out = sys.argv[1], Path(sys.argv[2])
    prompt = PROMPT.format(topic=topic.replace("\n", " ")[:500])
    result = subprocess.run(
        [HERMES, "-p", PROFILE, "--ignore-rules", "-z", prompt, "-m", MODEL],
        cwd=str(ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="ignore", timeout=150,
    )
    text = (result.stdout or "") + "\n" + (result.stderr or "")
    try:
        plan = _merge(topic, _extract_json(text))
    except Exception as exc:
        dbg = out.with_suffix(".raw.txt")
        dbg.parent.mkdir(parents=True, exist_ok=True)
        dbg.write_text(text, encoding="utf-8")
        print(f"LLM_PLAN_FAILED {type(exc).__name__}: {str(exc)[:120]}", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PLAN:{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
