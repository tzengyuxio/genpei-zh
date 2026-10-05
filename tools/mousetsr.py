#!/usr/bin/env python3
"""Build a DOS TSR that feeds the game a scripted mouse.

The game drives its menus with the mouse -- the arrow on screen is the
pointer and a left click activates an item -- so automating it means
automating the mouse. DOSBox-X cannot inject mouse input (AUTOTYPE is
keyboard only and the mapper has no pointer events), hence this TSR.

Faking INT 33h function 3 alone is not enough: the game registers a mouse
event handler (function 0Ch, movement mask) and only refreshes its pointer
when that handler fires. So the TSR emulates the driver properly:

  INT 33h  function 3   -> answer from the script
           function 0Ch -> capture the game's callback and mask
           anything else-> chain to the real driver
  INT 1Ch  (18.2 Hz)    -> when the scripted state changes, call the game's
                           callback with the usual driver register contract
                           (AX event flags, BX buttons, CX x, DX y, SI/DI
                           deltas), masked by what the game subscribed to
                           and guarded against re-entry

Time comes from the BIOS tick counter at 0040:006Ch, sampled at install.
Script entries are (seconds, x, y, buttons); the one in force is the first
whose `seconds` exceeds the elapsed time. buttons bit 0 is the left button.
Coordinates are in the game's 640x480 DOS/V screen.
"""
from __future__ import annotations

import struct
import sys

TICKS_PER_SEC = 18.2065
ORG = 0x100


class Asm:
    """Just enough two-pass assembler for the handful of forms used here."""

    def __init__(self, org=ORG):
        self.org = org
        self.items = []
        self.labels = {}

    def raw(self, b): self.items.append(('raw', bytes(b)))
    def label(self, name): self.items.append(('label', name))
    def rel8(self, op, target): self.items.append(('rel8', bytes(op), target))
    def rel16(self, op, target): self.items.append(('rel16', bytes(op), target))

    def at(self, pre, target, post=b''):
        """Instruction carrying a 16-bit absolute address of `target`."""
        self.items.append(('at', bytes(pre), target, bytes(post)))

    @staticmethod
    def _size(it):
        k = it[0]
        if k == 'raw': return len(it[1])
        if k == 'label': return 0
        if k == 'rel8': return len(it[1]) + 1
        if k == 'rel16': return len(it[1]) + 2
        if k == 'at': return len(it[1]) + 2 + len(it[3])
        raise ValueError(k)

    def assemble(self) -> bytes:
        pos = self.org
        for it in self.items:
            if it[0] == 'label':
                self.labels[it[1]] = pos
            else:
                pos += self._size(it)
        out = bytearray()
        pos = self.org
        for it in self.items:
            nxt = pos + self._size(it)
            if it[0] == 'raw':
                out += it[1]
            elif it[0] == 'rel8':
                d = self.labels[it[2]] - nxt
                assert -128 <= d <= 127, (it[2], d)
                out += it[1] + struct.pack('<b', d)
            elif it[0] == 'rel16':
                out += it[1] + struct.pack('<h', self.labels[it[2]] - nxt)
            elif it[0] == 'at':
                out += it[1] + struct.pack('<H', self.labels[it[2]]) + it[3]
            pos = nxt
        return bytes(out)


