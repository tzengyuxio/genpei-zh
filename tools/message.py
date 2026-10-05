#!/usr/bin/env python3
"""Message.gp text: extract to TSV, rebuild from a translated TSV.

Message.gp is an LS11 container (tools/ls11.py) of 5 blocks. Each block is

    u16-LE offset[n]      (offset[0] = 2n, so the table sizes itself)
    message[n]            Shift-JIS bytes, offset[k] .. offset[k+1]

Inside a message:

    0x0A          newline                       TSV: \\n
    ESC K / ESC H half-width kana render as      dropped from original_ja,
                  katakana / hiragana            TSV: {K} {H}
    ESC C<d>      colour                         TSV: {C6}
    %s %u %B1 ... printf-style arguments         kept verbatim
    05 05 05      end of message (some 00 pad)   kept automatically

The game stores most kana as half-width katakana and draws them as
hiragana unless ESC K is active, so `original_ja` shows them converted for
readability. Translations are written as plain full-width text.

    python3 tools/message.py extract game/GENPEI/Message.gp extracted/text/message.tsv
    python3 tools/message.py apply game/GENPEI/Message.gp translation/message.tsv \\
                                   build/GENPEI/Message.gp
"""
from __future__ import annotations

import csv
import re
import struct
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import ls11  # noqa: E402

FIELDS = ["id", "block", "index", "max_cols", "lines",
          "original_ja", "translation_zh"]
PRINTF = re.compile(rb"%[0-9]*[A-Za-z][0-9]?")


def split_block(block: bytes) -> list[bytes]:
    n = struct.unpack_from("<H", block, 0)[0] // 2
    offs = list(struct.unpack_from(f"<{n}H", block, 0)) + [len(block)]
    return [block[offs[k]:offs[k + 1]] for k in range(n)]


def join_block(msgs: list[bytes]) -> bytes:
    off = 2 * len(msgs)
    table = bytearray()
    for m in msgs:
        table += struct.pack("<H", off)
        off += len(m)
    if off > 0xFFFF:
        raise ValueError(f"block too large for u16 offsets ({off} B)")
    return bytes(table) + b"".join(msgs)


def split_suffix(msg: bytes) -> tuple[bytes, bytes]:
    body = msg.rstrip(b"\x05\x00")
    return body, msg[len(body):]


def _kana(ch: str, katakana: bool) -> str:
    ch = unicodedata.normalize("NFKC", ch)
    if not katakana:
        ch = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c
                     for c in ch)
    return ch


def to_display(body: bytes) -> str:
    """Raw message body -> readable text with {codes}."""
    out = []
    kata = False
    i = 0
    while i < len(body):
        b = body[i]
        if b == 0x1B:
            op = chr(body[i + 1])
            if op == "K":
                kata = True
            elif op == "H":
                kata = False
            elif op == "C":
                out.append(f"{{C{chr(body[i + 2])}}}")
                i += 1
            else:
                out.append(f"{{{op}}}")
            i += 2
            continue
        if b == 0x0A:
            out.append("\\n")
            i += 1
            continue
        if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC:
            out.append(body[i:i + 2].decode("cp932"))
            i += 2
            continue
        if 0xA1 <= b <= 0xDF:
            # keep a kana and its following (han)dakuten together
            j = i + 1
            if j < len(body) and body[j] in (0xDE, 0xDF):
                j += 1
            out.append(_kana(body[i:j].decode("cp932"), kata))
            i = j
            continue
        out.append("\\\\" if b == 0x5C else chr(b))
        i += 1
    return "".join(out)


def from_display(text: str) -> bytes:
    """Translated TSV text -> raw message body."""
    out = bytearray()
    for tok in re.split(r"(\{[A-Z][0-9]?\}|\\n|\\\\)", text):
        if tok == "\\n":
            out += b"\n"
        elif tok == "\\\\":
            out += b"\\"
        elif re.fullmatch(r"\{[A-Z][0-9]?\}", tok):
            out += b"\x1b" + tok[1:-1].encode("ascii")
        elif tok:
            out += tok.encode("cp932")
    return bytes(out)


