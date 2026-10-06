#!/usr/bin/env python3
"""Build a local web page for exploring the montage ("generic") faces.

Generals without a Kaodata portrait get a face composed from Montage.gp
(head, body) and Haikei.gp (eyes, mouth) parts, picked by the bits of
their face code (formats.md §10.3):

    bit 15-14 type (1 armour + helmet, 2 armour, 3 hitatare)
    bit 13-11 head, 10-8 body, 7-4 eyes, 3-0 mouth

The page lets you pick every part, shows the 64x80 in-game window over
one of the five Haikei backgrounds, the resulting code, and which
generals use it. Parts, positions and the drawing order come from
dump_gfx.py (montage_types / masked part decoding), so the faces match
`dump_gfx.py ... Generals` pixel for pixel.

    python3 tools/dump_data.py game/GENPEI build/data      # generals.tsv
    python3 tools/mob_kao_explorer.py                      -> build/mob-kao-explorer.html

The page embeds game graphics, so it lives in build/ and is not committed.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dump_gfx  # noqa: E402
import gfx  # noqa: E402
import unpack_exe  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LAYERS = ("body", "head", "eyes", "mouth")     # drawing order
COUNTS = dict(body=8, head=8, eyes=16, mouth=16)


def b64(px: bytes) -> str:
    return base64.b64encode(px).decode()


def collect(game: Path, generals_tsv: Path) -> dict:
    types = dump_gfx.montage_types(unpack_exe.unpack((game / "Main.exe").read_bytes()))
    files = {n: (game / n).read_bytes() for n in ("Montage.gp", "Haikei.gp")}
    out_types = []
    for n, t in enumerate(types, 1):
        layers = {}
        for layer in LAYERS:
            name, off, w, h, pos = t[layer]
            data = files[name]
            csize = w * h * 3 // 8
            step = csize + w * h // 8
            parts = []
            for i in range(COUNTS[layer]):
                o = off + i * step
                parts.append(b64(gfx.apply_mask(dump_gfx.planar(data, o, w, h, 3),
                                                data, w, h, o + csize)))
            x, y = dump_gfx.buf_xy(pos)
            layers[layer] = dict(file=name, offset=off, step=step, w=w, h=h, x=x, y=y,
                                 parts=parts)
        out_types.append(dict(type=n, window=list(t["window"]), layers=layers))

    generals = []
    with generals_tsv.open(encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE, quotechar=None):
            code = int(r["face"])
            if r["scenario"] == "0" and code >= 0x4000:
                generals.append([int(r["id"]), r["name"],
                                 r["surname_kana"] + " " + r["given_kana"], code])

    pal = gfx.load_palettes(game / "Mainpal.pld")[0]
    return dict(palette=[list(c) for c in pal],
                backgrounds=b64(dump_gfx.planar(files["Haikei.gp"], 0, 64, 400, 3)),
                types=out_types, generals=generals)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("game", nargs="?", default=ROOT / "game/GENPEI", type=Path)
    ap.add_argument("generals", nargs="?", default=ROOT / "build/data/generals.tsv", type=Path)
    ap.add_argument("out", nargs="?", default=ROOT / "build/mob-kao-explorer.html", type=Path)
    a = ap.parse_args()
    if not a.generals.exists():
        sys.exit(f"{a.generals} not found; run tools/dump_data.py first")
    data = collect(a.game, a.generals)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(PAGE.replace("__DATA__", json.dumps(data, ensure_ascii=False)),
                     encoding="utf-8")
    print(f"{a.out}: {len(data['generals'])} montage generals")


PAGE = r"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>大眾臉探索器</title>
<style>
:root {
  --bg: #1b1c22; --panel: #262832; --panel2: #1f2028; --line: #3a3d4a;
  --text: #e6e3da; --dim: #9a978e; --accent: #d9b25f; --sel: #6fbf73; --link: #7cc4e6;
}
* { box-sizing: border-box; }
body { margin: 0; padding: 20px 16px; background: var(--bg); color: var(--text);
  font-family: "PingFang TC", "Noto Sans TC", "Microsoft JhengHei", sans-serif; font-size: 14px; }
h1 { margin: 0 0 18px; text-align: center; color: var(--accent); font-size: 22px; letter-spacing: .1em; }
h1 small { display: block; color: var(--dim); font-size: 12px; letter-spacing: 0; font-weight: normal; margin-top: 4px; }
.wrap { max-width: 1400px; margin: 0 auto; display: grid; gap: 18px;
  grid-template-columns: 360px minmax(0, 1fr) 320px; }
.panel { background: var(--panel); border-radius: 10px; padding: 14px 16px; min-width: 0; }
.panel h2 { margin: 0 0 10px; font-size: 15px; color: var(--link); border-bottom: 1px solid var(--line); padding-bottom: 8px; }
.panel h3 { margin: 14px 0 6px; font-size: 13px; color: var(--sel); display: flex; justify-content: space-between; }
.panel h3 span { color: var(--dim); font-weight: normal; font-family: ui-monospace, Menlo, monospace; }
canvas { image-rendering: pixelated; image-rendering: crisp-edges; }
.seg { display: flex; gap: 6px; flex-wrap: wrap; }
.seg button, .btn { background: #34374a; color: var(--text); border: 1px solid #4a4e63; border-radius: 6px;
  padding: 6px 10px; cursor: pointer; font: inherit; }
.seg button:hover, .btn:hover { border-color: #8a8fa8; }
.seg button.on { background: #24452a; border-color: var(--sel); color: #b9f0bc; }
.btn.primary { background: #5a4520; border-color: var(--accent); }
.parts { display: grid; gap: 5px; }
.parts.c4 { grid-template-columns: repeat(4, 1fr); }
.parts.c8 { grid-template-columns: repeat(8, 1fr); }
.part { position: relative; background: var(--panel2); border: 2px solid transparent; border-radius: 6px;
  padding: 3px; cursor: pointer; display: flex; flex-direction: column; align-items: center; }
.part:hover { border-color: #666b80; }
.part.on { border-color: var(--sel); background: #213025; }
.part canvas { width: 100%; height: auto; display: block;
  background: repeating-conic-gradient(#30323d 0 25%, #282a33 0 50%) 0 0 / 8px 8px; }
.part .n { font-size: 11px; color: var(--dim); font-family: ui-monospace, Menlo, monospace; line-height: 1.4; }
.part .u { position: absolute; top: 2px; right: 3px; font-size: 10px; color: var(--accent); }
.part .u.zero { color: #5c5d66; }
.center { display: flex; flex-direction: column; align-items: center; }
#view { margin-bottom: 10px; }
#face { border: 3px solid #4a4e63; border-radius: 6px; background: #000; max-width: 100%; height: auto; }
.code { margin-top: 14px; font-family: ui-monospace, Menlo, monospace; font-size: 28px; color: var(--accent);
  display: flex; align-items: center; gap: 8px; }
.code input { width: 6.2em; font: inherit; color: var(--accent); background: var(--panel2); border: 1px solid var(--line);
  border-radius: 6px; padding: 2px 8px; text-transform: uppercase; }
.code input.bad { border-color: #c55; }
.bits { margin-top: 6px; font-family: ui-monospace, Menlo, monospace; font-size: 13px; color: var(--dim); text-align: center; }
.bits b { font-weight: normal; padding: 0 1px; }
.bits .t { color: #e6a35f; } .bits .h { color: #7cc4e6; } .bits .bo { color: #c79be6; }
.bits .e { color: #8fd18f; } .bits .m { color: #e68f8f; }
.who { margin-top: 10px; font-size: 16px; min-height: 1.5em; text-align: center; }
.who a { color: var(--link); cursor: pointer; }
.who .none { color: var(--dim); font-size: 14px; }
.share .none { color: var(--dim); }
.controls { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; margin-top: 14px; }
.bgrow { margin-top: 14px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; justify-content: center; }
.bgrow .lbl { color: var(--dim); margin-right: 4px; }
.bgrow button { padding: 2px; border: 2px solid transparent; background: none; border-radius: 5px; cursor: pointer; }
.bgrow button.on { border-color: var(--sel); }
.bgrow button canvas { width: 32px; height: 40px; display: block; }
.bgrow button.auto { color: var(--text); background: #34374a; padding: 6px 8px; border-color: #4a4e63; }
.bgrow button.auto.on { border-color: var(--sel); background: #24452a; }
table.info { width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 12px; }
table.info th, table.info td { padding: 4px 8px; border-bottom: 1px solid var(--line); text-align: left; white-space: nowrap; }
table.info th { color: var(--dim); font-weight: normal; }
table.info td.mono { font-family: ui-monospace, Menlo, monospace; }
.legend { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: -1px; }
.share { margin-top: 12px; width: 100%; font-size: 12px; }
.share div { margin: 4px 0; line-height: 1.8; }
.share .k { color: var(--dim); display: inline-block; width: 4.5em; }
.chip { display: inline-block; margin: 0 4px 0 0; color: var(--link); cursor: pointer; }
.chip:hover { text-decoration: underline; }
.list-tools { display: flex; gap: 6px; margin-bottom: 8px; flex-wrap: wrap; }
.list-tools input { flex: 1; min-width: 120px; font: inherit; color: var(--text); background: var(--panel2);
  border: 1px solid var(--line); border-radius: 6px; padding: 5px 8px; }
.list-tools .seg button { padding: 4px 8px; }
#count { color: var(--dim); font-size: 12px; margin-bottom: 6px; }
#list { max-height: 900px; overflow-y: auto; background: var(--panel2); border-radius: 8px; padding: 6px; }
.gen { display: flex; align-items: center; gap: 8px; padding: 4px 6px; border-radius: 5px; cursor: pointer; }
.gen:hover { background: #2e303c; }
.gen.on { background: #24452a; outline: 1px solid var(--sel); }
.gen canvas { width: 32px; height: 40px; flex: none; }
.gen .nm { flex: 1; min-width: 0; }
.gen .nm small { display: block; color: var(--dim); font-size: 11px; }
.gen .cd { font-family: ui-monospace, Menlo, monospace; font-size: 12px; color: var(--dim); text-align: right; }
#tip { position: fixed; z-index: 10; display: none; pointer-events: none; background: #111217; border: 1px solid #666b80;
  border-radius: 8px; padding: 6px; text-align: center; font-size: 12px; color: var(--dim); }
#tip canvas { width: 128px; height: 160px; display: block; margin-bottom: 4px; }
.note { margin-top: 16px; color: var(--dim); font-size: 12px; line-height: 1.6; max-width: 560px; }
@media (max-width: 1150px) { .wrap { grid-template-columns: minmax(0, 1fr); } #list { max-height: 480px; } }
</style>
</head>
<body>
<h1>大眾臉探索器<small>源平合戦（KOEI, 1994）Montage 組合頭像</small></h1>
<div id="tip"><canvas width="64" height="80"></canvas><div></div></div>
<div class="wrap">
  <div class="panel">
    <h2>部件</h2>
    <h3>類型 <span>bit 15–14</span></h3>
    <div class="seg" id="types"></div>
    <h3>頭部 <span>bit 13–11</span></h3><div class="parts c4" id="p-head"></div>
    <h3>身體 <span>bit 10–8</span></h3><div class="parts c4" id="p-body"></div>
    <h3>眼 <span>bit 7–4</span></h3><div class="parts c4" id="p-eyes"></div>
    <h3>口 <span>bit 3–0</span></h3><div class="parts c4" id="p-mouth"></div>
  </div>

  <div class="panel center">
    <h2 style="align-self: stretch">頭像預覽</h2>
    <div class="seg" id="view"><button data-v="0">頭像 64×80</button><button data-v="1">半身像 128×160</button><button id="grid" class="on">格線</button></div>
    <canvas id="face" width="384" height="480"></canvas>
    <div class="code">0x<input id="code" maxlength="4" spellcheck="false" title="輸入頭像碼（4000–FFFF）後按 Enter"></div>
    <div class="bits" id="bits"></div>
    <div class="who" id="who"></div>
    <div class="bgrow" id="bgs"><span class="lbl">背景</span></div>
    <div class="controls">
      <button class="btn" id="rand">隨機組合</button>
      <button class="btn" id="randgen">隨機武將</button>
      <button class="btn primary" id="dl">下載頭像</button>
      <button class="btn primary" id="dlfull">下載半身像（去背）</button>
    </div>
    <table class="info" id="info"></table>
    <div class="share" id="share"></div>
    <div class="note">畫的順序是身體 → 頭部 → 眼 → 口，各依自己的 mask 疊在 128×160 緩衝區上，遊戲只顯示其中 64×80 的窗；
      沒被任何零件蓋到的地方露出 Haikei.gp 背景，遊戲用 (武將編號 ÷ 2) mod 5 決定是哪一張。部件右上角數字＝遊戲中使用這個部件的武將數。</div>
  </div>

  <div class="panel">
    <h2>遊戲中的武將</h2>
    <div class="list-tools">
      <input id="q" placeholder="姓名、編號或頭像碼">
      <div class="seg" id="ltypes"></div>
    </div>
    <div id="count"></div>
    <div id="list"></div>
  </div>
</div>

<script>
const D = __DATA__;
const T = 16;                                   // transparent pixel value
const LAYERS = ['body', 'head', 'eyes', 'mouth']; // drawing order
const UI = [['head', '頭部', 8], ['body', '身體', 8], ['eyes', '眼', 16], ['mouth', '口', 16]];
const TYPE_NAME = {1: '大鎧（戴兜）', 2: '鎧', 3: '直垂／狩衣'};
const COLORS = {body: '#c79be6', head: '#7cc4e6', eyes: '#8fd18f', mouth: '#e68f8f'};
const unb64 = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
const BG = unb64(D.backgrounds);
const TYPES = D.types.map(t => {
  const layers = {};
  for (const k of LAYERS) layers[k] = {...t.layers[k], parts: t.layers[k].parts.map(unb64)};
  return {...t, layers};
});
const GENERALS = D.generals.map(([id, name, kana, code]) => ({id, name, kana, code}));
const BY_CODE = new Map(GENERALS.map(g => [g.code, g]));

const toCode = s => (s.type << 14) | (s.head << 11) | (s.body << 8) | (s.eyes << 4) | s.mouth;
const fromCode = c => ({type: c >> 14, head: c >> 11 & 7, body: c >> 8 & 7, eyes: c >> 4 & 15, mouth: c & 15});
const hex = c => c.toString(16).toUpperCase().padStart(4, '0');

// Same as dump_gfx.render_face: 128x160 buffer, TRANSPARENT where nothing is drawn.
function composeFull(s) {
  const t = TYPES[s.type - 1], out = new Uint8Array(128 * 160).fill(T);
  for (const k of LAYERS) {
    const L = t.layers[k], px = L.parts[s[k]];
    for (let y = 0; y < L.h; y++) for (let x = 0; x < L.w; x++) {
      const v = px[y * L.w + x];
      if (v !== T && L.x + x < 128 && L.y + y < 160) out[(L.y + y) * 128 + L.x + x] = v;
    }
  }
  return out;
}
// The 64x80 in-game window over Haikei background `bg`.
function composeWindow(s, bg) {
  const full = composeFull(s), [cx, cy] = TYPES[s.type - 1].window, win = new Uint8Array(64 * 80);
  for (let y = 0; y < 80; y++) for (let x = 0; x < 64; x++) {
    const v = full[(cy + y) * 128 + cx + x];
    win[y * 64 + x] = v === T ? BG[(bg * 80 + y) * 64 + x] : v;
  }
  return win;
}
const autoBg = id => (id >> 1) % 5;
function toImage(px, w, h) {
  const img = new ImageData(w, h);
  for (let i = 0; i < w * h; i++) {
    const v = px[i];
    if (v === T) continue;
    const c = D.palette[v];
    img.data.set([c[0], c[1], c[2], 255], i * 4);
  }
  return img;
}
function paint(canvas, px, w, h) {
  canvas.width = w; canvas.height = h;
  canvas.getContext('2d').putImageData(toImage(px, w, h), 0, 0);
}
function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
}

let S = {type: 1, head: 0, body: 0, eyes: 0, mouth: 0};
let bgMode = 'auto';          // 'auto' or 0..4
let showBuf = false, showGrid = true, spareBg = 0;  // spareBg: auto mode, code used by nobody
let listType = 0;
const $ = id => document.getElementById(id);

function bgFor(s) {
  if (bgMode !== 'auto') return bgMode;
  const g = BY_CODE.get(toCode(s));
  return g ? autoBg(g.id) : spareBg;
}
function usage(type, layer, i) {
  return GENERALS.filter(g => { const p = fromCode(g.code); return p.type === type && p[layer] === i; });
}

// ---------------------------------------------------------------- UI
function buildTypes() {
  for (const t of [1, 2, 3]) {
    const b = el('button', '', `${t} ${TYPE_NAME[t]}`);
    b.dataset.t = t;
    b.onclick = () => set({type: t});
    hover(b, () => ({...S, type: t}), `類型 ${t}`);
    $('types').append(b);
  }
  const all = el('button', 'on', '全部'); all.dataset.t = 0;
  $('ltypes').append(all);
  for (const t of [1, 2, 3]) { const b = el('button', '', String(t)); b.dataset.t = t; $('ltypes').append(b); }
  for (const b of $('ltypes').children) b.onclick = () => {
    listType = +b.dataset.t;
    for (const x of $('ltypes').children) x.classList.toggle('on', x === b);
    buildList();
  };
}
function buildParts() {
  const t = TYPES[S.type - 1];
  for (const [k, label, n] of UI) {
    const box = $('p-' + k);
    box.innerHTML = '';
    const L = t.layers[k];
    for (let i = 0; i < n; i++) {
      const d = el('div', 'part');
      const c = el('canvas');
      paint(c, L.parts[i], L.w, L.h);
      const u = usage(S.type, k, i).length;
      d.append(c, el('span', 'n', String(i)), el('span', 'u' + (u ? '' : ' zero'), String(u)));
      d.dataset.i = i;
      d.onclick = () => set({[k]: i});
      hover(d, () => ({...S, [k]: i}), `${label} ${i}`);
      box.append(d);
    }
  }
}
function buildBgs() {
  const a = el('button', 'auto', '依武將');
  a.title = '(武將編號 ÷ 2) mod 5；沒有武將用這個頭像碼時用 0';
  a.onclick = () => { bgMode = 'auto'; render(); };
  $('bgs').append(a);
  for (let b = 0; b < 5; b++) {
    const btn = el('button');
    const c = el('canvas');
    paint(c, BG.subarray(b * 5120, (b + 1) * 5120), 64, 80);
    btn.append(c);
    btn.title = ['綠野河川', '藍色山影', '淺藍瀑布', '岩壁', '雲天'][b] + `（${b}）`;
    btn.onclick = () => { bgMode = b; render(); };
    $('bgs').append(btn);
  }
}
function buildList() {
  const q = $('q').value.trim().toLowerCase();
  const box = $('list');
  box.innerHTML = '';
  let n = 0;
  for (const g of GENERALS) {
    const p = fromCode(g.code);
    if (listType && p.type !== listType) continue;
    if (q && !(g.name.includes(q) || String(g.id) === q || hex(g.code).toLowerCase().includes(q.replace(/^0x/, '')))) continue;
    const d = el('div', 'gen');
    d.dataset.code = g.code;
    const c = el('canvas');
    paint(c, composeWindow(p, autoBg(g.id)), 64, 80);
    d.append(c, el('div', 'nm', `${g.name}<small>#${g.id}　${g.kana}</small>`),
             el('div', 'cd', `0x${hex(g.code)}<br>類型 ${p.type}`));
    d.onclick = () => { bgMode = 'auto'; set(p); };
    box.append(d);
    n++;
  }
  $('count').textContent = `${n} / ${GENERALS.length} 位使用組合頭像的武將`;
  markList();
}
function markList() {
  const code = toCode(S);
  for (const d of $('list').children) d.classList.toggle('on', +d.dataset.code === code);
}

const tip = $('tip');
function hover(node, state, label) {
  node.addEventListener('mouseenter', () => {
    const s = state(), g = BY_CODE.get(toCode(s));
    paint(tip.querySelector('canvas'), composeWindow(s, bgMode === 'auto' ? (g ? autoBg(g.id) : 0) : bgMode), 64, 80);
    tip.querySelector('div').textContent = `${label} → 0x${hex(toCode(s))}` + (g ? `（${g.name}）` : '');
    tip.style.display = 'block';
  });
  node.addEventListener('mousemove', e => {
    const r = tip.getBoundingClientRect();
    tip.style.left = Math.min(e.clientX + 16, innerWidth - r.width - 8) + 'px';
    tip.style.top = Math.min(e.clientY + 16, innerHeight - r.height - 8) + 'px';
  });
  node.addEventListener('mouseleave', () => { tip.style.display = 'none'; });
}

function set(patch) {
  const typeChanged = patch.type && patch.type !== S.type;
  S = {...S, ...patch};
  if (typeChanged) buildParts();
  render();
}

function drawFace() {
  const cv = $('face'), ctx = cv.getContext('2d'), bg = bgFor(S);
  const off = document.createElement('canvas');
  if (!showBuf) {
    paint(off, composeWindow(S, bg), 64, 80);
    cv.width = 384; cv.height = 480;
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(off, 0, 0, 384, 480);
    return;
  }
  // full 128x160 buffer on a checkerboard, no portrait background
  const t = TYPES[S.type - 1], [cx, cy] = t.window;
  paint(off, composeFull(S), 128, 160);
  const k = 3;
  cv.width = 128 * k; cv.height = 160 * k;
  for (let y = 0; y < 160; y += 4) for (let x = 0; x < 128; x += 4) {
    ctx.fillStyle = (x + y) / 4 % 2 ? '#2a2c35' : '#22242c';
    ctx.fillRect(x * k, y * k, 4 * k, 4 * k);
  }
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(off, 0, 0, 128 * k, 160 * k);
  if (!showGrid) return;
  ctx.lineWidth = 2;
  for (const name of LAYERS) {
    const L = t.layers[name];
    ctx.strokeStyle = COLORS[name];
    ctx.strokeRect(L.x * k + 1, L.y * k + 1, Math.min(L.w, 128 - L.x) * k - 2, Math.min(L.h, 160 - L.y) * k - 2);
  }
  ctx.setLineDash([6, 4]);
  ctx.strokeStyle = '#fff';
  ctx.strokeRect(cx * k, cy * k, 64 * k, 80 * k);
  ctx.setLineDash([]);
}

function render() {
  const code = toCode(S), t = TYPES[S.type - 1], g = BY_CODE.get(code), bg = bgFor(S);
  drawFace();
  const inp = $('code');
  if (document.activeElement !== inp) inp.value = hex(code);
  inp.classList.remove('bad');
  const b = code.toString(2).padStart(16, '0');
  $('bits').innerHTML = `<b class="t">${b.slice(0, 2)}</b> <b class="h">${b.slice(2, 5)}</b> <b class="bo">${b.slice(5, 8)}</b> ` +
    `<b class="e">${b.slice(8, 12)}</b> <b class="m">${b.slice(12)}</b><br>` +
    `<b class="t">類型 ${S.type}</b>　<b class="h">頭 ${S.head}</b>　<b class="bo">身 ${S.body}</b>　<b class="e">眼 ${S.eyes}</b>　<b class="m">口 ${S.mouth}</b>`;
  $('who').innerHTML = g ? `<a>${g.name}</a>（#${g.id}，背景 ${autoBg(g.id)}）`
                         : '<span class="none">遊戲中沒有武將使用這個組合</span>';
  if (g) $('who').querySelector('a').onclick = () => { $('q').value = g.name; buildList(); };

  for (const x of $('types').children) x.classList.toggle('on', +x.dataset.t === S.type);
  for (const [k] of UI) for (const d of $('p-' + k).children) d.classList.toggle('on', +d.dataset.i === S[k]);
  const bgb = $('bgs').querySelectorAll('button');
  bgb[0].classList.toggle('on', bgMode === 'auto');
  for (let i = 0; i < 5; i++) bgb[i + 1].classList.toggle('on', bgMode !== 'auto' && bgMode === i);
  for (const x of $('view').querySelectorAll('[data-v]')) x.classList.toggle('on', +x.dataset.v === +showBuf);
  $('grid').style.display = showBuf ? '' : 'none';
  $('grid').classList.toggle('on', showGrid);

  // part table: where each layer comes from and where it goes
  let rows = '<tr><th>部件</th><th>檔案 offset</th><th>尺寸</th><th>緩衝區位置</th><th>使用數</th></tr>';
  for (const [k, label] of UI) {
    const L = t.layers[k];
    rows += `<tr><td><span class="legend" style="background:${COLORS[k]}"></span>${label} ${S[k]}</td>` +
      `<td class="mono">${L.file} 0x${(L.offset + S[k] * L.step).toString(16).toUpperCase()}</td>` +
      `<td class="mono">${L.w}×${L.h}</td><td class="mono">(${L.x}, ${L.y})</td><td class="mono">${usage(S.type, k, S[k]).length}</td></tr>`;
  }
  rows += `<tr><td>窗口</td><td class="mono">—</td><td class="mono">64×80</td><td class="mono">(${t.window[0]}, ${t.window[1]})</td><td class="mono">背景 ${bg}</td></tr>`;
  $('info').innerHTML = rows;

  // generals that share a part with the current face
  const share = $('share');
  share.innerHTML = '';
  for (const [k, label] of UI) {
    const gs = usage(S.type, k, S[k]);
    const row = el('div', '', `<span class="k">同${label}</span>`);
    if (!gs.length) row.append(el('span', 'none', '—'));
    for (const x of gs) {
      const c = el('span', 'chip', x.name);
      c.onclick = () => { bgMode = 'auto'; set(fromCode(x.code)); };
      hover(c, () => fromCode(x.code), x.name);
      row.append(c);
    }
    share.append(row);
  }
  markList();
  history.replaceState(null, '', '#' + hex(code));
}

$('code').addEventListener('keydown', e => {
  if (e.key !== 'Enter') return;
  const c = parseInt(e.target.value.replace(/^0x/i, ''), 16);
  if (!(c >= 0x4000 && c <= 0xFFFF)) { e.target.classList.add('bad'); return; }
  set(fromCode(c));
  e.target.blur();
});
$('code').addEventListener('blur', () => render());
$('rand').onclick = () => {
  const r = n => Math.floor(Math.random() * n);
  spareBg = r(5);
  set({type: 1 + r(3), head: r(8), body: r(8), eyes: r(16), mouth: r(16)});
};
$('randgen').onclick = () => { bgMode = 'auto'; set(fromCode(GENERALS[Math.floor(Math.random() * GENERALS.length)].code)); };
for (const x of $('view').querySelectorAll('[data-v]')) x.onclick = () => { showBuf = x.dataset.v === '1'; render(); };
$('grid').onclick = () => { showGrid = !showGrid; render(); };
function download(name, canvas) {
  const a = document.createElement('a');
  a.download = name;
  a.href = canvas.toDataURL('image/png');
  a.click();
}
$('dl').onclick = () => {
  const off = document.createElement('canvas'), cv = document.createElement('canvas');
  paint(off, composeWindow(S, bgFor(S)), 64, 80);
  cv.width = 384; cv.height = 480;
  const ctx = cv.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(off, 0, 0, 384, 480);
  download(`face_${hex(toCode(S))}.png`, cv);
};
// transparent 128x160 at native size
$('dlfull').onclick = () => {
  const cv = document.createElement('canvas');
  paint(cv, composeFull(S), 128, 160);
  download(`face_${hex(toCode(S))}_full.png`, cv);
};
$('q').addEventListener('input', buildList);

buildTypes();
buildBgs();
const h = parseInt(location.hash.slice(1), 16);
const start = h >= 0x4000 && h <= 0xFFFF ? h : GENERALS[Math.floor(Math.random() * GENERALS.length)].code;
S = fromCode(start);
buildParts();
buildList();
render();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
