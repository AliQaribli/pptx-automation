#!/usr/bin/env node
/* Build an editable PPTX from a structured slide plan using PptxGenJS. */
const fs = require('fs');
const path = require('path');
const pptxgen = require('pptxgenjs');

const [, , planPath, outPath] = process.argv;
if (!planPath || !outPath) {
  console.error('Usage: node build_deck.js <plan.json> <output.pptx>');
  process.exit(2);
}
const plan = JSON.parse(fs.readFileSync(planPath, 'utf8'));
const p = plan.palette || {
  bg: 'F7F8F5', ink: '12212B', accent: '0E7C7B', accent2: 'E8B44A', muted: '5B6B73', panel: 'EAF1EF'
};
const FONT = plan.font || 'Aptos';
const SW = 13.333, SH = 7.5, M = 0.7, CW = SW - 2 * M;

const pptx = new pptxgen();
pptx.defineLayout({ name: 'WIDE', width: SW, height: SH });
pptx.layout = 'WIDE';
pptx.author = plan.author || 'AI Presentation Pipeline';
pptx.company = 'AI Presentation Pipeline';
pptx.subject = plan.topic || plan.title;
pptx.title = plan.title;
pptx.lang = 'en-US';
pptx.theme = { headFontFace: FONT, bodyFontFace: FONT, lang: 'en-US' };

function base(slide, num) {
  slide.background = { color: p.bg };
  slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 0.12, h: SH, fill: { color: p.accent }, line: { color: p.accent, transparency: 100 } });
  slide.addText(String(num).padStart(2, '0'), {
    x: SW - 1.05, y: SH - 0.48, w: 0.4, h: 0.25, fontSize: 10, color: p.muted, align: 'right', fontFace: FONT
  });
  slide.addText(plan.shortTitle || plan.title, {
    x: M, y: SH - 0.48, w: 5, h: 0.25, fontSize: 9, color: p.muted, fontFace: FONT, charSpacing: 1
  });
}

function kicker(slide, text) {
  slide.addText(text.toUpperCase(), { x: M, y: 0.55, w: CW, h: 0.3, fontSize: 11, bold: true, color: p.accent, charSpacing: 2, fontFace: FONT });
}

function title(slide, text, y, size, w) {
  slide.addText(text, { x: M, y: y || 1.0, w: w || CW, h: 1.2, fontSize: size || 30, bold: true, color: p.ink, fontFace: FONT, valign: 'top', breakLine: false, fit: 'shrink' });
}

function bullets(slide, items, x, y, w, h, size) {
  slide.addText((items || []).join('\n'), {
    x, y, w, h, valign: 'top', fit: 'shrink',
    fontSize: size || 18, color: p.ink, fontFace: FONT,
    bullet: { type: 'bullet', indent: 18 }, paraSpaceAfterPt: 10, breakLine: false
  });
}

function note(slide, text) { if (text) slide.addNotes(text); }

const L = {};

L.cover = (s, d) => {
  base(s, d.n);
  s.addShape(pptx.ShapeType.rect, { x: M, y: 1.5, w: 1.6, h: 0.08, fill: { color: p.accent2 }, line: { color: p.accent2, transparency: 100 } });
  s.addText(d.kicker || plan.topic, { x: M, y: 1.9, w: CW, h: 0.4, fontSize: 13, bold: true, color: p.accent, charSpacing: 2, fontFace: FONT });
  s.addText(d.title, { x: M, y: 2.45, w: 10.8, h: 1.7, fontSize: 40, bold: true, color: p.ink, fontFace: FONT, fit: 'shrink', breakLine: false });
  s.addText(d.subtitle || '', { x: M, y: 4.35, w: 9.6, h: 0.8, fontSize: 18, color: p.muted, fontFace: FONT, fit: 'shrink' });
  s.addText(d.footer || '', { x: M, y: 6.5, w: CW, h: 0.3, fontSize: 10, color: p.muted, fontFace: FONT });
  note(s, d.notes);
};

