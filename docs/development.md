# 開發紀錄

建置流程、工具、目前進度、重要發現與踩過的坑。檔案格式見 [`formats.md`](formats.md)，翻譯規則見 [`translation-style.md`](translation-style.md)，字庫政策見 [`font-policy.md`](font-policy.md)。

## 目前進度（2026-10-06）

| 階段 | 狀態 |
|---|---|
| Phase 1：遊戲跑起來、檔案分析、抽取／回寫雛形 | 完成 |
| 1. 清理 Main.exe TSV | 完成（發現 Main.exe 是壓縮的，改為解包後抽取） |
| 2. 翻譯風格與詞彙表 | 完成（`translation-style.md`、`translation/glossary.tsv`） |
| 3. 和歌翻譯 | 完成（40 首 80 則，七言；歌會實機驗證） |
| 4. Message.gp 劇情 | 完成初譯（1,305 則全數；實機抽查歌會、開局） |
| 5. EXE UI | 完成初譯（Main.exe 494 條、Open.exe 21、End.exe 23；實機抽查主選單、劇本、環境設定、統治畫面） |
| 6. 片頭／片尾文字圖 | 完成（Opendat 12 張、Enddat 16 張重繪；片頭與片尾旁白實機驗證） |
| **下一步** | 實機巡檢與潤稿、`jis.py`／`consistency.py`／`install.py`、發佈修補程式 |

文字都已初譯：
- `translation/message.tsv`：Message.gp 1,305 則
- `translation/main.tsv`、`translation/open.tsv`、`translation/end.tsv`：EXE 的 UI
- `translation/images.tsv`：片頭／片尾的文字圖

## 工具

全部只用 Python 標準庫，不需要虛擬環境。

| 工具 | 用途 |
|---|---|
| `tools/unpack_exe.py` | Main.exe（RLE 壓縮）→ 普通 MZ |
| `tools/exe_text.py` | Main/Open/End.exe 的 UI 字串、Main.exe 資料表 → TSV（去雜訊、合併重複） |
| `tools/patch.py` | TSV → EXE 原地回寫（多位置；長度、cp932、printf、色碼、原文仍在原位檢核） |
| `tools/ls11.py` | KOEI LS11 解壓／重新壓縮（`selftest` 做 round-trip） |
| `tools/message.py` | Message.gp ↔ TSV（重建 offset table、重新壓縮；printf 檢核、行寬 warning） |
| `tools/npk.py` | NPK016 圖形解壓（48-byte header） |
| `tools/gfx.py` | 共用圖形函式：BRG 色盤、planar／mask／RLE3 解碼、純標準庫 PNG 輸出 |
| `tools/dump_gfx.py` | 全部圖檔 → `build/dump/<分類>/<檔名>/` PNG＋總覽＋index.tsv；`Generals` 依頭像碼組出 400 人的遊戲內頭像（formats.md §10、§10.3） |
| `tools/dump_data.py` | 武將、勢力、據點、官位、名物（Sndata.gp 4 劇本）＋戰略地圖節點（Main.exe）＋合戰地圖（Hchikei.gp）→ `build/data/*.tsv`（formats.md §4） |
| `tools/guide_tables.py` | `build/data/*.tsv` → `docs/guide/` 攻略用資料表（劇本、武將、據點、寶物、官位；`tables.md` 為目錄與欄位說明） |
| `tools/sjis_scan.py` | 通用 Shift-JIS 掃描（探索未知檔案用） |
| `tools/analyze_sndata_gp.py` | Sndata.gp 武將 record dump |
| `tools/mousetsr.py` | 產生腳本化滑鼠 TSR（kami-zh 原封移植） |
| `tools/dosbox/run.sh`、`genpei.conf` | DOSBox-X 啟動（帶秒數時錄影＋看門狗） |
| `tools/dosbox/newgame.mouse` | 滑鼠腳本：片頭 → 新遊戲 → 1180 年 → 源頼朝 → 開局對話 |
| `tools/dosbox/kakai.mouse` | 滑鼠腳本：讀存檔欄 1 → 外交 → 歌會 → 吟歌（約 100 秒） |
| `tools/textimg.py` | 片頭／片尾文字圖：依 `translation/images.tsv` 重繪 → NPK016 壓縮 → 原位寫回 Opendat/Enddat.gp |
| `tools/calligraphy_editor.py` | 產生 `build/calligraphy-editor.html`：調整片頭法帖字的大小與位置，即時顯示壓縮大小，匯出 `layout.json` |
| `tools/mob_kao_explorer.py` | 產生 `build/mob-kao-explorer.html`：大眾臉（Montage 組合頭像）探索器，選類型／頭／身／眼／口／背景即時組出 64×80 頭像與頭像碼，列出使用該碼與相同部件的武將（沿用 `dump_gfx.py` 的組法，310 人逐 pixel 相同；需先跑 `dump_data.py`） |
| `tools/saves.py` | Savedata.gp 存檔欄 ↔ `build/saves/*.slot` 快照庫（list/library/export/import/reset） |

