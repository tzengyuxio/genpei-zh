#!/usr/bin/env python3
"""Build a local web page for placing calligraphy glyphs.

The glyph images in translation/calligraphy/<target>/ (one PNG per glyph,
`<column>-<pos>-<char>[_...].png`, black ink on white) are drawn the way
textimg.py will draw them: scaled per glyph, laid out down the column,
box-filtered to game pixels, light core plus a 1 px dark rim, over the
game screen. The page exports the per-glyph scale/offset as JSON to save
as translation/calligraphy/<target>/layout.json.

    python3 tools/calligraphy_editor.py [--target opendat|maincmd2] [--bg FRAME.png]
        -> build/calligraphy-editor[-maincmd2].html

opendat   the opening 平家物語 (Opendat.gp chunks 14-17); shows each chunk's
          compressed size against the slot it must fit in. FRAME.png is a
          640x480 DOSBox-X capture of the opening (game area at y=40);
          without it the background is black.
maincmd2  the defeat screen (Maincmd2.gp, four uncompressed 48x358
          columns); the background is the folding-screen painting from the
          game file in the colours of the last frame.

The page embeds game graphics, so it lives in build/ and is not committed.
"""
from __future__ import annotations

import argparse
import base64
import json
import struct
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gfx  # noqa: E402
import npk  # noqa: E402
import textimg  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# Maincmd2.gp columns, right to left: game-area (x, y) of each 48x358 column (formats.md §10.6)
MAINCMD2_COLUMNS = [(416, 24), (336, 38), (256, 28), (176, 34)]
# colours of the painting on the last frame of the defeat screen (Losepal fade end)
MAINCMD2_PAL = ['000000', '102092', '8261a2', '301041', '003030', '3041b2', '925182', 'a2d3e3',
                '715192', '612061', '714161', '512030', '713061', '714192', '000030', '612041']


def png_url(args: list[str]) -> str:
    data = subprocess.run(['magick', *args, 'png:-'], check=True, capture_output=True).stdout
    return 'data:image/png;base64,' + base64.b64encode(data).decode()


def collect(target: str) -> dict:
    files = sorted((ROOT / 'translation/calligraphy' / target).glob('*-*-*.png'),
                   key=lambda f: [int(n) for n in f.name.split('-')[:2]])
    lines: dict[int, list] = {}
    for f in files:
        chunk, pos, rest = f.stem.split('-', 2)
        char, *source = rest.split('_')
        gw, gh = map(int, subprocess.run(['magick', 'identify', '-format', '%w %h', str(f)],
                                         check=True, capture_output=True, text=True).stdout.split())
        lines.setdefault(int(chunk), []).append({
            'key': f'{chunk}-{pos}', 'char': char, 'source': ' '.join(source), 'gw': gw, 'gh': gh,
            'url': png_url([str(f), '-colorspace', 'gray', '-negate']),
        })
    if target == 'maincmd2':
        _, w, h = textimg.RAW_COLUMNS['Maincmd2.gp']
        return {'unit': '欄', 'core': 'a2d3e3', 'rim': '000030',
                'chunks': [{'chunk': i, 'x': x, 'y': y, 'w': w, 'h': h, 'room': None, 'glyphs': lines[i]}
                           for i, (x, y) in enumerate(MAINCMD2_COLUMNS, 1) if i in lines]}
    chunks = npk.scan_archive((ROOT / 'game/GENPEI/Opendat.gp').read_bytes())
    out = []
    for i, glyphs in sorted(lines.items()):
        npk.decode(chunks[i - 1])          # its trailer holds this chunk's (x, y, w, h)
        x, y, _, _ = struct.unpack('<4H', chunks[i - 1].trailer[-8:])
        c = chunks[i]
        npk.decode(c)
        out.append({'chunk': i, 'x': x, 'y': y, 'w': c.width, 'h': c.height,
                    'room': c.size - len(c.trailer), 'glyphs': glyphs})
    return {'unit': '張', 'core': 'e3f3f3', 'rim': '002051', 'chunks': out}