L.statement = (s, d) => {
  base(s, d.n); kicker(s, d.kicker || 'Key message');
  title(s, d.title, 1.05, 30, 10.8);
  s.addText(d.stat, { x: M, y: 2.65, w: 5.2, h: 2.1, fontSize: 76, bold: true, color: p.accent, fontFace: FONT, fit: 'shrink' });
  s.addText(d.statLabel || '', { x: M, y: 4.75, w: 5.2, h: 0.7, fontSize: 17, color: p.ink, fontFace: FONT, fit: 'shrink' });
  s.addShape(pptx.ShapeType.rect, { x: 6.25, y: 2.55, w: 0.03, h: 2.8, fill: { color: p.panel }, line: { color: p.panel, transparency: 100 } });
  bullets(s, d.bullets || [], 6.65, 2.6, 5.7, 2.7, 17);
  if (d.citation) s.addText(d.citation, { x: M, y: 6.35, w: CW, h: 0.3, fontSize: 10, color: p.muted, fontFace: FONT });
  note(s, d.notes);
};

L.chart = (s, d) => {
  base(s, d.n); kicker(s, d.kicker || 'Evidence');
  title(s, d.title, 1.05, 28, 11.4);
  s.addChart(pptx.ChartType.bar, d.series, {
    x: M, y: 2.25, w: 8.0, h: 3.8,
    showTitle: false, showLegend: false, showValue: true, dataLabelPosition: 'outEnd',
    dataLabelColor: p.ink, dataLabelFormatCode: '$0.000',
    catAxisLabelColor: p.ink, catAxisLabelFontSize: 12,
    valAxisMinVal: 0,
    valAxisLabelColor: p.muted, valAxisLabelFontSize: 10,
    valGridLine: { color: p.panel, size: 0.5 }, catGridLine: { style: 'none' },
    chartColors: d.colors || [p.muted, p.accent, p.accent, p.accent2],
    barGapWidthPct: 45
  });
  s.addShape(pptx.ShapeType.rect, { x: 8.85, y: 2.4, w: 3.75, h: 2.8, fill: { color: p.panel }, line: { color: p.panel, transparency: 100 } });
  s.addText(d.takeaway || '', { x: 9.15, y: 2.7, w: 3.2, h: 2.2, fontSize: 16, bold: true, color: p.ink, fontFace: FONT, fit: 'shrink' });
  if (d.citation) s.addText(d.citation, { x: M, y: 6.35, w: CW, h: 0.3, fontSize: 10, color: p.muted, fontFace: FONT });
  note(s, d.notes);
};

L.compare = (s, d) => {
  base(s, d.n); kicker(s, d.kicker || 'Comparison');
  title(s, d.title, 1.05, 29, 11.6);
  const colW = 3.75, gap = 0.55, startY = 2.35;
  d.columns.forEach((col, i) => {
    const x = M + i * (colW + gap);
    s.addShape(pptx.ShapeType.rect, { x, y: startY, w: colW, h: 3.35, fill: { color: i === 1 ? p.panel : p.bg }, line: { color: i === 1 ? p.accent : p.panel, width: 1 } });
    s.addShape(pptx.ShapeType.rect, { x, y: startY, w: colW, h: 0.08, fill: { color: i === 1 ? p.accent2 : p.accent }, line: { color: i === 1 ? p.accent2 : p.accent, transparency: 100 } });
    s.addText(col.head, { x: x + 0.25, y: startY + 0.3, w: colW - 0.5, h: 0.65, fontSize: 20, bold: true, color: p.ink, fontFace: FONT, fit: 'shrink' });
    bullets(s, col.items, x + 0.25, startY + 1.15, colW - 0.5, 1.9, 15);
  });
  if (d.citation) s.addText(d.citation, { x: M, y: 6.35, w: CW, h: 0.3, fontSize: 10, color: p.muted, fontFace: FONT });
  note(s, d.notes);
};

