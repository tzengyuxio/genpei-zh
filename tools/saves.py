#!/usr/bin/env python3
"""Manage Savedata.gp slots as a library of named snapshots.

Savedata.gp is 10 fixed slots of 43,403 bytes, no header. A slot starts with
u16 year, u8 month, ..., and the leader's name (Shift-JIS) at +13.
Unused slots start with 00 b4 90 00.

The game only has 10 slots, so snapshots live in build/saves/NAME.slot and
are copied in and out of build/GENPEI/Savedata.gp as needed:

  saves.py list                 slots in build/GENPEI/Savedata.gp
  saves.py library              snapshots in build/saves/
  saves.py export SLOT NAME     slot (1-10) -> build/saves/NAME.slot
  saves.py import NAME SLOT     build/saves/NAME.slot -> slot (1-10)
  saves.py reset                Savedata.gp <- game/GENPEI/Savedata.gp
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAVE = ROOT / 'build/GENPEI/Savedata.gp'
ORIG = ROOT / 'game/GENPEI/Savedata.gp'
LIB = ROOT / 'build/saves'
SLOT = 43403
SLOTS = 10


def describe(s: bytes) -> str:
    if s[:4] == b'\x00\xb4\x90\x00':
        return '(empty)'
    year = int.from_bytes(s[:2], 'little')
    name = s[13:s.index(0, 13)].decode('cp932', 'replace')
    return f'{year} {s[2]:2}月 {name}'


def slot(data: bytes, n: int) -> bytes:
    return data[(n - 1) * SLOT:n * SLOT]


def main(argv: list[str]) -> None:
    cmd, args = (argv[0], argv[1:]) if argv else ('list', [])
    if cmd == 'reset':
        shutil.copyfile(ORIG, SAVE)
        cmd = 'list'
    if cmd == 'list':
        data = SAVE.read_bytes()
        for n in range(1, SLOTS + 1):
            print(f'S{n:<2} {describe(slot(data, n))}')
    elif cmd == 'library':
        for p in sorted(LIB.glob('*.slot')):
            print(f'{p.stem:32} {describe(p.read_bytes())}')
    elif cmd == 'export':
        n, name = int(args[0]), args[1]
        LIB.mkdir(parents=True, exist_ok=True)
        (LIB / f'{name}.slot').write_bytes(slot(SAVE.read_bytes(), n))
        print(f'S{n} -> {name}')
    elif cmd == 'import':
        name, n = args[0], int(args[1])
        s = (LIB / f'{name}.slot').read_bytes()
        assert len(s) == SLOT, f'{name}: bad size {len(s)}'
        data = bytearray(SAVE.read_bytes())
        data[(n - 1) * SLOT:n * SLOT] = s
        SAVE.write_bytes(data)
        print(f'{name} -> S{n}')
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv[1:])
