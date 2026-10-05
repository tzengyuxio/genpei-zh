#!/usr/bin/env python3
"""Unpack Main.exe into a plain MZ executable.

Main.exe (both the shipped .exe and .ori) is run-length packed: the stub
at CS:0001 expands the image in place before jumping to the real entry.
Strings that sit in a zero run, or straddle one, are not visible in the
file, so text tools must work on the unpacked image.

Stub, all offsets relative to the stub segment (CS):

  * control records are read BACKWARDS from CS:1977, one per run:
        b0          bit0: literal count is 2 bytes; bit1: fill count is
                    2 bytes (high byte = b0 >> 2); otherwise counts are
                    1 byte (fill count = b0 >> 2)
        lit count   1 or 2 bytes (big-endian when read backwards)
        fill count  0 or 1 extra byte
        fill byte
    each record emits, going downwards: `lit` bytes copied from the packed
    data (also read backwards, from just below the stub), then `fill`
    copies of the fill byte. CS:002A holds the record count.
  * relocations are read FORWARDS from CS:1978, CS:008B holds the count:
        b > 1   advance b bytes
        b == 0  advance by the next u16
        b == 1  segment += next byte * 256, then advance by the next u16
    and the word at each position gets the load segment added.
  * real entry: far jmp at CS:00BF; SS:SP set at CS:00B7 / CS:00BC.

    python3 tools/unpack_exe.py game/GENPEI/Main.exe build/GENPEI/Main.exe
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path


def unpack(exe: bytes) -> bytes:
    hdr = struct.unpack_from("<14H", exe, 0)
    image = exe[hdr[4] * 16:]
    cs = hdr[11]
    stub = image[cs * 16:]
    if stub[1:7] != bytes.fromhex("9c508cda5252"):
        raise ValueError("unknown packer stub")

    # Copy stage moves the stub up by this many paragraphs; the expanded
    # image ends where the moved stub begins.
    shift = struct.unpack_from("<H", stub, 0x10)[0]
    top = cs * 16 + shift * 16 - 16 + 0x10       # (CS-1+shift):0010
    out = bytearray(top)

    nrec = struct.unpack_from("<H", stub, 0x2B)[0]
    ctl = 0x1977                                  # control, read backwards
    src = cs * 16 - 11                            # (CS-1):0005, backwards
    dst = top - 1
    for _ in range(nrec):
        b0 = stub[ctl]; ctl -= 1
        lit = stub[ctl]; ctl -= 1
        if b0 & 1:
            lit = (lit << 8) | stub[ctl]; ctl -= 1
        fill = b0 >> 2
        if b0 & 2:
            fill = (fill << 8) | stub[ctl]; ctl -= 1
        value = stub[ctl]; ctl -= 1
        for _ in range(lit):
            out[dst] = image[src]; dst -= 1; src -= 1
        for _ in range(fill):
            out[dst] = value; dst -= 1
    if dst != -1:
        raise ValueError(f"expansion ended at {dst + 1:#x}, not at 0")

    nrel = struct.unpack_from("<H", stub, 0x8B)[0]
    p = 0x1978
    seg = off = 0
    relocs = []
    for _ in range(nrel):
        b = stub[p]; p += 1
        if b > 1:
            delta = b
        else:
            if b == 1:
                seg += stub[p] << 8; p += 1
            delta = struct.unpack_from("<H", stub, p)[0]; p += 2
        off += delta
        if off > 0xFFFF:                         # carry: next 64 KB
            off -= 0x10000
            seg += 0x1000
        if off == 0xFFFF:                        # keep the word in-segment
            off = 0xFFEF
            seg += 1
        relocs.append((seg, off))

    ip, entry_cs = struct.unpack_from("<HH", stub, 0xC0)
    ss = struct.unpack_from("<H", stub, 0xB8)[0]
    sp = struct.unpack_from("<H", stub, 0xBD)[0]
    return build_mz(bytes(out), relocs, entry_cs, ip, ss, sp)


def build_mz(image: bytes, relocs, cs: int, ip: int, ss: int, sp: int) -> bytes:
    rel_off = 0x1C
    hdr_size = (rel_off + 4 * len(relocs) + 15) // 16 * 16
    total = hdr_size + len(image)
    # stack sits right after the image; reserve it plus some slack
    min_alloc = max(0, (ss * 16 + sp - len(image) + 15) // 16)
    hdr = struct.pack("<14H", 0x5A4D, total % 512, (total + 511) // 512,
                      len(relocs), hdr_size // 16, min_alloc, 0xFFFF,
                      ss, sp, 0, ip, cs, rel_off, 0)
    table = b"".join(struct.pack("<HH", o, s) for s, o in relocs)
    head = (hdr + table).ljust(hdr_size, b"\0")
    return head + image


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    out = unpack(src.read_bytes())
    dst.write_bytes(out)
    print(f"{src} ({src.stat().st_size} B) -> {dst} ({len(out)} B)")


if __name__ == "__main__":
    main()
