#!/usr/bin/env python3
"""In-place patch a DOS EXE with translated Shift-JIS strings.

Reads TSVs from tools/main_text.py (column `offsets`, a comma-separated
list of every copy of the string) or tools/text.py (column `offset_hex`),
takes the rows with a `translation_zh`, encodes them, checks them and
writes each one over every listed slot, NUL-padding the rest of the slot.

Text notation is shared with tools/message.py: {C6} = ESC C6, {K}/{H} =
ESC K/H, \\n = newline, \\\\ = backslash.

    python3 tools/patch.py --check translation/main.tsv --target build/GENPEI/Main.exe
    python3 tools/patch.py --apply translation/main.tsv --target build/GENPEI/Main.exe

Main.exe must be the unpacked one (tools/unpack_exe.py); the TSV offsets
refer to it. A row is rejected when its Shift-JIS is longer than
`max_bytes`, uses a character outside JIS X 0208, changes the printf
arguments or ESC codes, or when the file no longer holds the original at
that offset. Any rejection aborts without touching the file.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from message import PRINTF, from_display  # noqa: E402

ESC = re.compile(rb"\x1b(?:C\d|[A-Z])")


def load(tsv: Path) -> list[dict]:
    with tsv.open(encoding="utf-8") as f:
        rows = csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE,
                              quotechar=None)
        plan = []
        for row in rows:
            if not row.get("translation_zh", "").strip():
                continue
            offs = row.get("offsets") or row["offset_hex"]
            plan.append({
                "id": row["id"],
                "offsets": [int(o, 16) for o in offs.split(",")],
                "max_bytes": int(row["max_bytes"]),
                "original": row["original_ja"],
                "translation": row["translation_zh"],
            })
        return plan


def check(item: dict, data: bytes) -> tuple[bytes | None, str | None]:
    tag = f"[{item['id']}]"
    try:
        new = from_display(item["translation"])
    except UnicodeEncodeError as e:
        return None, f"{tag} {e.object[e.start:e.end]!r} is not in JIS X 0208"
    old = from_display(item["original"])
    if len(new) > item["max_bytes"]:
        return None, (f"{tag} {len(new)} bytes > max {item['max_bytes']}: "
                      f"{item['translation']!r}")
    for name, pat in (("printf arguments", PRINTF), ("ESC codes", ESC)):
        if Counter(pat.findall(new)) != Counter(pat.findall(old)):
            return None, (f"{tag} {name} differ: {pat.findall(old)} vs "
                          f"{pat.findall(new)}")
    for off in item["offsets"]:
        if data[off:off + len(old)] != old:
            return None, f"{tag} 0x{off:X} no longer holds {item['original']!r}"
    return new, None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("tsv", nargs="+", type=Path)
    ap.add_argument("--target", type=Path, required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    data = bytearray(args.target.read_bytes())
    plan = [item for tsv in args.tsv for item in load(tsv)]
    if not plan:
        print("no translations in TSV(s) -- nothing to do")
        return
    encoded, errors = [], []
    for item in plan:
        new, err = check(item, data)
        if err:
            errors.append(err)
        else:
            encoded.append((item, new))
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    slots = sum(len(item["offsets"]) for item, _ in encoded)
    print(f"{len(encoded)} translations ({slots} slots) ready for {args.target}")
    if not args.apply:
        return
    size = len(data)
    for item, new in encoded:
        for off in item["offsets"]:
            data[off:off + item["max_bytes"]] = new.ljust(item["max_bytes"],
                                                          b"\0")
    assert len(data) == size
    args.target.write_bytes(bytes(data))
    print(f"applied to {args.target} ({size} bytes, size unchanged)")


if __name__ == "__main__":
    main()