L.process = (s, d) => {
  base(s, d.n); kicker(s, d.kicker || 'Process');
  title(s, d.title, 1.05, 29, 11.6);
  const stepW = 2.75, gap = 0.36, y = 2.7;
  d.steps.forEach((st, i) => {
    const x = M + i * (stepW + gap);
    s.addShape(pptx.ShapeType.ellipse, { x: x + 1.05, y: y - 0.55, w: 0.65, h: 0.65, fill: { color: p.accent }, line: { color: p.accent, transparency: 100 } });
    s.addText(String(i + 1), { x: x + 1.05, y: y - 0.44, w: 0.65, h: 0.35, fontSize: 13, bold: true, color: 'FFFFFF', align: 'center', fontFace: FONT });
    s.addText(st.head, { x, y: y + 0.35, w: stepW, h: 0.7, fontSize: 17, bold: true, color: p.ink, align: 'center', fontFace: FONT, fit: 'shrink' });
    s.addText(st.body || '', { x, y: y + 1.15, w: stepW, h: 1.5, fontSize: 13, color: p.muted, align: 'center', fontFace: FONT, fit: 'shrink' });
    if (i < d.steps.length - 1) s.addShape(pptx.ShapeType.rect, { x: x + stepW + 0.06, y: y - 0.2, w: 0.24, h: 0.03, fill: { color: p.accent2 }, line: { color: p.accent2, transparency: 100 } });
  });
  if (d.citation) s.addText(d.citation, { x: M, y: 6.35, w: CW, h: 0.3, fontSize: 10, color: p.muted, fontFace: FONT });
  note(s, d.notes);
};

L.quote = (s, d) => {
  base(s, d.n);
  s.addText('\u201C', { x: M, y: 1.35, w: 1.2, h: 1.0, fontSize: 72, bold: true, color: p.accent2, fontFace: FONT });
  s.addText(d.quote, { x: M + 0.5, y: 2.15, w: 10.5, h: 2.2, fontSize: 31, bold: true, color: p.ink, fontFace: FONT, fit: 'shrink' });
  s.addText(d.attribution || '', { x: M + 0.5, y: 4.7, w: 8, h: 0.4, fontSize: 14, color: p.muted, fontFace: FONT });
  note(s, d.notes);
};

L.summary = (s, d) => {
  base(s, d.n); kicker(s, d.kicker || 'Conclusion');
  title(s, d.title, 1.05, 30, 11.4);
  bullets(s, d.bullets || [], M, 2.35, 7.3, 3.2, 19);
  s.addShape(pptx.ShapeType.rect, { x: 8.35, y: 2.3, w: 4.25, h: 3.35, fill: { color: p.panel }, line: { color: p.panel, transparency: 100 } });
  s.addText(d.calloutHead || 'Next step', { x: 8.65, y: 2.6, w: 3.6, h: 0.45, fontSize: 18, bold: true, color: p.accent, fontFace: FONT });
  s.addText(d.callout || '', { x: 8.65, y: 3.15, w: 3.6, h: 2.0, fontSize: 16, color: p.ink, fontFace: FONT, fit: 'shrink' });
  note(s, d.notes);
};

L.sources = (s, d) => {
  base(s, d.n); kicker(s, 'Sources');
  title(s, 'Sources', 1.05, 30, 6);
  const rows = (plan.sources || []).map((src, i) => ({
    text: `[${src.id}] ${src.title}\n${src.url}`,
    options: { bullet: { type: 'bullet' }, breakLine: i < plan.sources.length - 1, fontSize: 13, color: p.ink, paraSpaceAfterPt: 12, fontFace: FONT }
  }));
  if (rows.length) {
    s.addText(rows, { x: M, y: 2.1, w: CW, h: 3.6, valign: 'top', fit: 'shrink' });
  } else {
    s.addText('No external facts were added to this deck. It is a topic-only starter generated from your prompt.', {
      x: M, y: 2.2, w: CW, h: 1.2, fontSize: 18, color: p.ink, fontFace: FONT, fit: 'shrink'
    });
  }
  s.addText('Editable PowerPoint elements: text, shapes, process diagram and layouts.', { x: M, y: 6.15, w: CW, h: 0.4, fontSize: 10, italic: true, color: p.muted, fontFace: FONT });
};

plan.slides.forEach((d, i) => {
  const slide = pptx.addSlide();
  d.n = i + 1;
  const fn = L[d.layout];
  if (!fn) throw new Error(`Unknown layout: ${d.layout}`);
  fn(slide, d);
});

fs.mkdirSync(path.dirname(outPath), { recursive: true });
pptx.writeFile({ fileName: outPath }).then(() => {
  console.log(`PPTX:${path.resolve(outPath)}`);
  console.log(`SLIDES:${plan.slides.length}`);
}).catch(e => { console.error(e); process.exit(1); });
