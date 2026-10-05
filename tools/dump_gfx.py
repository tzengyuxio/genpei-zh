#!/usr/bin/env python3
"""Dump every graphics file of 《源平合戦》 to indexed PNGs.

    python3 tools/dump_gfx.py game/GENPEI build/dump [NAME ...]

NAME limits the run to some files (e.g. `Kaodata Mainmap`). Each file goes
to build/dump/<category>/<stem>/ with one PNG per image, a contact sheet
`_sheet.png` and `index.tsv` (offset, size, palette used, notes).
Masked sprites are written with a transparent 17th palette entry.
Layouts are documented in docs/formats.md section 10.
"""
from __future__ import annotations

import collections
import math
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gfx  # noqa: E402
import npk  # noqa: E402

GAME: Path
OUT: Path
PAL: dict[str, list[gfx.Palette]] = {}


# ---------------------------------------------------------------- helpers

class Dump:
    """Collects the images of one source file and writes them out."""

    def __init__(self, category: str, stem: str):
        self.dir = OUT / category / stem.lower()
        self.stem = stem.lower()
        self.rows: list[list] = []
        self.thumbs: list[tuple[int, int, bytes, gfx.Palette]] = []

    def add(self, name: str, w: int, h: int, px: bytes, pal: gfx.Palette,
            offset: int | str = "", size: int | str = "", palname: str = "",
            note: str = "", sheet: bool = True) -> None:
        gfx.write_png(self.dir / f"{name}.png", w, h, px, pal)
        self.rows.append([name, offset if isinstance(offset, str) else f"0x{offset:06X}",
                          size, w, h, palname, note])
        if sheet:
            self.thumbs.append((w, h, px, pal))

    def close(self, cols: int | None = None) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        with (self.dir / "index.tsv").open("w", encoding="utf-8") as f:
            f.write("name\toffset\tsize\twidth\theight\tpalette\tnote\n")
            for r in self.rows:
                f.write("\t".join(str(v) for v in r) + "\n")
        if len(self.thumbs) > 1:
            # up to 16 distinct palettes share one 256-colour sheet
            pals: list[gfx.Palette] = []
            imgs = []
            for w, h, px, pal in self.thumbs:
                if pal not in pals:
                    pals.append(pal)
                k = pals.index(pal) * 16
                imgs.append((w, h, bytes((v if v < 16 else 0) + k for v in px)))
            if len(pals) > 16:
                imgs = [im for im, t in zip(imgs, self.thumbs) if t[3] == pals[0]]
                pals = pals[:1]
            if cols is None:
                maxw = max(w for w, _, _ in imgs)
                cols = max(1, min(len(imgs), 2000 // (maxw + 2)))
            W, H, px = gfx.sheet(imgs, cols, pad=2, bg=0)
            gfx.write_png(self.dir / "_sheet.png", W, H, px, [c for p in pals for c in p])
        print(f"{self.dir.relative_to(OUT)}: {len(self.rows)} images")


def read(name: str) -> bytes:
    return (GAME / name).read_bytes()


def mainpal(i: int = 0) -> gfx.Palette:
    return PAL["Mainpal"][i]


def planar(data: bytes, off: int, w: int, h: int, bpp: int) -> bytes:
    """Byte-interleaved planes, byte k = bit k (see formats.md §10.1)."""
    return gfx.decode_planar_bytes(data, w, h, bpp, offset=off)


def mask_image(data: bytes, off: int, w: int, h: int) -> bytes:
    """1bpp mask as a picture: opaque = 7 (white), transparent = 0."""
    px = bytearray(w * h)
    for i in range(w * h // 8):
        b = data[off + i]
        for k in range(8):
            if not b & (0x80 >> k):
                px[i * 8 + k] = 7
    return bytes(px)


def frames(d: Dump, data: bytes, label: str, off: int, w: int, h: int, n: int,
           bpp: int, pal: gfx.Palette, palname: str, mask_off: int | None = None,
           note: str = "") -> int:
    """n consecutive planar frames (optionally with n consecutive masks)."""
    fsize = w * h * bpp // 8
    msize = w * h // 8
    for i in range(n):
        px = planar(data, off + i * fsize, w, h, bpp)
        if mask_off is not None:
            px = gfx.apply_mask(px, data, w, h, mask_off + i * msize)
        d.add(f"{label}_{i:03d}", w, h, px, pal, off + i * fsize, fsize, palname, note)
    return off + n * fsize


def masks(d: Dump, data: bytes, label: str, off: int, w: int, h: int, n: int,
          note: str = "") -> int:
    msize = w * h // 8
    for i in range(n):
        d.add(f"{label}_{i:03d}", w, h, mask_image(data, off + i * msize, w, h),
              mainpal(), off + i * msize, msize, "mask", note, sheet=False)
    return off + n * msize


def pick_palette(px: bytes, w: int, h: int, pals: list[gfx.Palette]) -> int:
    """Best guess among embedded palettes: keep the ones that light up the
    most pixels, then prefer the smoothest picture (lowest neighbour
    luminance difference relative to contrast)."""
    cnt = collections.Counter(px)
    total = len(px)

    def cover(p):
        return sum(k for c, k in cnt.items() if c == 0 or p[c] != (0, 0, 0)) / total

    pairs = collections.Counter()
    for y in range(0, h, 2):
        r = px[y * w:(y + 1) * w]
        pairs.update(zip(r, r[1:]))
    npairs = sum(pairs.values()) or 1

    def rough(p):
        lum = [0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2] for c in p]
        mean = sum(lum[c] * k for c, k in cnt.items()) / total
        var = sum((lum[c] - mean) ** 2 * k for c, k in cnt.items()) / total
        if var < 1:
            return math.inf
        nd = sum(abs(lum[a] - lum[b]) * k for (a, b), k in pairs.items()) / npairs
        return nd / math.sqrt(var)

    cv = [cover(p) for p in pals]
    best = max(cv)
    cands = [i for i in range(len(pals)) if cv[i] >= best * 0.97]
    return min(cands, key=lambda i: rough(pals[i]))


# ---------------------------------------------------------------- NPK016

def dump_npk(category: str, name: str, palname: str = "Mainpal[0]",
             note: str = "") -> list[tuple[npk.Chunk, bytes]]:
    data = read(name)
    d = Dump(category, Path(name).stem)
    out = []
    for c in npk.scan_archive(data):
        px = npk.decode(c)
        d.add(f"{d.stem}_{c.index:03d}", c.width, c.height, px, mainpal(), c.offset,
              c.size, palname, note + (f"; {len(c.trailer)} trailing bytes" if c.trailer else ""))
        out.append((c, px))
    d.close()
    return out


def dump_npk_prefix_pal(category: str, name: str) -> None:
    """Opendat/Enddat: 48-byte palettes before the first chunk."""
    data = read(name)
    first = data.find(npk.MAGIC)
    pals = gfx.load_palettes(GAME / name, 0, first // 48)
    d = Dump(category, Path(name).stem)
    for c in npk.scan_archive(data):
        px = npk.decode(c)
        i = pick_palette(px, c.width, c.height, pals)
        note = "palette is a best guess"
        if len(c.trailer) == 8:
            x, y, w, h = struct.unpack("<4H", c.trailer)
            note += f"; next chunk placed at ({x},{y}) {w}x{h}"
        elif c.trailer:
            note += f"; {len(c.trailer)} trailing bytes"
        d.add(f"{d.stem}_{c.index:03d}", c.width, c.height, px, pals[i], c.offset,
              c.size, f"prefix[{i}]", note)
    d.close()
    palette_sheet(f"{Path(name).stem.lower()}_prefix", pals)


# ---------------------------------------------------------------- palettes

def palette_sheet(stem: str, pals: list[gfx.Palette]) -> None:
    """Swatches (one row of 16 cells per set, 16 sets per PNG) + TSV."""
    cell = 16
    d = OUT / "palettes"
    d.mkdir(parents=True, exist_ok=True)
    for part in range(0, len(pals), 16):
        group = pals[part:part + 16]
        W, H = 16 * cell, len(group) * cell
        px = bytes((y // cell) * 16 + x // cell for y in range(H) for x in range(W))
        suffix = f"_{part // 16}" if len(pals) > 16 else ""
        gfx.write_png(d / f"{stem}{suffix}.png", W, H, px, [c for p in group for c in p])
    with (d / f"{stem}.tsv").open("w") as f:
        f.write("set\t" + "\t".join(f"c{i}" for i in range(16)) + "\n")
        for k, p in enumerate(pals):
            f.write(f"{k}\t" + "\t".join("%02x%02x%02x" % c for c in p) + "\n")


def dump_palettes() -> None:
    palette_sheet("mainpal", PAL["Mainpal"])
    palette_sheet("losepal", PAL["Losepal"])
    print("palettes: Mainpal 4, Losepal 4")


# ---------------------------------------------------------------- per file

def do_kaodata() -> None:
    data = read("Kaodata.gp")
    d = Dump("portraits", "Kaodata")
    pos, i = 0, 0
    while pos < len(data):
        start = pos
        w, h, face, pos = gfx.read_rle3(data, pos)
        w2, h2, sil, pos = gfx.read_rle3(data, pos)
        extra = data[pos:pos + 2]
        pos += 2
        d.add(f"face_{i:03d}", w, h, face, mainpal(), start, "", "Mainpal[0]",
              f"trailer bytes {extra[0]},{extra[1]}")
        d.add(f"face_{i:03d}_silhouette", w2, h2, sil, mainpal(), "", "", "Mainpal[0]",
              "", sheet=False)
        i += 1
    d.close(cols=10)


def do_kisetsu() -> None:
    data = read("Kisetsu.gp")
    d = Dump("events", "Kisetsu")
    pos, i = 0, 0
    while pos < len(data):
        start = pos
        w, h, px, pos = gfx.read_rle3(data, pos)
        d.add(f"kisetsu_{i:03d}", w, h, px, mainpal(), start, pos - start, "Mainpal[0]")
        i += 1
    d.close()


MONTAGE = [  # (offset, width, height, count, content)
    (0, 72, 77, 8, "type2_head"), (22176, 128, 99, 8, "type2_body"),
    (72864, 72, 88, 8, "type1_head"), (98208, 128, 103, 8, "type1_body"),
    (150944, 120, 78, 8, "type0_head"), (188384, 128, 99, 8, "type0_body"),
]
HAIKEI_PARTS = [
    (9600, 40, 14, 16, "type2_eyes"), (14080, 40, 25, 16, "type2_mouth"),
    (22080, 40, 11, 16, "type1_eyes"), (25600, 40, 30, 16, "type1_mouth"),
    (35200, 40, 12, 16, "type0_eyes"), (39040, 40, 27, 16, "type0_mouth"),
]


def masked_parts(d: Dump, data: bytes, table) -> None:
    """Montage-style parts: 3bpp colour followed by its own 1bpp mask."""
    for off, w, h, n, label in table:
        csize, msize = w * h * 3 // 8, w * h // 8
        for i in range(n):
            o = off + i * (csize + msize)
            px = gfx.apply_mask(planar(data, o, w, h, 3), data, w, h, o + csize)
            d.add(f"{label}_{i:02d}", w, h, px, mainpal(), o, csize + msize, "Mainpal[0]")


def do_montage() -> None:
    data = read("Montage.gp")
    d = Dump("portraits", "Montage")
    masked_parts(d, data, MONTAGE)
    d.close(cols=8)


def do_haikei() -> None:
    data = read("Haikei.gp")
    d = Dump("portraits", "Haikei")
    d.add("textures_64x400", 64, 400, planar(data, 0, 64, 400, 3), mainpal(), 0, 9600,
          "Mainpal[0]", "probably five 64x80 textures; use unknown", sheet=False)
    masked_parts(d, data, HAIKEI_PARTS)
    d.close(cols=16)


def do_mainmap() -> None:
    chunks = dump_npk("map", "Mainmap.gp", "Mainpal[0]")
    # 5 blocks of 4 strips (4 x 88 = 352 px); consecutive blocks overlap 16 px
    w, h = chunks[0][0].width, chunks[0][0].height
    W = w * len(chunks) - 16 * (len(chunks) // 4 - 1)
    canvas = bytearray(W * h)
    for i, (c, px) in enumerate(chunks):
        x0 = w * i - 16 * (i // 4)
        for y in range(h):
            canvas[y * W + x0:y * W + x0 + w] = px[y * w:(y + 1) * w]
    for s, season in enumerate(["spring", "summer", "autumn", "winter"]):
        gfx.write_png(OUT / "map" / "mainmap" / f"worldmap_{s}_{season}.png", W, h,
                      bytes(canvas), mainpal(s))
    print(f"map/mainmap: world map {W}x{h} x 4 seasons")


def do_hkeshiki() -> None:
    data = read("Hkeshiki.gp")
    d = Dump("battle", "Hkeshiki")
    for c in npk.scan_archive(data):
        px = npk.decode(c)
        for s in range(4):
            d.add(f"hkeshiki_{c.index:03d}_pal{s}", c.width, c.height, px, mainpal(s),
                  c.offset, c.size, f"Mainpal[{s}]", "season palette")
    d.close(cols=2)


def do_hground() -> None:
    data = read("Hground.gp")
    d = Dump("battle", "Hground")
    heights = [36] * 9 + [30] * 14 + [24] * 19 + [18] * 14 + [12] * 9
    for s in range(3):
        off = 37440 * s
        for i, h in enumerate(heights):
            d.add(f"set{s}_{i:02d}", 48, h, planar(data, off, 48, h, 4), mainpal(),
                  off, 48 * h // 2, "Mainpal[0]", "hex terrain tile")
            off += 48 * h // 2
    off = 112320
    for i in range(3):
        d.add(f"set3_{i:02d}", 48, 24, planar(data, off, 48, 24, 4), mainpal(),
              off, 576, "Mainpal[0]", "naval-battle tile")
        off += 576
    d.close(cols=13)


def do_hunitpat() -> None:
    data = read("Hunitpat.gp")
    d = Dump("battle", "Hunitpat")
    pal = mainpal()
    for s, kind in enumerate(["land", "naval"]):
        base = 74048 * s
        frames(d, data, f"{kind}_rider", base, 32, 36, 26, 3, pal, "Mainpal[0]")
        for t in range(5):
            frames(d, data, f"{kind}_banner{t}", base + 11232 + 5616 * t, 32, 36, 13, 3,
                   pal, "Mainpal[0]", note="banner colour variant")
        masks(d, data, f"{kind}_rider_banner_mask", base + 39312, 32, 36, 39,
              "masks for the 26 rider + 13 banner frames; order not verified")
        frames(d, data, f"{kind}_foot", base + 44928, 32, 40, 52, 3, pal, "Mainpal[0]",
               note="26 poses x 2 colour variants")
        masks(d, data, f"{kind}_foot_mask", base + 69888, 32, 40, 26,
              "shared by both colour variants")
    tail = 148096
    frames(d, data, "fence", tail, 32, 24, 2, 3, pal, "Mainpal[0]", mask_off=tail + 576)
    frames(d, data, "tree", tail + 768, 32, 48, 4, 3, pal, "Mainpal[0]",
           mask_off=tail + 3072, note="spring/summer/autumn/winter")
    d.close(cols=26)


def do_hikuchi() -> None:
    data = read("Hikuchi.gp")
    d = Dump("battle", "Hikuchi")
    frames(d, data, "rider", 0, 80, 48, 23, 3, mainpal(), "Mainpal[0]", mask_off=33120,
           note="一騎討ち rider")
    frames(d, data, "legs", 44160, 80, 16, 12, 3, mainpal(), "Mainpal[0]", mask_off=49920,
           note="horse legs")
    d.close(cols=6)


def do_hkei() -> None:
    data = read("Hkei.gp")
    d = Dump("battle", "Hkei")
    frames(d, data, "hkei", 0, 96, 96, 2, 3, mainpal(), "Mainpal[0]",
           note="battle event picture")
    d.close()


def do_hchikei() -> None:
    """Battle maps: 40 corner-height grids (14x14 u8) and 37 object lists."""
    data = read("Hchikei.gp")
    d = OUT / "battle" / "hchikei"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "heightmaps.tsv").open("w") as f:
        f.write("map\trow\t" + "\t".join(f"c{x}" for x in range(14)) + "\n")
        for m in range(40):
            for y in range(14):
                row = data[m * 196 + y * 14:m * 196 + (y + 1) * 14]
                f.write(f"{m}\t{y}\t" + "\t".join(map(str, row)) + "\n")
    with (d / "objects.tsv").open("w") as f:
        f.write("map\tentry\ttype\ta\tb\n")
        for m in range(37):
            rec = data[0x1EA0 + m * 60:0x1EA0 + (m + 1) * 60]
            for k in range(20):
                t, a, b = rec[k * 3:k * 3 + 3]
                if t == 0:
                    break
                f.write(f"{m}\t{k}\t{t}\t{a}\t{b}\n")
    # preview: heights 0..8 as a grey ramp, 8x scale, 8 maps per row
    grey = [(v * 28, v * 28, v * 28) for v in range(9)] + [(0, 0, 0)] * 7
    imgs = [(14, 14, data[m * 196:(m + 1) * 196]) for m in range(40)]
    W, H, px = gfx.sheet(imgs, 8, pad=1, bg=0)
    gfx.write_png(d / "_heightmaps.png", W, H, px, grey, scale=8)
    print("battle/hchikei: 40 height maps, 37 object lists")


def strip(d: Dump, data: bytes, label: str, start: int, end: int, w: int, bpp: int,
          note: str) -> None:
    """Undivided region rendered as one image of width w (frame splits unknown)."""
    row = w * bpp // 8
    h = (end - start) // row
    d.add(label, w, h, planar(data, start, w, h, bpp), mainpal(), start, h * row,
          "Mainpal[0]", note, sheet=False)


# Mainanm.gp: 3bpp 160x128 scene backgrounds, each followed by 4bpp sprites.
# Exact up to 108300; after that the background starts are +-2 rows and the
# sprite gaps are dumped as strips at their dominant width.
MAINANM_EXACT = [  # (offset, w, h, count, bpp, label)
    (0, 160, 128, 1, 3, "bg_courtyard"), (7680, 56, 56, 3, 4, "rider"),
    (12384, 48, 48, 2, 4, "farmer_hat"), (14688, 32, 48, 4, 4, "man_bowing"),
    (17760, 160, 128, 1, 3, "bg_field_gate"), (25440, 24, 48, 2, 4, "small_man"),
    (26592, 56, 56, 3, 4, "man_cart"), (31296, 40, 40, 2, 4, "standing_man"),
    (32896, 160, 128, 1, 3, "bg_3"), (40576, 48, 48, 4, 4, "farmer_hoe"),
    (45184, 32, 40, 3, 4, "man_orange"), (47104, 160, 128, 1, 3, "bg_castle_wall"),
    (54784, 48, 48, 4, 4, "spear_soldiers"), (59392, 32, 48, 2, 4, "man_scroll"),
    (60928, 160, 128, 4, 3, "bg_dojo_anim"), (91648, 160, 128, 1, 3, "bg_courtiers"),
    (99868, 160, 48, 2, 4, "courtier_anim"),
]
MAINANM_APPROX = [  # (start, end, w, bpp, label)
    (108300, 115980, 160, 3, "bg_street"), (115980, 125496, 128, 4, "sprites_a"),
    (125496, 133176, 160, 3, "bg_shrine"), (133176, 135648, 72, 4, "sprites_b"),
    (135648, 143328, 160, 3, "bg_procession"), (143328, 144288, 32, 4, "sprites_c"),
    (144288, 151968, 160, 3, "bg_fence_nobles"), (151968, 164540, 64, 4, "sprites_d"),
    (164540, 172220, 160, 3, "bg_banquet"), (172220, 197020, 112, 4, "sprites_e"),
    (197020, 204700, 160, 3, "bg_corridor"), (204700, 208828, 48, 4, "sprites_f"),
    (208828, 216508, 160, 3, "bg_cave"), (216508, 220040, 32, 4, "sprites_g"),
]


def do_mainanm() -> None:
    data = read("Mainanm.gp")
    d = Dump("backgrounds", "Mainanm")
    for off, w, h, n, bpp, label in MAINANM_EXACT:
        frames(d, data, label, off, w, h, n, bpp, mainpal(), "Mainpal[0]")
    for a, b, w, bpp, label in MAINANM_APPROX:
        strip(d, data, label, a, b, w, bpp, "approximate boundaries")
    d.close()


def do_mainobj() -> None:
    data = read("Mainobj.gp")
    d = Dump("map", "Mainobj")
    frames(d, data, "warrior", 0, 24, 32, 5, 4, mainpal(), "Mainpal[0]", note="colour variants")
    frames(d, data, "banner", 1920, 16, 32, 32, 4, mainpal(), "Mainpal[0]")
    frames(d, data, "fan", 10112, 24, 27, 16, 4, mainpal(), "Mainpal[0]",
           note="27-row period measured, medium confidence")
    strip(d, data, "icons_strip", 15296, 23648, 24, 4, "map icons, frame heights vary")
    frames(d, data, "ring", 23648, 16, 16, 7, 4, mainpal(), "Mainpal[0]")
    d.close()


# Maincmd.gp: 4bpp UI parts; only the first boundary is exact.
MAINCMD_BANDS = [(0, 3200, 16, "pillar"), (3200, 21312, 192, "frames_192"),
                 (21312, 36800, 24, "textures_24"), (36800, 46592, 64, "labels_icons_64"),
                 (46592, 50800, 40, "band_40"), (50800, 55600, 216, "band_216"),
                 (55600, 57408, 16, "band_16"), (57408, 61216, 160, "band_160")]


def do_maincmd() -> None:
    data = read("Maincmd.gp")
    d = Dump("commands", "Maincmd")
    for a, b, w, label in MAINCMD_BANDS:
        strip(d, data, label, a, b, w, 4,
              "exact" if a == 0 else "approximate band boundaries")
    d.close()


def do_maincmd2() -> None:
    dump_npk("commands", "Maincmd2.gp")
    data = read("Maincmd2.gp")
    d = Dump("commands", "Maincmd2_extra")
    d.add("plate_96x24", 96, 24, planar(data, 0x1507C, 96, 24, 4), mainpal(), 0x1507C,
          1152, "Mainpal[0]", "after NPK chunk 2")
    pos, i = 0x165A7, 0
    while pos < 0x25033:
        start = pos
        w, h, px, pos = gfx.read_rle3(data, pos)
        d.add(f"rle3_{i:02d}", w, h, px, mainpal(), start, pos - start, "Mainpal[0]",
              "RLE3 after NPK chunk 3")
        i += 1
    d.add("screen_640x400", 640, 400, planar(data, 0x25033, 640, 400, 4), mainpal(),
          0x25033, 128000, "Mainpal[0]", "folding-screen painting; colours 8-15 unverified",
          sheet=False)
    d.add("calligraphy_64x1432", 64, 1432, planar(data, 0x44433, 64, 1432, 3), mainpal(),
          0x44433, 34368, "Mainpal[0]", "4 columns of 64x358", sheet=False)
    d.close()


def do_npk_simple() -> None:
    dump_npk("events", "Mainevt.gp")
    dump_npk("items", "Mainitem.gp")
    dump_npk("map", "Mainstl.gp")
    dump_npk("battle", "Hikback.gp")
    dump_npk("battle", "Hkumi.gp")
    dump_npk("backgrounds", "Logo.gp")


def do_opening() -> None:
    dump_npk_prefix_pal("opening", "Opendat.gp")


def do_ending() -> None:
    dump_npk_prefix_pal("ending", "Enddat.gp")


JOBS = {
    "Palettes": dump_palettes, "Kaodata": do_kaodata, "Montage": do_montage,
    "Haikei": do_haikei, "Kisetsu": do_kisetsu, "Mainmap": do_mainmap,
    "Npk": do_npk_simple, "Hkeshiki": do_hkeshiki, "Hground": do_hground,
    "Hunitpat": do_hunitpat, "Hikuchi": do_hikuchi, "Hkei": do_hkei,
    "Hchikei": do_hchikei, "Mainanm": do_mainanm, "Mainobj": do_mainobj,
    "Maincmd": do_maincmd, "Maincmd2": do_maincmd2,
    "Opendat": do_opening, "Enddat": do_ending,
}


def main() -> None:
    global GAME, OUT
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    GAME, OUT = Path(sys.argv[1]), Path(sys.argv[2])
    PAL["Mainpal"] = gfx.load_palettes(GAME / "Mainpal.pld")
    PAL["Losepal"] = gfx.load_palettes(GAME / "Losepal.pld")
    only = {a.lower() for a in sys.argv[3:]}
    for name, job in JOBS.items():
        if not only or name.lower() in only:
            job()


if __name__ == "__main__":
    main()
