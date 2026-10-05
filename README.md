# genpei-zh

《源平合戦》(KOEI, 1994, IBM-PC DOS/V 版) 繁體中文化專案。

姊妹作：[kami-zh](https://github.com/tzengyuxio/kami-zh)（《神々の大地》）已完工，本專案沿用其做法與工具骨架。

## 本 repo 不包含遊戲檔案

遊戲 binary 與素材皆未納入版控（版權因素，`.gitignore` 已排除 `game/`）。請自備遊戲、解壓到 `game/GENPEI/`：

```
game/GENPEI/Main.exe
game/GENPEI/Message.gp
...（共 55 檔）
```

`game/` 永遠**保持原樣**；所有修補輸出到 `build/GENPEI/`（`tools/dosbox/run.sh` 首次執行時自動 mirror 一份過去）。

## Phase 1 已完成

工具與流程雛形已就緒，**所有文字來源都已能抽取與回寫**；試譯經 DOSBox-X 實機驗證通過：主選單（Main.exe）與遊戲內劇情對話（Message.gp）都顯示繁中（截圖見 `docs/screenshots/`）。

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
| 全部圖檔／資料表 dump（PNG、TSV → `build/dump/`） | ✓ `tools/dump_gfx.py`、`tools/dump_data.py` |
| Main.exe 解包（原檔是 RLE 壓縮） | ✓ `tools/unpack_exe.py` |
| EXE 文字抽取 → TSV（去雜訊、合併重複） | ✓ `tools/exe_text.py` |
| TSV → EXE 原地回寫 | ✓ `tools/patch.py`（多位置、JIS X 0208／printf／控制碼檢核，不變更檔案大小） |
| 字型政策 | ✓ `docs/font-policy.md`（建議抄 kami-zh：只用 JIS X 0208） |
| 翻譯 TSV 樣本 | ✓ `translation/main.tsv`、`translation/message.tsv`（各 8 筆試譯，已驗證可視） |

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

## 翻譯流程（Phase 1 已能跑通）

```bash
# 1. 抽字成 TSV（Main.exe 會在記憶體中解包；輸出 main/open/end.tsv 與 main_data.tsv）
python3 tools/exe_text.py game/GENPEI/Main.exe game/GENPEI/Open.exe game/GENPEI/End.exe

# 2. 編輯 extracted/text/*.tsv，填 translation_zh 欄
#    （或複製到 translation/*.tsv 編輯，避免被重跑的 extractor 蓋掉）

# 3. Main.exe 先解包到 build/（TSV 的 offset 都是解包後的位置）
python3 tools/unpack_exe.py game/GENPEI/Main.exe build/GENPEI/Main.exe

#    預檢：JIS X 0208 可編碼？長度不超過 max_bytes？參數與控制碼一致？
python3 tools/patch.py --check translation/main.tsv \
                              --target build/GENPEI/Main.exe

# 4. 套用
python3 tools/patch.py --apply translation/main.tsv \
                              --target build/GENPEI/Main.exe

# 5. 劇情訊息（Message.gp）：抽字、翻譯、回寫（重建 offset table 並重新 LS11 壓縮）
python3 tools/message.py extract game/GENPEI/Message.gp extracted/text/message.tsv
python3 tools/message.py apply game/GENPEI/Message.gp translation/message.tsv \
                               build/GENPEI/Message.gp

# 6. 在 DOSBox-X 驗證（搭 mousetsr 腳本，見上節）
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
| `Main.exe` 資料表 | 937 名稱＋624 讀音 | ~4,900 | 人名、地名、名物、官位（譯名政策待定） |
| `Open.exe` | 37 條 | ~180 | 環境設定、磁片提示 |
| `End.exe` | 41 條 | ~200 | 結尾程式 UI |
| `Sndata.gp` | ~2,300 筆（選翻） | — | 武將姓名（71-byte 固定長度 record） |

**UI＋劇情約 30,200 字**，另有資料表約 4,900 字，約《神々の大地》的兩倍。片頭／片尾的字樣是圖，不在文字檔內。

## 下一步（Phase 2 建議順序）

1. ~~清理 Main.exe TSV~~（完成：發現 Main.exe 是壓縮的，改為解包後抽取）
2. ~~定稿翻譯風格與詞彙表~~（完成：`docs/translation-style.md`、`translation/glossary.tsv`；人名、名物、官位、地名保留日文漢字，半形讀音保留）。**和歌（2-140～219）決議譯成中文詩句**，原則見 `docs/translation-style.md`「和歌」，下一步就是這項。
3. **移植 kami-zh 的 `jis.py`**：全 TSV 缺字掃描＋替代建議（「嗎」「擊」等）。
4. **整理 `install.py`**：一鍵從 `game/` 產生完整中文版 `build/`。
5. **Sndata.gp 武將名工具**（選翻）、確認各類訊息視窗的行寬上限。
6. 發佈：移植 `mkpatch.py`／Go patcher。

## 參考

- 姊妹專案 kami-zh：`~/works/kami-zh/`
- 檔案格式：`docs/formats.md`
- 開發紀錄（進度、發現、經驗、決議）：`docs/development.md`
- 翻譯風格與詞彙表：`docs/translation-style.md`、`translation/glossary.tsv`
- 字型政策：`docs/font-policy.md`
- Phase 1 驗證截圖：`docs/screenshots/phase1-main-menu-chinese.png`