## 建置與驗證（目前是手動步驟）

```bash
# 抽字（Main.exe 在記憶體中解包；輸出 main/open/end.tsv、main_data.tsv）
python3 tools/exe_text.py game/GENPEI/Main.exe game/GENPEI/Open.exe game/GENPEI/End.exe
python3 tools/message.py extract game/GENPEI/Message.gp extracted/text/message.tsv

# 產生 build/GENPEI（每次都從 game/ 重來，patch.py 不接受已改過的檔）
cp game/GENPEI/* build/GENPEI/
python3 tools/unpack_exe.py game/GENPEI/Main.exe build/GENPEI/Main.exe
python3 tools/patch.py --apply translation/main.tsv translation/main_data.tsv --target build/GENPEI/Main.exe
python3 tools/patch.py --apply translation/sndata.tsv --target build/GENPEI/Sndata.gp
python3 tools/message.py apply game/GENPEI/Message.gp translation/message.tsv build/GENPEI/Message.gp
python3 tools/patch.py --apply translation/open.tsv --target build/GENPEI/Open.exe
python3 tools/patch.py --apply translation/end.tsv --target build/GENPEI/End.exe
python3 tools/textimg.py build/GENPEI            # 讀 game/ 的 Opendat/Enddat.gp，寫到 build/

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

### 存檔快照（跳過前置流程）

新開局要約 150 秒才能進到統治畫面，讀存檔只要約 40 秒。存檔欄只有 10 格，所以在 `build/saves/` 建一個快照庫（gitignored），用 `tools/saves.py` 換進換出：

```bash
python3 tools/saves.py library                      # 列出快照
python3 tools/saves.py reset                        # Savedata.gp 回到原版
python3 tools/saves.py import kiyomori-1180-10-start 1   # 快照 → 欄 1
# ……玩到想保留的狀態，在遊戲裡 機能 → 保存 → 欄 N……
python3 tools/saves.py export N 新快照名            # 欄 N → 快照
```

快照名格式為 `<棟梁>-<年>-<月>-<狀態>`。目前有：

| 快照 | 內容 |
|---|---|
| `kiyomori-1180-10-start` | 平清盛，1180 年 10 月第一個統治階段。開局事件都已點完，可以直接下指令（歌會用這個） |
| `orig-s1-yoshitsune-1185-10`、`orig-s2-yoritomo-1183-01` | 原版 Savedata.gp 附的兩格 |
| `yoshitsune-1185-11-lose-before-battle` | 源義経，1185 年 11 月。麾下無人無兵，很快會被攻打，用來看勢力滅亡後的平家物語書法（Maincmd2） |

讀檔流程的座標：
- 片頭點過之後，約 17 秒出現主選單，「讀取進度」在 (328,236)。
- 讀檔畫面欄 n 在 (320, 126+26(n-1))。點下後約 10 秒進入統治畫面。

統治畫面的常用座標：
- 據點面板的指令鈕：內政 (380,133)、軍事 (413,133)、人事 (447,133)、外交 (482,133)、計略 (517,133)。
- 右側：命令 (575,180)、機能 (575,250)。
- 選單第 1～4 項大約在 y = 215、240、263、287。

同一份存檔重跑，結果**不一定**相同（吟哪首歌、成敗都會變），要重現特定畫面就另存快照。

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
13. **圖形全部解開**（`tools/dump_gfx.py`）：NPK016 header 其實是 48 bytes（含寬高與一張遊戲不用的制式色表）；色盤是 48-byte 的 B、R、G 三 nibble 格式，Mainpal 四組＝四季；未壓縮圖是 byte-interleaved planar，**byte k＝bit k**（由 Grpdrv.exe 的 blitter 與 DAC 對照表確認）；Kaodata/Kisetsu 用另一種 3bpp RLE。Sndata.gp 是 4 個劇本（1180/1183/1184/1185）的初始資料，不是單純武將表。
14. **Savedata.gp 是 10 格 × 43,403 bytes，沒有檔頭**。每格開頭是 u16 年、u8 月，棟梁名在 +13（Shift-JIS）；空欄以 `00 b4 90 00` 開頭。
15. **歌會會自動吟出整首歌**（兩行對話框，上句一行、下句一行），講評訊息顯示上下句是分開挑選再拼起來的（見 `translation-style.md`「和歌」）。
16. **片頭旁白、平家物語書法、片尾旁白都是 NPK016 圖**（Opendat 14–17、44–51；Enddat 68–83）。Open.exe／End.exe 內有這些 chunk 的 u32 offset 表與 size 表（例：Open.exe 0x12160、0x121F8），帶擺放座標的 chunk 另從「下一個 chunk − 8」讀那 8 bytes。所以換圖只能**原位覆寫、不改位移**：新 chunk＋補 0＋原座標。
17. **遊戲的 NPK016 解碼器是逐行的**：Python 版 `unpack()` 能解的串流遊戲不一定能解。原版壓縮器有三條限制，自己的壓縮器都要遵守，否則畫面全是條紋：
    - 回溯參照不跨行尾；
    - 水平參照不退到行首之前；
    - 不參照圖的起點之前。
    （`tools/npk.py` 的 `pack()`）
18. **End.exe 從 `A:ENDDAT.GP` 讀檔**（硬碟化只改了 Main.exe），而且要先載入 FMDRV.COM、GRPDRV.EXE。單獨測片尾的做法：`build/GENPEI/ENDTEST.BAT` 先 `mount a <build/GENPEI>`，再執行這三支程式，用 `GENPEI_START=ENDTEST.BAT tools/dosbox/run.sh 120` 啟動。播完第一段旁白後畫面會變淺灰並停住（原版也一樣），之後的毛筆字要從真正的結局才看得到。

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
- mousetsr 腳本的每一筆 `(t,x,y,b)` 是「**到 t 秒為止**」的狀態，也就是說座標在 t 之前就生效。遊戲進度每次執行會差幾秒，點擊之間至少留 5 秒。
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
| 2026-10-06 | 系統用語照 `translation/glossary.tsv`（182 條） |
| 2026-10-06 | 專有名詞中唯一的假名人名「かむろ」改作「禿童」，與 glossary、劇情、UI 一致（Main.exe 表＋Sndata.gp 四劇本） |
| 2026-10-06 | **和歌譯成中文詩句**（細節見 `translation-style.md`「和歌」） |
| 2026-10-06 | 和歌定案為上下句各一句七言 |
| 2026-10-06 | 片頭／片尾的文字圖也譯：旁白用思源宋體，書法用楷體，照原圖的色號與格局重繪；標題「源平合戦」保留不改 |
| 2026-10-06 | 旁白改用 jiskan 24 點陣明朝體、字距 26 px、外框 2 px。輪廓字（思源宋體、游明朝等）縮到 24 px 筆畫粗細不一或糊在一起；原版本身就是 24 點陣字。譯文每欄可比原文少 0～2 字以放進版面 |
| 2026-10-06 | 片頭平家物語改用古代法帖的字圖（逐字挑選，記出處於檔名），大小與位置用 `tools/calligraphy_editor.py` 調整後存 `layout.json`；外圍補 1 px 深藍邊。片尾書法維持楷體 |
| 2026-10-06 | 實機驗證改用存檔快照（`tools/saves.py`）。DOSBox-X 的 save state 只能用熱鍵讀取，沒有命令列參數可以在啟動時載入，所以不採用 |

## 下一步

1. 實機巡檢：
   - Message.gp 待確認的參數語序：0-115、0-526～529、3-032 的 `%W1`。
   - Main.exe 待確認的片段組合：40「結束」、304／305 的攻打通知（266～268 存讀檔句型已確認）。
   - 未譯的兩筆：246「蛇」、450「受け」。
   - 片尾的毛筆字（Enddat 68～77）。
2. 移植 kami-zh 的 `jis.py`（全 TSV 缺字掃描＋替代建議）與 `consistency.py`（變體混用、同原文多譯、與 glossary 不一致）。
3. 寫 `install.py`：把上面「建置與驗證」的手動步驟變成一鍵。
4. 其他含日文的圖（Logo「歴史シミュレーションゲーム」、Mainstl 月名、Maincmd「統治」「行軍」（指令按鈕都是漢字，不翻）、Maincmd2 平家物語書法）視需要再譯。
5. 發佈：移植 `mkpatch.py`／Go patcher。
