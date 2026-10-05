#!/usr/bin/env python3
"""Analyse Sndata.gp -- the officer / character database.

Despite the name ("sound data"?), this file is actually a flat array
of fixed-length officer records (71 bytes each) starting at offset
0x24. Each record contains surname + reading + given-name + reading +
stats.

Running this prints the first N records and the record geometry.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

RECORD_SIZE = 71
RECORD_START = 0x24


def read_sjis(record: bytes, start: int, length: int) -> str:
    raw = record[start:start + length].split(b"\x00", 1)[0]
    return raw.decode("cp932", errors="replace")


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else \
        "game/GENPEI/Sndata.gp"
    show_n = int(sys.argv[2]) if len(sys.argv) > 2 else 15

    data = Path(path).read_bytes()
    print(f"=== {path} ({len(data)} bytes) ===")

    # Header
    h0, h1 = struct.unpack_from("<HH", data, 0)
    print(f"header u16[0]  = 0x{h0:04x} ({h0})")
    print(f"header u16[1]  = 0x{h1:04x} ({h1})")
    # 0x04..0x24 is a short index table: u16 counter 00..0e, then ffff ... fe01
    print(f"index 0x04..0x24: {data[0x04:RECORD_START].hex(' ')}")

    body = data[RECORD_START:]
    print(f"body: {len(body)} bytes = {len(body) / RECORD_SIZE:.2f} "
          f"records of {RECORD_SIZE} bytes")

    # Dump a few records.
    print(f"\nfirst {show_n} records:")
    for i in range(show_n):
        off = RECORD_START + i * RECORD_SIZE
        r = data[off:off + RECORD_SIZE]
        if len(r) < RECORD_SIZE:
            break
        rec_id = struct.unpack_from("<H", r, 0)[0]
        # Field offsets inferred empirically. Padding (zero bytes)
        # separates each name from its reading, and names from stats.
        surname = read_sjis(r, 0x02, 7)
        sur_read = read_sjis(r, 0x09, 7)
        given = read_sjis(r, 0x10, 5)
        giv_read = read_sjis(r, 0x15, 5)
        print(f"  [{i:3d}] id={rec_id:5d}  "
              f"姓={surname!s:6}({sur_read!s:5})  "
              f"名={given!s:5}({giv_read!s:7})  "
              f"stats={r[0x1E:0x1E + 16].hex(' ')}...")


if __name__ == "__main__":
    main()
