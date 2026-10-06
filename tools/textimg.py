#!/usr/bin/env python3
"""Redraw the text images of Opendat.gp / Enddat.gp / Maincmd2.gp in Chinese.

The opening narration, the 平家物語 calligraphy and the ending narration
are NPK016 pictures, not text. This tool renders the translations from
translation/images.tsv with ImageMagick, maps them onto the original
chunk's colour indices and writes each new chunk back into its original
slot, so every chunk keeps its offset. The narration uses the jiskan
24x24 bitmap font (tools/fonts/), the calligraphy macOS Kaiti:

    python3 tools/textimg.py build/GENPEI [--preview DIR]

Open.exe/End.exe hold u32 offset and size tables for these chunks and
read the 8-byte (x, y, w, h) placement record that some chunks carry at
`next chunk - 8` separately. So a slot is rewritten as: new header +
payload, zero padding, the original trailing record. The decoder stops
after width*height pixels, so the padding is never decoded. A new chunk
larger than its slot is an error.

Maincmd2.gp's defeat calligraphy is not NPK: four uncompressed 4bpp
48x358 columns (rightmost first), rewritten in place; `chunk` is the
column number 1-4.

images.tsv columns: file, chunk, style, text.
  style  narr     vertical narration (white fill, 2 px outline), 24 px bitmap
                  glyphs on a 26 px pitch, 32 px columns
         brush    calligraphy in Kaiti, one column, glyphs spread over the height
         glyphs   one image per glyph from translation/calligraphy/<file>/
                  (`<chunk>-<pos>-<char>[_...].png`, black on white), sized and
                  offset by layout.json there (tools/calligraphy_editor.py);
                  white core inside a 1 px dark rim, as the original
         ink      glyph images as above, coloured like the ending scroll
                  (Enddat 72-77): dark ink fading out through INK_RAMP
  text   columns separated by "/", laid out right to left
"""
from __future__ import annotations

import csv
import json
import functools
import gzip
import math
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import dump_gfx  # noqa: E402
import gfx  # noqa: E402
import npk  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TSV = ROOT / 'translation/images.tsv'


def find_font(*patterns: str) -> Path:
    """First file matching any glob pattern (absolute, ~ expanded)."""
    for pat in patterns:
        hits = sorted(Path('/').glob(str(Path(pat).expanduser()).lstrip('/')))
        if hits:
            return hits[-1]
    sys.exit(f'font not found: {patterns}')


# macOS Kaiti, a downloadable system font whose asset path differs per machine
BRUSH_FONT = find_font('/System/Library/AssetsV2/com_apple_MobileAsset_Font*/*.asset/AssetData/Kaiti.ttc')
BITMAP_FONT = ROOT / 'tools/fonts/jiskan24-fullwidth.bdf.gz'
# ending scroll ink, darkest to lightest (Enddat prefix palette 10), and the
# coverage (0..255) each shade starts at
INK_RAMP = [14, 11, 15, 9, 12, 8]
INK_LEVELS = [128, 100, 80, 60, 40, 24]
# uncompressed calligraphy columns: file -> (offset, width, height), 4bpp (formats.md §10.6)
RAW_COLUMNS = {'Maincmd2.gp': (0x44433, 48, 358)}
# horizontal punctuation -> vertical presentation forms
VERT = str.maketrans({'，': '︐', '、': '︑', '。': '︒', '…': '︙', '：': '︓',
                      '！': '︕', '？': '︖', '「': '﹁', '」': '﹂'})


SS = 4  # supersampling factor; box-filtered down, so thin strokes survive


def render(chars: list[tuple[int, int, str]], w: int, h: int, font: Path, size: int) -> list[int]:
    """Draw (x, y, char) cells with ImageMagick; return 0..255 coverage."""
    cmd = ['magick', '-size', f'{w * SS}x{h * SS}', 'xc:black', '-fill', 'white',
           '-font', str(font), '-pointsize', str(size * SS), '-gravity', 'NorthWest']
    for x, y, c in chars:
        cmd += ['-annotate', f'+{x * SS}+{y * SS}', c]
    cmd += ['-filter', 'box', '-resize', f'{w}x{h}!', '-colorspace', 'gray', '-depth', '8', 'gray:-']
    return list(subprocess.run(cmd, check=True, capture_output=True).stdout)


