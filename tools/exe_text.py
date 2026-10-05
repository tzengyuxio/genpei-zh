#!/usr/bin/env python3
"""Extract the text of Main.exe / Open.exe / End.exe into TSVs.

All three are MS C 7 programs; their strings live in DGROUP, found from
the startup code (`mov di, DGROUP` at entry+0Dh). Everything before it is
code and only yields scanner noise, so only DGROUP is scanned.

Main.exe is packed (tools/unpack_exe.py); it is unpacked in memory, so
every offset in its TSVs is a file offset in the *unpacked* Main.exe,
which is what tools/patch.py patches in build/GENPEI/. Unpacked, it has

    0x000000 .. DATA_START   header + code
    DATA_START .. UI_START   far data: the scenario tables -- generals
                             (71-byte records, same layout as Sndata.gp),
                             court figures, places, treasures, ranks
    UI_START .. end          UI strings, almost all in DGROUP (514Ah)

Output, deduplicated by text (`offsets` lists every copy):

    extracted/text/<exe>.tsv       UI strings (kind `ui`)
    extracted/text/main_data.tsv   Main.exe table fields (`name`/`reading`)

Text notation is the one of tools/message.py: {C6} for ESC C6, {K}/{H}
for ESC K/H, \\n for newline. Menu items are space-padded to centre them
on their buttons; `max_bytes` includes the padding.

    python3 tools/exe_text.py game/GENPEI/Main.exe game/GENPEI/Open.exe \\
                              game/GENPEI/End.exe
"""
from __future__ import annotations

import csv
import re
import struct
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from unpack_exe import unpack  # noqa: E402

DATA_START = 0x4A570    # Main.exe: first general, 源 ﾐﾅﾓﾄ 頼朝 ﾖﾘﾄﾓ
UI_START = 0x54690      # Main.exe: after the last rank (前太政大臣)

FIELDS = ["id", "offsets", "max_bytes", "kind", "original_ja",
          "translation_zh"]


def is_lead(b: int) -> bool:
    return 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xEF


def scan(data: bytes, start: int, end: int):
    """Yield (offset, raw bytes, display tokens, first full-width char).

    first_fw is (file offset, token index) of the first kanji/kana/full-width
    form, or None; Cyrillic/Greek/box rows of Shift-JIS do not count, they
    only show up in binary noise here."""
    i = start
    while i < end:
        j = i
        out = []
        first_fw = None
        while j < end:
            b = data[j]
            if is_lead(b) and 0x40 <= data[j + 1] <= 0xFC and data[j + 1] != 0x7F:
                try:
                    out.append(data[j:j + 2].decode("cp932"))
                except UnicodeDecodeError:
                    break
                if first_fw is None and \
                        unicodedata.east_asian_width(out[-1]) in "WF":
                    first_fw = (j, len(out) - 1)
                j += 2
            elif b == 0x1B and data[j + 1:j + 2] == b"C" and \
                    data[j + 2:j + 3].isdigit():
                out.append("{C" + chr(data[j + 2]) + "}")
                j += 3
            elif b == 0x1B and data[j + 1] in b"KH":
                out.append("{" + chr(data[j + 1]) + "}")
                j += 2
            elif 0xA1 <= b <= 0xDF:
                out.append(bytes([b]).decode("cp932"))
                j += 1
            elif b == 0x0A:
                out.append("\\n")
                j += 1
            elif 0x20 <= b <= 0x7E:
                out.append("\\\\" if b == 0x5C else chr(b))
                j += 1
            else:
                break
        if j > i and data[j] == 0x00:
            yield i, data[i:j], out, first_fw
        i = j + 1 if j == i else j


JUNK_ASCII = set("^!\"#$&*+;<=>@[]_`|~")
PRINTF = re.compile(r"%[-0-9]*[dusxcBNWD][0-9]?")


def is_wide(tok: str) -> bool:
    return len(tok) == 1 and unicodedata.east_asian_width(tok) in "WF"


def anchor(toks: list[str]) -> int | None:
    """Index of the first full-width char that is not junk: a wide char
    glued to an ASCII letter, digit or odd symbol ("邑JQ", "咤^3") comes
    from binary data."""
    for i, t in enumerate(toks):
        nxt = toks[i + 1] if i + 1 < len(toks) else ""
        if is_wide(t) and not (len(nxt) == 1 and nxt.isascii() and
                               (nxt.isalnum() or nxt in JUNK_ASCII)):
            return i
    return None


def plausible_prefix(toks: list[str], whole: bool) -> bool:
    """Text allowed before a string's first full-width character; `whole`
    means nothing was cut off, i.e. it starts right after a NUL."""
    s = re.sub(r"\{[A-Z]\d?\}", "", "".join(toks))
    if whole and re.fullmatch(r"[\uff66-\uff9f]{3,}\d*", s):
        return True                           # "ｱﾅﾛｸﾞ16色": narrow-kana label
    if whole and re.match(r"[A-Za-z]%", s):
        s = s[1:]                             # "S%u": slot label + argument
    rest = PRINTF.sub("", s)
    if re.fullmatch(r"\d+", rest):
        return False                          # bare digit glued to text
    return re.fullmatch(r"[\s\d\-]*", rest) is not None


