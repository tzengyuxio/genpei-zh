#!/usr/bin/env python3
"""Scan a binary for runs of Shift-JIS / ASCII text.

Reports byte offset, length and decoded text for every run that looks
like Japanese game text, so we can locate which files hold translatable
strings. Ported from kami-zh/tools/sjis_scan.py.
"""
from __future__ import annotations

import sys
import unicodedata


def is_sjis_lead(b: int) -> bool:
    return 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xEF


def is_sjis_trail(b: int) -> bool:
    return 0x40 <= b <= 0x7E or 0x80 <= b <= 0xFC


def is_halfwidth_kana(b: int) -> bool:
    return 0xA1 <= b <= 0xDF


def plausible(ch: str) -> bool:
    return not unicodedata.category(ch).startswith("C")


def is_japanese(ch: str) -> bool:
    cp = ord(ch)
    return (
        0x3040 <= cp <= 0x30FF        # hiragana / katakana
        or 0x4E00 <= cp <= 0x9FFF     # kanji
        or 0xFF66 <= cp <= 0xFF9D     # halfwidth katakana
        or 0xFF01 <= cp <= 0xFF5E     # fullwidth ASCII
        or ch in "「」『』、。・ー～　"
    )


def japanese_ratio(text: str) -> float:
    if not text:
        return 0.0
    return sum(1 for c in text if is_japanese(c)) / len(text)


def scan(data: bytes, min_chars: int = 3):
    runs = []
    i = 0
    n = len(data)
    while i < n:
        start = i
        chars = []
        while i < n:
            b = data[i]
            if is_sjis_lead(b) and i + 1 < n and is_sjis_trail(data[i + 1]):
                try:
                    ch = data[i:i + 2].decode("cp932")
                except UnicodeDecodeError:
                    break
                if not plausible(ch):
                    break
                chars.append(ch)
                i += 2
            elif is_halfwidth_kana(b):
                chars.append(bytes([b]).decode("cp932"))
                i += 1
            elif 0x20 <= b <= 0x7E:
                chars.append(chr(b))
                i += 1
            else:
                break
        if len(chars) >= min_chars:
            runs.append((start, i - start, "".join(chars)))
        if i == start:
            i += 1
    return runs


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--min-chars", type=int, default=3)
    ap.add_argument("--min-jp", type=float, default=0.0,
                    help="drop runs whose Japanese ratio is below this")
    ap.add_argument("--summary", action="store_true",
                    help="one line per file")
    ap.add_argument("--xor", type=lambda s: int(s, 0), default=0,
                    help="XOR every byte with this key before scanning")
    args = ap.parse_args()

    for path in args.files:
        data = open(path, "rb").read()
        if args.xor:
            data = bytes(b ^ args.xor for b in data)
        runs = [r for r in scan(data, args.min_chars)
                if japanese_ratio(r[2]) >= args.min_jp]
        if not args.summary:
            for off, length, text in runs:
                print(f"{off:08x}  {length:4d}  {text}")
        total = sum(length for _, length, _ in runs)
        pct = total * 100 // max(len(data), 1)
        print(f"--- {path}: {len(runs)} runs, {total} bytes "
              f"({pct}% of file)")


if __name__ == "__main__":
    main()
