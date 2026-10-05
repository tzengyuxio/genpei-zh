#!/usr/bin/env python3
"""KOEI LS11 container: decompress and recompress.

LS11 is KOEI's generic compression format of the early 90s (also used by
the Sangokushi / Nobunaga series). In 源平合戦 it wraps Message.gp.

Layout (all integers big-endian):

    +0x000  "LS11" + 12 zero bytes
    +0x010  byte[256] dictionary: literal code i decodes to dict[i]
            (bytes sorted by frequency, so common bytes get short codes)
    +0x110  {u32 packed_size, u32 unpacked_size, u32 offset} per entry,
            terminated by a u32 zero
    ...     packed entries, each an independent MSB-first bit stream

Code word: n-1 one bits and a zero (value 2^n - 2), then n more bits
added on top. Codes < 256 are literals; otherwise distance = code - 256
and length = next code + 3 (LZ77 copy from the output).

    python3 tools/ls11.py unpack game/GENPEI/Message.gp OUTDIR
    python3 tools/ls11.py selftest game/GENPEI/Message.gp
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path


def read(data: bytes) -> tuple[bytes, list[bytes]]:
    """Return (dictionary, [unpacked entry, ...])."""
    if data[:4] != b"LS11":
        raise ValueError(f"not an LS11 file (magic {data[:4]!r})")
    dic = data[0x10:0x110]
    entries = []
    p = 0x110
    while (packed := struct.unpack_from(">I", data, p)[0]) != 0:
        unpacked, off = struct.unpack_from(">II", data, p + 4)
        entries.append(_decode(data[off:off + packed], unpacked, dic))
        p += 12
    return dic, entries


def _decode(src: bytes, size: int, dic: bytes) -> bytes:
    bits = int.from_bytes(src, "big")
    nbits = len(src) * 8
    pos = 0

    def take(n: int) -> int:
        nonlocal pos
        v = (bits >> (nbits - pos - n)) & ((1 << n) - 1)
        pos += n
        return v

    def code() -> int:
        n = 1
        while take(1):
            n += 1
        return (1 << n) - 2 + take(n)

    out = bytearray()
    while len(out) < size:
        c = code()
        if c < 256:
            out.append(dic[c])
        else:
            dist = c - 256
            for _ in range(code() + 3):
                out.append(out[-dist])
    return bytes(out[:size])


class _BitWriter:
    def __init__(self) -> None:
        self.acc = 0
        self.n = 0

    def code(self, c: int) -> None:
        n = 1
        while c >= (1 << (n + 1)) - 2:
            n += 1
        prefix = (1 << n) - 2          # n-1 ones then a zero
        self.acc = (self.acc << (2 * n)) | (prefix << n) | (c - prefix)
        self.n += 2 * n

    def bytes(self) -> bytes:
        pad = -self.n % 8
        return ((self.acc << pad).to_bytes((self.n + pad) // 8, "big"))


def _code_bits(c: int) -> int:
    n = 1
    while c >= (1 << (n + 1)) - 2:
        n += 1
    return 2 * n


def _encode(data: bytes, dic: bytes) -> bytes:
    inv = {b: i for i, b in enumerate(dic)}
    w = _BitWriter()
    heads: dict[bytes, list[int]] = {}
    i = 0
    n = len(data)
    while i < n:
        best_len = best_dist = 0
        if i + 3 <= n:
            for j in reversed(heads.get(data[i:i + 3], [])[-256:]):
                ln = 3
                while i + ln < n and data[j + ln] == data[i + ln]:
                    ln += 1
                if ln > best_len:
                    best_len, best_dist = ln, i - j
        if best_len >= 3:
            match_bits = _code_bits(256 + best_dist) + _code_bits(best_len - 3)
            lit_bits = sum(_code_bits(inv[b]) for b in data[i:i + best_len])
            if match_bits >= lit_bits:
                best_len = 0
        step = best_len if best_len >= 3 else 1
        if step == 1:
            w.code(inv[data[i]])
        else:
            w.code(256 + best_dist)
            w.code(best_len - 3)
        for k in range(i, i + step):
            if k + 3 <= n:
                heads.setdefault(data[k:k + 3], []).append(k)
        i += step
    return w.bytes()


def write(dic: bytes, entries: list[bytes]) -> bytes:
    missing = {b for e in entries for b in e} - set(dic)
    if missing:
        raise ValueError(f"bytes not in dictionary: {sorted(missing)}")
    packed = [_encode(e, dic) for e in entries]
    table_end = 0x110 + 12 * len(entries) + 4
    out = bytearray(b"LS11" + bytes(12) + dic)
    off = table_end
    for p, e in zip(packed, entries):
        out += struct.pack(">III", len(p), len(e), off)
        off += len(p)
    out += bytes(4)
    for p in packed:
        out += p
    return bytes(out)


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[1] not in ("unpack", "selftest"):
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    src = Path(sys.argv[2])
    data = src.read_bytes()
    dic, entries = read(data)
    if sys.argv[1] == "unpack":
        outdir = Path(sys.argv[3])
        outdir.mkdir(parents=True, exist_ok=True)
        for i, e in enumerate(entries):
            (outdir / f"{src.stem.lower()}_{i}.bin").write_bytes(e)
        print(f"{src}: {len(entries)} entries -> {outdir}")
        return
    rebuilt = write(dic, entries)
    _, again = read(rebuilt)
    assert again == entries, "round-trip mismatch"
    print(f"selftest OK: {len(entries)} entries, "
          f"original {len(data)} B, re-packed {len(rebuilt)} B")


if __name__ == "__main__":
    main()
