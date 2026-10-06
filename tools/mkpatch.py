#!/usr/bin/env python3
"""Build the patch file the browser version (web/) applies.

    python3 tools/mkpatch.py ORIGINAL_DIR PATCHED_DIR web/dist/genpei-zh.kzp

tools/web.sh runs this with a copy of game/GENPEI whose Main.exe is
already unpacked (tools/unpack_exe.py), since the build patches the
unpacked image; web/app.js unpacks the player's Main.exe the same way
before checking and patching it.

Only files that differ are recorded, each as a delta against the original:
COPY ops point back into the player's own file, INSERT ops carry the new
bytes (the translated text). No original game data is shipped beyond what
the translation itself replaces. Files only in the patched dir are ignored,
so the result is the translation alone.

Ported unchanged (apart from this note) from kami-zh tools/mkpatch.py.

Format (little endian):
  "KZP1", u16 file count, then per file:
    u8 name length, name (ASCII)
    u32 source size, 32-byte source SHA-256
    u32 target size, 32-byte target SHA-256
    u32 op count, then ops:
      0, u32 source offset, u32 length   copy from the original
      1, u32 length, bytes               insert new bytes
"""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

K = 8          # shortest match worth a COPY op
MAGIC = b"KZP1"


def delta(src: bytes, dst: bytes) -> list[tuple]:
    """Greedy COPY/INSERT delta, preferring to continue the last copy's offset."""
    index: dict[bytes, list[int]] = {}
    for i in range(len(src) - K + 1):
        index.setdefault(src[i:i + K], []).append(i)
    ops: list[tuple] = []
    pending = bytearray()
    shift = 0      # source offset minus target offset of the last copy
    i = 0
    while i < len(dst):
        key = dst[i:i + K]
        guess = i + shift
        cands = []
        if 0 <= guess and src[guess:guess + K] == key and len(key) == K:
            cands.append(guess)
        cands += index.get(key, [])[:16] if len(key) == K else []
        best, best_len = -1, 0
        for c in cands:
            n = K
            while i + n < len(dst) and c + n < len(src) and src[c + n] == dst[i + n]:
                n += 1
            if n > best_len:
                best, best_len = c, n
        if best_len >= K:
            if pending:
                ops.append((1, bytes(pending)))
                pending.clear()
            ops.append((0, best, best_len))
            shift = best - i
            i += best_len
        else:
            pending.append(dst[i])
            i += 1
    if pending:
        ops.append((1, bytes(pending)))
    return ops


def apply(src: bytes, ops: list[tuple]) -> bytes:
    out = bytearray()
    for op in ops:
        out += src[op[1]:op[1] + op[2]] if op[0] == 0 else op[1]
    return bytes(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("original", type=Path)
    ap.add_argument("patched", type=Path)
    ap.add_argument("out", type=Path)
    args = ap.parse_args()

    entries = []
    for src_path in sorted(args.original.iterdir()):
        dst_path = args.patched / src_path.name
        if not src_path.is_file() or not dst_path.is_file():
            continue
        src, dst = src_path.read_bytes(), dst_path.read_bytes()
        if src == dst:
            continue
        ops = delta(src, dst)
        assert apply(src, ops) == dst, src_path.name
        inserted = sum(len(op[1]) for op in ops if op[0] == 1)
        print(f"{src_path.name}: {len(ops)} ops, {inserted} new bytes")
        entries.append((src_path.name, src, dst, ops))

    blob = bytearray(MAGIC + struct.pack("<H", len(entries)))
    for name, src, dst, ops in entries:
        blob += bytes([len(name)]) + name.encode("ascii")
        blob += struct.pack("<I", len(src)) + hashlib.sha256(src).digest()
        blob += struct.pack("<I", len(dst)) + hashlib.sha256(dst).digest()
        blob += struct.pack("<I", len(ops))
        for op in ops:
            if op[0] == 0:
                blob += struct.pack("<BII", 0, op[1], op[2])
            else:
                blob += struct.pack("<BI", 1, len(op[1])) + op[1]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(bytes(blob))
    print(f"{args.out}: {len(blob)} bytes, {len(entries)} files")


if __name__ == "__main__":
    main()
