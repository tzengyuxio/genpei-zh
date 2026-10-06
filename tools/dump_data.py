#!/usr/bin/env python3
"""Dump the game data of 《源平合戦》 to readable TSV.

Sources (layouts in docs/formats.md §4 and §11):

  Sndata.gp      4 scenarios x 41266 bytes (1180, 1183, 1184, 1185):
                 0x26-byte header + tables (generals, clans, places,
                 regions, ranks, treasures)
  Main.exe       (unpacked) 0x4A570..0x54690: built-in copy of the same
                 tables (checked against scenario 0, not dumped again);
                 DGROUP: strategic map nodes, node adjacency, minimap
                 coordinates of the bases
  Hchikei.gp     battle maps: 40 corner-height grids + 37 object lists

    python3 tools/dump_data.py game/GENPEI build/data

Writes scenarios, generals, clans, places, regions, ranks, treasures,
map_nodes, battle_maps, battle_objects (.tsv). Column names ending in `?`
are guesses; `wXX`/`bXX` are undecoded u16/u8 fields named after their
offset. References are written as `id:name`; -1 means none.
"""
from __future__ import annotations

import csv
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import unpack_exe  # noqa: E402

SCEN_SIZE = 41266
SCEN_HEADER = 0x26
MAIN_BLOCK = (0x4A570, 0x54690)

# table offsets inside a scenario block (after the 0x26-byte header)
GENERALS, CLANS, PLACES, UNKNOWN32 = 0x0000, 0x6EF0, 0x7030, 0x7BA4
REGIONS, RANKS, TREASURES = 0x7BC4, 0x7C0C, 0x8F0C
# Main.exe keeps regions/ranks/treasures in another order
MAIN_REGIONS, MAIN_RANKS, MAIN_TREASURES = 0x7BD0, 0x8E20, 0x7C20
N_GENERALS, N_CLANS, N_PLACES, N_REGIONS, N_RANKS, N_TREASURES = 400, 16, 39, 8, 256, 256

# Main.exe (unpacked) file offsets, all inside DGROUP (0x56870)
MINIMAP = 0x57044      # 39 x (u16 x, u16 y) on the 520x168 minimap
EDGES = 0x58EF8        # 156 nodes x 4 x (u16 neighbour, u16 1); 156 = none
NODES = 0x598B8        # 156 x 11 bytes
N_NODES = 156

STATUS = {0: "御家人", 1: "棟梁", 2: "代官", 5: "在野", 6: "落武者?", 7: "死亡"}
CLAN_TYPE = {0: "源氏", 1: "平氏", 2: "藤原氏", 3: "豪族"}
TREASURE_KIND = ["名馬", "刀剣", "鎧", "兜", "鞍", "楽器", "歌集", "美術", "兵書", "唐物", "珍宝"]
NODE_TYPE = {0: "拠点", 1: "緑橙斑", 2: "橙", 3: "緑", 4: "赤緑斑", 5: "水色", 6: "海路"}
SKILLS = [(0x02, "waka"), (0x01, "music"), (0x04, "strategy"), (0x08, "ships")]
TRAITS = [(0x01, "monk"), (0x02, "female"), (0x04, "noble"), (0x08, "lineage?")]


def sjis(b: bytes) -> str:
    return b.split(b"\0", 1)[0].decode("cp932", errors="replace")


def u16(b: bytes, o: int) -> int:
    v = struct.unpack_from("<H", b, o)[0]
    return -1 if v == 0xFFFF else v


def ref(i: int, names: list[str]) -> str:
    return f"{i}:{names[i]}" if 0 <= i < len(names) else str(i)


def chain(head: int, nxt) -> list[int]:
    out = []
    while head != -1 and head not in out:
        out.append(head)
        head = nxt(head)
    return out


def recs(block: bytes, off: int, size: int, n: int) -> list[bytes]:
    return [block[off + i * size:off + (i + 1) * size] for i in range(n)]


