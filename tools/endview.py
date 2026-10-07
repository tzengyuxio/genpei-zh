#!/usr/bin/env python3
"""Play the ending (End.exe) without beating the game.

End.exe does not read Savedata.gp. Its only input is a byte the launcher
keeps for it: Genpei.com installs an INT 65h service (AH=3..8 are six word
slots, AL=0 stores BX, AL!=0 returns the slot in AX), Main.exe stores the
winner's clan kind in slot AH=6 just before it exits with code 0, and
End.exe reads it back with AX=0601h:

  0  Genji clan (clan +0x02 == 0)
  1  Heike clan (clan +0x02 == 1)
  2  anyone else (Fujiwara, local lords)

Run alone, End.exe has no INT 65h handler, so it stops after the first
narration. This tool copies build/GENPEI to a scratch directory, replaces
Open.exe and Main.exe there with a 13-byte COM that stores the chosen
value and exits with code 0, and runs the real Genpei.com, which then
launches End.exe as in a real game. build/GENPEI itself is not touched.

  endview.py genji|heike|other [--dir DIR] [--record SECONDS]

Without --record DOSBox-X opens interactively; with it the session is
recorded to DIR/captures/ and DOSBox-X exits after SECONDS.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / 'build/GENPEI'
CONF = ROOT / 'tools/dosbox/genpei.conf'
ENDINGS = {'genji': 0, 'heike': 1, 'other': 2}


def stub(value: int) -> bytes:
    """mov ax,0600h / mov bx,value / int 65h / mov ax,4C00h / int 21h"""
    return bytes([0xB8, 0x00, 0x06, 0xBB, value, 0x00, 0xCD, 0x65,
                  0xB8, 0x00, 0x4C, 0xCD, 0x21])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('ending', choices=ENDINGS)
    ap.add_argument('--dir', type=Path, default=ROOT / 'build/endtest')
    ap.add_argument('--record', type=int, metavar='SECONDS')
    a = ap.parse_args()

    game = a.dir / 'GENPEI'
    if game.exists():
        shutil.rmtree(game)
    shutil.copytree(BUILD, game)
    for name in ('Open.exe', 'Main.exe'):
        (game / name).write_bytes(stub(ENDINGS[a.ending]))
    captures = a.dir / 'captures'
    captures.mkdir(parents=True, exist_ok=True)
    for old in captures.glob('*.avi'):
        old.unlink()  # so the new recording is always end_000.avi

    # End.exe opens A:ENDDAT.GP etc., so run everything from drive A:
    conf = a.dir / 'endview.conf'
    lines = CONF.read_text().replace('@ROOT@', str(ROOT))
    lines = lines.replace('captures = build/captures', f'captures = {captures}')
    lines += f'mount a "{game}"\na:\n'
    if a.record:
        lines += 'config -avistart\n'
    lines += 'Genpei.com\n'
    conf.write_text(lines)

    args = ['dosbox-x', '-conf', str(conf), '-nopromptfolder', '-fastlaunch', '-nolog']
    if not a.record:
        subprocess.run(args)
        return
    proc = subprocess.Popen(args + ['-time-limit', str(a.record), '-exit'])
    try:
        proc.wait(timeout=a.record + 30)
    except subprocess.TimeoutExpired:
        proc.kill()  # DOSBox-X on macOS sometimes hangs past -time-limit
        print('watchdog: killed hung dosbox-x')
    time.sleep(1)
    print('\n'.join(str(p) for p in sorted(captures.glob('*.avi'))))


if __name__ == '__main__':
    main()