# starting (scale %, dx) before layout.json; same as calligraphy_editor.py.
# The 、 and 。 images are the original Maincmd2 marks: at 7 % / 12 % of a
# 44 px base they come out at their native 3 and 5 px, right of centre.
DEFAULTS = {'之': (50, 0), '、': (7, 12), '。': (12, 11)}


def spread(heights: list[int], top: int, span: float) -> list[int]:
    """Gaps that put the glyphs from `top` to `top + span` with equal spacing.

    gaps[0] is the space above the first glyph, gaps[k] the space between
    glyph k-1 and glyph k. Same rounding as calligraphy_editor.py.
    """
    n = len(heights)
    g = (span - sum(heights)) / (n - 1) if n > 1 else 0
    ys = [math.floor(top + sum(heights[:k]) + k * g + 0.5) for k in range(n)]
    return [ys[0]] + [ys[k] - ys[k - 1] - heights[k - 1] for k in range(1, n)]


@functools.cache
def glyph_cells(folder: Path, chunk: int, text: str, w: int, h: int) -> list[tuple[int, int, Path, int, int]]:
    """(x, y, image, width, height) per glyph; same layout as calligraphy_editor.py.

    layout.json gives each glyph a scale (percent of the base width: the
    column width less 4 px, or a fixed width), dx (from the column centre)
    and gap (px of space above it: from the column top for the first glyph,
    from the glyph above otherwise). Glyphs missing from layout.json get the
    DEFAULTS size and the whole column is spread evenly over 97 % of its
    height. Boxes are kept inside the column.
    """
    params = json.loads((folder / 'layout.json').read_text()) if (folder / 'layout.json').exists() else {}
    base = w - 4 if params.get('base', 'column') == 'column' else int(params['base'])
    files, boxes, dxs, gaps = [], [], [], []
    for k, ch in enumerate(text, 1):
        (f,) = folder.glob(f'{chunk}-{k}-*.png')
        p = params.get('glyphs', {}).get(f'{chunk}-{k}', {})
        scale, dx = DEFAULTS.get(ch, (100, 0))
        r = p.get('scale', scale) / 100
        gw, gh = map(int, subprocess.run(['magick', 'identify', '-format', '%w %h', str(f)],
                                         check=True, capture_output=True, text=True).stdout.split())
        files.append(f)
        boxes.append((int(base * r), int(base * r * gh / gw)))
        dxs.append(p.get('dx', dx))
        gaps.append(p.get('gap'))
    if None in gaps:
        gaps = spread([bh for _, bh in boxes], math.floor(h * 0.015 + 0.5), h * 0.97)
    cells, y = [], 0
    for f, (bw, bh), dx, gap in zip(files, boxes, dxs, gaps):
        y += gap
        x = (w - bw) // 2 + dx
        cells.append((min(max(x, 0), max(w - bw, 0)), min(max(y, 0), max(h - bh, 0)), f, bw, bh))
        y += bh
    return cells


def render_glyphs(cells: list[tuple[int, int, Path, int, int]], w: int, h: int) -> list[int]:
    """Draw glyph images (black on white) into their boxes; return 0..255 coverage."""
    cmd = ['magick', '-size', f'{w * SS}x{h * SS}', 'xc:black']
    for x, y, f, bw, bh in cells:
        cmd += ['(', str(f), '-colorspace', 'gray', '-negate', '-resize', f'{bw * SS}x{bh * SS}!', ')',
                '-geometry', f'+{x * SS}+{y * SS}', '-compose', 'lighten', '-composite']
    cmd += ['-filter', 'box', '-resize', f'{w}x{h}!', '-colorspace', 'gray', '-depth', '8', 'gray:-']
    return list(subprocess.run(cmd, check=True, capture_output=True).stdout)


def load_bdf(path: Path) -> dict[int, list[int]]:
    """24x24 BDF glyphs as {codepoint: 24 row bitmasks, bit 23 = leftmost}."""
    glyphs, cp, rows = {}, None, None
    with gzip.open(path, 'rt', encoding='latin-1') as f:
        for line in f:
            key = line.split()[0] if line.strip() else ''
            if key == 'ENCODING':
                cp = int(line.split()[1])
            elif key == 'BITMAP':
                rows = []
            elif key == 'ENDCHAR':
                glyphs[cp], rows = rows, None
            elif rows is not None:
                rows.append(int(key, 16))
    return glyphs