def scenario_tables(k: int, block: bytes, nodes: list[bytes], minimap: list[tuple]) -> dict:
    G = recs(block, GENERALS, 71, N_GENERALS)
    C = recs(block, CLANS, 20, N_CLANS)
    P = recs(block, PLACES, 76, N_PLACES)
    RG = recs(block, REGIONS, 9, N_REGIONS)
    R = recs(block, RANKS, 19, N_RANKS)
    T = recs(block, TREASURES, 18, N_TREASURES)

    gname = [sjis(g[0:7]) + sjis(g[14:19]) for g in G]
    pname = [sjis(p[0:9]) for p in P]
    cname = [gname[u16(c, 0)] if u16(c, 0) >= 0 else "" for c in C]
    rgname = [sjis(r[0:6]) for r in RG]
    rname = [sjis(r[0:13]) for r in R]
    tname = [sjis(t[0:11]) for t in T]
    face_owner = {u16(g, 0x1A): i for i, g in enumerate(G) if u16(g, 0x1A) >= 0}
    rank_holder = {u16(g, 0x29): i for i, g in enumerate(G) if u16(g, 0x29) >= 0}
    t_owner = {t: i for i, g in enumerate(G)
               for t in chain(u16(g, 0x3A), lambda x: u16(T[x], 0x0B))}
    out = {}

    rows = []
    for i, g in enumerate(G):
        face, kin = u16(g, 0x1A), u16(g, 0x1C)
        # montage: bits 15-14 type, 13-11 head, 10-8 body, 7-4 eyes, 3-0 mouth
        face_src = ("" if face < 0 else f"kaodata:{face}" if face < 90
                    else f"montage{face >> 14}:h{face >> 11 & 7}/b{face >> 8 & 7}"
                         f"/e{face >> 4 & 15}/m{face & 15}")
        parent = face_owner.get(kin, -1) if 0 <= kin < 400 or kin >= 0x4000 else -1
        rows.append([
            k, i, gname[i], sjis(g[0:7]), sjis(g[7:14]), sjis(g[14:19]), sjis(g[19:26]),
            face, face_src, i // 2 % 5, kin, ref(parent, gname),
            g[0x1E], 1180 - g[0x1E] if g[0x1E] else "", ref(g[0x1F], pname),
            *("○" if g[0x20] & m else "×" for m, _ in SKILLS),
            *(1 if g[0x21] & m else 0 for m, _ in TRAITS),
            STATUS.get(g[0x27], g[0x27]), ref(u16(g, 0x3C), cname), ref(u16(g, 0x3E), pname),
            ref(u16(g, 0x25), gname), ref(u16(g, 0x29), rname), ref(u16(g, 0x3A), tname),
            ref(u16(g, 0x23), gname),
            u16(g, 0x2B), g[0x2D], g[0x2F],
            g[0x31], g[0x32], g[0x33], g[0x34], g[0x35], g[0x36], g[0x37], g[0x38], g[0x39],
            g[0x42], u16(g, 0x40), g.hex()])
    out["generals"] = ([
        "scenario", "id", "name", "surname", "surname_kana", "given", "given_kana",
        "face", "face_src", "face_bg", "kin", "parent", "age1180", "born", "home?",
        *(n for _, n in SKILLS), *(n for _, n in TRAITS),
        "status", "clan", "location", "lord?", "rank", "treasure", "next_in_place",
        "mobilize", "b2d", "troop_quality",
        "武力", "勇名", "弓術", "知才", "優雅", "忠節", "菩提", "無常", "加護",
        "体力", "w40", "raw"], rows)

    rows = []
    for i, c in enumerate(C):
        lead = u16(c, 0)
        rows.append([k, i, ref(lead, gname), CLAN_TYPE.get(u16(c, 2), u16(c, 2)),
                     *(u16(c, o) for o in (4, 6, 8, 10)), u16(c, 0x0C), u16(c, 0x0E),
                     u16(c, 0x10), u16(c, 0x12),
                     sum(1 for p in P if u16(p, 0x28) == i),
                     sum(1 for g in G if u16(g, 0x3C) == i) if lead >= 0 else 0])
    out["clans"] = (["scenario", "id", "leader", "type", "rel_c0", "rel_c1", "rel_c2",
                     "rel_c3", "color", "court?", "government", "w12", "n_places",
                     "n_generals"], rows)

    rows = []
    for i, p in enumerate(P):
        nid = u16(p, 0x4A)
        nd = nodes[nid]
        members = chain(u16(p, 0x20), lambda x: u16(G[x], 0x23))
        ronin = chain(u16(p, 0x24), lambda x: u16(G[x], 0x23))
        rows.append([
            k, i, pname[i], sjis(p[9:18]), ref(u16(p, 0x26), rgname),
            ref(u16(p, 0x28), cname),
            ref(members[0] if members else -1, gname), len(members), len(ronin),
            ",".join(pname[a] for a in (u16(p, 0x12 + 2 * j) for j in range(7)) if a >= 0),
            *(u16(p, o) for o in range(0x2A, 0x3E, 2)),
            *(u16(p, o) for o in range(0x3E, 0x46, 2)), u16(p, 0x46), u16(p, 0x48),
            nid, u16(nd, 0), u16(nd, 2), nd[7], *minimap[i]])
    out["places"] = ([
        "scenario", "id", "name", "kana", "region", "clan", "governor", "n_members",
        "n_ronin", "adjacent", "pop_max?", "population", "commerce", "security",
        "farm_max?", "farm", "gold", "food", "soldiers", "soldier_quality",
        "w3e", "w40", "w42", "w44", "flags", "w48",
        "map_node", "map_x", "map_y", "battle_map?", "mini_x", "mini_y"], rows)

    out["regions"] = (["scenario", "id", "name", "b06", "w07"],
                      [[k, i, rgname[i], r[6], u16(r, 7)] for i, r in enumerate(RG)])

    out["ranks"] = (["scenario", "id", "name", "held", "holder", "mobilize", "military?",
                     "court?", "w11"],
                    [[k, i, rname[i], 1 if r[13] == 0x50 else 0,
                      ref(rank_holder.get(i, -1), gname), r[14] * 100, r[15], r[16],
                      u16(r, 17)] for i, r in enumerate(R)])

    out["treasures"] = (["scenario", "id", "name", "kind", "value", "flags", "icon",
                         "b11", "owner", "next"],
                        [[k, i, tname[i], TREASURE_KIND[t[13]] if t[13] < 11 else t[13],
                          t[14], f"{t[15]:02x}", t[16], t[17],
                          ref(t_owner.get(i, -1), gname), u16(t, 0x0B)]
                         for i, t in enumerate(T)])
    return out


