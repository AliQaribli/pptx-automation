"""Typed, fail-closed contract parsing for the offline PPTX renderer.

``contract.py`` is the only place that decides whether a contract JSON is
acceptable.  Errors are collected and raised together as :class:`ContractError`
with actionable, slide-numbered messages.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import theme

ALLOWED_KINDS = {
    "title", "statement", "bullets", "metrics", "two_column",
    "image_hero", "closing", "sources",
}

_SECRET_RE = re.compile(
    r"(?i)\b(?:api[_-]?key|secret|token|password|passwd|access[_-]?key|"
    r"authorization|bearer)\b\s*[:=]\s*\S+"
)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_HOME_RE = re.compile(r"(?:/(?:Users|home)/|(?i:[A-Za-z]:\\Users\\))")
_BCP47_RE = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
_URL_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


class ContractError(ValueError):
    """Raised when a contract cannot be rendered safely."""


def fail(errors: List[str]) -> None:
    if errors:
        raise ContractError(
            "Invalid contract (%d issue%s):\n  - %s"
            % (len(errors), "" if len(errors) == 1 else "s", "\n  - ".join(errors))
        )


def is_declarative(title: str) -> bool:
    """Cheap conclusion-style heuristic; label-like titles fail."""
    t = (title or "").strip()
    words = t.split()
    if len(words) < 4 or t.endswith(":") or t.endswith("?") or t.endswith(","):
        return False
    if t != t[0].upper() + t[1:]:
        return False
    if t.isupper():
        return False
    return True


def slide_word_items(spec: "Slide") -> List[str]:
    """Every string rendered as visible text on a slide (for the 40-word cap)."""
    items: List[str] = [spec.title]
    if spec.kicker:
        items.append(spec.kicker)
    items.extend(spec.body)
    if spec.caption:
        items.append(spec.caption)
    if spec.image is not None:
        if spec.image.caption:
            items.append(spec.image.caption)
        if spec.image.credit:
            items.append(spec.image.credit)
    for m in spec.metrics:
        items.extend([m.value, m.label])
    for col in spec.columns:
        items.append(col.heading)
        items.extend(col.body)
    for src in spec.sources:
        items.append(src.label)
    return [s for s in items if s]


def count_words(spec: "Slide") -> int:
    return sum(len(s.split()) for s in slide_word_items(spec))


# ----------------------------------------------------------------- dataclasses
@dataclass
class Theme:
    color_primary: str = theme.DEFAULT_COLORS["color_primary"]
    color_secondary: str = theme.DEFAULT_COLORS["color_secondary"]
    neutral_dark: str = theme.DEFAULT_COLORS["neutral_dark"]
    white: str = theme.DEFAULT_COLORS["white"]
    grey: str = theme.DEFAULT_COLORS["grey"]
    font_heading: str = theme.DEFAULT_FONTS["font_heading"]
    font_body: str = theme.DEFAULT_FONTS["font_body"]


@dataclass
class Meta:
    title: str
    subtitle: str = ""
    language: str = "en"
    theme: Theme = field(default_factory=Theme)


@dataclass
class ImageSpec:
    path: str = ""
    credit: str = ""
    caption: str = ""
    layout: str = "right"


@dataclass
class Metric:
    value: str
    label: str


@dataclass
class Column:
    heading: str
    body: List[str] = field(default_factory=list)


@dataclass
class Source:
    label: str
    url: str = ""


@dataclass
class Slide:
    kind: str
    title: str
    kicker: str = ""
    body: List[str] = field(default_factory=list)
    notes: str = ""
    caption: str = ""
    image: Optional[ImageSpec] = None
    metrics: List[Metric] = field(default_factory=list)
    columns: List[Column] = field(default_factory=list)
    sources: List[Source] = field(default_factory=list)


@dataclass
class Contract:
    version: int
    meta: Meta
    slides: List[Slide]
    base_dir: Path = field(default_factory=Path.cwd)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], base_dir: Optional[Path] = None) -> "Contract":
        errors: List[str] = []
        if not isinstance(data, dict):
            raise ContractError("Contract root must be a JSON object, got %s"
                                % type(data).__name__)

        version = data.get("version")
        if version != 1:
            errors.append("version must be exactly 1 (got %r); update the generator"
                          % (version,))

        meta_raw = data.get("meta")
        if not isinstance(meta_raw, dict):
            errors.append("meta must be an object with a non-empty 'title'")
            meta_raw = {}

        theme_raw = meta_raw.get("theme") or {}
        if not isinstance(theme_raw, dict):
            errors.append("meta.theme must be an object")
            theme_raw = {}
        tvals: Dict[str, str] = {}
        for key, default in {**theme.DEFAULT_COLORS, **theme.DEFAULT_FONTS}.items():
            value = theme_raw.get(key, default)
            if not isinstance(value, str) or not value.strip():
                errors.append("meta.theme.%s must be a non-empty string" % key)
                value = default
            tvals[key] = value.strip()
        for key in ("color_primary", "color_secondary", "neutral_dark", "white", "grey"):
            if not theme.is_hex_color(tvals[key]):
                errors.append("meta.theme.%s must be #RRGGBB (got %r); e.g. #1F6FEB"
                              % (key, tvals[key]))
        for key in ("font_heading", "font_body"):
            if tvals[key] not in theme.FONT_ALLOWLIST:
                errors.append(
                    "meta.theme.%s=%r is not an installed, allowlisted font; "
                    "choose from %s" % (key, tvals[key],
                                        ", ".join(sorted(theme.FONT_ALLOWLIST)))
                )
        if tvals["font_heading"] == tvals["font_body"]:
            # one family with two weights is explicitly allowed
            pass

        title = meta_raw.get("title", "")
        if not isinstance(title, str) or not title.strip():
            errors.append("meta.title must be a non-empty string (used for metadata)")
        subtitle = meta_raw.get("subtitle", "")
        language = meta_raw.get("language", "en")
        if not isinstance(language, str) or not _BCP47_RE.match(language):
            errors.append("meta.language must be a BCP-47 tag such as 'en' or 'en-US'")

        slides_raw = data.get("slides")
        if not isinstance(slides_raw, list):
            errors.append("slides must be a list of 5-10 slide objects")
            slides_raw = []
        if not 5 <= len(slides_raw) <= 10:
            errors.append("slides must contain 5-10 slides (got %d); add or merge slides"
                          % len(slides_raw))
        if slides_raw and (not isinstance(slides_raw[-1], dict)
                           or slides_raw[-1].get("kind") != "sources"):
            errors.append("the last slide must be kind='sources' (sources/credits is always last)")

        slides: List[Slide] = []
        for idx, raw in enumerate(slides_raw, start=1):
            if not isinstance(raw, dict):
                errors.append("slide %d must be an object" % idx)
                continue
            slides.append(cls._slide_from_dict(raw, idx, errors))

        # Recursive privacy / secret scrub over all string values.
        _scrub_strings(data, errors)

        fail(errors)
        return cls(
            version=1,
            meta=Meta(
                title=title.strip(),
                subtitle=str(subtitle).strip(),
                language=language,
                theme=Theme(**tvals),
            ),
            slides=slides,
            base_dir=Path(base_dir) if base_dir else Path.cwd(),
        )

    @staticmethod
    def _slide_from_dict(raw: Dict[str, Any], idx: int, errors: List[str]) -> Slide:
        kind = raw.get("kind")
        if kind not in ALLOWED_KINDS:
            errors.append("slide %d: kind=%r is invalid; allowed: %s"
                          % (idx, kind, ", ".join(sorted(ALLOWED_KINDS))))
            kind = "statement"

        title = raw.get("title", "")
        if not isinstance(title, str) or not title.strip():
            errors.append("slide %d: title must be a non-empty conclusion-style statement"
                          % idx)
            title = ""
        elif len(title) > 200:
            errors.append("slide %d: title is %d chars; keep it under 200"
                          % (idx, len(title)))

        body = raw.get("body") or []
        if not isinstance(body, list):
            errors.append("slide %d: body must be a list of at most 3 strings" % idx)
            body = []
        if len(body) > 3:
            errors.append("slide %d: body has %d items; cap is 3 — split the slide"
                          % (idx, len(body)))
        for j, item in enumerate(body):
            if not isinstance(item, str) or not item.strip():
                errors.append("slide %d: body[%d] must be a non-empty string" % (idx, j))
            elif len(item) > 90:
                errors.append("slide %d: body[%d] is %d chars; cap is 90 — shorten it"
                              % (idx, j, len(item)))
        body = [str(x).strip() for x in body if isinstance(x, str)]

        image = None
        raw_img = raw.get("image")
        if raw_img is not None:
            if not isinstance(raw_img, dict):
                errors.append("slide %d: image must be an object with path/credit" % idx)
            else:
                p = str(raw_img.get("path") or "")
                if p:
                    if _URL_RE.match(p):
                        errors.append("slide %d: image.path must be a local relative path; "
                                      "remote URLs are forbidden" % idx)
                    if Path(p).is_absolute() or ".." in Path(p).parts or "\\" in p:
                        errors.append("slide %d: image.path=%r must be job-relative; "
                                      "absolute paths and '..' traversal are rejected"
                                      % (idx, p))
                layout = str(raw_img.get("layout") or "right")
                if layout not in {"right", "left", "full"}:
                    errors.append("slide %d: image.layout=%r must be right/left/full"
                                  % (idx, layout))
                    layout = "right"
                image = ImageSpec(
                    path=p,
                    credit=str(raw_img.get("credit") or ""),
                    caption=str(raw_img.get("caption") or ""),
                    layout=layout,
                )

        metrics: List[Metric] = []
        raw_metrics = raw.get("metrics") or []
        if kind == "metrics" and not raw_metrics:
            errors.append("slide %d: kind='metrics' needs 1-3 metrics with value/label"
                          % idx)
        if not isinstance(raw_metrics, list):
            errors.append("slide %d: metrics must be a list" % idx)
            raw_metrics = []
        if len(raw_metrics) > 3:
            errors.append("slide %d: at most 3 metrics per slide (got %d)"
                          % (idx, len(raw_metrics)))
        for j, m in enumerate(raw_metrics):
            if not isinstance(m, dict) or not str(m.get("value") or "").strip() \
                    or not str(m.get("label") or "").strip():
                errors.append("slide %d: metrics[%d] needs non-empty 'value' and 'label'"
                              % (idx, j))
            else:
                metrics.append(Metric(str(m["value"]).strip(), str(m["label"]).strip()))

        columns: List[Column] = []
        raw_columns = raw.get("columns") or []
        if kind == "two_column" and len(raw_columns) != 2:
            errors.append("slide %d: kind='two_column' needs exactly 2 columns" % idx)
        if not isinstance(raw_columns, list):
            raw_columns = []
        for j, col in enumerate(raw_columns[:2]):
            if not isinstance(col, dict) or not str(col.get("heading") or "").strip():
                errors.append("slide %d: columns[%d] needs a non-empty 'heading'" % (idx, j))
                continue
            cbody = col.get("body") or []
            if not isinstance(cbody, list) or len(cbody) > 3:
                errors.append("slide %d: columns[%d].body must be a list of <= 3 strings"
                              % (idx, j))
                cbody = []
            columns.append(Column(
                str(col["heading"]).strip(),
                [str(x).strip() for x in cbody if isinstance(x, str) and str(x).strip()],
            ))

        sources: List[Source] = []
        raw_sources = raw.get("sources") or []
        if kind == "sources" and not raw_sources:
            errors.append("slide %d: sources must be a non-empty list "
                          "(use a label 'None - original analysis')" % idx)
        if not isinstance(raw_sources, list):
            raw_sources = []
        for j, s in enumerate(raw_sources):
            if not isinstance(s, dict) or not str(s.get("label") or "").strip():
                errors.append("slide %d: sources[%d] needs a non-empty 'label'" % (idx, j))
            else:
                url = str(s.get("url") or "")
                sources.append(Source(str(s["label"]).strip(), url))

        spec = Slide(
            kind=kind,
            title=title,
            kicker=str(raw.get("kicker") or "").strip(),
            body=body,
            notes=str(raw.get("notes") or ""),
            caption=str(raw.get("caption") or "").strip(),
            image=image,
            metrics=metrics,
            columns=columns,
            sources=sources,
        )
        words = count_words(spec)
        if words > 40:
            errors.append("slide %d: ~%d words on slide; cap is ~40 — cut roughly %d words"
                          % (idx, words, words - 40))
        return spec

    @classmethod
    def from_json(cls, path: str | Path) -> "Contract":
        p = Path(path)
        if not p.is_file():
            raise ContractError("Contract file not found: %s" % p)
        try:
            raw = p.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ContractError("Cannot read contract %s: %s" % (p, exc))
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ContractError("Contract %s is not valid JSON at line %d col %d: %s"
                                % (p, exc.lineno, exc.colno, exc.msg))
        return cls.from_dict(data, base_dir=p.resolve().parent)


def _scrub_strings(value: Any, errors: List[str], trail: str = "") -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            _scrub_strings(v, errors, "%s.%s" % (trail, k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _scrub_strings(v, errors, "%s[%d]" % (trail, i))
    elif isinstance(value, str):
        if _SECRET_RE.search(value):
            errors.append("%s looks like a credential (KEY=VALUE); remove it" % trail)
        if _EMAIL_RE.search(value):
            errors.append("%s contains an email address (personal data); remove it" % trail)
        if _HOME_RE.search(value):
            errors.append("%s contains an absolute home path; use a job-relative path" % trail)
