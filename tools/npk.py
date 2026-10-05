#!/usr/bin/env python3
"""KOEI NPK016 container reader for 《源平合戦》.

Variant of the kami-zh NPK016 reader (ported from
https://github.com/tzengyuxio/kaodata, dekoei/utils.py).

The chunks are concatenated with NO offset table at the top -- unlike
the kami-zh counterpart where the first u32 is `offsets[0] / 4`. We
locate chunks by scanning for the b"NPK016" magic.

NPK016 chunk layout (48-byte header):

    +0x00  char[6]  "NPK016"
    +0x06  u16      bit planes (always 4 -> 16 colours)
    +0x08  u16      canvas width  (always 640)
    +0x0a  u16      canvas height (always 400)
    +0x0c  u16      image width in pixels (also the decoder's `line`)
    +0x0e  u16      image height in pixels
    +0x10  u16[16]  palette, 0x0RGB -- in every chunk of every file this
                    is the same stock table (000 00f 0f0 0ff f00 ... aaa);
                    the game ignores it and uses .pld / prefix palettes
    +0x30  ...      flag-bit-driven LZ-RLE payload; decodes to exactly
                    width * height 4-bit palette indices

Some files keep extra bytes after a chunk's payload (the next magic is
further on): Opendat.gp has an 8-byte (x, y, w, h) placement record
before some chunks, Maincmd2.gp has non-NPK image data. `Chunk.trailer`
holds those bytes.

Payload decoder (same as kami-zh):
- Read a flag byte; its 8 LSB-first bits each decide the next unit:
  - bit=0 -> literal: read 2 bytes, interleave to 4 output pixels
            (b1 bit7 -> pixel bit 3, b1 bit3 -> bit 2, b2 bit7 -> bit 1,
            b2 bit3 -> bit 0; then shift both left)
  - bit=1 -> back-reference: read 1 byte `b`
            run_size   = (b & 0x1F) + 1       # 1..32 (in 4-pixel units)
            run_offset = ((b >> 5) & 3) + 1   # 1..4
            run_offset *= width if (b & 0x80) else 4
            emit (run_size * 4) bytes copied from (len(out) - run_offset)
"""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass

MAGIC = b"NPK016"
HEADER_SIZE = 0x30


@dataclass
class Chunk:
    index: int
    offset: int
    size: int          # bytes up to the next magic (or EOF)
    planes: int
    canvas_w: int
    canvas_h: int
    width: int
    height: int
    palette: bytes     # 32 bytes, stock 0x0RGB table (unused by the game)
    payload: bytes     # everything after the header up to the next magic
    used: int = 0      # payload bytes consumed by unpack()
    trailer: bytes = b""


def read_chunk(data: bytes, offset: int, size: int, index: int = 0) -> Chunk | None:
    if data[offset:offset + 6] != MAGIC:
        return None
    planes, cw, ch, w, h = struct.unpack_from("<5H", data, offset + 6)
    return Chunk(index, offset, size, planes, cw, ch, w, h,
                 data[offset + 0x10:offset + HEADER_SIZE],
                 data[offset + HEADER_SIZE:offset + size])


def scan_archive(data: bytes) -> list[Chunk]:
    """Locate chunks by searching for the magic."""
    offsets = []
    pos = data.find(MAGIC)
    while pos != -1:
        offsets.append(pos)
        pos = data.find(MAGIC, pos + 1)
    offsets.append(len(data))
    return [
        c
        for i in range(len(offsets) - 1)
        if (c := read_chunk(data, offsets[i], offsets[i + 1] - offsets[i], i)) is not None
    ]