def scenario_row(k: int, s: bytes, block: bytes) -> list:
    G = recs(block, GENERALS, 71, N_GENERALS)
    gname = [sjis(g[0:7]) + sjis(g[14:19]) for g in G]
    C = recs(block, CLANS, 20, N_CLANS)
    clans = [c for c in struct.unpack_from("<16h", s, 4) if c >= 0]
    leaders = ",".join(f"{c}:{gname[u16(C[c], 0)]}" for c in clans)
    return [k, u16(s, 0), s[2] + 1, s[3], leaders, u16(s, 0x24),
            block[UNKNOWN32:UNKNOWN32 + 32].hex()]


def map_tables(exe: bytes, P0: list[bytes]) -> tuple[list[bytes], list[tuple], tuple]:
    nodes = recs(exe, NODES, 11, N_NODES)
    minimap = [struct.unpack_from("<HH", exe, MINIMAP + 4 * i) for i in range(N_PLACES)]
    base = {u16(p, 0x4A): sjis(p[0:9]) for p in P0}
    rows = []
    for n, r in enumerate(nodes):
        nb = [struct.unpack_from("<H", exe, EDGES + 16 * n + 4 * j)[0] for j in range(4)]
        rows.append([n, u16(r, 0), u16(r, 2), r[4], NODE_TYPE.get(r[4], ""), r[7],
                     base.get(n, ""), ",".join(str(x) for x in nb if x < N_NODES),
                     r[5:7].hex(), r[8:11].hex()])
    cols = ["node", "x", "y", "type", "dot", "battle_map?", "place", "neighbours",
            "b05", "b08"]
    return nodes, minimap, (cols, rows)


