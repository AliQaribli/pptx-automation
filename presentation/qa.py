"""Pre-render (contract) and post-render (file) quality gates.

Any ``error`` fails the job.  ``warning`` is reported for the agent to revise
but does not prevent delivery.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from pptx import Presentation

from . import theme
from .contract import Contract, count_words, is_declarative, ALLOWED_KINDS

_TITLE_MIN_PT = 29.0
_EMU_TOLERANCE = 2500


def _add(checks: List[Dict[str, str]], cid: str, stage: str, ok: bool,
         message: str, severity: str = "error") -> None:
    if ok:
        status = "pass"
    else:
        status = "warn" if severity == "warning" else "fail"
    checks.append({"id": cid, "stage": stage, "status": status, "message": message})


def _near_multiple(value: float, unit: float) -> bool:
    if unit <= 0:
        return False
    q = value / unit
    return abs(q - round(q)) * unit <= _EMU_TOLERANCE


def pre_render_check(contract: Contract) -> Dict[str, Any]:
    checks: List[Dict[str, str]] = []
    t = contract.meta.theme
    slides = contract.slides

    _add(checks, "version", "pre", contract.version == 1,
         "Contract version is 1")
    _add(checks, "slide_count", "pre", 5 <= len(slides) <= 10,
         "Slide count %d is within 5-10" % len(slides))
    _add(checks, "sources_last", "pre",
         bool(slides) and slides[-1].kind == "sources",
         "Sources/credits slide is last")
    _add(checks, "kinds", "pre",
         all(s.kind in ALLOWED_KINDS for s in slides),
         "All slide kinds are recognised")

    bad_titles = [
        "%d: %r" % (i, s.title) for i, s in enumerate(slides, 1)
        if s.title and s.kind != "sources" and not is_declarative(s.title)
    ]
    _add(checks, "conclusion_titles", "pre", not bad_titles,
         "All titles are conclusion-style declaratives" if not bad_titles
         else "Non-declarative titles (write the takeaway, not a label): "
              + "; ".join(bad_titles))

    bad_bodies = [
        "%d" % i for i, s in enumerate(slides, 1)
        if len(s.body) > 3 or any(len(b) > 90 for b in s.body)
    ]
    _add(checks, "body_limits", "pre", not bad_bodies,
         "Every body has <= 3 items of <= 90 chars" if not bad_bodies
         else "Slides with oversized body: " + ", ".join(bad_bodies))

    dense = ["%d (~%d words)" % (i, count_words(s))
             for i, s in enumerate(slides, 1) if count_words(s) > 40]
    _add(checks, "word_density", "pre", not dense,
         "Every slide is within ~40 words" if not dense
         else "Over the ~40-word cap: " + ", ".join(dense))

    fonts = {t.font_heading, t.font_body}
    _add(checks, "font_families", "pre", len(fonts) <= 2,
         "At most 2 font families (%d used)" % len(fonts))
    bad_fonts = sorted(f for f in fonts if f not in theme.FONT_ALLOWLIST)
    _add(checks, "font_allowlist", "pre", not bad_fonts,
         "Fonts are locally stable" if not bad_fonts
         else "Unavailable fonts: " + ", ".join(bad_fonts))
    color_fields = {k: getattr(t, k) for k in (
        "color_primary", "color_secondary", "neutral_dark", "white", "grey")}
    _add(checks, "palette", "pre",
         all(theme.is_hex_color(v) for v in color_fields.values()),
         "All palette tokens are #RRGGBB")
    _add(checks, "contrast", "pre",
         theme.contrast_ratio(t.neutral_dark, t.white) >= 4.5,
         "Body text contrast on the chosen background is >= 4.5:1",
         severity="warning")

    bad_paths = [
        "%d: %s" % (i, s.image.path) for i, s in enumerate(slides, 1)
        if s.image and s.image.path and (
            Path(s.image.path).is_absolute() or ".." in Path(s.image.path).parts
            or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", s.image.path))
    ]
    _add(checks, "image_paths", "pre", not bad_paths,
         "Image paths are job-relative" if not bad_paths
         else "Unsafe absolute/remote paths: " + "; ".join(bad_paths))

    n_images = sum(1 for s in slides if s.image is not None)
    _add(checks, "imagery", "pre", n_images >= 1,
         "%d image slot(s) declared" % n_images, severity="warning")

    return _report(checks, "pre")


def post_render_check(path: Path, contract: Contract) -> Dict[str, Any]:
    checks: List[Dict[str, str]] = []
    try:
        prs = Presentation(str(path))
    except Exception as exc:
        _add(checks, "opens", "post", False, "Cannot open PPTX: %s" % exc)
        return _report(checks, "post")

    _add(checks, "opens", "post", True, "PPTX opens with python-pptx")
    _add(checks, "slide_count", "post", len(prs.slides) == len(contract.slides),
         "Slide count %d matches contract (%d)" % (len(prs.slides), len(contract.slides)))
    ratio_ok = (abs(prs.slide_width - theme.SLIDE_W) <= 1
                and abs(prs.slide_height - theme.SLIDE_H) <= 1)
    _add(checks, "aspect_ratio", "post", ratio_ok,
         "Slide size %d x %d EMU is 16:9" % (prs.slide_width, prs.slide_height))

    title_texts: List[str] = []
    slide_number_counts: List[int] = []
    image_counts: List[int] = []
    fonts = set()
    max_words = 0
    max_glyph_area = 0.0
    safe_area_pt2 = (theme.SAFE_W / 914400 * 72) * (theme.SAFE_H / 914400 * 72)

    for idx, slide in enumerate(prs.slides, start=1):
        accent = [s for s in slide.shapes if s.name == "accent_bar"]
        _add(checks, "accent_%02d" % idx, "post", len(accent) == 1,
             "Slide %d has exactly one accent bar (found %d)" % (idx, len(accent)))

        excluded = idx in {
            i for i, s in enumerate(contract.slides, 1)
            if s.kind in {"title", "sources"}
        }
        nums = [s for s in slide.shapes if s.name == "slide_number"]
        slide_number_counts.append(len(nums))
        expected = 0 if excluded else 1
        _add(checks, "number_%02d" % idx, "post", len(nums) == expected,
             "Slide %d has %d slide-number text box(es), expected %d"
             % (idx, len(nums), expected))
        foots = [s for s in slide.shapes if s.name == "footer_line"]
        foot_ok = (len(foots) == 0) if excluded else (len(foots) == 1)
        _add(checks, "footer_%02d" % idx, "post", foot_ok,
             "Slide %d footer-line count %d is %s"
             % (idx, len(foots), "correct" if foot_ok else "wrong"))

        words = 0
        glyph_area = 0.0
        for shape in slide.shapes:
            l, t_, w, h = shape.left, shape.top, shape.width, shape.height
            inside = (l >= -_EMU_TOLERANCE and t_ >= -_EMU_TOLERANCE
                      and l + w <= theme.SLIDE_W + _EMU_TOLERANCE
                      and t_ + h <= theme.SLIDE_H + _EMU_TOLERANCE)
            if not inside:
                _add(checks, "bounds_%02d" % idx, "post", False,
                     "Slide %d: shape %r lies outside slide bounds" % (idx, shape.name))
            snapped = (
                _near_multiple(l - theme.MARGIN, theme.snap_unit_x())
                and _near_multiple(t_ - theme.MARGIN, theme.snap_unit_y())
                and _near_multiple(w + theme.GUTTER, theme.snap_unit_x())
                and _near_multiple(h + theme.GUTTER, theme.snap_unit_y())
            )
            if not snapped:
                _add(checks, "grid_%02d" % idx, "post", False,
                     "Slide %d: shape %r is off-grid" % (idx, shape.name))
            if shape.name.startswith(("image_", "placeholder_")):
                image_counts.append(idx)
            if shape.has_text_frame and not shape.name.startswith("slide_number"):
                for p in shape.text_frame.paragraphs:
                    for run in p.runs:
                        if run.font.name:
                            fonts.add(run.font.name)
                        if run.text:
                            words += len(run.text.split())
                            size = run.font.size.pt if run.font.size else 18
                            glyph_area += len(run.text) * size * 0.5 * size * 1.2
        max_words = max(max_words, words)
        max_glyph_area = max(max_glyph_area, glyph_area)
        _add(checks, "words_%02d" % idx, "post", words <= 40,
             "Slide %d has ~%d rendered words (cap 40)" % (idx, words))

        big = [s for s in slide.shapes if s.has_text_frame
               and any((r.font.size and r.font.size.pt >= _TITLE_MIN_PT)
                       for p in s.text_frame.paragraphs for r in p.runs)]
        if big:
            title_texts.append(big[0].text_frame.text.strip())

    _add(checks, "glyph_area", "post", max_glyph_area < 0.40 * safe_area_pt2,
         "Max estimated glyph area %.0f pt2 < 40%% of safe area (%.0f pt2)"
         % (max_glyph_area, 0.40 * safe_area_pt2))
    _add(checks, "imagery", "post", len(set(image_counts)) >= 1,
         "At least one image or labelled placeholder is present (%d slides)"
         % len(set(image_counts)), severity="warning")
    _add(checks, "fonts", "post", len(fonts) <= 2,
         "Rendered fonts: %s" % (", ".join(sorted(fonts)) or "none"))
    _add(checks, "font_allowlist", "post", fonts <= set(theme.FONT_ALLOWLIST),
         "All rendered fonts are allowlisted")
    _add(checks, "sources_position", "post",
         bool(title_texts) and "sources" in title_texts[-1].lower(),
         "Last rendered slide is Sources & credits")
    non_source = title_texts[:-1]
    bad = [x for x in non_source if not is_declarative(x)]
    _add(checks, "declarative_rendered", "post", not bad,
         "Rendered titles are conclusion-style" if not bad
         else "Label-like titles: " + "; ".join(repr(x) for x in bad))

    size = path.stat().st_size
    _add(checks, "file_size", "post", size < 50 * 1024 * 1024,
         "Deck is %.1f KB, under the 50 MB delivery cap" % (size / 1024.0))

    return _report(checks, "post")


def _report(checks: List[Dict[str, str]], stage: str) -> Dict[str, Any]:
    errors = [c["message"] for c in checks if c["status"] == "fail"]
    warnings = [c["message"] for c in checks if c["status"] == "warn"]
    return {
        "status": "fail" if errors else ("warn" if warnings else "pass"),
        "stage": stage,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "checks": len(checks),
            "errors": len(errors),
            "warnings": len(warnings),
        },
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }


def combine(pre: Dict[str, Any], post: Dict[str, Any], deck: str,
            contract_path: str) -> Dict[str, Any]:
    checks = pre["checks"] + post["checks"]
    errors = [c["message"] for c in checks if c["status"] == "fail"]
    warnings = [c["message"] for c in checks if c["status"] == "warn"]
    return {
        "status": "fail" if errors else ("warn" if warnings else "pass"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": contract_path,
        "deck": deck,
        "summary": {
            "checks": len(checks),
            "errors": len(errors),
            "warnings": len(warnings),
            "slides": len([c for c in checks if c["id"] == "opens"]),
        },
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }
