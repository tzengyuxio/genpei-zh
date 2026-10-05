# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

《源平合戰》(KOEI, 1994, IBM-PC DOS/V) 的繁體中文化專案。Phase 1 已完成：所有文字來源（Main/Open/End.exe UI、Message.gp 劇情）都能抽取與回寫，試譯在 DOSBox-X 實機驗證通過。所有文字（劇情、UI、片頭／片尾文字圖）已完成初譯，接下來是實機巡檢與潤稿。

## 不可動的檔案

- `game/`（gitignored）— 遊戲原檔，版權因素**絕不 commit**，任何工具都**不可寫入**。所有輸出目的地只能是 `build/`、`extracted/`、`translation/`、`tools/`、`docs/`。
- `.DS_Store` 已在 `.gitignore` 中排除。

## 接手先讀

`docs/development.md`：目前進度、完整建置步驟、重要發現、踩過的坑與決議。所有文字已初譯，**下一項是實機巡檢**（待確認清單在 development.md「下一步」）。實機驗證用存檔快照（`tools/saves.py`，見 development.md「存檔快照」）跳過前置流程。

## 資料流

```
game/GENPEI/（唯讀原檔）
  ├─ exe_text.py / message.py extract → extracted/text/*.tsv（可重生，重跑會蓋掉）
  └─ 建置 → build/GENPEI/（gitignored，可隨時整包重建）
translation/*.tsv（手動維護的正本，翻譯只改這裡）──┘
```

- `translation/` 與 `extracted/text/` 同欄位；翻譯只填 `translation_zh`，不要改 `offsets`／`max_bytes`／`original_ja`。
- 兩種回寫方式不同：EXE 是**原地覆寫**（`patch.py`，長度不得超過 `max_bytes`、不改檔案大小）；Message.gp 是**整檔重建**（`message.py apply`，重建 offset table 再 LS11 壓縮，長度只受訊息視窗行寬限制）；Opendat/Enddat.gp 文字圖是**原位換 chunk**（`textimg.py`，EXE 內寫死 chunk 位移，新 chunk 不能比原本大）。
- 文字記法 `patch.py`／`message.py` 共用：`{C6}` = ESC C6 色碼、`{K}`/`{H}` = ESC K/H、`\n` 換行；printf 參數與 ESC 碼必須與原文一致，工具會擋。
- TSV 一律用 `csv` 模組 `quoting=csv.QUOTE_NONE, quotechar=None` 讀寫（字串含 `"`）；macOS `sed` 不認 `\t`，改 TSV 用 Python。

## 建置與驗證

沒有單元測試、linter；驗證靠工具的預檢與實機。完整步驟見 `docs/development.md`「建置與驗證」，重點：

```bash
# 每次都從 game/ 整包重建：patch.py 會確認原文仍在原位，不接受已改過的檔
cp game/GENPEI/* build/GENPEI/
python3 tools/unpack_exe.py game/GENPEI/Main.exe build/GENPEI/Main.exe
python3 tools/patch.py --apply translation/main.tsv --target build/GENPEI/Main.exe   # --check 只預檢
python3 tools/patch.py --apply translation/open.tsv --target build/GENPEI/Open.exe
python3 tools/patch.py --apply translation/end.tsv  --target build/GENPEI/End.exe
python3 tools/message.py apply game/GENPEI/Message.gp translation/message.tsv build/GENPEI/Message.gp
python3 tools/textimg.py build/GENPEI        # 讀 game/ 的 Opendat/Enddat.gp，寫到 build/

# 實機：腳本化滑鼠 + 錄影 N 秒（→ build/captures/open_000.avi）
python3 tools/mousetsr.py build/FAKEMS.COM "$(grep -v '^#' tools/dosbox/newgame.mouse | tr -d '\n')"
tools/dosbox/run.sh 170
ffmpeg -fflags +ignidx -i build/captures/open_000.avi -vf fps=1 build/captures/g_%03d.png

# 存檔快照（讀檔約 40 秒進統治畫面，新開局要 150 秒）
python3 tools/saves.py library | reset | import NAME SLOT | export SLOT NAME
```