PAGE = r'''<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Calligraphy Layout</title>
<style>
:root { --bg: #f4f4f2; --fg: #222; --muted: #777; --line: #ccc; --bad: #c0392b; --ok: #2e7d32; --sel: #fff6c8; }
body { margin: 0; font: 14px/1.4 -apple-system, "PingFang TC", sans-serif; background: var(--bg); color: var(--fg); }
main { display: flex; gap: 12px; padding: 12px; align-items: flex-start; }
#stage { position: relative; flex: none; }
canvas { image-rendering: pixelated; display: block; }
#overlay { position: absolute; left: 0; top: 0; cursor: crosshair; }
aside { flex: 1; min-width: 300px; max-width: 760px; }
#tables { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 0 12px; }
table { border-collapse: collapse; width: 100%; margin-bottom: 6px; font-size: 13px; }
th, td { border-bottom: 1px solid var(--line); padding: 1px 3px; text-align: left; white-space: nowrap; }
tr.sel td { background: var(--sel); }
td.char { font-size: 16px; width: 1.2em; }
td.src { color: var(--muted); font-size: 11px; max-width: 7em; overflow: hidden; text-overflow: ellipsis; }
input[type=number] { width: 3.6em; }
button { font-size: 12px; }
.size { font-variant-numeric: tabular-nums; font-weight: 600; }
.size.bad { color: var(--bad); } .size.ok { color: var(--ok); }
.bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 8px 0; }
textarea { width: 100%; height: 90px; font: 12px ui-monospace, monospace; }
h3 { margin: 12px 0 4px; }
.help { color: var(--muted); font-size: 12px; }
</style></head><body><main>
<div id="stage"><canvas id="screen" width="640" height="400"></canvas><canvas id="overlay" width="640" height="400"></canvas></div>
<aside>
  <div class="bar">
    <label>顯示倍率 <select id="zoom"><option>1.5</option><option selected>2</option><option>3</option><option>4</option></select></label>
    <label>100% 基準 <select id="base"><option value="column">各欄寬度</option><option value="36">統一 36 px</option><option value="40">統一 40 px</option></select></label>
    <label><input type="checkbox" id="boxes" checked> 顯示框線</label>
  </div>
  <div class="bar"><label>分配高度 <input type="number" id="pct" value="80" min="10" max="100" step="5"> %</label>
    <button id="even-all">全部欄：平均字距</button><button id="span-all">全部欄：依分配高度</button></div>
  <p class="help">字距＝與上一個字的距離（第一個字是與欄頂的距離）；改字距會帶動下面的字。點選字後拖曳移動；拖曳時按住 Shift 只水平或垂直移動；方向鍵移動 1 px（Shift 5 px）；+／− 調整大小 5%（Shift 1%）。拖曳、方向鍵與改大小都只動這個字，上下的字不動。Esc 取消選取。單位是遊戲像素。</p>
  <div id="tables"></div>
  <h3>參數（存成 translation/calligraphy/__TARGET__/layout.json）</h3>
  <div class="bar"><button id="copy">複製</button><button id="download">下載 layout.json</button><button id="load">套用下方 JSON</button><button id="reset">全部重設</button></div>
  <textarea id="json"></textarea>
</aside></main>
<script>
const D = __DATA__;
const INIT = __INIT__;
// unsaved edits survive a reload, unless layout.json changed since they were made
const STORE = 'genpei-calligraphy-__TARGET__', INIT_TEXT = JSON.stringify(INIT);
const rgb = h => [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16));
const SS = 4, CORE = 112, C6 = rgb(D.rim), C7 = rgb(D.core);
const screen = document.getElementById('screen'), overlay = document.getElementById('overlay');
const sctx = screen.getContext('2d', { willReadFrequently: true }), octx = overlay.getContext('2d');
// load() below needs these before P exists
const DEF = { '之': [50, 0], '、': [7, 12], '。': [12, 11] };
let P = load();                 // { base, glyphs: { "14-1": {scale, dx, gap} } }
let sel = null, drag = null, layoutCache = {}, pixels = {};
// show only the area around the columns
const V = (() => {
  const x0 = Math.max(0, Math.min(...D.chunks.map(c => c.x)) - 24), x1 = Math.min(640, Math.max(...D.chunks.map(c => c.x + c.w)) + 24);
  const y0 = Math.max(0, Math.min(...D.chunks.map(c => c.y)) - 16), y1 = Math.min(400, Math.max(...D.chunks.map(c => c.y + c.h)) + 16);
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
})();
screen.width = V.w; screen.height = V.h;

// same starting values and rounding as textimg.DEFAULTS / spread() / glyph_cells()
function box(c, g, scale, base) {
  const B = base === 'column' ? c.w - 4 : +base, r = scale / 100;
  return [Math.floor(B * r), Math.floor(B * r * g.gh / g.gw)];
}
function spread(hs, top, span) {
  const n = hs.length, g = n > 1 ? (span - hs.reduce((s, v) => s + v, 0)) / (n - 1) : 0;
  const ys = hs.map((_, k) => Math.floor(top + hs.slice(0, k).reduce((s, v) => s + v, 0) + k * g + 0.5));
  return ys.map((y, k) => k ? y - ys[k - 1] - hs[k - 1] : y);
}
function defaultGlyphs(c, base) {
  const gl = {};
  for (const g of c.glyphs) { const [scale, dx] = DEF[g.char] || [100, 0]; gl[g.key] = { scale, dx, gap: 0 }; }
  const hs = c.glyphs.map(g => box(c, g, gl[g.key].scale, base)[1]);
  spread(hs, Math.floor(c.h * 0.015 + 0.5), c.h * 0.97).forEach((v, i) => { gl[c.glyphs[i].key].gap = v; });
  return gl;
}
function defaults() {
  const p = { base: 'column', glyphs: {} };
  for (const c of D.chunks) Object.assign(p.glyphs, defaultGlyphs(c, p.base));
  return p;
}
// layouts saved before gaps existed ({scale, dx, dy}, equal spacing): convert to {scale, dx, gap}
function fromLegacy(src) {
  const base = src.base ?? 'column', out = { base, glyphs: {} };
  for (const c of D.chunks) {
    const B = base === 'column' ? c.w - 4 : +base, sp = g => src.glyphs[g.key] || {};
    const rel = c.glyphs.map(g => (sp(g).scale ?? (DEF[g.char] || [100])[0]) / 100);
    const fit = Math.min(B, c.h * 0.97 / rel.reduce((s, r, i) => s + r * c.glyphs[i].gh / c.glyphs[i].gw, 0));
    const old = c.glyphs.map((g, i) => [Math.floor(fit * rel[i]), Math.floor(fit * rel[i] * g.gh / g.gw)]);
    const gap = (c.h - old.reduce((s, b) => s + b[1], 0)) / old.length;
    let y = gap / 2, prev = 0;
    c.glyphs.forEach((g, i) => {
      const [bw, bh] = old[i], x0 = Math.floor((c.w - bw) / 2), y0 = Math.floor(y);
      const cx = Math.min(Math.max(x0 + (sp(g).dx ?? 0), 0), Math.max(c.w - bw, 0));
      const cy = Math.min(Math.max(y0 + (sp(g).dy ?? 0), 0), Math.max(c.h - bh, 0));
      const scale = rel[i] * 100 * fit / B, [nw, nh] = box(c, g, scale, base);
      out.glyphs[g.key] = { scale, dx: cx - Math.floor((c.w - nw) / 2), gap: cy - prev };
      prev = cy + nh; y += bh + gap;
    });
  }
  return out;
}
function isLegacy(src) { return Object.values(src.glyphs || {}).some(g => 'dy' in g && !('gap' in g)); }
function load() {
  let stored = null;
  try { stored = JSON.parse(localStorage.getItem(STORE)); } catch (e) {}
  const p = defaults();
  let src = stored && stored.init === INIT_TEXT ? stored.params : INIT;
  if (src) {
    if (isLegacy(src)) src = fromLegacy(src);
    p.base = src.base ?? p.base;
    for (const k in src.glyphs || {}) if (p.glyphs[k]) Object.assign(p.glyphs[k], src.glyphs[k]);
  }
  return p;
}
function save() {
  const text = JSON.stringify(P, null, 1);
  document.getElementById('json').value = text;
  try { localStorage.setItem(STORE, JSON.stringify({ init: INIT_TEXT, params: P })); } catch (e) {}
}

// each glyph sits `gap` px below the one above (the first: below the column top), centred + dx
function layout(c) {
  let y = 0;
  const cells = c.glyphs.map(g => {
    const p = P.glyphs[g.key], [bw, bh] = box(c, g, p.scale, P.base);
    y += p.gap;
    // dx keeps the glyph box inside the column; the clamped value is what gets saved
    const x0 = Math.floor((c.w - bw) / 2), cx = Math.min(Math.max(x0 + p.dx, 0), Math.max(c.w - bw, 0));
    p.dx = cx - x0;
    const cy = Math.min(Math.max(y, 0), Math.max(c.h - bh, 0));
    const cell = { x: cx, y: cy, bw, bh, g, c, out: cy !== y };
    y += bh; return cell;
  });
  cells.over = cells.some(k => k.out);
  return cells;
}
const where = key => { for (const c of D.chunks) { const i = c.glyphs.findIndex(g => g.key === key); if (i >= 0) return { c, i }; } };
// resize around the glyph's centre; the glyphs above and below stay put
function setScale(key, v) {
  const { c, i } = where(key), g = c.glyphs[i], p = P.glyphs[key];
  const h0 = box(c, g, p.scale, P.base)[1];
  p.scale = Math.max(1, v);
  const dh = box(c, g, p.scale, P.base)[1] - h0, up = Math.floor(dh / 2), next = c.glyphs[i + 1];
  p.gap -= up;
  if (next) P.glyphs[next.key].gap -= dh - up;
}
// move one glyph down by d; the glyphs below stay put
function moveY(key, d) {
  const { c, i } = where(key), next = c.glyphs[i + 1];
  P.glyphs[key].gap += d;
  if (next) P.glyphs[next.key].gap -= d;
}
function tops(c) {
  let y = 0;
  const hs = c.glyphs.map(g => box(c, g, P.glyphs[g.key].scale, P.base)[1]);
  const t = c.glyphs.map((g, k) => { y += P.glyphs[g.key].gap; const top = y; y += hs[k]; return top; });
  return { hs, top: t[0], bottom: y };
}
// equal gaps between the glyphs; first top and last bottom unchanged
function evenGaps(c) {
  const { hs, top, bottom } = tops(c);
  spread(hs, top, bottom - top).forEach((v, i) => { P.glyphs[c.glyphs[i].key].gap = v; });
}
// equal gaps over pct % of the column height, from the first glyph's top (moved up if it would overflow)
function spanGaps(c, pct) {
  const { hs, top } = tops(c), span = c.h * pct / 100;
  spread(hs, Math.max(0, Math.min(top, c.h - span)), span).forEach((v, i) => { P.glyphs[c.glyphs[i].key].gap = v; });
}

const images = {};
function img(g) { return images[g.key] ||= Object.assign(new Image(), { src: g.url, onload: renderAll }); }

function renderChunk(c) {
  const cells = layout(c); layoutCache[c.chunk] = cells;
  const cv = new OffscreenCanvas(c.w * SS, c.h * SS), ctx = cv.getContext('2d', { willReadFrequently: true });
  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, cv.width, cv.height);
  ctx.globalCompositeOperation = 'lighten'; ctx.imageSmoothingQuality = 'high';
  for (const k of cells) { const im = img(k.g); if (im.complete && im.naturalWidth) ctx.drawImage(im, k.x * SS, k.y * SS, k.bw * SS, k.bh * SS); }
  const src = ctx.getImageData(0, 0, cv.width, cv.height).data, w = c.w, h = c.h;
  const core = new Uint8Array(w * h), px = new Uint8Array(w * h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    let s = 0;
    for (let j = 0; j < SS; j++) for (let i = 0; i < SS; i++) s += src[(((y * SS + j) * cv.width) + x * SS + i) * 4];
    core[y * w + x] = Math.round(s / (SS * SS)) >= CORE;
  }
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    if (core[y * w + x]) { px[y * w + x] = 7; continue; }
    let r = 0;
    for (let dy = -1; dy <= 1 && !r; dy++) for (let dx = -1; dx <= 1; dx++) {
      const xx = x + dx, yy = y + dy;
      if (xx >= 0 && xx < w && yy >= 0 && yy < h && core[yy * w + xx]) { r = 6; break; }
    }
    px[y * w + x] = r;
  }
  pixels[c.chunk] = px;
  const el = document.getElementById('size-' + c.chunk);
  const over = layoutCache[c.chunk].over ? '　超出欄高' : '';
  if (c.room === null) { el.textContent = '未壓縮，大小固定' + over; el.className = 'size ' + (over ? 'bad' : 'ok'); return; }
  const size = 48 + pack(px, w);
  el.textContent = `${size} / ${c.room} bytes${over}`; el.className = 'size ' + (size <= c.room && !over ? 'ok' : 'bad');
}

// port of npk.pack(): greedy NPK016 encoder, returns the payload length only
function pack(px, line) {
  const n = px.length, offs = [];
  for (let k = 1; k <= 4; k++) offs.push([k * 4, false]);
  for (let k = 1; k <= 4; k++) offs.push([k * line, true]);
  let len = 0, bit = 8, p = 0;
  while (p < n) {
    if (bit === 8) { len++; bit = 0; }
    let best = 0;
    for (const [off, vert] of offs) {
      if (off > p || (!vert && off > p % line)) continue;
      const limit = Math.min(32, Math.floor((line - p % line) / 4));
      let u = 0;
      while (u < limit) {
        const q = p + u * 4;
        if (px[q] !== px[q - off] || px[q + 1] !== px[q + 1 - off] || px[q + 2] !== px[q + 2 - off] || px[q + 3] !== px[q + 3 - off]) break;
        u++;
      }
      if (u > best) best = u;
    }
    if (best) { len += 1; p += best * 4; } else { len += 2; p += 4; }
    bit++;
  }
  return len;
}

const bgImg = D.bg ? Object.assign(new Image(), { src: D.bg, onload: renderAll }) : null;
function paint() {
  sctx.fillStyle = '#000'; sctx.fillRect(0, 0, V.w, V.h);
  if (bgImg && bgImg.complete) sctx.drawImage(bgImg, -V.x, -V.y);
  const id = sctx.getImageData(0, 0, V.w, V.h);
  for (const c of D.chunks) {
    const px = pixels[c.chunk]; if (!px) continue;
    for (let y = 0; y < c.h; y++) for (let x = 0; x < c.w; x++) {
      const v = px[y * c.w + x]; if (!v) continue;
      const col = v === 7 ? C7 : C6, o = ((c.y + y - V.y) * V.w + c.x + x - V.x) * 4;
      id.data[o] = col[0]; id.data[o + 1] = col[1]; id.data[o + 2] = col[2];
    }
  }
  sctx.putImageData(id, 0, 0);
  drawOverlay();
}
function drawOverlay() {
  const z = +document.getElementById('zoom').value;
  octx.setTransform(1, 0, 0, 1, 0, 0); octx.clearRect(0, 0, overlay.width, overlay.height); octx.setTransform(z, 0, 0, z, -V.x * z, -V.y * z);
  octx.lineWidth = 1 / z;
  for (const c of D.chunks) {
    if (document.getElementById('boxes').checked) { octx.strokeStyle = 'rgba(255,255,255,.35)'; octx.setLineDash([4 / z, 4 / z]); octx.strokeRect(c.x, c.y, c.w, c.h); octx.setLineDash([]); }
    for (const k of layoutCache[c.chunk] || []) {
      const on = sel === k.g.key;
      if (!on && !document.getElementById('boxes').checked) continue;
      octx.strokeStyle = on ? '#ffd400' : 'rgba(255,212,0,.35)'; octx.lineWidth = (on ? 2 : 1) / z;
      octx.strokeRect(c.x + k.x, c.y + k.y, k.bw, k.bh);
    }
  }
}
function renderAll() { for (const c of D.chunks) renderChunk(c); paint(); syncInputs(); save(); }
function renderOne(key) { renderChunk(D.chunks.find(c => c.glyphs.some(g => g.key === key))); paint(); syncInputs(); save(); }

function resize() {
  const z = +document.getElementById('zoom').value;
  for (const cv of [screen, overlay]) { cv.style.width = V.w * z + 'px'; cv.style.height = V.h * z + 'px'; }
  overlay.width = V.w * z; overlay.height = V.h * z; drawOverlay();
}

function buildTables() {
  const box = document.getElementById('tables');
  for (const c of D.chunks) {
    const t = document.createElement('table');
    t.innerHTML = `<tr><th colspan="2">第 ${c.chunk} ${D.unit}（${c.w}×${c.h}）</th><th colspan="4"><span class="size" id="size-${c.chunk}"></span></th></tr>
      <tr><td colspan="6"><button data-even="${c.chunk}">平均字距</button> <button data-span="${c.chunk}">依分配高度</button></td></tr>
      <tr><th></th><th>出處</th><th>大小 %</th><th>dx</th><th title="第一個字：與欄頂的距離">字距</th><th></th></tr>`;
    for (const g of c.glyphs) {
      const tr = document.createElement('tr'); tr.id = 'row-' + g.key;
      tr.innerHTML = `<td class="char">${g.char}</td><td class="src" title="${g.source}">${g.source}</td>` +
        ['scale', 'dx', 'gap'].map(f => `<td><input type="number" data-key="${g.key}" data-f="${f}" step="${f === 'scale' ? 5 : 1}"></td>`).join('') +
        `<td><button data-reset="${g.key}">重設</button></td>`;
      tr.addEventListener('click', e => { if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'BUTTON') select(g.key); });
      t.appendChild(tr);
    }
    box.appendChild(t);
  }
  box.addEventListener('input', e => {
    const { key, f } = e.target.dataset; if (!key) return;
    const v = parseFloat(e.target.value); if (Number.isNaN(v)) return;
    if (f === 'scale') setScale(key, v); else P.glyphs[key][f] = v;
    sel = key; renderOne(key);
  });
  box.addEventListener('click', e => {
    const { reset, even, span } = e.target.dataset;
    if (even || span) { const c = D.chunks.find(c => c.chunk === +(even || span)); if (even) evenGaps(c); else spanGaps(c, pct()); renderAll(); return; }
    if (!reset) return;
    const { c, i } = where(reset), [scale, dx] = DEF[c.glyphs[i].char] || [100, 0];
    setScale(reset, scale); P.glyphs[reset].dx = dx; renderOne(reset);
  });
}
function syncInputs() {
  for (const el of document.querySelectorAll('input[data-key]')) if (el !== document.activeElement) el.value = +(+P.glyphs[el.dataset.key][el.dataset.f]).toFixed(2);
  for (const tr of document.querySelectorAll('tr[id^=row-]')) tr.classList.toggle('sel', tr.id === 'row-' + sel);
}
function select(key) { sel = key; syncInputs(); drawOverlay(); }

function hit(ev) {
  const r = overlay.getBoundingClientRect(), gx = V.x + (ev.clientX - r.left) * V.w / r.width, gy = V.y + (ev.clientY - r.top) * V.h / r.height;
  for (const c of D.chunks) for (const k of layoutCache[c.chunk] || [])
    if (gx >= c.x + k.x && gx < c.x + k.x + k.bw && gy >= c.y + k.y && gy < c.y + k.y + k.bh) return { key: k.g.key, gx, gy };
  return { key: null, gx, gy };
}
overlay.addEventListener('mousedown', e => {
  const h = hit(e); select(h.key);
  if (h.key) drag = { key: h.key, gx: h.gx, gy: h.gy, dx: P.glyphs[h.key].dx, my: 0 };
});
window.addEventListener('mousemove', e => {
  if (!drag) return;
  const h = hit(e), p = P.glyphs[drag.key];
  let mx = Math.round(h.gx - drag.gx), my = Math.round(h.gy - drag.gy);
  if (e.shiftKey) { if (Math.abs(mx) >= Math.abs(my)) my = 0; else mx = 0; }   // Shift: horizontal or vertical only
  if (drag.dx + mx !== p.dx || my !== drag.my) { p.dx = drag.dx + mx; moveY(drag.key, my - drag.my); drag.my = my; renderOne(drag.key); }
});
window.addEventListener('mouseup', () => { drag = null; });
window.addEventListener('keydown', e => {
  if (!sel || e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  const p = P.glyphs[sel], step = e.shiftKey ? 5 : 1;
  const act = { ArrowLeft: () => p.dx -= step, ArrowRight: () => p.dx += step, ArrowUp: () => moveY(sel, -step), ArrowDown: () => moveY(sel, step),
    '+': () => setScale(sel, p.scale + (e.shiftKey ? 1 : 5)), '=': () => setScale(sel, p.scale + 5),
    '-': () => setScale(sel, Math.max(1, p.scale - (e.shiftKey ? 1 : 5))), '_': () => setScale(sel, Math.max(1, p.scale - 1)),
    Escape: () => { sel = null; } }[e.key];
  if (!act) return;
  e.preventDefault(); act();
  if (sel) renderOne(sel); else { syncInputs(); drawOverlay(); }
});

const pct = () => Math.min(100, Math.max(10, +document.getElementById('pct').value || 80));
document.getElementById('even-all').addEventListener('click', () => { D.chunks.forEach(evenGaps); renderAll(); });
document.getElementById('span-all').addEventListener('click', () => { D.chunks.forEach(c => spanGaps(c, pct())); renderAll(); });
document.getElementById('zoom').addEventListener('change', resize);
document.getElementById('boxes').addEventListener('change', drawOverlay);
document.getElementById('base').addEventListener('change', e => { P.base = e.target.value; renderAll(); });
document.getElementById('copy').addEventListener('click', () => navigator.clipboard.writeText(document.getElementById('json').value));
document.getElementById('download').addEventListener('click', () => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([document.getElementById('json').value + '\n'], { type: 'application/json' }));
  a.download = 'layout.json'; a.click();
});
document.getElementById('load').addEventListener('click', () => {
  try { let src = JSON.parse(document.getElementById('json').value); if (isLegacy(src)) src = fromLegacy(src); P = defaults(); P.base = src.base ?? P.base;
    for (const k in src.glyphs || {}) if (P.glyphs[k]) Object.assign(P.glyphs[k], src.glyphs[k]);
    document.getElementById('base').value = P.base; renderAll(); } catch (err) { alert('JSON 格式錯誤：' + err.message); }
});
document.getElementById('reset').addEventListener('click', () => { if (confirm('全部回到預設？')) { P = defaults(); document.getElementById('base').value = P.base; renderAll(); } });

buildTables(); document.getElementById('base').value = P.base; resize(); renderAll();
</script></body></html>
'''


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--target', choices=['opendat', 'maincmd2'], default='opendat')
    ap.add_argument('--bg', type=Path, help='640x480 capture of the screen (game area at y=40)')
    args = ap.parse_args()
    layout = ROOT / 'translation/calligraphy' / args.target / 'layout.json'
    out = ROOT / ('build/calligraphy-editor.html' if args.target == 'opendat'
                  else f'build/calligraphy-editor-{args.target}.html')
    data = collect(args.target)
    out.parent.mkdir(exist_ok=True)
    if args.bg:
        data['bg'] = png_url([str(args.bg), '-crop', '640x400+0+40', '+repage'])
    elif args.target == 'maincmd2':
        bg = out.parent / 'maincmd2-bg.png'
        px = gfx.decode_planar_bytes((ROOT / 'game/GENPEI/Maincmd2.gp').read_bytes(), 640, 400, 4, offset=0x25033)
        gfx.write_png(bg, 640, 400, px, [tuple(bytes.fromhex(c)) for c in MAINCMD2_PAL])
        data['bg'] = png_url([str(bg)])
    init = json.loads(layout.read_text()) if layout.exists() else None
    page = PAGE.replace('__TARGET__', args.target)
    out.write_text(page.replace('__DATA__', json.dumps(data)).replace('__INIT__', json.dumps(init)), encoding='utf-8')
    print(f'{out} ({out.stat().st_size // 1024} KB; layout {"from " + layout.name if init else "defaults"})')


if __name__ == '__main__':
    main()
