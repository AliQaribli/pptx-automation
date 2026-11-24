"""Offline demo: render ``examples/brief.json`` with the local PPTX engine.

This script is the "no secrets, no network" proof that the presentation
pipeline works on its own. It invokes the real engine CLI
(``python -m presentation.cli``) on the example contract and prints the path of
the generated deck. It never reads ``.env``, never opens a socket, and never
contacts Telegram or Canva.

Usage:
    python scripts/demo.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIEF = ROOT / "examples" / "brief.json"
OUTPUT = ROOT / "output"

# Matches a path to a generated .pptx in CLI output (forward or back slashes).
_PPTX_RE = re.compile(r"[A-Za-z0-9_./\\\-]+\.pptx\b", re.IGNORECASE)


def _newest_deck(after: set[Path] | None = None) -> Path | None:
    decks = [p.resolve() for p in OUTPUT.glob("**/*.pptx")]
    if after is not None:
        decks = [p for p in decks if p not in after]
    if not decks:
        return None
    return max(decks, key=lambda p: p.stat().st_mtime)


def main() -> int:
    if not BRIEF.is_file():
        print(f"Missing example brief: {BRIEF}", file=sys.stderr)
        return 2

    before = {p.resolve() for p in OUTPUT.glob("**/*.pptx")}

    # Run the real offline engine. cwd=ROOT keeps relative output/ paths stable.
    proc = subprocess.run(
        [sys.executable, "-m", "presentation.cli", str(BRIEF)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )

    out = proc.stdout.strip()
    err = proc.stderr.strip()
    if out:
        print(out)
    if proc.returncode != 0:
        if err:
            print(err, file=sys.stderr)
        return proc.returncode
    if err:
        print(err, file=sys.stderr)

    # Prefer the path the CLI itself reported; otherwise discover the new file.
    deck: Path | None = None
    match = _PPTX_RE.search(out)
    if match:
        candidate = Path(match.group(0))
        if not candidate.is_absolute():
            candidate = (ROOT / candidate).resolve()
        if candidate.is_file():
            deck = candidate
    if deck is None:
        deck = _newest_deck(before) or _newest_deck()

    if deck is None or not deck.is_file():
        print("Engine ran but no generated .pptx was found.", file=sys.stderr)
        return 1

    # The last line is the machine-readable output path.
    print(deck)
    return 0


if __name__ == "__main__":
    sys.exit(main())
