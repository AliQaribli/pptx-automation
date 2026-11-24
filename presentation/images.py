"""Local-only image resolution, normalisation and labelled placeholders.

No network access is ever performed.  Missing, unreadable or uncredited images
degrade to a labelled placeholder, which the contract treats as a valid image
state.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Pt

from . import theme
from .contract import ImageSpec, Theme

try:  # Pillow ships with python-pptx but stay defensive.
    from PIL import Image as PILImage
except Exception:  # pragma: no cover
    PILImage = None  # type: ignore

MAX_IMAGE_BYTES = 40 * 1024 * 1024
MAX_EDGE = 1920


def resolve(spec: ImageSpec, base_dirs: List[Path]) -> Optional[Path]:
    """Return the first existing job-relative image path, or ``None``."""
    if spec is None or not spec.path or not spec.credit:
        return None
    rel = Path(spec.path)
    if rel.is_absolute() or ".." in rel.parts:
        return None
    for base in base_dirs:
        try:
            candidate = (Path(base) / rel).resolve()
            root = Path(base).resolve()
            if root not in candidate.parents and candidate != root:
                continue
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def normalize(src: Path, work_dir: Path) -> Optional[Path]:
    """Strip metadata, cap the long edge, and write a stable PNG/JPEG copy."""
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        if src.stat().st_size > MAX_IMAGE_BYTES:
            return None
        if PILImage is None:
            dest = work_dir / ("img_" + src.name)
            shutil.copyfile(src, dest)
            return dest if dest.stat().st_size <= MAX_IMAGE_BYTES else None
        with PILImage.open(src) as im:
            im.load()
            im = im.convert("RGB")
            im.thumbnail((MAX_EDGE, MAX_EDGE))
            dest = work_dir / ("img_" + src.stem + ".png")
            im.save(dest, format="PNG", optimize=True)
        return dest if dest.stat().st_size <= MAX_IMAGE_BYTES else None
    except Exception:
        return None


def _crop(picture, dest_w: int, dest_h: int, src_w: int, src_h: int) -> None:
    dest_ratio = dest_w / dest_h
    src_ratio = src_w / src_h
    if src_ratio > dest_ratio:
        crop = (1 - dest_ratio / src_ratio) / 2
        picture.crop_left = crop
        picture.crop_right = crop
    else:
        crop = (1 - src_ratio / dest_ratio) / 2
        picture.crop_top = crop
        picture.crop_bottom = crop


def _set_text(slide, text: str, box: Tuple[int, int, int, int], size: int,
              color: str, font: str, t: Theme, *, bold: bool = False,
              align: PP_ALIGN = PP_ALIGN.LEFT) -> None:
    from .render_pptx import textbox  # local import avoids a module cycle
    textbox(slide, text, box, size=size, color=color, font=font,
            bold=bold, align=align, anchor=MSO_ANCHOR.MIDDLE)


def add(slide, spec: ImageSpec, base_dirs: List[Path], work_dir: Path,
        x0: float, y0: float, cols: float, rows: float, caption: str,
        t: Theme, dark: bool, budget: Dict[str, int], index: int) -> str:
    """Draw a real image or a labelled placeholder inside a grid box.

    Returns ``"image"`` or ``"placeholder"`` for QA/bookkeeping.
    """
    box = theme.grid(x0, y0, cols, rows)
    src = resolve(spec, base_dirs)
    if src is not None:
        norm = normalize(src, work_dir)
        if norm is not None and budget["bytes"] + norm.stat().st_size <= MAX_IMAGE_BYTES:
            try:
                dims = None
                if PILImage is not None:
                    with PILImage.open(norm) as im:
                        dims = im.size
                pic = slide.shapes.add_picture(str(norm), box[0], box[1],
                                                width=box[2], height=box[3])
                if dims:
                    _crop(pic, box[2], box[3], dims[0], dims[1])
                pic.name = "image_%02d" % index
                budget["bytes"] += norm.stat().st_size
                budget["images"] += 1
                if caption:
                    _set_text(slide, caption,
                              theme.grid(x0, y0 + rows - 0.5, cols, 0.5),
                              12, t.grey, t.font_body, t)
                return "image"
            except Exception:
                pass

    # ------------------------------------------------ labelled placeholder
    panel = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, *box)
    panel.name = "image_placeholder_%02d" % index
    panel.fill.solid()
    panel.fill.fore_color.rgb = theme.rgb(t.neutral_dark if dark else t.white)
    panel.line.color.rgb = theme.rgb(t.grey)
    panel.line.width = Pt(1.0)

    icon_color = t.white if dark else t.neutral_dark
    if cols >= 2 and rows >= 2:
        ibox = theme.grid(x0 + 1, y0 + 1, min(1.2, cols - 1.2),
                          min(1.2, rows - 1.2))
        icon = slide.shapes.add_shape(MSO_SHAPE.OVAL, *ibox)
        icon.name = "placeholder_icon_%02d" % index
        icon.fill.background()
        icon.line.color.rgb = theme.rgb(t.color_primary)
        icon.line.width = Pt(1.5)

    label = "Image placeholder"
    _set_text(slide, label,
              theme.grid(x0, max(0, y0 + rows - 1.25), cols, 0.75),
              12, icon_color, t.font_body, t, bold=True, align=PP_ALIGN.CENTER)
    detail = " — ".join(x for x in (spec.credit or "Original", caption) if x)
    _set_text(slide, detail,
              theme.grid(x0, max(0, y0 + rows - 0.5), cols, 0.5),
              11, t.grey, t.font_body, t, align=PP_ALIGN.CENTER)
    budget["placeholders"] += 1
    return "placeholder"
