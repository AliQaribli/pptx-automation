"""CLI: ``python -m presentation.cli BRIEF.json --out output/demo``.

Writes ``deck.pptx`` and ``qa_report.json`` into the output directory.  A QA
error or an invalid contract exits 2 and never emits a broken deck.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from . import qa
from .contract import Contract, ContractError
from .render_pptx import render


def _write_report(out_dir: Path, report: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "qa_report.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m presentation.cli",
        description="Render a contract JSON to an offline, editable PPTX deck.",
    )
    parser.add_argument("contract", help="path to the UTF-8 contract JSON")
    parser.add_argument("--out", default=None,
                        help="output directory (default: output/<contract-stem>)")
    args = parser.parse_args(argv)

    source = Path(args.contract)
    out_dir = Path(args.out) if args.out else Path("output") / source.stem

    try:
        contract = Contract.from_json(source)
    except ContractError as exc:
        msg = str(exc)
        print("FAIL: " + msg, file=sys.stderr)
        report = {
            "status": "fail", "stage": "parse",
            "contract": str(source), "deck": "",
            "summary": {"checks": 0, "errors": 1, "warnings": 0},
            "errors": [msg], "warnings": [], "checks": [],
        }
        print("QA report: %s" % _write_report(out_dir, report))
        return 2

    pre = qa.pre_render_check(contract)
    if pre["errors"]:
        for err in pre["errors"]:
            print("FAIL: " + err, file=sys.stderr)
        report = qa.combine(pre, {"checks": [], "errors": [], "warnings": []},
                            "", str(source))
        print("QA report: %s" % _write_report(out_dir, report))
        return 2

    try:
        deck = render(contract, out_dir)
    except Exception as exc:  # rendering must also fail closed
        msg = "Rendering failed: %s: %s" % (type(exc).__name__, exc)
        print("FAIL: " + msg, file=sys.stderr)
        report = qa.combine(pre, {
            "checks": [{"id": "render", "stage": "post", "status": "fail",
                        "message": msg}],
            "errors": [msg], "warnings": [],
        }, "", str(source))
        print("QA report: %s" % _write_report(out_dir, report))
        return 2

    post = qa.post_render_check(deck, contract)
    report = qa.combine(pre, post, str(deck), str(source))
    report_path = _write_report(out_dir, report)

    print("Deck:     %s" % deck)
    print("QA report:%s" % report_path)
    print("Slides:   %d" % len(contract.slides))
    print("Status:   %s (%d errors, %d warnings)"
          % (report["status"].upper(), report["summary"]["errors"],
             report["summary"]["warnings"]))
    for warn in report["warnings"]:
        print("WARN: " + warn, file=sys.stderr)
    for err in report["errors"]:
        print("FAIL: " + err, file=sys.stderr)
    return 2 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
