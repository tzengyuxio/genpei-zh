#!/usr/bin/env python3
"""Build a local web page for placing the opening calligraphy glyphs.

The glyph images in translation/calligraphy/opendat/ (one PNG per glyph,
`<chunk>-<pos>-<char>[_...].png`, black ink on white) are drawn the way
textimg.py will draw them: scaled per glyph, laid out down the column,
box-filtered to game pixels, white core plus a 1 px dark rim, over a
frame of the opening. The page shows each chunk's compressed size against
the slot it must fit in, and exports the per-glyph scale/offset as JSON
to save as translation/calligraphy/opendat/layout.json.

    python3 tools/calligraphy_editor.py [--bg FRAME.png]   -> build/calligraphy-editor.html

FRAME.png is a 640x480 DOSBox-X capture of the opening (game area at
y=40); without it the background is black. The page embeds game graphics,
so it lives in build/ and is not committed.
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
import npk  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GLYPHS = ROOT / 'translation/calligraphy/opendat'
LAYOUT = GLYPHS / 'layout.json'
OUT = ROOT / 'build/calligraphy-editor.html'


def png_url(args: list[str]) -> str:
    data = subprocess.run(['magick', *args, 'png:-'], check=True, capture_output=True).stdout
    return 'data:image/png;base64,' + base64.b64encode(data).decode()


def collect() -> dict:
    chunks = npk.scan_archive((ROOT / 'game/GENPEI/Opendat.gp').read_bytes())
    files = sorted(GLYPHS.glob('*-*-*.png'), key=lambda f: [int(n) for n in f.name.split('-')[:2]])
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
    out = []
    for i, glyphs in sorted(lines.items()):
        npk.decode(chunks[i - 1])          # its trailer holds this chunk's (x, y, w, h)
        x, y, _, _ = struct.unpack('<4H', chunks[i - 1].trailer[-8:])
        c = chunks[i]
        npk.decode(c)
        out.append({'chunk': i, 'x': x, 'y': y, 'w': c.width, 'h': c.height,
                    'room': c.size - len(c.trailer), 'glyphs': glyphs})
    return {'chunks': out}


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
  <p class="help">點選字後拖曳移動；拖曳時按住 Shift 只水平或垂直移動；方向鍵移動 1 px（Shift 5 px）；+／− 調整大小 5%（Shift 1%）；Esc 取消選取。位置單位是遊戲像素。</p>
  <div id="tables"></div>
  <h3>參數（存成 translation/calligraphy/opendat/layout.json）</h3>
  <div class="bar"><button id="copy">複製</button><button id="download">下載 layout.json</button><button id="load">套用下方 JSON</button><button id="reset">全部重設</button></div>
  <textarea id="json"></textarea>
</aside></main>
<script>
const D = __DATA__;
const INIT = __INIT__;
// unsaved edits survive a reload, unless layout.json changed since they were made
const STORE = 'genpei-calligraphy', INIT_TEXT = JSON.stringify(INIT);
const SS = 4, CORE = 112, C6 = [0x00, 0x20, 0x51], C7 = [0xe3, 0xf3, 0xf3];
const screen = document.getElementById('screen'), overlay = document.getElementById('overlay');
const sctx = screen.getContext('2d', { willReadFrequently: true }), octx = overlay.getContext('2d');
let P = load();                 // { base, glyphs: { "14-1": {scale, dx, dy} } }
let sel = null, drag = null, layoutCache = {}, pixels = {};
// show only the area around the columns
const V = (() => {
  const x0 = Math.max(0, Math.min(...D.chunks.map(c => c.x)) - 24), x1 = Math.min(640, Math.max(...D.chunks.map(c => c.x + c.w)) + 24);
  const y0 = Math.max(0, Math.min(...D.chunks.map(c => c.y)) - 16), y1 = Math.min(400, Math.max(...D.chunks.map(c => c.y + c.h)) + 16);
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
})();
screen.width = V.w; screen.height = V.h;

function defaults() {
  const g = {};
  for (const c of D.chunks) for (const x of c.glyphs) g[x.key] = { scale: x.char === '之' ? 50 : 100, dx: 0, dy: 0 };
  return { base: 'column', glyphs: g };
}
function load() {
  let stored = null;
  try { stored = JSON.parse(localStorage.getItem(STORE)); } catch (e) {}
  const p = defaults(), src = stored && stored.init === INIT_TEXT ? stored.params : INIT;
  if (src) { p.base = src.base ?? p.base; for (const k in src.glyphs || {}) if (p.glyphs[k]) Object.assign(p.glyphs[k], src.glyphs[k]); }
  return p;
}
function save() {
  const text = JSON.stringify(P, null, 1);
  document.getElementById('json').value = text;
  try { localStorage.setItem(STORE, JSON.stringify({ init: INIT_TEXT, params: P })); } catch (e) {}
}

// same layout as tools/textimg.py: 100% = base width; shrink all only if the column overflows
function layout(c) {
  const B = P.base === 'column' ? c.w - 4 : +P.base;
  const rel = c.glyphs.map(g => P.glyphs[g.key].scale / 100);
  const need = rel.reduce((s, r, i) => s + r * c.glyphs[i].gh / c.glyphs[i].gw, 0);
  const base = Math.min(B, c.h * 0.97 / need);
  const boxes = c.glyphs.map((g, i) => [Math.floor(base * rel[i]), Math.floor(base * rel[i] * g.gh / g.gw)]);
  const gap = (c.h - boxes.reduce((s, b) => s + b[1], 0)) / boxes.length;
  let y = gap / 2;
  return boxes.map(([bw, bh], i) => {
    // offsets keep the glyph box inside the column; the clamped value is what gets saved
    const p = P.glyphs[c.glyphs[i].key], x0 = Math.floor((c.w - bw) / 2), y0 = Math.floor(y);
    const cx = Math.min(Math.max(x0 + p.dx, 0), Math.max(c.w - bw, 0));
    const cy = Math.min(Math.max(y0 + p.dy, 0), Math.max(c.h - bh, 0));
    p.dx = cx - x0; p.dy = cy - y0;
    const cell = { x: cx, y: cy, bw, bh, g: c.glyphs[i], c };
    y += bh + gap; return cell;
  });
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
  const size = 48 + pack(px, w);
  const el = document.getElementById('size-' + c.chunk);
  el.textContent = `${size} / ${c.room} bytes`; el.className = 'size ' + (size <= c.room ? 'ok' : 'bad');
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
    t.innerHTML = `<tr><th colspan="2">第 ${c.chunk} 張（${c.w}×${c.h}）</th><th colspan="3"><span class="size" id="size-${c.chunk}"></span></th><th></th></tr>
      <tr><th></th><th>出處</th><th>大小 %</th><th>dx</th><th>dy</th><th></th></tr>`;
    for (const g of c.glyphs) {
      const tr = document.createElement('tr'); tr.id = 'row-' + g.key;
      tr.innerHTML = `<td class="char">${g.char}</td><td class="src" title="${g.source}">${g.source}</td>` +
        ['scale', 'dx', 'dy'].map(f => `<td><input type="number" data-key="${g.key}" data-f="${f}" step="${f === 'scale' ? 5 : 1}"></td>`).join('') +
        `<td><button data-reset="${g.key}">重設</button></td>`;
      tr.addEventListener('click', e => { if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'BUTTON') select(g.key); });
      t.appendChild(tr);
    }
    box.appendChild(t);
  }
  box.addEventListener('input', e => {
    const { key, f } = e.target.dataset; if (!key) return;
    const v = parseFloat(e.target.value); if (Number.isNaN(v)) return;
    P.glyphs[key][f] = v; sel = key; renderOne(key);
  });
  box.addEventListener('click', e => {
    const k = e.target.dataset.reset; if (!k) return;
    P.glyphs[k] = defaults().glyphs[k]; renderOne(k);
  });
}
function syncInputs() {
  for (const el of document.querySelectorAll('input[data-key]')) if (el !== document.activeElement) el.value = P.glyphs[el.dataset.key][el.dataset.f];
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
  if (h.key) drag = { key: h.key, gx: h.gx, gy: h.gy, dx: P.glyphs[h.key].dx, dy: P.glyphs[h.key].dy };
});
window.addEventListener('mousemove', e => {
  if (!drag) return;
  const h = hit(e), p = P.glyphs[drag.key];
  let mx = Math.round(h.gx - drag.gx), my = Math.round(h.gy - drag.gy);
  if (e.shiftKey) { if (Math.abs(mx) >= Math.abs(my)) my = 0; else mx = 0; }   // Shift: horizontal or vertical only
  const nx = drag.dx + mx, ny = drag.dy + my;
  if (nx !== p.dx || ny !== p.dy) { p.dx = nx; p.dy = ny; renderOne(drag.key); }
});
window.addEventListener('mouseup', () => { drag = null; });
window.addEventListener('keydown', e => {
  if (!sel || e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  const p = P.glyphs[sel], step = e.shiftKey ? 5 : 1;
  const act = { ArrowLeft: () => p.dx -= step, ArrowRight: () => p.dx += step, ArrowUp: () => p.dy -= step, ArrowDown: () => p.dy += step,
    '+': () => p.scale += e.shiftKey ? 1 : 5, '=': () => p.scale += 5, '-': () => p.scale = Math.max(5, p.scale - (e.shiftKey ? 1 : 5)), '_': () => p.scale = Math.max(5, p.scale - 1),
    Escape: () => { sel = null; } }[e.key];
  if (!act) return;
  e.preventDefault(); act();
  if (sel) renderOne(sel); else { syncInputs(); drawOverlay(); }
});

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
  try { const src = JSON.parse(document.getElementById('json').value); P = defaults(); P.base = src.base ?? P.base;
    for (const k in src.glyphs || {}) if (P.glyphs[k]) Object.assign(P.glyphs[k], src.glyphs[k]);
    document.getElementById('base').value = P.base; renderAll(); } catch (err) { alert('JSON 格式錯誤：' + err.message); }
});
document.getElementById('reset').addEventListener('click', () => { if (confirm('全部回到預設？')) { P = defaults(); document.getElementById('base').value = P.base; renderAll(); } });

buildTables(); document.getElementById('base').value = P.base; resize(); renderAll();
</script></body></html>
'''


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--bg', type=Path, help='640x480 capture of the opening (game area at y=40)')
    args = ap.parse_args()
    data = collect()
    if args.bg:
        data['bg'] = png_url([str(args.bg), '-crop', '640x400+0+40', '+repage'])
    init = json.loads(LAYOUT.read_text()) if LAYOUT.exists() else None
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(PAGE.replace('__DATA__', json.dumps(data)).replace('__INIT__', json.dumps(init)), encoding='utf-8')
    print(f'{OUT} ({OUT.stat().st_size // 1024} KB; layout {"from " + LAYOUT.name if init else "defaults"})')


if __name__ == '__main__':
    main()
