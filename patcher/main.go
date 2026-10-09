// Command genpei-zh-patch turns an installed DOS/V copy of 源平合戦 (KOEI,
// 1994) into the Traditional Chinese version.
//
// The patch (genpei-zh.kzp, written by tools/mkpatch.py) is embedded. The
// original folder is never modified: everything is copied to a sibling
// folder GENPEIZH and the changed files are rebuilt there.
//
//	genpei-zh-patch [game folder]
//
// Without an argument it looks next to the executable and in the current
// directory, for a folder holding MAIN.EXE or a GENPEI subfolder.
//
// Ported from kami-zh patcher/main.go. Main.exe ships RLE-packed and the
// patch is made against the unpacked image, so it is unpacked first.
package main

import (
	"bufio"
	"bytes"
	"crypto/sha256"
	_ "embed"
	"encoding/binary"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

//go:embed genpei-zh.kzp
var patchData []byte

// outName is the output folder; 8 characters at most, as DOS shows longer
// names as GENPEI~1.
const outName = "GENPEIZH"

// packed lists the files kept RLE-packed on disk (see unpack.go).
var packed = map[string]bool{"MAIN.EXE": true}

// skippable lists the patched files the game can do without: each is used
// on its own, so a damaged or different copy can be left as it is and the
// rest still translated. MAIN.EXE (the interface) and MESSAGE.GP (the
// story) are the translation itself and are not here.
var skippable = map[string]string{
	"END.EXE":     "結局的文字會維持日文（若檔案損毀，破關後的結局也無法正常播放）",
	"ENDDAT.GP":   "結局的旁白與卷軸書法會維持日文",
	"OPEN.EXE":    "片頭與主選單會維持日文",
	"OPENDAT.GP":  "片頭的旁白與書法會維持日文",
	"MAINCMD2.GP": "勢力滅亡畫面的書法會維持日文",
	"SNDATA.GP":   "劇本裡的「かむろ」不會改成「禿童」",
}

var stdin = bufio.NewReader(os.Stdin)

type filePatch struct {
	name             string
	srcSize, dstSize uint32
	srcSum, dstSum   [32]byte
	ops              []byte
	opCount          uint32
}

func parse(data []byte) ([]filePatch, error) {
	r := bytes.NewReader(data)
	magic := make([]byte, 4)
	r.Read(magic)
	if string(magic) != "KZP1" {
		return nil, errors.New("內建的修補資料損毀")
	}
	var count uint16
	binary.Read(r, binary.LittleEndian, &count)
	var files []filePatch
	for i := 0; i < int(count); i++ {
		var f filePatch
		n, _ := r.ReadByte()
		name := make([]byte, n)
		r.Read(name)
		f.name = string(name)
		binary.Read(r, binary.LittleEndian, &f.srcSize)
		r.Read(f.srcSum[:])
		binary.Read(r, binary.LittleEndian, &f.dstSize)
		r.Read(f.dstSum[:])
		binary.Read(r, binary.LittleEndian, &f.opCount)
		start := len(data) - r.Len()
		for j := uint32(0); j < f.opCount; j++ {
			kind, _ := r.ReadByte()
			if kind == 0 {
				r.Seek(8, 1)
			} else {
				var length uint32
				binary.Read(r, binary.LittleEndian, &length)
				r.Seek(int64(length), 1)
			}
		}
		f.ops = data[start : len(data)-r.Len()]
		files = append(files, f)
	}
	return files, nil
}

func (f filePatch) apply(src []byte) []byte {
	out := make([]byte, 0, f.dstSize)
	ops := f.ops
	for j := uint32(0); j < f.opCount; j++ {
		kind := ops[0]
		if kind == 0 {
			off := binary.LittleEndian.Uint32(ops[1:])
			length := binary.LittleEndian.Uint32(ops[5:])
			out = append(out, src[off:off+length]...)
			ops = ops[9:]
		} else {
			length := binary.LittleEndian.Uint32(ops[1:])
			out = append(out, ops[5:5+length]...)
			ops = ops[5+length:]
		}
	}
	return out
}

// diagnose explains why a file does not match the supported original.
func diagnose(src []byte, f filePatch) string {
	if uint32(len(src)) != f.srcSize {
		return fmt.Sprintf("大小是 %d bytes，原版是 %d bytes，可能是其他版本或已被修改", len(src), f.srcSize)
	}
	// Floppies are formatted with 0xF6; a copy that failed to read some
	// sectors keeps that filler. (Runs of 0x00 prove nothing: MAIN.EXE
	// legitimately ends in several KB of them.)
	n := 0
	for n < len(src) && src[len(src)-1-n] == 0xF6 {
		n++
	}
	if n >= 512 {
		return fmt.Sprintf("檔案已損毀：結尾 %d bytes 全是 0xF6（磁片讀取不完整時留下的格式化填充值）。"+
			"請從原版磁片重新複製這個檔案", n)
	}
	return "大小相同但內容不同，可能是其他版本或已被修改"
}

func ask(question string) bool {
	fmt.Print(question, " (y/N) ")
	line, _ := stdin.ReadString('\n')
	line = strings.TrimSpace(strings.ToLower(line))
	return line == "y" || line == "yes"
}

// findFile matches a name case-insensitively, as DOS file names are.
func findFile(dir, name string) (string, bool) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return "", false
	}
	for _, e := range entries {
		if !e.IsDir() && strings.EqualFold(e.Name(), name) {
			return filepath.Join(dir, e.Name()), true
		}
	}
	return "", false
}

