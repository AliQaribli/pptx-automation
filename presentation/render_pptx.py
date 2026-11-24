"""Core deterministic renderer: contract JSON -> editable PPTX.

Every shape is placed through :func:`theme.grid`; backgrounds use the slide's
own background fill so no off-grid full-bleed rectangles are needed.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Pt

from . import images, theme
from .contract import Contract, ImageSpec, Slide, Theme

BOX = theme.BOX
DARK_KINDS = {"title", "closing"}


def textbox(slide, text: str, box: Tuple[int, int, int, int], *, size: int = 18,
            color: str, font: str, bold: bool = False,
            align: PP_ALIGN = PP_ALIGN.LEFT,
            anchor: MSO_ANCHOR = MSO_ANCHOR.TOP,
            line_spacing: float = 1.2) -> object:
    shape = slide.shapes.add_textbox(*box)
    tf = shape.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.vertical_anchor = anchor
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = line_spacing
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = font
    run.font.color.rgb = theme.rgb(color)
    return shape


def paragraph_box(slide, items: List[str], box: Tuple[int, int, int, int], *,
                  size: int, color: str, font: str, spacing: float = 1.2) -> object:
    shape = slide.shapes.add_textbox(*box)
    tf = shape.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.line_spacing = spacing
        p.space_after = Pt(12)
        run = p.add_run()
        run.text = item
        run.font.size = Pt(size)
        run.font.name = font
        run.font.color.rgb = theme.rgb(color)
    return shape


def _rect(slide, box, color: str, name: str) -> object:
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, *box)
    shape.name = name
    shape.fill.solid()
    shape.fill.fore_color.rgb = theme.rgb(color)
    shape.line.fill.background()
    return shape


def _background(slide, color: str) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = theme.rgb(color)


def _common(slide, spec: Slide, number: int, total: int, c: Contract,
            dark: bool) -> None:
    t = c.meta.theme
    ink = t.white if dark else t.neutral_dark
    muted = t.grey

    if spec.kicker:
        box = theme.grid(0, 0.40, 3.5 if spec.kind == "title" else 6, 0.5)
        textbox(slide, spec.kicker.upper(), box, size=theme.FONT_SIZES["kicker"],
                color=ink if dark else t.color_primary, font=t.font_body,
                bold=True, anchor=MSO_ANCHOR.MIDDLE)

    if spec.kind == "title":
        title_box = theme.grid(0, 0.9, 3.5, 1.7)
    elif spec.kind == "sources":
        title_box = theme.grid(0, 0.9, 6, 1.4)
    elif spec.kicker:
        title_box = theme.grid(*BOX["title_kicker"])
    else:
        title_box = theme.grid(*BOX["title"])
    size = theme.FONT_SIZES["title_small"] if spec.kind == "sources" \
        else theme.FONT_SIZES["title"]
    textbox(slide, spec.title, title_box, size=size, color=ink,
            font=t.font_heading, bold=True, line_spacing=1.05)

    # Exactly one accent bar on every slide, identical treatment throughout.
    _rect(slide, theme.grid(*BOX["accent"]), t.color_primary, "accent_bar")

    if spec.kind in {"title", "sources"}:
        return  # no footer line / slide number on title and credits slides
    _rect(slide, theme.grid(*BOX["footer_line"]), muted, "footer_line")
    number_box = textbox(slide, "%02d / %02d" % (number, total),
            theme.grid(*BOX["slide_number"]), size=theme.FONT_SIZES["slide_number"],
            color=muted, font=t.font_body, align=PP_ALIGN.RIGHT,
            anchor=MSO_ANCHOR.MIDDLE)
    number_box.name = "slide_number"


def _render_slide(prs, spec: Slide, number: int, c: Contract, base_dirs: List[Path],
                  work_dir: Path, budget: Dict[str, int]) -> None:
    t = c.meta.theme
    dark = spec.kind in DARK_KINDS
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _background(slide, t.neutral_dark if dark else t.white)
    _common(slide, spec, number, len(c.slides), c, dark)
    ink = t.white if dark else t.neutral_dark
    img_index = [0]

    def place_image(img: ImageSpec, x0, y0, cols, rows, caption="") -> None:
        img_index[0] += 1
        images.add(slide, img, base_dirs, work_dir, x0, y0, cols, rows,
                   caption, t, dark, budget, img_index[0])

    if spec.kind == "title":
        if spec.body:
            paragraph_box(slide, spec.body[:3], theme.grid(0, 3.05, 3.5, 2.6),
                          size=theme.FONT_SIZES["subtitle"], color=ink,
                          font=t.font_body, spacing=1.25)
        if spec.image:
            place_image(spec.image, 3.5, 1.6, 2.5, 4.8)

    elif spec.kind in {"statement", "bullets"}:
        for i, item in enumerate(spec.body[:3]):
            sq = _rect(slide, theme.grid(0, 3.25 + i * 0.9, 0.12, 0.28),
                       t.color_primary, "bullet_square_%d" % i)
            sq.line.fill.background()
            textbox(slide, item, theme.grid(0.28, 3.1 + i * 0.9, 5.72, 0.8),
                    size=theme.FONT_SIZES["body"], color=ink, font=t.font_body,
                    anchor=MSO_ANCHOR.MIDDLE)

    elif spec.kind == "metrics":
        if spec.body:
            textbox(slide, spec.body[0], theme.grid(0, 2.95, 6, 0.5),
                    size=theme.FONT_SIZES["subtitle"], color=ink, font=t.font_body,
                    anchor=MSO_ANCHOR.MIDDLE)
        for i, m in enumerate(spec.metrics[:3]):
            x = i * 2
            textbox(slide, m.value, theme.grid(x, 3.55, 2, 1.4),
                    size=theme.FONT_SIZES["big_number"], color=t.color_primary,
                    font=t.font_heading, bold=True, anchor=MSO_ANCHOR.MIDDLE)
            textbox(slide, m.label, theme.grid(x, 5.0, 2, 0.8),
                    size=theme.FONT_SIZES["label"], color=t.grey, font=t.font_body,
                    anchor=MSO_ANCHOR.MIDDLE)

    elif spec.kind == "two_column":
        for i, col in enumerate(spec.columns[:2]):
            x = i * 3
            textbox(slide, col.heading, theme.grid(x, 3.05, 3, 0.7),
                    size=20, color=ink, font=t.font_heading, bold=True,
                    anchor=MSO_ANCHOR.MIDDLE)
            _rect(slide, theme.grid(x, 3.82, 3, 0.16), t.grey, "divider_%d" % i)
            paragraph_box(slide, col.body[:3], theme.grid(x, 4.05, 3, 2.8),
                          size=theme.FONT_SIZES["body"], color=ink, font=t.font_body)

    elif spec.kind == "image_hero":
        if spec.body:
            textbox(slide, spec.body[0], theme.grid(0, 2.9, 6, 0.5),
                    size=theme.FONT_SIZES["subtitle"], color=ink, font=t.font_body,
                    anchor=MSO_ANCHOR.MIDDLE)
        if spec.image:
            place_image(spec.image, 0.5, 3.25, 5, 3.0)
        if spec.caption:
            textbox(slide, spec.caption, theme.grid(0.5, 6.45, 5, 0.5),
                    size=theme.FONT_SIZES["label"], color=t.grey, font=t.font_body,
                    anchor=MSO_ANCHOR.MIDDLE)

    elif spec.kind == "closing":
        cols = 3.5 if spec.image else 6
        if spec.body:
            paragraph_box(slide, spec.body[:3], theme.grid(0, 3.05, cols, 2.6),
                          size=theme.FONT_SIZES["subtitle"], color=ink,
                          font=t.font_body, spacing=1.25)
        if spec.image:
            place_image(spec.image, 3.5, 2.95, 2.5, 3.2)

    elif spec.kind == "sources":
        textbox(slide, "Content sources", theme.grid(0, 2.95, 3, 0.6),
                size=16, color=ink, font=t.font_heading, bold=True,
                anchor=MSO_ANCHOR.MIDDLE)
        textbox(slide, "Asset credits", theme.grid(3, 2.95, 3, 0.6),
                size=16, color=ink, font=t.font_heading, bold=True,
                anchor=MSO_ANCHOR.MIDDLE)
        paragraph_box(slide, [s.label for s in spec.sources[:6]],
                      theme.grid(0, 3.6, 3, 2.9), size=theme.FONT_SIZES["sources"],
                      color=ink, font=t.font_body)
        asset_credits = [
            (im.credit or "Original") for sl in c.slides
            for im in ([sl.image] if sl.image else [])
        ]
        asset_credits.append("Aptos fonts — Microsoft")
        paragraph_box(slide, asset_credits[:8], theme.grid(3, 3.6, 3, 2.9),
                      size=theme.FONT_SIZES["sources"], color=ink, font=t.font_body)
        textbox(slide, "Built with free assets only.", theme.grid(*BOX["note"]),
                size=theme.FONT_SIZES["sources"], color=t.grey, font=t.font_body,
                anchor=MSO_ANCHOR.MIDDLE)

    if spec.notes:
        slide.notes_slide.notes_text_frame.text = spec.notes


def render(contract: Contract, out_dir: str | Path,
           base_dirs: Optional[List[Path]] = None) -> Path:
    """Write ``<out_dir>/deck.pptx`` and return its path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = out_dir / "_assets"
    if base_dirs is None:
        base_dirs = [contract.base_dir, out_dir]

    prs = Presentation()
    prs.slide_width = theme.SLIDE_W
    prs.slide_height = theme.SLIDE_H
    cp = prs.core_properties
    cp.title = contract.meta.title
    cp.subject = contract.meta.subtitle
    cp.author = "presentation-agent (offline fallback)"
    cp.language = contract.meta.language
    stamp = datetime(2020, 1, 1)
    cp.created = stamp
    cp.modified = stamp

    budget: Dict[str, int] = {"bytes": 0, "images": 0, "placeholders": 0}
    for number, spec in enumerate(contract.slides, start=1):
        _render_slide(prs, spec, number, contract, base_dirs, work_dir, budget)

    path = out_dir / "deck.pptx"
    prs.save(str(path))
    return path