- 改 `tools/ls11.py` 後跑 `python3 tools/ls11.py selftest game/GENPEI/Message.gp`（round-trip）。
- 改 `tools/npk.py` 的 `pack()` 要守住遊戲逐行解碼器的三條限制（development.md 重要發現 17），Python 版 `unpack()` 解得開不代表遊戲解得開，一定要實機看。
- mousetsr 腳本的 `(t,x,y,b)` 是「到 t 秒為止」的狀態；遊戲每次快慢差幾秒，點擊間隔至少 5 秒。常用座標在 development.md。

## 參考姊妹專案

`~/works/kami-zh/` 已完整做過一輪（《神々の大地》）。本專案移植了：

- `kami-zh/tools/mousetsr.py` → `tools/mousetsr.py`（原封不動）
- `kami-zh/tools/sjis_scan.py` → `tools/sjis_scan.py`（原封不動）
- NPK016 LZ-RLE 演算法 → `tools/npk.py`（stride 欄位語意有調整）
- DOSBox-X 配置骨架 → `tools/dosbox/genpei.conf`（dosv=jp 關鍵）

本專案與 kami-zh 的關鍵差異：

- 文字容器不同：kami-zh 用 `EVENT.DAT`（XOR 0x77 的 Shift-JIS 明文），本作用 `Message.gp`（KOEI LS11 壓縮，整檔表為 big-endian；訊息裡的半形假名由引擎畫成平假名，`ESC K`/`ESC H` 切片／平假名）。
- 本作 NPK016 header 的 stride 欄位語意改為「scanline 像素寬」（kami-zh 是 chunk byte-size）。
- 本作 chunks 以 magic `"NPK016"` 掃描直接串接，沒有 kami-zh 那層 u32 offset table。
- 本作在 DOS/V 模式下不需 `DOSJP.COM`，相當於 kami-zh 的 setup 簡化版。
- **Main.exe 是 RLE 壓縮的 EXE**：直接掃檔案會漏字、欄位黏連、選單置中空白消失。抽字與回寫一律以 `tools/unpack_exe.py` 解包後的檔案為準（TSV offset 都是解包後的位置，build/ 裡放解包版）。

## 翻譯規範

翻譯前先讀 `docs/translation-style.md`（語域、稱謂、缺字替代、格式限制），系統用語照 `translation/glossary.tsv`。

- **人名、名物、官位、地名保留日文漢字原樣**（`頼朝` 不改 `賴朝`），劇情裡寫死的名字也一樣，與 `%s` 帶入的資料表一致；`main_data.tsv` 的半形讀音保留。`main_data.tsv` 整份不翻。
- 一般詞彙繁體優先，JIS X 0208 缺字才退回日系新字體（錄→録、值→値、脫→脱、擊→撃），再不行就換詞（嗎→否／乎、吧→罷）。
- **cp932 能編碼不等於有字模**：NEC 0x87 區與 0xED 以上的擴充區畫不出來。不確定的字先實測，別憑印象（「戲」其實在字庫內）。
- 字庫政策（不換字型、不擴字庫）的評估見 `docs/font-policy.md`。

## DOSBox-X 踩坑

- 遊戲需要 EMS，但 XMS 同時存在時選完棟梁就卡死（CPU 核心在 `rep movs` 例外迴圈，連 `-time-limit` 都不觸發）。`genpei.conf` 固定 `xms = false`、`ems = emsboard`，不要改回預設。
- 結束卡住的 DOSBox-X 用 `kill -9`，一般 SIGTERM 會停在離開確認框。只殺 `genpei-conf` 的行程，同機可能有別的專案的 DOSBox-X。
- 錄影 `.avi` 搬到 repo 根目錄（已 gitignore），截圖放 `docs/screenshots/`。

## 執行環境

- Python 3.14 系統裝的；本專案目前**沒有 `.venv/`**。工具都是純 Python 標準庫，不需要額外套件。
- `dosbox-x` 要可以在 `PATH` 上找到（Homebrew `/usr/local/bin/dosbox-x`）。
- `ffmpeg` 需要（截影片的 frame）。
- `tools/textimg.py` 需要 ImageMagick（`magick`）與思源宋體、楷體字型；字型路徑寫在檔案頂端的 `FONT`，換機器要改。