func findGame(args []string) (string, error) {
	var tries []string
	if len(args) > 0 {
		tries = append(tries, args[0], filepath.Join(args[0], "GENPEI"))
	} else {
		if exe, err := os.Executable(); err == nil {
			dir := filepath.Dir(exe)
			tries = append(tries, dir, filepath.Join(dir, "GENPEI"))
		}
		if wd, err := os.Getwd(); err == nil {
			tries = append(tries, wd, filepath.Join(wd, "GENPEI"))
		}
	}
	for _, dir := range tries {
		if _, ok := findFile(dir, "MAIN.EXE"); ok {
			return filepath.Abs(dir)
		}
	}
	return "", errors.New("找不到遊戲資料夾（含 MAIN.EXE 的 GENPEI 資料夾）。\n" +
		"請把本程式放在 GENPEI 資料夾裡或旁邊再執行，或把 GENPEI 資料夾拖到本程式上。")
}

func run(args []string) error {
	files, err := parse(patchData)
	if err != nil {
		return err
	}
	game, err := findGame(args)
	if err != nil {
		return err
	}
	fmt.Println("遊戲資料夾：", game)

	// Check every file before writing anything, and report all problems
	// at once rather than stopping at the first.
	sources := map[string][]byte{}
	var bad, fatal []string
	done := 0
	for _, f := range files {
		path, ok := findFile(game, f.name)
		if !ok {
			fatal = append(fatal, fmt.Sprintf("缺少 %s", f.name))
			continue
		}
		src, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		if packed[strings.ToUpper(f.name)] {
			// An already patched Main.exe is unpacked and fails here; it is
			// then compared as it is.
			if u, err := unpackExe(src); err == nil {
				src = u
			}
		}
		switch sha256.Sum256(src) {
		case f.srcSum:
			sources[f.name] = src
		case f.dstSum:
			done++
			fatal = append(fatal, fmt.Sprintf("%s 已經是中文版，不需要再修補", f.name))
		default:
			msg := fmt.Sprintf("%s：%s", f.name, diagnose(src, f))
			if _, ok := skippable[strings.ToUpper(f.name)]; ok {
				bad = append(bad, f.name)
				fmt.Println("  ", msg)
			} else {
				fatal = append(fatal, msg)
			}
		}
	}
	if done == len(files) {
		return errors.New("這個資料夾已經是中文版，不需要再修補")
	}
	if len(fatal) > 0 {
		return errors.New(strings.Join(fatal, "\n") + "\n以上檔案無法修補，沒有寫入任何東西。")
	}
	if len(bad) > 0 {
		fmt.Println()
		fmt.Println("以上檔案可以跳過，其他檔案照常中文化。跳過的檔案會原樣複製：")
		for _, name := range bad {
			fmt.Printf("   %s：%s\n", name, skippable[strings.ToUpper(name)])
		}
		if !ask("要跳過這些檔案繼續嗎？") {
			return errors.New("已取消，沒有寫入任何東西")
		}
		fmt.Println()
	}

	out := filepath.Join(filepath.Dir(game), outName)
	if strings.EqualFold(filepath.Clean(out), filepath.Clean(game)) {
		out = filepath.Join(filepath.Dir(game), outName+"2")
	}
	if _, err := os.Stat(out); err == nil {
		return fmt.Errorf("%s 已存在，請先刪除或改名後再執行", out)
	}
	if err := os.Mkdir(out, 0o755); err != nil {
		return err
	}

	entries, err := os.ReadDir(game)
	if err != nil {
		return err
	}
	self, _ := os.Executable()
	for _, e := range entries {
		if e.IsDir() || filepath.Join(game, e.Name()) == self {
			continue
		}
		data, err := os.ReadFile(filepath.Join(game, e.Name()))
		if err != nil {
			return err
		}
		if err := os.WriteFile(filepath.Join(out, e.Name()), data, 0o644); err != nil {
			return err
		}
	}
	for _, f := range files {
		if sources[f.name] == nil {
			fmt.Printf("  已跳過 %s（原樣複製）\n", f.name)
			continue
		}
		dst := f.apply(sources[f.name])
		if sha256.Sum256(dst) != f.dstSum {
			return fmt.Errorf("%s 修補結果不正確", f.name)
		}
		path, _ := findFile(out, f.name)
		if err := os.WriteFile(path, dst, 0o644); err != nil {
			return err
		}
		fmt.Println("  已修補", f.name)
	}
	fmt.Println("完成！中文版在：", out)
	fmt.Println("原本的資料夾沒有任何變動。")
	if len(bad) > 0 {
		fmt.Printf("跳過的檔案：%s。換成完好的原版檔後重新執行，就能完整中文化。\n", strings.Join(bad, "、"))
	}
	return nil
}

func main() {
	setupConsole()
	fmt.Println("《源平合戦》繁體中文化修補程式")
	fmt.Println()
	err := run(os.Args[1:])
	if err != nil {
		fmt.Println("錯誤：", err)
	}
	fmt.Println()
	fmt.Print("按 Enter 結束…")
	stdin.ReadString('\n')
	if err != nil {
		os.Exit(1)
	}
}