def unpack(src: bytes, line: int, count: int | None = None) -> tuple[bytes, int]:
    """Decompress an NPK016 payload into one byte per pixel (4bpp index).

    Stops after `count` pixels (or when the input runs out). Returns the
    pixels and the number of input bytes consumed.
    """
    dest = bytearray()
    pos = 0
    n = len(src)
    limit = count if count is not None else 1 << 30
    bitflag = 0
    while pos < n and len(dest) < limit:
        if not (bitflag & 0xFF00):
            bitflag = 0xFF00 | src[pos]
            pos += 1
            if pos >= n:
                break
        if bitflag & 1:
            b = src[pos]
            pos += 1
            run_size = (b & 0x1F) + 1
            run_offset = ((b & 0x60) >> 5) + 1
            run_offset = run_offset * line if (b & 0x80) else run_offset * 4
            for _ in range(run_size * 4):
                sp = len(dest) - run_offset
                dest.append(dest[sp] if sp >= 0 else 0)
        else:
            if pos + 2 > n:
                break
            b1, b2 = src[pos], src[pos + 1]
            pos += 2
            for _ in range(4):
                dest.append(((b1 & 0x80) >> 4) | ((b1 & 0x08) >> 1)
                            | ((b2 & 0x80) >> 6) | ((b2 & 0x08) >> 3))
                b1 = (b1 << 1) & 0xFF
                b2 = (b2 << 1) & 0xFF
        bitflag >>= 1
    if count is not None:
        dest = dest[:count]
    return bytes(dest), pos


def pack(pixels: bytes, line: int) -> bytes:
    """Compress width*height 4-bit indices into an NPK016 payload.

    Greedy: at each 4-pixel unit take the longest back-reference among the
    eight offsets the format allows (1-4 units back, 1-4 rows up), else a
    literal. Inverse of unpack(); pixel count must be a multiple of 4.
    """
    n = len(pixels)
    assert n % 4 == 0
    offsets = [(k, k * 4, 0) for k in range(1, 5)] + [(k, k * line, 0x80) for k in range(1, 5)]
    out = bytearray()
    flag_pos = -1
    bit = 8
    p = 0
    while p < n:
        if bit == 8:
            flag_pos = len(out)
            out.append(0)
            bit = 0
        best, code = 0, 0
        for k, off, hi in offsets:
            # the game's decoder works row by row: no zeros before the start,
            # and horizontal references stay inside the current row
            if off > p or (not hi and off > p % line):
                continue
            units = 0
            # nor may a run cross the row end
            limit = min(32, (line - p % line) // 4)
            while units < limit:
                q = p + units * 4
                if any(pixels[q + j] != pixels[q + j - off] for j in range(4)):
                    break
                units += 1
            if units > best:
                best, code = units, hi | ((k - 1) << 5)
        if best:
            out[flag_pos] |= 1 << bit
            out.append(code | (best - 1))
            p += best * 4
        else:
            b1 = b2 = 0
            for j in range(4):
                v = pixels[p + j]
                b1 |= ((v >> 3) & 1) << (7 - j) | ((v >> 2) & 1) << (3 - j)
                b2 |= ((v >> 1) & 1) << (7 - j) | (v & 1) << (3 - j)
            out += bytes((b1, b2))
            p += 4
        bit += 1
    return bytes(out)


def build_chunk(width: int, height: int, pixels: bytes, palette: bytes, planes: int = 4,
                canvas: tuple[int, int] = (640, 400)) -> bytes:
    """A complete NPK016 chunk (48-byte header + payload)."""
    return (MAGIC + struct.pack("<5H", planes, canvas[0], canvas[1], width, height)
            + palette + pack(pixels, width))


def decode(chunk: Chunk) -> bytes:
    """Decode a chunk to width*height indices; fills `used`/`trailer`."""
    px, used = unpack(chunk.payload, chunk.width, chunk.width * chunk.height)
    chunk.used = used
    chunk.trailer = chunk.payload[used:]
    return px


def main() -> None:
    import argparse
    import gfx
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--extract", metavar="DIR",
                    help="also save each chunk as PNG (Mainpal.pld set 0) into DIR")
    args = ap.parse_args()

    data = open(args.path, "rb").read()
    chunks = scan_archive(data)
    print(f"{args.path}: {len(chunks)} chunks ({len(data)} bytes)")
    if args.extract:
        os.makedirs(args.extract, exist_ok=True)
        pal = gfx.load_palettes(os.path.join(os.path.dirname(args.path), "Mainpal.pld"))[0]
    stem = os.path.splitext(os.path.basename(args.path))[0]
    for c in chunks:
        px = decode(c)
        print(f"  [{c.index:03d}] off=0x{c.offset:06x} size={c.size:7d} "
              f"{c.width}x{c.height} trailer={len(c.trailer)}")
        if args.extract:
            gfx.write_png(os.path.join(args.extract, f"{stem}_{c.index:03d}.png"),
                          c.width, c.height, px, pal)


if __name__ == "__main__":
    main()
