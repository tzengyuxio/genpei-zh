# 開發紀錄

建置流程、工具、目前進度、重要發現與踩過的坑。檔案格式見 [`formats.md`](formats.md)，翻譯規則見 [`translation-style.md`](translation-style.md)，字庫政策見 [`font-policy.md`](font-policy.md)。

## 目前進度（2026-10-06）

| 階段 | 狀態 |
|---|---|
| Phase 1：遊戲跑起來、檔案分析、抽取／回寫雛形 | 完成 |
| 1. 清理 Main.exe TSV | 完成（發現 Main.exe 是壓縮的，改為解包後抽取） |
| 2. 翻譯風格與詞彙表 | 完成（`translation-style.md`、`translation/glossary.tsv`） |
| **下一步：和歌翻譯** | 決議譯成中文詩句（見下方「決議」），尚未開始 |
| 之後 | 移植 `jis.py`、`consistency.py`、`install.py`，正式翻譯，發佈修補程式 |

試譯只有 Main.exe 9 筆（`translation/main.tsv`）與 Message.gp 8 筆（`translation/message.tsv`），用來驗證流程，**正式翻譯尚未開始**。

## 工具

全部只用 Python 標準庫，不需要虛擬環境。

| 工具 | 用途 |
|---|---|
| `tools/unpack_exe.py` | Main.exe（RLE 壓縮）→ 普通 MZ |
| `tools/exe_text.py` | Main/Open/End.exe 的 UI 字串、Main.exe 資料表 → TSV（去雜訊、合併重複） |
| `tools/patch.py` | TSV → EXE 原地回寫（多位置；長度、cp932、printf、色碼、原文仍在原位檢核） |
| `tools/ls11.py` | KOEI LS11 解壓／重新壓縮（`selftest` 做 round-trip） |
| `tools/message.py` | Message.gp ↔ TSV（重建 offset table、重新壓縮；printf 檢核、行寬 warning） |
| `tools/npk.py` | NPK016 圖形解壓 |
| `tools/sjis_scan.py` | 通用 Shift-JIS 掃描（探索未知檔案用） |
| `tools/analyze_sndata_gp.py` | Sndata.gp 武將 record dump |
| `tools/mousetsr.py` | 產生腳本化滑鼠 TSR（kami-zh 原封移植） |
| `tools/dosbox/run.sh`、`genpei.conf` | DOSBox-X 啟動（帶秒數時錄影＋看門狗） |
| `tools/dosbox/newgame.mouse` | 滑鼠腳本：片頭 → 新遊戲 → 1180 年 → 源頼朝 → 開局對話 |

## 建置與驗證（目前是手動步驟）

```bash
# 抽字（Main.exe 在記憶體中解包；輸出 main/open/end.tsv、main_data.tsv）
python3 tools/exe_text.py game/GENPEI/Main.exe game/GENPEI/Open.exe game/GENPEI/End.exe
python3 tools/message.py extract game/GENPEI/Message.gp extracted/text/message.tsv

# 產生 build/GENPEI（每次都從 game/ 重來，patch.py 不接受已改過的檔）
cp game/GENPEI/* build/GENPEI/
python3 tools/unpack_exe.py game/GENPEI/Main.exe build/GENPEI/Main.exe
python3 tools/patch.py --apply translation/main.tsv --target build/GENPEI/Main.exe
python3 tools/message.py apply game/GENPEI/Message.gp translation/message.tsv build/GENPEI/Message.gp

# 實機驗證：自動點到開局對話，錄 170 秒
python3 tools/mousetsr.py build/FAKEMS.COM "$(grep -v '^#' tools/dosbox/newgame.mouse | tr -d '\n')"
tools/dosbox/run.sh 170
ffmpeg -fflags +ignidx -i build/captures/open_000.avi -vf fps=1 build/captures/g_%03d.png
```

`newgame.mouse` 的時間軸（Savedata.gp 有存檔，所以先出讀檔畫面）：

| 約略秒數 | 畫面 |
|---|---|
| 0–20 | 片頭動畫（點擊跳過） |
| ~25 | 讀檔畫面 → 30 秒點右上「中止」(500,85) |
| ~45 | 主選單「何をなさいますか?」→ 50 秒點「新しくゲームを始める」(328,211) |
| ~55 | 劇本選擇 → 62 秒點 1180 年 (320,212) |
| ~64 | 選棟梁 → 71 秒點源頼朝 (165,200)、77 秒點「決定」(465,79) |
| ~78 | 環境設定 → 86 秒點「決定」(380,144) |
| ~91 起 | 統治開始；軍議 4-000～004、渋谷重国來投 1-021～026；之後每 12 秒點一下中央 |

先備份或從 `game/` 複製 Savedata.gp：遊戲中的操作可能改寫存檔。

## 重要發現

依發現順序：

