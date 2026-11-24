#!/usr/bin/env python3
"""Build, render and prepare an 8-slide PPTX for visual inspection."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "pptxgen" / "scripts" / "build_deck.js"
RENDER = ROOT / "pptxgen" / "scripts" / "render_deck.ps1"


def run(cmd: list[str | Path]) -> None:
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, cwd=str(ROOT))


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python pptxgen/scripts/run_pipeline.py <plan.json> <output.pptx>")
        return 2
    plan = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    render_dir = out.parent / "render"

    run(["node", SCRIPT, plan, out])
    run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", RENDER, "-PptxPath", out, "-OutDir", render_dir,
    ])

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("PIL not available; contact sheet skipped.")
        return 0

    files = sorted(render_dir.glob("Slide*.PNG"))
    if not files:
        print("No rendered slides found.")
        return 1
    tw, th = 640, 360
    cols = 2
    rows = (len(files) + cols - 1) // cols
    sheet = Image.new("RGB", (tw * cols, th * rows), "white")
    draw = ImageDraw.Draw(sheet)
    for i, f in enumerate(files):
        im = Image.open(f).convert("RGB")
        im.thumbnail((tw, th))
        x, y = (i % cols) * tw, (i // cols) * th
        sheet.paste(im, (x, y))
        draw.rectangle([x, y, x + 70, y + 22], fill=(20, 33, 43))
        draw.text((x + 8, y + 5), f"S{i + 1}", fill="white")
    contact = render_dir / "contact_sheet.png"
    sheet.save(contact)
    print(f"CONTACT_SHEET:{contact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
