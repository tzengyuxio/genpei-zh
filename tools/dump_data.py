#!/usr/bin/env python3
"""Dump the scenario tables of 《源平合戦》 to TSV.

Sources:

  Sndata.gp      4 scenarios x 41266 bytes (1180, 1183, 1184, 1185):
                   +0x00 u16 year, u8 month-1, u8 ?, u16[16] active clan
                   ids (-1 = none), u16 ? (380 in all four)
                   +0x26 scenario block (layout S below)
  Main.exe       (unpacked) 0x4A570..0x54690: the same tables, 41248
                 bytes, in a slightly different order (layout M below).
                 Its generals/clans/places equal scenario 0 of Sndata.gp.

Block layouts (offsets relative to the block):

                        S (Sndata.gp)   M (Main.exe)
  generals 400 x 71     0x0000          0x0000
  clans     16 x 20     0x6EF0          0x6EF0
  places    39 x 76     0x7030          0x7030
  unknown   32 bytes    0x7BA4          0x7BA4  (+12 more bytes in M)
  regions    8 x 9      0x7BC4          0x7BD0
  ranks    256 x 19     0x7C0C          0x8E20
  treasures 256 x 18    0x8F0C          0x7C20  (M has 8 bytes before it)

Field names ending in `?` are guesses (see docs/formats.md); `wXX`/`bXX`
are undecoded u16/u8 fields named after their offset in the record.
All u16 are little-endian; 0xFFFF is written as -1.

    python3 tools/dump_data.py game/GENPEI build/dump/data
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import unpack_exe  # noqa: E402

SCEN_SIZE = 41266
SCEN_HEADER = 0x26
MAIN_BLOCK = (0x4A570, 0x54690)

LAYOUT_S = dict(regions=0x7BC4, ranks=0x7C0C, treasures=0x8F0C)
LAYOUT_M = dict(regions=0x7BD0, ranks=0x8E20, treasures=0x7C20)
GENERALS, CLANS, PLACES, UNKNOWN32 = 0x0000, 0x6EF0, 0x7030, 0x7BA4
N_GENERALS, N_CLANS, N_PLACES, N_REGIONS, N_RANKS, N_TREASURES = 400, 16, 39, 8, 256, 256


def sjis(b: bytes) -> str:
    return b.split(b"\0", 1)[0].decode("cp932", errors="replace")


def u16(b: bytes, o: int) -> int:
    v = struct.unpack_from("<H", b, o)[0]
    return -1 if v == 0xFFFF else v


def general_row(r: bytes) -> list:
    row = [sjis(r[0:7]), sjis(r[7:14]), sjis(r[14:19]), sjis(r[19:24])]
    row += [u16(r, 0x18), u16(r, 0x1A), u16(r, 0x1C), r[0x1E], r[0x1F], r[0x20],
            r[0x21], r[0x22], u16(r, 0x23), u16(r, 0x25), r[0x27], r[0x28],
            u16(r, 0x29), u16(r, 0x2B), u16(r, 0x2D), u16(r, 0x2F)]
    row += list(r[0x31:0x3A])
    row += [u16(r, 0x3A), u16(r, 0x3C), u16(r, 0x3E), u16(r, 0x40), u16(r, 0x42),
            r[0x44:0x47].hex(), r.hex()]
    return row


GENERAL_COLS = (["surname", "surname_kana", "given", "given_kana",
                 "w18", "w1a", "w1c", "age", "b1f_place?", "b20", "b21", "b22",
                 "w23", "lord", "b27_status?", "b28", "w29", "w2b", "w2d", "w2f"]
                + [f"s{o:02x}" for o in range(0x31, 0x3A)]
                + ["w3a", "clan", "location", "w40", "w42", "tail", "raw"])

CLAN_COLS = ["leader", "w02_type?", "rel0?", "rel1?", "rel2?", "rel3?",
             "clan_id", "w0e", "w10", "w12", "raw"]

PLACE_COLS = (["name", "kana"] + [f"adj{i}" for i in range(7)]
              + ["lord", "w20", "w22", "region", "clan"]
              + [f"w{o:02x}" for o in range(0x28, 0x4C, 2)] + ["raw"])

RANK_COLS = ["name", "b0d", "b0e_grade?", "b0f", "b10", "w11", "raw"]
TREASURE_COLS = ["name", "w0b", "b0d_kind?", "b0e", "b0f", "b10", "b11", "raw"]
REGION_COLS = ["name", "b06", "w07", "raw"]


def tables(block: bytes, layout: dict) -> dict[str, tuple[list, list]]:
    out: dict[str, tuple[list, list]] = {}
    rows = []
    for i in range(N_GENERALS):
        r = block[GENERALS + i * 71:GENERALS + (i + 1) * 71]
        rows.append([i] + general_row(r))
    out["generals"] = (["idx"] + GENERAL_COLS, rows)

    rows = []
    for i in range(N_CLANS):
        r = block[CLANS + i * 20:CLANS + (i + 1) * 20]
        rows.append([i] + [u16(r, o) for o in range(0, 20, 2)] + [r.hex()])
    out["clans"] = (["idx"] + CLAN_COLS, rows)

    rows = []
    for i in range(N_PLACES):
        r = block[PLACES + i * 76:PLACES + (i + 1) * 76]
        rows.append([i, sjis(r[0:9]), sjis(r[9:18])]
                    + [u16(r, o) for o in range(18, 76, 2)] + [r.hex()])
    out["places"] = (["idx"] + PLACE_COLS, rows)

    rows = []
    for i in range(N_REGIONS):
        o = layout["regions"] + i * 9
        r = block[o:o + 9]
        rows.append([i, sjis(r[0:6]), r[6], u16(r, 7), r.hex()])
    out["regions"] = (["idx"] + REGION_COLS, rows)

    rows = []
    for i in range(N_RANKS):
        o = layout["ranks"] + i * 19
        r = block[o:o + 19]
        rows.append([i, sjis(r[0:13]), r[13], r[14], r[15], r[16], u16(r, 17), r.hex()])
    out["ranks"] = (["idx"] + RANK_COLS, rows)

    rows = []
    for i in range(N_TREASURES):
        o = layout["treasures"] + i * 18
        r = block[o:o + 18]
        rows.append([i, sjis(r[0:11]), u16(r, 11), r[13], r[14], r[15], r[16], r[17],
                     r.hex()])
    out["treasures"] = (["idx"] + TREASURE_COLS, rows)
    return out


def write_tsv(path: Path, cols: list, rows: list) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(v) for v in r) + "\n")


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    game, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)

    # Sndata.gp: four scenarios
    sn = (game / "Sndata.gp").read_bytes()
    assert len(sn) == 4 * SCEN_SIZE, len(sn)
    merged: dict[str, tuple[list, list]] = {}
    scen_rows = []
    for k in range(4):
        s = sn[k * SCEN_SIZE:(k + 1) * SCEN_SIZE]
        clans = [v for v in struct.unpack_from("<16h", s, 4) if v >= 0]
        scen_rows.append([k, u16(s, 0), s[2] + 1, s[3], ",".join(map(str, clans)),
                          u16(s, 0x24), s[SCEN_HEADER + UNKNOWN32:SCEN_HEADER + UNKNOWN32 + 32].hex()])
        for name, (cols, rows) in tables(s[SCEN_HEADER:], LAYOUT_S).items():
            merged.setdefault(name, (["scenario"] + cols, []))[1].extend([k] + r for r in rows)
    write_tsv(out / "sndata_scenarios.tsv",
              ["scenario", "year", "month", "b03", "active_clans", "w24", "unknown32"], scen_rows)
    for name, (cols, rows) in merged.items():
        write_tsv(out / f"sndata_{name}.tsv", cols, rows)
        print(f"sndata_{name}.tsv: {len(rows)} rows")

    # Main.exe built-in copy
    exe = unpack_exe.unpack((game / "Main.exe").read_bytes())
    block = exe[MAIN_BLOCK[0]:MAIN_BLOCK[1]]
    for name, (cols, rows) in tables(block, LAYOUT_M).items():
        write_tsv(out / f"mainexe_{name}.tsv", cols, rows)
        print(f"mainexe_{name}.tsv: {len(rows)} rows")


if __name__ == "__main__":
    main()