# the font has no vertical forms: shift the horizontal comma/full stop from
# the bottom-left to the top-right of the cell, turn the ellipsis upright
SHIFTED = {'︐': '，', '︑': '、', '︒': '。'}


def bitmap_glyph(glyphs: dict[int, list[int]], ch: str) -> list[list[bool]]:
    base = SHIFTED.get(ch, '…' if ch == '︙' else ch)
    if ord(base) not in glyphs:
        sys.exit(f'{ch!r} is not in {BITMAP_FONT.name}')
    grid = [[bool(r >> (23 - x) & 1) for x in range(24)] for r in glyphs[ord(base)]]
    if ch in SHIFTED:
        return [[0 <= y + 13 < 24 and 0 <= x - 13 < 24 and grid[y + 13][x - 13] for x in range(24)]
                for y in range(24)]
    if ch == '︙':
        return [[grid[23 - x][y] for x in range(24)] for y in range(24)]
    return grid


def render_bitmap(chars: list[tuple[int, int, str]], w: int, h: int) -> list[int]:
    """Draw (x, y, char) cells with the bitmap font; return 0/255 coverage."""
    glyphs = load_bdf(BITMAP_FONT)
    cov = [0] * (w * h)
    for x0, y0, ch in chars:
        for y, row in enumerate(bitmap_glyph(glyphs, ch)):
            for x, on in enumerate(row):
                if on:
                    cov[(y0 + y) * w + x0 + x] = 255
    return cov


