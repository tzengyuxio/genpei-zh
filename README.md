# genpei-zh

《源平合戦》(KOEI, 1994, IBM-PC DOS/V 版) 繁體中文化專案。

姊妹作：[kami-zh](https://github.com/tzengyuxio/kami-zh)（《神々の大地》）已完工，本專案沿用其做法與工具骨架。

## 下載與遊玩

到 [Releases](https://github.com/tzengyuxio/genpei-zh/releases) 下載修補程式（Windows／macOS）。修補程式只含譯文，需要自備 DOS/V 原版遊戲檔（安裝後的 `GENPEI` 資料夾）；執行後會在旁邊建立中文版的 `GENPEIZH` 資料夾，不動原檔。用 DOSBox-X 的 DOS/V 模式遊玩，壓縮檔附設定檔與說明（`README.txt`）。

修補程式在 `patcher/`（Go，移植自 kami-zh），以 `tools/release.sh VERSION` 建置：重新建置譯文、用 `tools/mkpatch.py` 產生只含差異的 `genpei-zh.kzp` 內嵌進去，輸出到 `patcher/dist/`。

## 本 repo 不包含遊戲檔案

遊戲 binary 與素材皆未納入版控（版權因素，`.gitignore` 已排除 `game/`）。請自備遊戲、解壓到 `game/GENPEI/`：

```
game/GENPEI/Main.exe
game/GENPEI/Message.gp
...（共 55 檔）
```

`game/` 永遠**保持原樣**；所有修補輸出到 `build/GENPEI/`（`tools/dosbox/run.sh` 首次執行時自動 mirror 一份過去）。

## 目前進度

**所有文字都已完成初譯**：劇情（Message.gp）、EXE 介面（Main/Open/End.exe），以及片頭與片尾的文字圖。主選單、開局劇情、歌會、統治畫面、片頭與片尾旁白都在 DOSBox-X 上實際跑過，畫面顯示的是繁中（截圖存在 `docs/screenshots/`，已 gitignore）。下一步是實機巡檢與潤稿，詳見 `docs/development.md`。

| 翻譯 | 筆數 |
|---|---|
| `translation/message.tsv`（Message.gp 劇情，含和歌 40 首） | 1,305 則 |
| `translation/main.tsv`（Main.exe UI） | 494 條 |
| `translation/open.tsv`、`translation/end.tsv`（Open/End.exe UI） | 21＋23 條 |
| `translation/images.tsv`（片頭／片尾文字圖） | Opendat 12 張＋Enddat 16 張 |
| `translation/glossary.tsv`（系統用語詞彙表） | 182 條 |

## 工具

| 元件 | 狀態 |
|---|---|
| DOSBox-X 配置與啟動腳本 | ✓ `tools/dosbox/{run.sh, genpei.conf}` |
| 滑鼠自動化（跳過片頭動畫） | ✓ `tools/mousetsr.py`（移植自 kami-zh） |
| 片頭／片尾文字圖重繪 | ✓ `tools/textimg.py`（`translation/images.tsv` → NPK016，原位寫回） |
| 存檔快照庫（跳過前置流程） | ✓ `tools/saves.py`（Savedata.gp 欄位 ↔ `build/saves/*.slot`） |
| 檔案格式分析 | ✓ `docs/formats.md` |
| Message.gp（LS11）解壓／重新壓縮 | ✓ `tools/ls11.py` |
| Message.gp ↔ TSV | ✓ `tools/message.py`（1,305 則，printf 參數與 JIS 檢核） |
| NPK016 圖形解壓 | ✓ `tools/npk.py` |
| 全部圖檔／資料表 dump（PNG → `build/dump/`、TSV → `build/data/`） | ✓ `tools/dump_gfx.py`、`tools/dump_data.py` |
| Main.exe 解包（原檔是 RLE 壓縮） | ✓ `tools/unpack_exe.py` |
| EXE 文字抽取 → TSV（去雜訊、合併重複） | ✓ `tools/exe_text.py` |
| TSV → EXE 原地回寫 | ✓ `tools/patch.py`（多位置、JIS X 0208／printf／控制碼檢核，不變更檔案大小） |
| 字型政策 | ✓ `docs/font-policy.md`（照 kami-zh：只用 JIS X 0208） |

## 執行遊戲

```bash
# 直接玩（滑鼠靠自己）
tools/dosbox/run.sh

# 錄影 N 秒並退出（存成 build/captures/open_000.avi）
tools/dosbox/run.sh 60

# 搭配 mousetsr 腳本自動點到開局劇情（片頭 → 新遊戲 → 1180 年 → 源頼朝）
python3 tools/mousetsr.py build/FAKEMS.COM \
  "$(grep -v '^#' tools/dosbox/newgame.mouse | tr -d '\n')"
tools/dosbox/run.sh 170
```

注意：
- 遊戲需要 EMS，但 XMS 同時開著會在選完棟梁後讓 DOSBox-X 卡死，所以 `genpei.conf` 設 `xms = false`、`ems = emsboard`。
- macOS 上 DOSBox-X 偶爾不理會 `-time-limit`，`run.sh` 帶秒數時有看門狗，逾時 30 秒強制結束。
- 結束 DOSBox-X 請用 `kill -9`；一般 `kill` 會跳出確認離開的對話框而卡住。

`run.sh` 第一次執行時會把 `game/GENPEI/` 複製到 `build/GENPEI/`，之後都操作 `build/` 不碰原檔。

## 翻譯與建置流程

```bash
# 1. 抽字成 TSV → extracted/text/（重跑會覆蓋；翻譯正本在 translation/）
#    Main.exe 會在記憶體中解包；輸出 main/open/end.tsv 與 main_data.tsv
python3 tools/exe_text.py game/GENPEI/Main.exe game/GENPEI/Open.exe game/GENPEI/End.exe
python3 tools/message.py extract game/GENPEI/Message.gp extracted/text/message.tsv

# 2. 在 translation/*.tsv 填 translation_zh 欄（片頭／片尾文字圖在 translation/images.tsv）

# 3. 每次都從 game/ 整包重建 build/GENPEI（patch.py 會確認原文仍在原位，不接受改過的檔）
cp game/GENPEI/* build/GENPEI/
python3 tools/unpack_exe.py game/GENPEI/Main.exe build/GENPEI/Main.exe   # TSV 的 offset 是解包後的位置

# 4. 回寫。--check 只預檢：JIS X 0208 可編碼？長度不超過 max_bytes？參數與控制碼一致？
python3 tools/patch.py --apply translation/main.tsv translation/main_data.tsv --target build/GENPEI/Main.exe
python3 tools/patch.py --apply translation/sndata.tsv --target build/GENPEI/Sndata.gp
python3 tools/patch.py --apply translation/open.tsv --target build/GENPEI/Open.exe
python3 tools/patch.py --apply translation/end.tsv  --target build/GENPEI/End.exe
python3 tools/message.py apply game/GENPEI/Message.gp translation/message.tsv \
                               build/GENPEI/Message.gp   # 重建 offset table 並重新 LS11 壓縮
python3 tools/textimg.py build/GENPEI   # 重繪文字圖，讀 game/ 的 Opendat/Enddat.gp，寫到 build/

# 5. 在 DOSBox-X 驗證（mousetsr 腳本見上節；存檔快照見 docs/development.md「存檔快照」）
tools/dosbox/run.sh 170
```

長度限制：
- EXE 內的 UI 字串是原地覆寫，Shift-JIS 後不可超過原字串 bytes（`max_bytes`）。選單字串用空白補齊置中，`max_bytes` 含空白，譯文請補回同寬並置中。同一字串的所有位置（`offsets`）會一起改。
- 對話框右上那種小按鈕（讀檔畫面的「中止」、選棟梁的「決定」）是圖，不在文字檔裡。
- Message.gp 會整檔重建，譯文長度不受原文限制（每個 block 上限 64 KB）；實際限制是訊息視窗大小，`apply` 以原文行數／行寬（`lines`、`max_cols`，半形格）為準發 warning。printf 參數必須與原文一致。

## 遊戲檔案來源說明

來源：`源平合戰.zip`（53 檔）。經分析：

- **`Version`**：『源平合戦』For IBM-PC，Ver. 1.0（1994-11-16）。
- **`Main.exe` vs `Main.ori`**：**同一遊戲版本、同一份壓縮資料**。兩者都是 RLE 壓縮的 EXE；`Main.exe`（1994-12-28）是 KOEI 安裝程式做過硬碟化的版本（`A:/B:` 路徑改成 `C:`、停用兩處 `INT 13h` 軟碟檢查），`Main.ori`（1994-11-14）是磁片原版，前 2 KB 多包一層。翻譯基準用 **`Main.exe`**，先以 `tools/unpack_exe.py` 解包（詳見 `docs/formats.md` §5.1）。
- **`DOSJP.COM` / `FONT.DAT` / `JIS.FNT` / `FONT.CHR` / `Play.bat` / `DOSV.BAT`**：第三方日文字型載入器（1997 年），**非 KOEI 原版**。在 DOSBox-X 的 DOS/V 模式下（`dosv=jp + getsysfont=true`）**不需要**，`tools/dosbox/run.sh` 不會載入它。
- **`Savedata.gp`**：2004 年玩家存檔。遊戲啟動時會自動偵測並進入讀檔對話框。
- **`.gp` 資料檔**：格式詳見 `docs/formats.md`。多數是 NPK016 圖形容器或未壓縮 planar 圖；`Message.gp` 是劇情文字（KOEI LS11 壓縮）；`Sndata.gp` 是武將資料表。
- **Loader chain**：`Play.bat → DOSJP → Genpei.com → FMDRV → GRPDRV → OPEN.EXE → MAIN.EXE → END.EXE`。

## 翻譯量（實測）

| 來源 | 筆數 | 字數 | 說明 |
|---|---|---|---|
| `Message.gp` | 1,305 則 | ~26,300 | 對話、戰報、事件、遊戲說明 |
| `Main.exe` UI | 496 條（595 處） | ~3,500 | 選單、指令、狀態欄、對話框 |
| `Main.exe` 資料表 | 937 名稱＋624 讀音 | ~4,900 | 人名、地名、名物、官位（保留日文漢字，不翻） |
| `Open.exe` | 37 條 | ~180 | 環境設定、磁片提示 |
| `End.exe` | 41 條 | ~200 | 結尾程式 UI |
| `Sndata.gp` | ~2,300 筆 | — | 4 個劇本的初始資料（武將姓名保留日文漢字，不翻；唯一的假名人名「かむろ」改「禿童」） |

**UI＋劇情約 30,200 字**，另有資料表約 4,900 字，約《神々の大地》的兩倍。片頭／片尾的字樣是圖，不在文字檔內。

## 下一步

1. **實機巡檢與潤稿**：待確認的參數語序、片段組合、片尾毛筆字等清單見 `docs/development.md`「下一步」。
2. **移植 kami-zh 的 `jis.py`、`consistency.py`**：全 TSV 缺字掃描＋替代建議；變體混用、同原文多譯、與詞彙表不一致的檢查。
3. **寫 `install.py`**：一鍵從 `game/` 產生完整中文版 `build/`。
4. 其他含日文的圖（Logo、月名、指令圖等）視需要再譯。
5. 發佈：移植 `mkpatch.py`／Go patcher。

## 參考

- 姊妹專案 kami-zh：`~/works/kami-zh/`
- 檔案格式：`docs/formats.md`
- 開發紀錄（進度、發現、經驗、決議）：`docs/development.md`
- 翻譯風格與詞彙表：`docs/translation-style.md`、`translation/glossary.tsv`
- 字型政策：`docs/font-policy.md`
- 實機驗證截圖：`docs/screenshots/`（遊戲畫面有版權，gitignored，只留在本機）
