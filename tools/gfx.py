#!/usr/bin/env python3
"""Shared graphics helpers for 《源平合戦》: palettes, planar decoders, PNG.

Pure standard library (PNG is written with zlib + struct).

Palette format (Mainpal.pld, Losepal.pld, the prefixes of Opendat.gp and
Enddat.gp): 16 colours x 3 bytes, one 4-bit value per byte, in the order
B, R, G (the PC-98 style "digital" colour order: index 1 = blue,
2 = red, 3 = magenta, 4 = green, 5 = cyan, 6 = yellow, 7 = white).
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

Palette = list[tuple[int, int, int]]

# Pixel value used for "transparent" (masked) pixels; written as a
# 17th palette entry with alpha 0.
TRANSPARENT = 16


def pal_from_brg(data: bytes) -> Palette:
    """48 bytes (16 x B,R,G nibbles) -> 16 RGB888 tuples."""
    out = []
    for i in range(16):
        b, r, g = data[i * 3:i * 3 + 3]
        out.append((r * 0x11, g * 0x11, b * 0x11))
    return out


def pal_from_0rgb(data: bytes) -> Palette:
    """32 bytes (16 x u16-LE 0x0RGB) -> 16 RGB888 tuples (NPK016 header)."""
    out = []
    for i in range(16):
        v = struct.unpack_from("<H", data, i * 2)[0]
        out.append((((v >> 8) & 15) * 0x11, ((v >> 4) & 15) * 0x11, (v & 15) * 0x11))
    return out


def load_palettes(path: str | Path, offset: int = 0, count: int | None = None) -> list[Palette]:
    """Read consecutive 48-byte palettes from a file."""
    data = Path(path).read_bytes()[offset:]
    n = len(data) // 48 if count is None else count
    return [pal_from_brg(data[i * 48:i * 48 + 48]) for i in range(n)]


# Fallback: stock PC-98 digital 8 colours + dim versions.
DEFAULT_PALETTE: Palette = pal_from_brg(bytes.fromhex(
    "000000" "0f0000" "000f00" "0f0f00" "00000f" "0f000f" "000f0f" "0f0f0f"
    "070707" "0a0000" "000a00" "0a0a00" "00000a" "0a000a" "000a0a" "0a0a0a"))


# ---------------------------------------------------------------- decoders

def decode_planar_rows(data: bytes, width: int, height: int, planes: int = 4,
                       offset: int = 0) -> bytes:
    """Line-interleaved planes: each scanline stores plane 0..N-1, each
    width/8 bytes (MSB = leftmost pixel). Plane k supplies bit k."""
    rb = width // 8
    out = bytearray(width * height)
    pos = offset
    for y in range(height):
        out_row = y * width
        for p in range(planes):
            bit = 1 << p
            seg = data[pos:pos + rb]
            pos += rb
            for i, b in enumerate(seg):
                if not b:
                    continue
                x = out_row + i * 8
                for k in range(8):
                    if b & (0x80 >> k):
                        out[x + k] |= bit
    return bytes(out)


def decode_planar_bytes(data: bytes, width: int, height: int, planes: int = 4,
                        offset: int = 0) -> bytes:
    """Byte-interleaved planes: every `planes` bytes hold 8 pixels;
    byte k of the group supplies bit k."""
    out = bytearray(width * height)
    pos = offset
    for i in range(width * height // 8):
        grp = data[pos:pos + planes]
        pos += planes
        x = i * 8
        for p, b in enumerate(grp):
            if not b:
                continue
            bit = 1 << p
            for k in range(8):
                if b & (0x80 >> k):
                    out[x + k] |= bit
    return bytes(out)


def encode_planar_bytes(pixels: bytes, planes: int = 4) -> bytes:
    """Inverse of decode_planar_bytes: every 8 pixels become `planes` bytes."""
    out = bytearray()
    for x in range(0, len(pixels), 8):
        grp = pixels[x:x + 8]
        for p in range(planes):
            out.append(sum(0x80 >> k for k, v in enumerate(grp) if v >> p & 1))
    return bytes(out)


def decode_planar_frames(data: bytes, width: int, height: int, planes: int = 4,
                         offset: int = 0) -> bytes:
    """Whole-plane layout: plane 0 for the whole image, then plane 1, ..."""
    rb = width // 8
    psize = rb * height
    out = bytearray(width * height)
    for p in range(planes):
        bit = 1 << p
        base = offset + p * psize
        for i in range(psize):
            b = data[base + i]
            if not b:
                continue
            x = i * 8
            for k in range(8):
                if b & (0x80 >> k):
                    out[x + k] |= bit
    return bytes(out)


def apply_mask(pixels: bytes, mask: bytes, width: int, height: int,
               offset: int = 0) -> bytes:
    """1bpp mask (row-major, MSB = leftmost, bit 1 = transparent): set
    transparent pixels to TRANSPARENT."""
    out = bytearray(pixels)
    for i in range(width * height // 8):
        b = mask[offset + i]
        if not b:
            continue
        for k in range(8):
            if b & (0x80 >> k):
                out[i * 8 + k] = TRANSPARENT
    return bytes(out)


def unpack_rle3(src: bytes, pos: int, line: int, count: int) -> tuple[bytes, int]:
    """KOEI 3-bit RLE used by Kaodata.gp, Kisetsu.gp and part of Maincmd2.gp.

    Each image is `u16 width, u16 height` followed by this stream:
      b & 0x80 -> copy: n = (b & 0x0F) + 1 groups of 4 pixels from
                  ((b >> 4) & 3) + 1 times (width if b & 0x40 else 4) back
      else     -> literal: with the next byte b2, 4 pixels whose bits are
                  b's low nibble (bit 2), b2's high nibble (bit 1) and low
                  nibble (bit 0), repeated (b >> 4) + 1 times
    Returns `count` pixels and the position after the stream.
    """
    dest = bytearray()
    n = len(src)
    while len(dest) < count and pos < n:
        b = src[pos]
        pos += 1
        if b & 0x80:
            run = (b & 0x0F) + 1
            back = ((b & 0x30) >> 4) + 1
            back = back * line if b & 0x40 else back * 4
            for _ in range(run * 4):
                sp = len(dest) - back
                dest.append(dest[sp] if sp >= 0 else 0)
        else:
            b1, b2 = b, src[pos]
            pos += 1
            quad = []
            for _ in range(4):
                quad.append(((b1 & 8) >> 1) | ((b2 & 0x80) >> 6) | ((b2 & 8) >> 3))
                b1 <<= 1
                b2 <<= 1
            dest.extend(quad * ((b >> 4) + 1))
    return bytes(dest[:count]), pos


def read_rle3(data: bytes, pos: int) -> tuple[int, int, bytes, int]:
    """Read one `u16 w, u16 h` + RLE3 image; returns (w, h, pixels, next_pos)."""
    w, h = struct.unpack_from("<HH", data, pos)
    px, pos = unpack_rle3(data, pos + 4, w, w * h)
    return w, h, px, pos


# ---------------------------------------------------------------- output


def write_png(path: str | Path, width: int, height: int, pixels: bytes,
              palette: Palette, scale: int = 1) -> None:
    """Write an 8-bit indexed PNG (one byte per pixel in `pixels`)."""
    if scale > 1:
        rows = []
        for y in range(height):
            row = pixels[y * width:(y + 1) * width]
            row = bytes(v for v in row for _ in range(scale))
            rows.extend([row] * scale)
        width, height = width * scale, height * scale
        raw = b"".join(b"\x00" + r for r in rows)
    else:
        raw = b"".join(b"\x00" + pixels[y * width:(y + 1) * width] for y in range(height))
    pal = list(palette) + [(0, 0, 0)] * max(0, 16 - len(palette))
    # index 16 = transparent (only for plain 16-colour palettes)
    trns = len(pal) == TRANSPARENT and TRANSPARENT in pixels
    if trns:
        pal.append((255, 0, 255))

    def chunk(tag: bytes, body: bytes) -> bytes:
        return (struct.pack(">I", len(body)) + tag + body
                + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 3, 0, 0, 0))
    png += chunk(b"PLTE", b"".join(bytes(c) for c in pal))
    if trns:
        png += chunk(b"tRNS", b"\xff" * TRANSPARENT + b"\x00")
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(png)


def sheet(images: list[tuple[int, int, bytes]], cols: int, pad: int = 2,
          bg: int = 0) -> tuple[int, int, bytes]:
    """Tile same-or-different sized images into one contact sheet."""
    if not images:
        return (1, 1, b"\x00")
    cw = max(w for w, _, _ in images)
    chh = max(h for _, h, _ in images)
    rows = (len(images) + cols - 1) // cols
    W = cols * (cw + pad) + pad
    H = rows * (chh + pad) + pad
    out = bytearray([bg]) * (W * H)
    for n, (w, h, px) in enumerate(images):
        ox = pad + (n % cols) * (cw + pad)
        oy = pad + (n // cols) * (chh + pad)
        for y in range(h):
            out[(oy + y) * W + ox:(oy + y) * W + ox + w] = px[y * w:(y + 1) * w]
    return (W, H, bytes(out))
