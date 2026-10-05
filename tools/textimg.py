#!/usr/bin/env python3
"""Redraw the text images of Opendat.gp / Enddat.gp in Chinese.

The opening narration, the 平家物語 calligraphy and the ending narration
are NPK016 pictures, not text. This tool renders the translations from
translation/images.tsv with ImageMagick, maps them onto the original
chunk's colour indices and writes each new chunk back into its original
slot, so every chunk keeps its offset:

    python3 tools/textimg.py build/GENPEI [--preview DIR]

Open.exe/End.exe hold u32 offset and size tables for these chunks and
read the 8-byte (x, y, w, h) placement record that some chunks carry at
`next chunk - 8` separately. So a slot is rewritten as: new header +
payload, zero padding, the original trailing record. The decoder stops
after width*height pixels, so the padding is never decoded. A new chunk
larger than its slot is an error.

images.tsv columns: file, chunk, style, text.
  style  narr   ruled vertical narration (white fill, outlined), 24 px
         brush  calligraphy, one column, glyphs spread over the height
  text   columns separated by "/", laid out right to left
"""
from __future__ import annotations

import csv
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gfx  # noqa: E402
import npk  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TSV = ROOT / 'translation/images.tsv'
FONT = {
    'narr': Path.home() / 'Library/Fonts/SourceHanSerif-VF.otf.ttc',
    'brush': Path('/System/Library/AssetsV2/com_apple_MobileAsset_Font7/'
                  '54a2ad3dac6cac875ad675d7d273dc425010a877.asset/AssetData/Kaiti.ttc'),
}
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


def layout(style: str, text: str, w: int, h: int) -> tuple[list[tuple[int, int, str]], int]:
    cols = [c.translate(VERT) for c in text.split('/')]
    if style == 'narr':
        size, pitch_x, pitch_y = 24, 32, 24
        assert len(cols) * pitch_x <= w + 8, f'{len(cols)} columns do not fit {w}px'
        x0 = w - (w - len(cols) * pitch_x) // 2 - pitch_x + (pitch_x - size) // 2
        cells = []
        for i, col in enumerate(cols):
            assert len(col) * pitch_y <= h, f'column too long for {h}px: {col}'
            cells += [(x0 - i * pitch_x, j * pitch_y, ch) for j, ch in enumerate(col)]
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
        # original: thin white strokes (index 7) inside a pink rim (index 14)
        fill, rim = 7, 14
        out = bytearray(w * h)
        for y in range(h):
            for x in range(w):
                i = y * w + x
                if on[i]:
                    out[i] = fill
                elif any(on[yy * w + xx] for yy in range(max(0, y - 1), min(h, y + 2))
                         for xx in range(max(0, x - 1), min(w, x + 2))):
                    out[i] = rim
        return bytes(out)
    main = ranked[0]
    edge = ranked[1] if len(ranked) > 1 else main
    return bytes(main if c >= 112 else edge if c >= 48 else 0 for c in cov)


def main(argv: list[str]) -> None:
    build = Path(argv[0])
    preview = Path(argv[argv.index('--preview') + 1]) if '--preview' in argv else None
    with TSV.open(encoding='utf-8') as f:
        rows = list(csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE, quotechar=None))
    for name in dict.fromkeys(r['file'] for r in rows):
        src = (ROOT / 'game/GENPEI' / name).read_bytes()
        data = bytearray(src)
        chunks = npk.scan_archive(src)
        pals = gfx.load_palettes(ROOT / 'game/GENPEI' / name, 0, chunks[0].offset // 48)
        for r in (r for r in rows if r['file'] == name):
            c = chunks[int(r['chunk'])]
            orig = npk.decode(c)
            cells, size = layout(r['style'], r['text'], c.width, c.height)
            cov = render(cells, c.width, c.height, FONT[r['style']], size)
            px = colorize(r['style'], cov, c.width, c.height, orig)
            new = npk.build_chunk(c.width, c.height, px, c.palette, c.planes, (c.canvas_w, c.canvas_h))
            room = c.size - len(c.trailer)
            if len(new) > room:
                sys.exit(f'{name}#{c.index}: {len(new)} bytes > slot {room}')
            data[c.offset:c.offset + c.size] = new + bytes(room - len(new)) + c.trailer
            print(f'{name}#{c.index}: {len(new)}/{room} bytes')
            if preview:
                # palette: the one the dump picked as most plausible
                gfx.write_png(preview / f'{Path(name).stem.lower()}_{c.index:03d}.png',
                              c.width, c.height, px, pals[best_pal(orig, pals)], scale=2)
        (build / name).write_bytes(data)


def best_pal(px: bytes, pals: list[gfx.Palette]) -> int:
    used = set(px) - {0}
    return max(range(len(pals)), key=lambda i: sum(sum(pals[i][u]) for u in used))


if __name__ == '__main__':
    main(sys.argv[1:])