def battle_tables(hc: bytes, nodes: list[bytes]) -> dict:
    used: dict[int, list[str]] = {}
    for n, r in enumerate(nodes):
        used.setdefault(r[7], []).append(str(n))
    rows = []
    for m in range(40):
        h = hc[m * 196:(m + 1) * 196]
        rows.append([m, ",".join(used.get(m, [])), max(h),
                     " ".join("".join(str(v) for v in h[y * 14:(y + 1) * 14]) for y in range(14))])
    obj = []
    for m in range(37):
        rec = hc[0x1EA0 + m * 60:0x1EA0 + (m + 1) * 60]
        for e in range(20):
            t, a, b = rec[e * 3:e * 3 + 3]
            if t == 0:
                break
            obj.append([m, e, t, a, b, a * 13 + b])
    return {"battle_maps": (["map", "nodes", "max_height", "heights_14x14"], rows),
            "battle_objects": (["map", "entry", "type", "a", "b", "cell"], obj)}


def write_tsv(path: Path, cols: list, rows: list) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", quoting=csv.QUOTE_NONE, quotechar=None,
                       lineterminator="\n")
        w.writerow(cols)
        w.writerows(rows)
    print(f"{path.name}: {len(rows)} rows")


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    game, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)

    sn = (game / "Sndata.gp").read_bytes()
    assert len(sn) == 4 * SCEN_SIZE, len(sn)
    exe = unpack_exe.unpack((game / "Main.exe").read_bytes())
    scen = [sn[k * SCEN_SIZE:(k + 1) * SCEN_SIZE] for k in range(4)]
    blocks = [s[SCEN_HEADER:] for s in scen]

    nodes, minimap, node_table = map_tables(exe, recs(blocks[0], PLACES, 76, N_PLACES))
    merged: dict[str, tuple[list, list]] = {}
    for k in range(4):
        for name, (cols, rows) in scenario_tables(k, blocks[k], nodes, minimap).items():
            merged.setdefault(name, (cols, []))[1].extend(rows)
    write_tsv(out / "scenarios.tsv",
              ["scenario", "year", "month", "b03", "clans", "w24", "unknown32"],
              [scenario_row(k, scen[k], blocks[k]) for k in range(4)])
    for name, (cols, rows) in merged.items():
        write_tsv(out / f"{name}.tsv", cols, rows)
    write_tsv(out / "map_nodes.tsv", *node_table)
    for name, (cols, rows) in battle_tables((game / "Hchikei.gp").read_bytes(), nodes).items():
        write_tsv(out / f"{name}.tsv", cols, rows)

    # Main.exe keeps a copy of the 1180 tables; report where it differs.
    m = exe[MAIN_BLOCK[0]:MAIN_BLOCK[1]]
    b = blocks[0]
    for label, mo, so, size in [("generals..places", 0, 0, UNKNOWN32),
                                ("regions", MAIN_REGIONS, REGIONS, N_REGIONS * 9),
                                ("ranks", MAIN_RANKS, RANKS, N_RANKS * 19),
                                ("treasures", MAIN_TREASURES, TREASURES, N_TREASURES * 18)]:
        diff = sum(1 for i in range(size) if m[mo + i] != b[so + i])
        print(f"Main.exe vs 1180 {label}: {diff} bytes differ")


if __name__ == "__main__":
    main()
