#!/usr/bin/env python3
"""KOEI NPK016 container reader for 《源平合戦》.

Variant of the kami-zh NPK016 reader (ported from
https://github.com/tzengyuxio/kaodata, dekoei/utils.py).

Archive layout for most .gp files in 《源平合戦》:

    NPK016 chunk 0
    NPK016 chunk 1
    ...

The chunks are concatenated with NO offset table at the top -- unlike
the kami-zh counterpart where the first u32 is `offsets[0] / 4`. We
locate chunks by scanning for the b"NPK016" magic.

NPK016 chunk layout (14-byte header):

    +0x00  char[6]  "NPK016"
    +0x06  u16      bit planes (always 4 -> 16 colors)
    +0x08  u16      canvas width in pixels  (always 640 in 《源平合戦》)
    +0x0a  u16      canvas height in pixels (always 400)
    +0x0c  u16      chunk's own scanline stride, in BYTES
                    == pixel width of the real content; this is what
                    the compressor uses as `line` for back-reference
                    arithmetic. In 《源平合戦》 this is often much
                    smaller than 640 (the chunk is a sprite strip,
                    not a full-screen bitmap).
    +0x0e  ...      flag-bit-driven LZ-RLE payload; decodes to one
                    4-bit palette index per output byte.

Important difference from 《神々の大地》:

- `declared_size` field at +0x0c in 《神々の大地》 holds the chunk's
  own byte count (including the 14-byte header). In 《源平合戦》 it
  is instead the scanline STRIDE used by the decoder.
- The 《源平合戦》 decoder lets the stream self-terminate (reads flag
  bits until the payload is consumed) rather than pre-knowing the
  pixel count. Output height is therefore `len(output) / line`.
- Chunks live in a flat concatenated layout -- the magic scan is the
  authoritative way to enumerate them.

Payload decoder (same as kami-zh):
- Read a flag byte; its 8 LSB-first bits each decide the next unit:
  - bit=0 -> literal: read 2 bytes, interleave to 4 output pixels
            (b1 bit7 -> plane 0 bit, b1 bit3 -> plane 0 next bit, etc.)
  - bit=1 -> back-reference: read 1 byte `b`
            run_size   = (b & 0x1F) + 1       # 1..32 (in 4-pixel units)
            run_offset = ((b >> 5) & 3) + 1   # 1..4
            run_offset *= line  if (b & 0x80) else 4
            emit (run_size * 4) bytes copied from (len(out) - run_offset)
"""
from __future__ import annotations

import io
import os
import struct
import sys
from dataclasses import dataclass

MAGIC = b"NPK016"
HEADER_SIZE = 0x0E


@dataclass
class Chunk:
    index: int
    offset: int
    size: int
    planes: int
    canvas_w: int
    canvas_h: int
    stride: int        # == scanline width in pixels (one byte per pixel)
    payload: bytes


def read_chunk(data: bytes, offset: int, size: int, index: int = 0) -> Chunk | None:
    if data[offset:offset + 6] != MAGIC:
        return None
    planes, w, h, stride = struct.unpack_from("<4H", data, offset + 6)
    return Chunk(
        index=index,
        offset=offset,
        size=size,
        planes=planes,
        canvas_w=w,
        canvas_h=h,
        stride=stride,
        payload=data[offset + HEADER_SIZE:offset + size],
    )


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


def unpack(src: bytes, line: int) -> bytes:
    """Decompress an NPK016 payload into one byte per pixel (4bpp index).

    The stream self-terminates: it is consumed until the input bytes
    run out. `line` is the per-chunk scanline stride; the height of
    the decoded image is `len(output) // line`.
    """
    data = io.BytesIO(src)
    dest = bytearray()
    bitflag = 0x0000
    data_len = len(src)
    while data.tell() < data_len:
        if not (bitflag & 0xFF00):
            b = data.read(1)
            if not b:
                break
            bitflag = 0xFF00 | b[0]
        if bitflag & 1:
            b = data.read(1)
            if not b:
                break
            b = b[0]
            run_size = (b & 0x1F) + 1
            run_offset = ((b & 0x60) >> 5) + 1
            run_offset = run_offset * line if (b & 0x80) else run_offset * 4
            for _ in range(run_size * 4):
                sp = len(dest) - run_offset
                # In practice sp is always >= 0 for valid 《源平合戦》 streams;
                # we 0-fill if an edge case appears so the decoder keeps going.
                dest.append(dest[sp] if sp >= 0 else 0)
        else:
            pair = data.read(2)
            if len(pair) < 2:
                break
            b1, b2 = pair[0], pair[1]
            for _ in range(4):
                dest.append(
                    ((b1 & 0x80) >> 4) | ((b1 & 0x08) >> 1)
                    | ((b2 & 0x80) >> 6) | ((b2 & 0x08) >> 3)
                )
                b1 = (b1 << 1) & 0xFF
                b2 = (b2 << 1) & 0xFF
        bitflag >>= 1
    return bytes(dest)


def save_pgm(path: str, pixels: bytes, line: int) -> tuple[int, int]:
    """Write a 4-bit indexed buffer as a greyscale PGM (previewing only)."""
    height = len(pixels) // line
    with open(path, "wb") as f:
        f.write(f"P5\n{line} {height}\n255\n".encode())
        f.write(bytes(min(255, p * 17) for p in pixels[:line * height]))
    return (line, height)


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--extract", metavar="DIR",
                    help="also save each chunk as a greyscale PGM into DIR")
    args = ap.parse_args()

    data = open(args.path, "rb").read()
    chunks = scan_archive(data)
    print(f"{args.path}: {len(chunks)} chunks ({len(data)} bytes)")
    if args.extract:
        os.makedirs(args.extract, exist_ok=True)
    stem = os.path.splitext(os.path.basename(args.path))[0]
    for c in chunks:
        pixels = unpack(c.payload, c.stride)
        height = len(pixels) // max(1, c.stride)
        print(f"  [{c.index:03d}] off=0x{c.offset:06x} size={c.size:7d} "
              f"planes={c.planes} canvas={c.canvas_w}x{c.canvas_h} "
              f"stride={c.stride:4d} -> {c.stride}x{height} ({len(pixels)} px)")
        if args.extract:
            out = os.path.join(args.extract, f"{stem}_{c.index:03d}.pgm")
            save_pgm(out, pixels, c.stride)


if __name__ == "__main__":
    main()
