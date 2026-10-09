package main

import (
	"bytes"
	"encoding/binary"
	"errors"
)

// unpackExe expands the RLE-packed Main.exe into a plain MZ executable.
// Port of tools/unpack_exe.py (see there for the packer's layout); the
// patch is made against the unpacked image.
func unpackExe(exe []byte) ([]byte, error) {
	if len(exe) < 0x1c {
		return nil, errors.New("not an MZ executable")
	}
	w := func(b []byte, o int) int { return int(binary.LittleEndian.Uint16(b[o:])) }
	image := exe[w(exe, 8)*16:]
	cs := w(exe, 22)
	if cs*16+0x1978 > len(image) {
		return nil, errors.New("unknown packer stub")
	}
	stub := image[cs*16:]
	if !bytes.Equal(stub[1:7], []byte{0x9c, 0x50, 0x8c, 0xda, 0x52, 0x52}) {
		return nil, errors.New("unknown packer stub")
	}

	top := cs*16 + w(stub, 0x10)*16 - 16 + 0x10
	out := make([]byte, top)
	ctl := 0x1977
	src := cs*16 - 11
	dst := top - 1
	for r := w(stub, 0x2b); r > 0; r-- {
		b0 := int(stub[ctl])
		ctl--
		lit := int(stub[ctl])
		ctl--
		if b0&1 != 0 {
			lit = lit<<8 | int(stub[ctl])
			ctl--
		}
		fill := b0 >> 2
		if b0&2 != 0 {
			fill = fill<<8 | int(stub[ctl])
			ctl--
		}
		value := stub[ctl]
		ctl--
		if dst+1 < lit+fill || src+1 < lit {
			return nil, errors.New("bad packed image")
		}
		for ; lit > 0; lit-- {
			out[dst] = image[src]
			dst--
			src--
		}
		for ; fill > 0; fill-- {
			out[dst] = value
			dst--
		}
	}
	if dst != -1 {
		return nil, errors.New("bad packed image")
	}

	var relocs [][2]int
	p, seg, off := 0x1978, 0, 0
	for r := w(stub, 0x8b); r > 0; r-- {
		b := int(stub[p])
		p++
		delta := b
		if b <= 1 {
			if b == 1 {
				seg += int(stub[p]) << 8
				p++
			}
			delta = w(stub, p)
			p += 2
		}
		off += delta
		if off > 0xffff {
			off -= 0x10000
			seg += 0x1000
		}
		if off == 0xffff {
			off = 0xffef
			seg++
		}
		relocs = append(relocs, [2]int{seg, off})
	}

	// build_mz(): a plain MZ header, the relocation table, then the image.
	ss, sp := w(stub, 0xb8), w(stub, 0xbd)
	hdrSize := (0x1c + 4*len(relocs) + 15) / 16 * 16
	total := hdrSize + len(out)
	minAlloc := (ss*16 + sp - len(out) + 15) / 16
	if minAlloc < 0 {
		minAlloc = 0
	}
	res := make([]byte, total)
	for i, x := range []int{0x5a4d, total % 512, (total + 511) / 512, len(relocs), hdrSize / 16,
		minAlloc, 0xffff, ss, sp, 0, w(stub, 0xc0), w(stub, 0xc2), 0x1c, 0} {
		binary.LittleEndian.PutUint16(res[i*2:], uint16(x))
	}
	for i, r := range relocs {
		binary.LittleEndian.PutUint16(res[0x1c+i*4:], uint16(r[1]))
		binary.LittleEndian.PutUint16(res[0x1e+i*4:], uint16(r[0]))
	}
	copy(res[hdrSize:], out)
	return res, nil
}