def layout(style: str, text: str, w: int, h: int) -> tuple[list[tuple[int, int, str]], int]:
    cols = [c.translate(VERT) for c in text.split('/')]
    if style == 'narr':
        # the original glyphs ink 22 px on a 24 px pitch; jiskan inks the full
        # 24 px, so a 26 px pitch keeps the same 2 px gap. Top margin as original.
        size, pitch_x, pitch_y, top = 24, 32, 26, 5
        assert len(cols) * pitch_x <= w + 8, f'{len(cols)} columns do not fit {w}px'
        x0 = w - (w - len(cols) * pitch_x) // 2 - pitch_x + (pitch_x - size) // 2
        cells = []
        for i, col in enumerate(cols):
            assert top + (len(col) - 1) * pitch_y + size <= h, f'column too long for {h}px: {col}'
            cells += [(x0 - i * pitch_x, top + j * pitch_y, ch) for j, ch in enumerate(col)]
        return cells, size
    (col,) = cols
    size = min(w - 4, h // len(col))
    step = h / len(col)
    return [((w - size) // 2, int(j * step + (step - size) / 2), ch) for j, ch in enumerate(col)], size


def colorize(style: str, cov: list[int], w: int, h: int, orig: bytes) -> bytes:
    """Map coverage to the original picture's text colours."""
    ranked = [i for i, _ in Counter(v for v in orig if v).most_common()]
    on = [c >= 72 for c in cov]
    if style == 'narr':
        # original: white strokes (index 7) inside a 2 px dark rim (index 14)
        # with clipped corners
        fill, rim = 7, 14
        ring = [(dx, dy) for dy in range(-2, 3) for dx in range(-2, 3) if abs(dx) + abs(dy) < 4]
        out = bytearray(w * h)
        for y in range(h):
            for x in range(w):
                i = y * w + x
                if on[i]:
                    out[i] = fill
                elif any(0 <= x + dx < w and 0 <= y + dy < h and on[(y + dy) * w + x + dx]
                         for dx, dy in ring):
                    out[i] = rim
        return bytes(out)
    if style == 'ink':
        return bytes(next((k for k, t in zip(INK_RAMP, INK_LEVELS) if c >= t), 0) for c in cov)
    # the core colour is the one enclosed by ink, not the most frequent one
    # (Opendat 14-17 have more edge pixels than core pixels)
    def enclosed(v: int) -> float:
        inner = [all(orig[(y + dy) * w + x + dx] for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                 for y in range(1, h - 1) for x in range(1, w - 1) if orig[y * w + x] == v]
        return sum(inner) / max(len(inner), 1)
    main, edge = sorted(ranked[:2], key=enclosed, reverse=True) if len(ranked) > 1 else ranked * 2
    if style == 'glyphs':
        # like the original: the core always sits inside a 1 px ring of the edge colour
        core = [c >= 112 for c in cov]
        out = bytearray(w * h)
        for y in range(h):
            for x in range(w):
                i = y * w + x
                if core[i]:
                    out[i] = main
                elif any(0 <= x + dx < w and 0 <= y + dy < h and core[(y + dy) * w + x + dx]
                         for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                    out[i] = edge
        return bytes(out)
    return bytes(main if c >= 112 else edge if c >= 48 else 0 for c in cov)


def main(argv: list[str]) -> None:
    build = Path(argv[0])
    preview = Path(argv[argv.index('--preview') + 1]) if '--preview' in argv else None
    with TSV.open(encoding='utf-8') as f:
        rows = list(csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE, quotechar=None))
    for name in dict.fromkeys(r['file'] for r in rows):
        src = (ROOT / 'game/GENPEI' / name).read_bytes()
        data = bytearray(src)
        if name in RAW_COLUMNS:
            redraw_columns(name, [r for r in rows if r['file'] == name], data, preview)
            (build / name).write_bytes(data)
            continue
        chunks = npk.scan_archive(src)
        pals = gfx.load_palettes(ROOT / 'game/GENPEI' / name, 0, chunks[0].offset // 48)
        for r in (r for r in rows if r['file'] == name):
            c = chunks[int(r['chunk'])]
            orig = npk.decode(c)
            if r['style'] in ('glyphs', 'ink'):
                folder = ROOT / 'translation/calligraphy' / Path(name).stem.lower()
                cov = render_glyphs(glyph_cells(folder, c.index, r['text'], c.width, c.height), c.width, c.height)
            else:
                cells, size = layout(r['style'], r['text'], c.width, c.height)
                if r['style'] == 'narr':
                    cov = render_bitmap(cells, c.width, c.height)
                else:
                    cov = render(cells, c.width, c.height, BRUSH_FONT, size)
            px = colorize(r['style'], cov, c.width, c.height, orig)
            new = npk.build_chunk(c.width, c.height, px, c.palette, c.planes, (c.canvas_w, c.canvas_h))
            room = c.size - len(c.trailer)
            if len(new) > room:
                sys.exit(f'{name}#{c.index}: {len(new)} bytes > slot {room}')
            data[c.offset:c.offset + c.size] = new + bytes(room - len(new)) + c.trailer
            print(f'{name}#{c.index}: {len(new)}/{room} bytes')
            if preview:
                # palette: the one the dump picked as most plausible
                k = dump_gfx.KNOWN_PALETTES.get((name, c.index)) or best_pal(orig, pals)
                gfx.write_png(preview / f'{Path(name).stem.lower()}_{c.index:03d}.png',
                              c.width, c.height, px, pals[k], scale=2)
        (build / name).write_bytes(data)


def redraw_columns(name: str, rows: list[dict], data: bytearray, preview: Path | None) -> None:
    """Rewrite the uncompressed calligraphy columns of RAW_COLUMNS in place."""
    off, w, h = RAW_COLUMNS[name]
    size = w * h // 2
    folder = ROOT / 'translation/calligraphy' / Path(name).stem.lower()
    for r in rows:
        col = int(r['chunk'])
        at = off + (col - 1) * size
        orig = gfx.decode_planar_bytes(data, w, h, 4, offset=at)
        cov = render_glyphs(glyph_cells(folder, col, r['text'], w, h), w, h)
        px = colorize('glyphs', cov, w, h, orig)
        data[at:at + size] = gfx.encode_planar_bytes(px)
        print(f'{name} column {col}: {r["text"]}')
        if preview:
            # the colours of the last frame of the defeat screen
            pal = [(0, 0, 0)] * 16
            pal[7], pal[14] = (0xa2, 0xd3, 0xe3), (0x00, 0x00, 0x30)
            gfx.write_png(preview / f'{Path(name).stem.lower()}_col{col}.png', w, h, px, pal, scale=2)


def best_pal(px: bytes, pals: list[gfx.Palette]) -> int:
    used = set(px) - {0}
    return max(range(len(pals)), key=lambda i: sum(sum(pals[i][u]) for u in used))


if __name__ == '__main__':
    main(sys.argv[1:])