def _emit(script, paragraphs: int) -> bytes:
    a = Asm()
    a.rel16(b'\xe9', 'install')                 # jmp install

    a.label('old33');     a.raw(b'\x00\x00')
    a.label('old33_seg'); a.raw(b'\x00\x00')
    a.label('old1c');     a.raw(b'\x00\x00')
    a.label('old1c_seg'); a.raw(b'\x00\x00')
    a.label('base_tick'); a.raw(b'\x00\x00')
    a.label('cb_off');    a.raw(b'\x00\x00')
    a.label('cb_seg');    a.raw(b'\x00\x00')
    a.label('cb_mask');   a.raw(b'\x00\x00')
    a.label('last_x');    a.raw(b'\xff\xff')
    a.label('last_y');    a.raw(b'\xff\xff')
    a.label('last_btn');  a.raw(b'\x00\x00')
    a.label('busy');      a.raw(b'\x00')

    table = b''
    for seconds, x, y, buttons in script:
        ticks = min(0xFFFF, int(seconds * TICKS_PER_SEC))
        table += struct.pack('<4H', ticks, x, y, buttons)
    table += struct.pack('<4H', 0xFFFF, script[-1][1], script[-1][2], 0)
    a.label('table'); a.raw(table)

    # calc: elapsed ticks -> cx = x, dx = y, bx = buttons
    a.label('calc')
    a.raw(b'\x1e\x56')                          # push ds / push si
    a.raw(b'\xb8\x40\x00\x8e\xd8')              # mov ax,0040h / mov ds,ax
    a.raw(b'\xa1\x6c\x00')                      # mov ax,[006Ch]
    a.raw(b'\x0e\x1f')                          # push cs / pop ds
    a.at(b'\x2b\x06', 'base_tick')              # sub ax,[base_tick]
    a.at(b'\xbe', 'table')                      # mov si,table
    a.label('scan')
    a.raw(b'\x3b\x04')                          # cmp ax,[si]
    a.rel8(b'\x72', 'use')                      # jb use
    a.raw(b'\x83\xc6\x08')                      # add si,8
    a.rel8(b'\xeb', 'scan')                     # jmp scan
    a.label('use')
    a.raw(b'\x8b\x4c\x02\x8b\x54\x04\x8b\x5c\x06')
    a.raw(b'\x5e\x1f\xc3')                      # pop si / pop ds / ret

    # INT 33h
    a.label('h33')
    a.raw(b'\x3d\x03\x00'); a.rel8(b'\x74', 'h33_f3')
    a.raw(b'\x3d\x0c\x00'); a.rel8(b'\x74', 'h33_f0c')
    a.at(b'\x2e\xff\x2e', 'old33')              # jmp far [cs:old33]
    a.label('h33_f3')
    a.raw(b'\x50'); a.rel16(b'\xe8', 'calc'); a.raw(b'\x58\xcf')
    a.label('h33_f0c')
    a.at(b'\x2e\x89\x16', 'cb_off')             # mov [cs:cb_off],dx
    a.at(b'\x2e\x8c\x06', 'cb_seg')             # mov [cs:cb_seg],es
    a.at(b'\x2e\x89\x0e', 'cb_mask')            # mov [cs:cb_mask],cx
    a.raw(b'\xcf')

    # INT 1Ch
    a.label('h1c')
    a.raw(b'\x9c'); a.at(b'\x2e\xff\x1e', 'old1c')   # pushf / call far [cs:old1c]
    a.raw(b'\x50\x53\x51\x52\x56\x57\x1e\x06')       # push ax bx cx dx si di ds es
    a.at(b'\x2e\x80\x3e', 'busy', b'\x00'); a.rel8(b'\x75', 'h1c_done')
    a.at(b'\x2e\x83\x3e', 'cb_mask', b'\x00'); a.rel8(b'\x74', 'h1c_done')
    a.rel16(b'\xe8', 'calc')
    a.raw(b'\x31\xc0')                          # xor ax,ax
    a.at(b'\x2e\x3b\x0e', 'last_x'); a.rel8(b'\x75', 'h1c_moved')
    a.at(b'\x2e\x3b\x16', 'last_y'); a.rel8(b'\x74', 'h1c_nomove')
    a.label('h1c_moved'); a.raw(b'\x0d\x01\x00')    # or ax,1  (movement)
    a.label('h1c_nomove')
    a.at(b'\x2e\x3b\x1e', 'last_btn'); a.rel8(b'\x74', 'h1c_nobtn')
    a.raw(b'\xf7\xc3\x01\x00'); a.rel8(b'\x74', 'h1c_release')
    a.raw(b'\x0d\x02\x00'); a.rel8(b'\xeb', 'h1c_nobtn')   # or ax,2  (press)
    a.label('h1c_release'); a.raw(b'\x0d\x04\x00')         # or ax,4  (release)
    a.label('h1c_nobtn')
    a.raw(b'\x09\xc0'); a.rel8(b'\x74', 'h1c_done')
    a.at(b'\x2e\x89\x0e', 'last_x')
    a.at(b'\x2e\x89\x16', 'last_y')
    a.at(b'\x2e\x89\x1e', 'last_btn')
    # A real driver only calls the handler for events the game asked for.
    # This game asks for movement only and polls function 3 for buttons, so
    # passing it unmasked button bits upsets its state machine.
    a.at(b'\x2e\x23\x06', 'cb_mask')         # and ax,[cs:cb_mask]
    a.rel8(b'\x74', 'h1c_done')
    a.at(b'\x2e\xc6\x06', 'busy', b'\x01')
    a.raw(b'\x31\xf6\x31\xff')                  # xor si,si / xor di,di
    a.at(b'\x2e\xff\x1e', 'cb_off')             # call far [cs:cb_off]
    a.at(b'\x2e\xc6\x06', 'busy', b'\x00')
    a.label('h1c_done')
    a.raw(b'\x07\x1f\x5f\x5e\x5a\x59\x5b\x58\xcf')

    a.label('install')
    a.raw(b'\xb8\x33\x35\xcd\x21')              # mov ax,3533h / int 21h
    a.at(b'\x89\x1e', 'old33'); a.at(b'\x8c\x06', 'old33_seg')
    a.raw(b'\xb8\x1c\x35\xcd\x21')              # mov ax,351Ch / int 21h
    a.at(b'\x89\x1e', 'old1c'); a.at(b'\x8c\x06', 'old1c_seg')
    a.raw(b'\x1e\xb8\x40\x00\x8e\xd8\xa1\x6c\x00\x1f')
    a.at(b'\xa3', 'base_tick')
    a.at(b'\xba', 'h33'); a.raw(b'\xb8\x33\x25\xcd\x21')
    a.at(b'\xba', 'h1c'); a.raw(b'\xb8\x1c\x25\xcd\x21')
    a.raw(b'\xba' + struct.pack('<H', paragraphs))
    a.raw(b'\xb8\x00\x31\xcd\x21')              # TSR
    return a.assemble()


def build(script) -> bytes:
    if not script:
        raise ValueError('script is empty')
    probe = _emit(script, 0)
    paragraphs = (ORG + len(probe) + 15) >> 4
    return _emit(script, paragraphs)


def parse(spec: str):
    out = []
    for part in spec.split(';'):
        part = part.strip()
        if not part:
            continue
        sec, x, y, btn = (v.strip() for v in part.split(','))
        out.append((float(sec), int(x), int(y), int(btn)))
    return out


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        print('usage: mousetsr.py <out.com> "sec,x,y,btn; sec,x,y,btn; ..."')
        raise SystemExit(2)
    com = build(parse(sys.argv[2]))
    open(sys.argv[1], 'wb').write(com)
    print(f'{sys.argv[1]}: {len(com)} bytes')


if __name__ == '__main__':
    main()