def columns(body: bytes) -> list[int]:
    """Display width of each line in half-width cells (codes take none).

    Half-width kana are drawn as full-width hiragana/katakana, so they
    take two cells; a following ﾞ/ﾟ merges into the same glyph."""
    widths = [0]
    i = 0
    while i < len(body):
        b = body[i]
        if b == 0x1B:
            i += 3 if body[i + 1:i + 2] == b"C" else 2
        elif b == 0x0A:
            widths.append(0)
            i += 1
        elif 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC:
            widths[-1] += 2
            i += 2
        elif b in (0xDE, 0xDF):
            i += 1
        else:
            widths[-1] += 2 if 0xA1 <= b <= 0xDD else 1
            i += 1
    return widths


def extract(src: Path, out: Path) -> None:
    _, blocks = ls11.read(src.read_bytes())
    rows = []
    for bi, block in enumerate(blocks):
        for k, msg in enumerate(split_block(block)):
            body, _ = split_suffix(msg)
            w = columns(body)
            rows.append({
                "id": f"{bi}-{k:03d}", "block": bi, "index": k,
                "max_cols": max(w), "lines": len(w),
                "original_ja": to_display(body), "translation_zh": "",
            })
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        wr = csv.DictWriter(f, FIELDS, delimiter="\t", lineterminator="\n",
                            quoting=csv.QUOTE_NONE, escapechar=None)
        wr.writeheader()
        wr.writerows(rows)
    chars = sum(len(re.sub(r"\{[A-Z][0-9]?\}|\\n", "", r["original_ja"]))
                for r in rows)
    print(f"{src}: {len(rows)} messages in {len(blocks)} blocks, "
          f"~{chars} characters -> {out}")


def load_translations(tsv: Path) -> dict[tuple[int, int], str]:
    with tsv.open(encoding="utf-8") as f:
        rows = csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        return {(int(r["block"]), int(r["index"])): r["translation_zh"]
                for r in rows if r.get("translation_zh", "").strip()}


def apply(src: Path, tsv: Path, dst: Path) -> None:
    dic, blocks = ls11.read(src.read_bytes())
    tr = load_translations(tsv)
    errors, warnings = [], []
    new_blocks = []
    for bi, block in enumerate(blocks):
        msgs = split_block(block)
        for k, msg in enumerate(msgs):
            if (bi, k) not in tr:
                continue
            tag = f"[{bi}-{k:03d}]"
            body, suffix = split_suffix(msg)
            try:
                new = from_display(tr[(bi, k)])
            except UnicodeEncodeError as e:
                errors.append(f"{tag} {e.object[e.start:e.end]!r} "
                              f"is not in JIS X 0208")
                continue
            if Counter(PRINTF.findall(new)) != Counter(PRINTF.findall(body)):
                errors.append(f"{tag} printf arguments differ: "
                              f"{PRINTF.findall(body)} vs "
                              f"{PRINTF.findall(new)}")
                continue
            ow, nw = columns(body), columns(new)
            if max(nw) > max(ow) or len(nw) > len(ow):
                warnings.append(f"{tag} {len(nw)} lines / {max(nw)} cols, "
                                f"original {len(ow)} / {max(ow)}")
            msgs[k] = new + suffix
        new_blocks.append(join_block(msgs))
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    dst.write_bytes(ls11.write(dic, new_blocks))
    sizes = ", ".join(str(len(b)) for b in new_blocks)
    print(f"applied {len(tr)} translations -> {dst} "
          f"(block sizes {sizes})")


def main() -> None:
    if len(sys.argv) >= 4 and sys.argv[1] == "extract":
        extract(Path(sys.argv[2]), Path(sys.argv[3]))
    elif len(sys.argv) >= 5 and sys.argv[1] == "apply":
        apply(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