1. **Main.exe 與 Main.ori 是同一份壓縮資料**。2 KB 之後只差 45 bytes：Main.exe 做了硬碟化（35 處 `A:`/`B:` 路徑改 `C:`、停用兩處 `INT 13h` 軟碟檢查）；Main.ori 的前 2 KB 另外多包一層、stub 不同。Genpei.com 只呼叫 MAIN.EXE，基準用 Main.exe。
2. **DOSJP.COM／FONT.DAT 不需要**：DOSBox-X 的 `dosv=jp` + `getsysfont=true` 自己提供 DOS/V 日文字型。
3. **多數 .gp 是圖**：Mainevt.gp 等 NPK016 容器全是 CG，檔名會誤導；片頭「祇園精舎の鐘」、「歴史シミュレーションゲーム」字樣也是 Opendat.gp 的圖。Sndata.gp 不是音效而是武將資料表。
4. **Message.gp 是 KOEI 標準 LS11 壓縮**，檔案表是 **big-endian**。第一輪分析把它讀成 little-endian 才誤以為是「15 筆劇本描述」而卡住。5 個 block、1,305 則、約 26,300 字。
5. **訊息裡的半形假名會畫成平假名**（全形寬），`ESC K`／`ESC H` 切換片／平假名。行寬計算時半形假名算 2 格。
6. **Main.exe 本身是 RLE 壓縮**（專壓連續的 0 與空白）。直接掃檔案會漏字、欄位黏連（「ｲﾏｲ兼平」），**選單字串的置中空白也被壓掉**，原地覆寫只能碰運氣。解包後一切正常，實機可玩。
7. **Main.exe 解包後分三區**：程式碼／劇本資料表（武將 71 bytes、據點 76、名物 18、官位 19）／UI 字串（DGROUP 段 514Ah）。UI 字串經指標陣列引用，常緊貼在指標表後面，表的 bytes 會被誤解成「^3」「G!G」黏在字串前。
8. **Open/End.exe 未壓縮**，同樣只有 DGROUP 之後才有文字。
9. **DOSBox-X 卡死的原因是 XMS**：遊戲需要 EMS（否則「空きメモリが足りません」），但 XMS 同時存在時，選完棟梁就卡死。只開 EMS（`xms=false`、`ems=emsboard`）才正常。與翻譯無關，完全原版也會卡。
10. **對話框會隨譯文長度自動調寬**；block 擴大 1.5 倍、全形字取代半形假名都沒問題。
11. **小按鈕是圖**：讀檔畫面的「中止」、選棟梁的「決定」不在任何文字檔。
12. **「戲」在字庫內**；「嗎、吧、您、你、她、哪、擊、錄、值、脫、檔」不在。

## 踩過的坑與經驗

### 分析方法

- **sub-agent 的結論要自己驗證**。三次 agent 分析各有一個關鍵錯誤：說 Main.exe「已解包」（其實是壓縮的）、把 LS11 檔案表讀成 LE、把 Main.ori 說成 PKLITE 版。之後都是靠「實際解出來看」或「實機跑」才推翻。
- **對照組要真的乾淨**。查卡死時，前兩次「對照組」其實各帶著一個改過的檔，差點誤判成翻譯造成的。要比對就整包從 `game/` 複製。
- **設定變體平行跑**：每個實驗用獨立的 cwd 與絕對路徑的 `captures =`，四組一起跑，三分鐘內就能定位 XMS 問題。行程「有沒有靠 `-time-limit` 自己結束」本身就是凍結偵測器。
- **字串真偽用分區判斷最有效**。試過「字串位址有沒有被程式引用」：全檔 u16 引用九成機率碰巧命中、只看立即值又只命中 16%（字串多經指標陣列引用），都不可用。按程式碼／資料表／DGROUP 分區，再加內容規則就夠了。
- **字庫要實測**。cp932 能編碼不等於 DOS/V 有字模（NEC 0x87、0xED 以上無字模）；反過來「戲」被我憑印象當成缺字寫進文件，實測才發現有字。

### DOSBox-X（macOS）

- 結束卡住的 DOSBox-X 要 `kill -9`；SIGTERM 會跳出離開確認框，行程以 100% CPU 一直掛著。同機可能有別的專案的 DOSBox-X，先比對 conf 名（`genpei-conf`）再殺。
- `-time-limit` 在模擬器卡住時不會觸發，`run.sh` 帶秒數時有看門狗（逾時 30 秒 `kill -9`）。
- 被 `-time-limit` 或 kill 結束的 AVI 索引會壞，ffmpeg 要加 `-fflags +ignidx`。
- 本作不需要 kami-zh 那套 A:/B: 軟碟映像（試過，沒影響）。
- 直接跑 MAIN.EXE（不經 Genpei.com／Open.exe）會停在 DOS 提示字元，要從 Genpei.com 走完整流程。

### 環境

- `rm` 是 `trash` 的 alias，不吃 `-rf`；要真刪用 `command rm -rf`。
- macOS 的 `sed` 不認 `\t`，TSV 欄位替換改用 Python。
- TSV 一律 `quoting=csv.QUOTE_NONE, quotechar=None` 讀寫（字串裡有 `"`）。

## 決議

| 日期 | 決議 |
|---|---|
| 2026-10-05 | 翻譯基準用 Main.exe（解包後），不用 Main.ori |
| 2026-10-05 | 字庫政策照 kami-zh：不改編碼、不換字型，只用 JIS X 0208（`font-policy.md`） |
| 2026-10-06 | 人名、名物、官位保留日文漢字；地名同樣保留（為與資料表一致）；`main_data.tsv` 的半形讀音保留，整份不翻 |
| 2026-10-06 | 系統用語照 `translation/glossary.tsv`（165 條） |
| 2026-10-06 | **和歌譯成中文詩句**（細節見 `translation-style.md`「和歌」） |

## 下一步

1. **和歌翻譯**（2-140～219，40 首）。動筆前先實機看歌會與合戰中「一首」的畫面，確認上下句是純展示還是配對選擇。
2. 移植 kami-zh 的 `jis.py`（全 TSV 缺字掃描＋替代建議）與 `consistency.py`（變體混用、同原文多譯、與 glossary 不一致）。
3. 寫 `install.py`：把上面「建置與驗證」的手動步驟變成一鍵。
4. 正式翻譯：Main.exe UI → Message.gp → Open/End.exe。
5. 發佈：移植 `mkpatch.py`／Go patcher。