def token_size(tok: str) -> int:
    if tok.startswith("{"):
        return len(tok) - 1                   # {C6} -> ESC C 6
    if tok in ("\\n", "\\\\"):
        return 1
    return len(tok.encode("cp932"))


def jis0208(raw: bytes) -> bool:
    """False if the bytes use cp932's NEC/IBM extension rows."""
    i = 0
    while i < len(raw):
        if is_lead(raw[i]):
            if raw[i] == 0x87 or raw[i] >= 0xED:
                return False
            i += 2
        else:
            i += 1
    return True


def is_level2(text: str) -> bool:
    try:
        b = text.encode("cp932")
    except UnicodeEncodeError:
        return False
    return len(b) == 2 and (b[0] << 8 | b[1]) >= 0x989F


def clean(toks: list[str]) -> int | None:
    """Number of junk tokens in front of the string, None if it is junk.

    Strings often follow a pointer table whose bytes decode as junk like
    "^3" or "G!G" glued in front: cut at the first token from which the
    part before the anchor (first real full-width char) is plausible."""
    k = anchor(toks)
    if k is None:
        return None
    return next(c for c in range(k + 1)
                if plausible_prefix(toks[c:k], whole=c == 0))


def dgroup(data: bytes) -> int:
    """File offset of DGROUP, from the MS C startup code."""
    hdr = struct.unpack_from("<14H", data, 0)
    entry = hdr[4] * 16 + hdr[11] * 16 + hdr[10]
    if data[entry:entry + 4] != bytes.fromhex("b430cd21") or data[entry + 13] != 0xBF:
        raise ValueError("not an MS C startup")
    return hdr[4] * 16 + struct.unpack_from("<H", data, entry + 14)[0] * 16


def extract(data: bytes, ui_start: int, tables: bool):
    ds = dgroup(data)
    ui, table = {}, {}
    for off, raw, toks, first_fw in scan(data, ui_start, len(data) - 1):
        if first_fw is None or (cut := clean(toks)) is None:
            continue                     # no UI text in it
        skip = sum(token_size(t) for t in toks[:cut])
        off, raw, toks = off + skip, raw[skip:], toks[cut:]
        text = "".join(toks)
        if not jis0208(raw):
            continue
        if len(toks) == 1 and (off < ds or is_level2(text)):
            continue                     # stray single kanji in data
        ui.setdefault(text, (len(raw), []))[1].append(off)
    for off, raw, toks, first_fw in scan(data, DATA_START, UI_START if tables else 0):
        text = "".join(toks)
        if first_fw is None:
            if len(text) < 2 or \
                    not all(0xFF61 <= ord(c) <= 0xFF9F for c in text):
                continue
            kind = "reading"
        else:
            # table fields start right after NUL padding: nothing to cut
            if clean(toks) != 0 or not jis0208(raw) or \
                    (len(toks) == 1 and is_level2(text)):
                continue
            kind = "name"
        table.setdefault((kind, text), (len(raw), []))[1].append(off)
    return ui, table


def write(path: Path, rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, FIELDS, delimiter="\t", lineterminator="\n",
                           quoting=csv.QUOTE_NONE, quotechar=None)
        w.writeheader()
        for i, (kind, text, size, offs) in enumerate(rows):
            w.writerow({"id": i,
                        "offsets": ",".join(f"0x{o:X}" for o in offs),
                        "max_bytes": size, "kind": kind,
                        "original_ja": text, "translation_zh": ""})


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("exe", nargs="+", type=Path)
    ap.add_argument("--outdir", type=Path, default=Path("extracted/text"))
    args = ap.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)
    for exe in args.exe:
        data = exe.read_bytes()
        try:
            data = unpack(data)
        except ValueError:
            pass                         # not packed
        is_main = data[DATA_START:DATA_START + 2] == "源".encode("cp932")
        ui, table = extract(data, UI_START if is_main else dgroup(data),
                            tables=is_main)
        outputs = [(exe.stem.lower() + ".tsv",
                    [("ui", t, s, o) for t, (s, o) in ui.items()])]
        if is_main:
            outputs.append(("main_data.tsv",
                            [(k, t, s, o) for (k, t), (s, o) in table.items()]))
        for name, rows in outputs:
            rows.sort(key=lambda r: r[3][0])
            write(args.outdir / name, rows)
            copies = sum(len(r[3]) for r in rows)
            chars = sum(len(r[1]) for r in rows)
            print(f"{exe.name} -> {name}: {len(rows)} unique strings "
                  f"({copies} copies), ~{chars} chars")


if __name__ == "__main__":
    main()
