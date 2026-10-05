# 《源平合戦》(KOEI, 1994, IBM-PC DOS/V) 檔案格式分析

本文件描述遊戲資料檔的格式，整理「哪些檔案含劇情／UI 文字必翻、哪些是純圖形／音樂可跳過」，並附上已可用的解包工具與尚待破解的部分。

分析對象為 `game/GENPEI/` 下 1994 年 KOEI DOS/V 版的原始檔案（版權因素不入 repo）。

目錄：

- [1. 檔案一覽](#1-檔案一覽)
- [2. NPK016 容器（圖形壓縮）](#2-npk016-容器圖形壓縮)
- [3. Message.gp（KOEI LS11 壓縮，已破解）](#3-messagegpkoei-ls11-壓縮已破解)
- [4. Sndata.gp（武將／人物資料庫）](#4-sndatagp武將人物資料庫)
- [5. 執行檔內嵌的 UI 文字](#5-執行檔內嵌的-ui-文字)
- [6. 單檔格式速查](#6-單檔格式速查)
- [7. 翻譯優先序與必翻清單](#7-翻譯優先序與必翻清單)
- [8. TODO](#8-todo)
- [9. 工具](#9-工具)

---

## 1. 檔案一覽

遊戲資料目錄（`game/GENPEI/`）共 55 個檔案。副檔名 `.gp` 的資料檔共 33 個；其餘為執行檔、字型、BAT／設定檔與第三方 TSR。

| 類別 | 檔案 |
|---|---|
| 執行檔 | `Install.exe`, `Open.exe`, `Main.exe`, `End.exe`, `Main.ori`, `Grpdrv.exe` |
| TSR / 字型（第三方）| `DOSJP.COM`, `Fmdrv.com`, `Genpei.com`, `FONT.CHR`, `FONT.DAT`, `JIS.FNT` |
| 設定 / BAT | `Config.5`, `DOSV.BAT`, `Play.bat`, `Install.sys`, `Version` |
| 遊戲資料 (`.gp`) | 下列各節描述 |

遊戲進入點：`Install.exe` → `Open.exe`（標題／劇情前段）→ `Main.exe`（主遊戲迴圈）→ `End.exe`（結尾）。日文字型由 `DOSJP.COM -F:font.dat -TJ` 載入，是非原版的 1997 年第三方工具（參考 README）。

---

## 2. NPK016 容器（圖形壓縮）

《源平合戦》所有壓縮圖像都用 **NPK016 容器 + 一種 flag-bit 驅動的 LZ-RLE**，和姊妹作《神々の大地》同屬 KOEI 1994 年前後的通用格式；但容器與 chunk header 的欄位語意有差異，直接套用 `kami-zh/tools/npk.py` 會解壓失敗（已踩過坑）。本專案的實作在 `tools/npk.py`。

### 2.1 容器 layout

**《源平合戦》版**：NPK016 chunk **直接串接**，檔頭沒有 u32 offset table。用 magic `b"NPK016"` 掃描即可列出所有 chunk。

**對照《神々の大地》版**：檔頭有 `u32[n]` offset table（第一個 u32 = `offsets[0] / 4` = chunk 數）。本作沒有這個 table。

### 2.2 Chunk header（14 bytes）

```
+0x00  char[6]  "NPK016"
+0x06  u16      planes      (固定為 4，即 4bpp / 16 色)
+0x08  u16      canvas_w    (多為 640，螢幕畫布寬)
+0x0a  u16      canvas_h    (多為 400，螢幕畫布高)
+0x0c  u16      stride      (本 chunk 的 scanline 像素寬 ← 《神々の大地》
                             這個欄位是 chunk 自己的 byte-size；
                             本作改成「真正影像的像素寬」)
+0x0e  ...      LZ-RLE 壓縮 payload；解壓後每 byte = 1 個 4-bit 色盤索引
```

- `stride` 即解壓演算法的 `line` 參數，也等於解壓結果的「每行像素數」。
- Chunk 的 payload 自己會結束（讀完 bit 旗標與資料就停）。影像高度在 header 裡沒給，用 `len(decoded) / stride` 算出來。多數檔案的 chunk 是尺寸不定的 sprite strip，不是整張 640×400。

### 2.3 Payload 解壓演算法（和 kami-zh 完全相同）

```python
# 每讀 1 byte flag → 以 LSB 優先、8 bits 控制接下來的 8 單元
# bit = 0 → literal：讀 2 bytes，解交織成 4 pixels（planar bits 分散佈局）
#         b1 的 bit 7 → plane 0 bit, bit 3 → plane 0 下一 bit; 
#         b2 的 bit 7 → plane 2 bit, bit 3 → plane 2 下一 bit; 以此類推
# bit = 1 → back-reference：讀 1 byte b
#     run_size   = (b & 0x1F) + 1          # 1..32，單位是「4 pixels」
#     run_offset = ((b >> 5) & 3) + 1      # 1..4
#     run_offset *= stride if (b & 0x80) else 4
#     從 (dest 尾端 - run_offset) 複製 run_size * 4 個 pixel
```

### 2.4 哪些檔案是 NPK016 容器

全部用 magic scan 確認過（12 個）：

| 檔案 | chunks | stride 分布 | 內容判讀 |
|---|---|---|---|
| `Logo.gp` | 5 | 208, 208, 368, 400, 272 | KOEI 商標／標題動畫 |
| `Mainevt.gp` | 13 | 160, 128, 32 | 事件 CG（劇情插圖） |
| `Maincmd2.gp` | 4 | 640 | 全螢幕 CG（議政廳、宮廷等場景） |
| `Mainitem.gp` | 19 | 64 | 道具 / 馬匹 sprite |
| `Mainstl.gp` | 13 | 64 | 立繪 sprite strip |
| `Mainmap.gp` | 20 | 88 | 世界地圖地形 tile strip |
| `Hikback.gp` | 1 | 288 | 一騎討ち背景 |
| `Hkeshiki.gp` | 4 | 640 | 景色 CG（山景、海景） |
| `Hkumi.gp` | 5 | 208 | 一騎討ち角色組合畫 |
| `Opendat.gp` | 52 | 640 | 片頭動畫 CG（開頭有 ~1968 bytes 的 palette prefix 不是 NPK） |
| `Enddat.gp` | 84 | 640 | 片尾動畫 CG（開頭有 ~672 bytes 的 palette prefix） |

`Opendat.gp` 與 `Enddat.gp` 前面的小 prefix（看起來是 4bpp palette 定義，nibble 值 0..F）**不是 NPK chunk 的一部分**，magic scan 自動跳過即可。

### 2.5 用法

```bash
# 列出 chunk
python3 tools/npk.py game/GENPEI/Mainevt.gp

# 解壓並儲存成 PGM（灰階 preview）
python3 tools/npk.py game/GENPEI/Mainevt.gp --extract /tmp/out
```

輸出範例：

```
game/GENPEI/Mainevt.gp: 13 chunks (57891 bytes)
  [000] off=0x000000 size=   8141 planes=4 canvas=640x400 stride= 160 -> 160x139 (22368 px)
  [001] off=0x001fcd size=   8334 planes=4 canvas=640x400 stride= 160 -> 160x133 (21352 px)
  ...
```

真正的 16 色 palette 不存在 chunk 裡，而是另外存放（本作疑似在 `Mainpal.pld`、`Losepal.pld` 等 `.pld` 檔，與對應 CG 配對）。目前還沒做出彩色預覽；灰階 PGM 已足夠辨識畫面內容。

---

## 3. Message.gp（KOEI LS11 壓縮，已破解）

### 3.1 LS11 容器

LS11 是 KOEI 90 年代前期通用的壓縮格式（三國志、信長之野望系列也用）。**所有整數皆為 big-endian**（先前分析把檔案表讀成 little-endian，才會誤以為是「15 筆劇本描述」）。

```
+0x000  char[4]   "LS11"
+0x004  byte[12]  全 0
+0x010  byte[256] 字典：literal code i 解成 dict[i]（依頻率排序，常用 byte 碼短）
+0x110  {u32 packed, u32 unpacked, u32 offset} × N，以 u32 0 結尾
...     各 entry 的壓縮資料，彼此獨立的 MSB-first bit stream
```

本檔 N = 5：

| entry | packed | unpacked | offset | 訊息數 |
|---|---|---|---|---|
| 0 | 15,550 | 21,799 | 0x0150 | 599 |
| 1 | 4,368 | 5,899 | 0x3E0E | 174 |
| 2 | 4,884 | 6,014 | 0x4F1E | 220 |
| 3 | 4,359 | 5,685 | 0x6232 | 174 |
| 4 | 4,476 | 5,487 | 0x7339 | 138 |

最後一筆 offset + packed = 33,973 = 檔案大小。

### 3.2 解壓演算法

```python
def code():                     # 變長碼
    n = 1
    while getbit(): n += 1      # n-1 個 1 再一個 0 → 值 2^n - 2
    return (1 << n) - 2 + getbits(n)

while len(out) < unpacked:
    c = code()
    if c < 256: out.append(dict[c])            # literal
    else:                                       # LZ77 copy
        dist = c - 256; length = code() + 3
        for _ in range(length): out.append(out[-dist])
```

壓縮端（`tools/ls11.py`）沿用原字典，greedy LZ77（3-byte hash chain，只在省 bit 時才用 copy）。重新壓縮原內容得 33,047 bytes（比原檔小），round-trip 驗證位元一致。

### 3.3 Block 結構

每個解壓後的 entry 是一個 message block：

```
u16-LE offset[n]     offset[0] = 2n（表自己決定筆數）
message[n]           offset[k] .. offset[k+1]（最後一則到 block 結尾）
```

offset 是 u16，**單一 block 上限 64 KB**。回寫時重建 offset table，訊息長度不受原長度限制。

### 3.4 訊息內容與控制碼

| bytes | 意義 | TSV 表示 |
|---|---|---|
| `0A` | 換行 | `\n` |
| `1B 4B` / `1B 48` (ESC K / ESC H) | 半形假名改以片假名／平假名顯示 | 不列出（`original_ja` 直接轉好） |
| `1B 43 d` (ESC C d) | 顏色（見 `C6` 標題色、`C7` 還原） | `{C6}` |
| `%s %u %4u %B1 %B2 %N1..3 %W1 %D1` | 遊戲帶入的參數（人名、數字、軍名…） | 原樣保留 |
| `05 05 05` | 訊息結尾（1 則缺、1 則後面多 `00`） | 自動保留，不列出 |

**半形假名＝平假名**：本作為了省空間，訊息裡的假名幾乎都存成半形片假名（1 byte），引擎預設把它畫成平假名，遇 `ESC K` 才畫成片假名。例：`武将ｦ選択ｼﾃｸﾀﾞｻｲ` 實際顯示「武将を選択してください」。`tools/message.py` 抽字時已轉回可讀的平／片假名。

譯文寫全形繁中即可（Shift-JIS 2 bytes），不需要半形。

### 3.5 文字量

1,305 則訊息、約 26,300 字（不含控制碼）。內容：戰報、軍議／家臣進言、事件、人物死亡、朝廷／官位、合戰結果、操作提示、遊戲說明（`{C6}…說明{C7}` 的長篇說明頁）。

### 3.6 長度限制

- 不再是「≤ 原 byte 數」：block 重建後只受 u16 offset（64 KB/block）限制。實測：1,305 則全改全形並加前綴（block 0 從 21.8 KB 長到 32.7 KB）遊戲仍正常（見 §3.8）。
- 真正的限制是**訊息視窗大小**：`message.py apply` 以原文的行數與每行半形格寬（`lines`、`max_cols` 欄）為準，譯文超過時發 warning（不擋）。視窗實際寬度待逐類畫面確認。
- printf 參數數量與種類必須與原文一致，不一致直接 error（錯了會讀錯堆疊、可能當機）。

### 3.7 工具

```bash
python3 tools/ls11.py selftest game/GENPEI/Message.gp      # codec round-trip
python3 tools/ls11.py unpack   game/GENPEI/Message.gp OUT/ # 解出 5 個 block
python3 tools/message.py extract game/GENPEI/Message.gp extracted/text/message.tsv
python3 tools/message.py apply   game/GENPEI/Message.gp translation/message.tsv \
                                 build/GENPEI/Message.gp
```

### 3.8 實機驗證

8 則試譯（`translation/message.tsv`）重新壓縮後放入 `build/GENPEI/`，以 `tools/dosbox/newgame.mouse` 腳本開新遊戲（1180 年劇本、源頼朝），首批對話全部正確顯示繁中，`%s` 參數（人名、地名）正確帶入，對話框依內容自動調寬。截圖：`docs/screenshots/phase1-message-chinese-{1,2}.png`。

先前另做過壓力測試：1,305 則全部改成全形並加上 `測<block><index>` 前綴，遊戲照常運作，也藉此對出畫面訊息與 TSV id 的對應（開局軍議 = 4-000～4-004，來投武將 = 1-021～1-026）。

## 4. Sndata.gp（武將／人物資料庫）

**檔名誤導**：`Sn` 一度看起來像「sound」，但實際內容是**武將／人物屬性表**，和「音訊」無關。真正的音樂資料在 `Music.gp` / `Opmusic.gp` / `Edmusic.gp`。

### 4.1 Layout

```
+0x00  u16        0x049C (= 1180，意義未確認；可能是 record 總數相關)
+0x02  u16        0x0209 (=  521，意義未確認)
+0x04  byte[0x20] 索引表 prefix：
                  00 00  01 00  02 00  ...  0E 00   (u16[15] = 0..14)
                  FF FF   (u16 = -1 ，結束標記)
                  7C 01   (u16 = 0x017C，第 1 筆的某個欄位值)
+0x24  record[N]  固定長度 71 bytes 的武將紀錄
```

檔案大小 165,064 bytes。從 0x24 起的 body 共 165,028 bytes，`165028 / 71 ≈ 2324.3` → 粗略 2324 筆 record（可能最後一筆是 partial / 哨兵）。

### 4.2 Record（71 bytes）內容

以第 1 筆（源頼朝）為例：
```
offset   bytes                     field
+0x00    7C 01                     u16  ID / 體力？（0x017C = 380）
+0x02    8C B9 00 00 00 00 00      SJIS 姓（6 bytes 內容 + padding），例 "源"
+0x09    D0 C5 D3 C4 00 00 00      半形假名 姓讀法，例 "ﾐﾅﾓﾄ"
+0x10    97 8A 92 A9 00            SJIS 名（4 bytes + padding），例 "頼朝"
+0x15    D6 D8 C4 D3 00            半形假名 名讀法，例 "ﾖﾘﾄﾓ"
+0x1A    00 00 00 00 00            padding
+0x1E    90 01 22 1E 00 08 00 ...  u8/u16 混合的能力值／屬性區（具體 41 bytes 未詳）
```

### 4.3 驗證結果

前 15 筆 record 解析一致：源頼朝、源義経、源範頼、阿野全成、源義円、武田信義、…。所有源氏成員「姓=源 / 姓讀=ﾐﾅﾓﾄ」固定出現，record 間距精確等於 71 bytes。

### 4.4 翻譯意義

本檔要翻的只有：
- **姓／名 SJIS 欄位**（第 1、3 欄）：角色名字；大多是歷史人物，應保留日文漢字即可（可選擇是否轉繁簡）。
- **半形假名讀法**（第 2、4 欄）：遊戲內顯示讀音，中文版可能不需要讀音（但要注意固定長度，不能縮短）。

能力值區（+0x1E 起）**不需要翻譯**，但若要改 record 內容時要原地覆寫、不要改變 record size。

### 4.5 工具

- `tools/analyze_sndata_gp.py`：印出 header 與前 N 筆 record。
  ```bash
  python3 tools/analyze_sndata_gp.py game/GENPEI/Sndata.gp 20
  ```

---

## 5. 執行檔內嵌的 UI 文字

### 5.1 Main.exe（主遊戲，384,322 bytes；解包後 392,816 bytes）

#### 5.1.1 Main.exe 是壓縮過的

Main.exe 用一種「字面值＋填充值」的 RLE 壓縮（專吃連續的 0 與空白），入口 `5440:0001` 的 stub 執行時先在記憶體裡展開，再跳到真正入口 `0000:0B86`。**直接掃檔案只看得到剛好以字面值保存的片段**：補零／補空白被壓掉、相鄰欄位黏在一起（如「ｲﾏｲ兼平」）、選單字串尾端的置中空白消失。所以 Main.exe 的抽字與回寫一律在解包後的檔案上做。

stub 格式（offset 相對於 stub 段）：

| 位置 | 內容 |
|---|---|
| `+0x10` | 先把 stub 往上搬的段落數（解開後映像的結尾就在搬移後的 stub 起點） |
| `+0x2B` | 控制 record 數（0x81F） |
| `+0x1977` 往回讀 | 每筆 record：`b0`（bit0：字面值長度 2 bytes；bit1：填充長度 2 bytes，高位元組 = b0>>2）、字面值長度、填充長度、填充值。從映像尾端往前寫：先複製字面值（壓縮資料自 stub 正下方往回讀），再寫填充 |
| `+0x8B` | relocation 筆數（5,354） |
| `+0x1978` 往後讀 | relocation：`b>1` 前進 b bytes；`b=0` 前進下一個 u16；`b=1` 段落 += 下一 byte×256 再前進下一個 u16 |
| `+0xBF` / `+0xB7` / `+0xBC` | 真正的 CS:IP、SS、SP |

`tools/unpack_exe.py` 照此解成普通 MZ（無壓縮、帶完整 relocation table），已實機驗證可正常遊玩。

**與 Main.ori 的關係**：兩者是同一份 RLE 壓縮資料。2 KB 之後只差 45 bytes——Main.exe 把 35 處 `A:`/`B:` 路徑改成 `C:`、停用兩處 `INT 13h` 軟碟檢查（KOEI 安裝程式的硬碟化處理）。Main.ori 的前 2 KB 另外多包一層、stub 也不同（未解，不需要）。Genpei.com 只會呼叫 `MAIN.EXE`，翻譯基準用 Main.exe。

#### 5.1.2 解包後的分區

| 檔案位置 | 內容 |
|---|---|
| 0x000000–0x4A570 | header（0x53D0）＋程式碼：沒有文字，只有掃描雜訊 |
| 0x4A570–0x54690 | 劇本資料表（far data）：武將（71-byte record，與 Sndata.gp 同格式：姓 7、姓讀音 7、名 5、名讀音 5 bytes…）、院／法皇等、據點（76-byte，名稱＋讀音）、名物（18-byte，同一名物每件一筆）、官位（19-byte） |
| 0x54690– | UI 字串；主體在 DGROUP（段 514Ah = 檔案 0x56870，由啟動碼 `mov di, 514Ah` 得知） |

UI 字串以 NUL 結尾，多數經由**指標陣列**引用（不是 `push imm16`），常常緊接在指標表之後，指標表的 bytes 會被解碼成「^3」「G!G」「4Y9Y…」之類的殘渣黏在字串前面；`tools/exe_text.py` 會把它們切掉。

#### 5.1.3 字串內容

- 控制碼與 Message.gp 相同：`ESC C6`／`ESC C7`（標題色／還原，TSV 寫 `{C6}`）、`ESC C3`、`\n`、printf 參數（`%s %u %3u %4d …`）。
- **選單字串用空白補齊來置中**（如 `'    新しくゲームを始める    '`，28 bytes），`max_bytes` 含空白；譯文應補回同樣寬度並置中。
- 同一字串常有多份（「財貨」5 處），TSV 已合併，`offsets` 列出全部位置，回寫時一起改。
- 人名讀音是半形片假名（武將情報畫面上的小字讀音）。
- 對話框右上的小按鈕（讀檔畫面的「中止」、選棟梁的「決定」）是圖：Main.exe 裡「中  止」只有一份，改掉後只影響登用確認框的按鈕。

#### 5.1.4 數量

| TSV | 條數（不重複） | 位置數 | 字數 |
|---|---|---|---|
| `extracted/text/main.tsv`（UI） | 496 | 595 | ~3,500 |
| `extracted/text/main_data.tsv`（name：人名、地名、名物、官位） | 937 | — | — |
| 同上（reading：半形讀音） | 624 | — | — |

`main_data.tsv` 合計 1,561 條、2,168 處、約 4,900 字。資料表欄位的長度上限取原字串長度（補零之後可能接著值為 0 的數值欄，不能假設可以借用）。

### 5.2 Open.exe（片頭程式，79,605 bytes）

- 實測（`tools/exe_text.py`，只掃 DGROUP = 檔案 0x11C40 之後）：37 條、約 180 字，包括：
  - UI 字串「よろしいですか？」、「決定」、「中止」、「決定  中止」、「確認」等。
  - 磁片／設定提示文字。
- 檔案很乾淨（entropy 6.67，無封裝器簽章），可以直接改字串。
- 關鍵檔名表位於 **0x11CB0..0x11DC2**，可用於驗證遊戲會載入哪些 `.gp` 檔。

### 5.3 End.exe（結尾程式，92,121 bytes）

- 實測（DGROUP = 檔案 0x14DB0 之後）：41 條、約 200 字，大多與 Open.exe 相同的磁片／環境設定訊息（片尾 staff roll 是 Enddat.gp 的圖，不是文字）。

### 5.4 檔名／路徑字串（Open.exe + Main.exe 都有）

```
A:SNDATA1.GP     A:MAINCMD.GP     A:MAINOBJ.GP     A:MAINANM.GP
A:MESSAGE.GP     A:USERDAT.GP     A:MAINPAL.PLD    A:KAODATA.GP
A:HAIKEI.GP      B:MAINMAP.GP     B:CHIKEI.GP      B:KESHIKI.GP
B:GROUND.GP      B:UNITPAT.GP     B:IKKIUCHI.GP    B:IKKIBACK.GP
A:SAVEDAT.GP     A:USERDIR.GP     A:ADISK.GP       A:OPENDAT.GP
A:LOGO.GP        A:OPMUSIC.GP     A:DISK-1.GP      A:DISK-2.GP
A:DISK-3.GP      B:DISK-4.GP     ...
```

磁碟代號 `A:` / `B:` 是歷史殘留（原本是雙磁片組合）；安裝到 HDD 後都在同一個 `game/GENPEI/` 目錄。檔名中帶 `H` 前綴的（`Hchikei`, `Hkumi`, `Hikuchi`, `Hikback`, …）去掉 `H` 就是程式碼裡的名字；可能是 HDD 安裝版的檔名轉換（Hard-disk 版？）。

---

## 6. 單檔格式速查

| 檔案 | 大小 | 分類 | 格式 | 翻譯需求 |
|---|---|---|---|---|
| `Message.gp` | 33,973 | 文字 | **LS11** 壓縮（§3） | **必翻**，核心訊息 |
| `Sndata.gp` | 165,064 | 資料 | 71-byte record 表（人物） | 選翻（姓名、讀法） |
| `Mainevt.gp` | 57,891 | 圖形 | NPK016 (13 chunks) | 不翻（劇情插圖） |
| `Maincmd.gp` | 61,216 | 圖形 | 原始 4bpp planar | 不翻 |
| `Maincmd2.gp` | 313,971 | 圖形 | NPK016 (4 chunks, 640px) | 不翻（場景 CG） |
| `Mainitem.gp` | 20,801 | 圖形 | NPK016 (19 chunks, 64px) | 不翻（道具 sprite） |
| `Mainstl.gp` | 60,633 | 圖形 | NPK016 (13 chunks, 64px) | 不翻（立繪 sprite） |
| `Mainmap.gp` | 257,913 | 圖形 | NPK016 (20 chunks, 88px) | 不翻（地圖 tiles） |
| `Mainobj.gp` | 24,544 | 圖形 | 原始 4bpp planar | 不翻 |
| `Mainanm.gp` | 220,040 | 圖形 | 原始 4bpp planar | 不翻（單位動畫） |
| `Hikback.gp` | 9,643 | 圖形 | NPK016 (1 chunk, 288px) | 不翻（一騎討背景） |
| `Hikuchi.gp` | 51,840 | 圖形 | 原始 planar（CHIKEI=地形） | 不翻 |
| `Hunitpat.gp` | 151,936 | 圖形 | 原始 planar（UNITPAT=兵種圖樣） | 不翻 |
| `Hchikei.gp` | 10,060 | 圖形 | 原始 planar（CHIKEI 小圖） | 不翻 |
| `Hkei.gp` | 6,912 | 圖形 | 原始 planar | 不翻 |
| `Hkeshiki.gp` | 208,531 | 圖形 | NPK016 (4 chunks, 640px) | 不翻（景色 CG） |
| `Hkumi.gp` | 41,563 | 圖形 | NPK016 (5 chunks, 208px) | 不翻（角色組合） |
| `Haikei.gp` | 47,680 | 圖形 | 原始 planar（背景） | 不翻 |
| `Kaodata.gp` | 495,435 | 圖形 | 原始 4bpp planar（人物肖像集） | 不翻 |
| `Kisetsu.gp` | 66,428 | 圖形 | 原始 planar（季節 tile set） | 不翻 |
| `Montage.gp` | 239,072 | 圖形 | 原始 planar（face parts？） | 不翻 |
| `Logo.gp` | 8,043 | 圖形 | NPK016 (5 chunks) | 不翻 |
| `Opendat.gp` | 853,233 | 圖形 | NPK016 (52 chunks + palette 前綴) | 不翻（片頭 CG） |
| `Enddat.gp` | 1,037,151 | 圖形 | NPK016 (84 chunks + palette 前綴) | 不翻（片尾 CG） |
| `Music.gp` | 44,640 | 音樂 | FM 音源曲譜（entropy 6.5） | 不翻 |
| `Opmusic.gp` | 3,760 | 音樂 | FM（片頭） | 不翻 |
| `Edmusic.gp` | 3,477 | 音樂 | FM（片尾） | 不翻 |
| `Mainpal.pld` | 192 | palette | 96 × u16 0x0RGB | 不翻（16 色 × 多組？） |
| `Losepal.pld` | 192 | palette | 同上 | 不翻 |
| `Savedata.gp` | 434,030 | 存檔 | 玩家存檔（含 SJIS 姓名） | 不翻 |
| `Disk-1.gp` ... `Disk-5.gp` | 18 | 磁片標籤 | `源平合戦 DISK-N\r` SJIS | 不翻 |
| `Install.exe`, `Install.sys` | — | 安裝 | — | 不翻（安裝選單） |
| `Open.exe` | 79,605 | 執行檔 | ~200 字 UI | **選翻**（環境設定 UI） |
| `Main.exe` | 384,322 | 執行檔（RLE 壓縮，§5.1） | UI ~3,500 字＋資料表 ~4,900 字 | **必翻**（主程式 UI） |
| `End.exe` | 92,121 | 執行檔 | ~210 字 UI | **選翻**（結尾程式 UI） |
| `Main.ori` | 357,780 | 執行檔 | 磁片版 Main.exe（同一份壓縮資料，§5.1） | 不用 |

> 「原始 planar」= 無壓縮的 4bpp 位元平面排列，和 PC-9801／DOS/V 的 VRAM layout 一樣。要替換成翻譯過的畫面才會動到。

---

## 7. 翻譯優先序與必翻清單

### 7.1 必翻（文字）

| 來源 | 筆數 | 字數（實測） | 說明 |
|---|---|---|---|
| **`Message.gp`** | 1,305 則 | ~26,300 | 對話、戰報、事件、遊戲說明，占全遊戲最大宗 |
| **`Main.exe` UI** | 496 條 | ~3,500 | 選單、指令、狀態欄、對話框 |
| `Main.exe` 資料表 | 937 名稱＋624 讀音 | ~4,900 | 人名、地名、名物、官位（譯名政策待定） |
| **`Open.exe`** | 37 條 | ~180 | 環境設定、磁片提示 |
| **`End.exe`** | 41 條 | ~200 | 結尾程式 UI（片尾字幕本身是 Enddat.gp 的圖） |

**總計約 30,200 字**（UI 與劇情；另有資料表約 4,900 字、Sndata.gp 人名）。片頭「祇園精舎…」、「歴史シミュレーションゲーム」等字樣是 Opendat.gp 的圖，不在文字檔內。

### 7.2 選翻

- `Sndata.gp`：武將姓名 2,000+ 筆。日文漢字姓名通常直接保留即可；若要繁簡轉換（如「頼」→「賴」），要全檔案逐 record 處理，注意 71-byte 固定長度。

### 7.3 不翻（純圖形／音樂）

全部的 NPK016 圖形檔、planar 圖形檔、音樂檔。這些檔案的內容是**畫面美術與音效**，不含文字；真的要本地化圖像（如把 CG 裡的日文看板畫新圖），再另外處理。

---

## 8. TODO

- [ ] **確認各類訊息視窗的實際寬度／行數上限**（目前以原文行寬當 warning 門檻）。
- [ ] **搞清楚 Sndata.gp 的能力值欄位**（record 內 +0x1E 之後的 41 bytes）。要修改武將屬性或擴充 record 時才需要。
- [ ] **palette 檔案 (`.pld`) 格式確認**：目前推測是 `u16[16] × 多組`（每組 16 色），每個 u16 用 kami-zh 同款 `0x0RGB` 編碼。192 bytes = 96 × u16 = 6 組 × 16 色。要彩色預覽 NPK016 CG 時需要。
- [ ] **原始 planar 圖形檔的 header 結構**：`Mainobj.gp`, `Mainanm.gp`, `Mainitem.gp` 等看起來有「索引表 + sprite 資料」layout，但未解析細節。做圖像替換時需要。
- [ ] **音樂檔格式**（`Music.gp` 等）：entropy ~6.3，應該是 YM2608 OPNA / MDX 類的音符資料。若要重做 BGM 才需要解。

---

## 9. 工具

### 已完成（`tools/`）

- **`tools/npk.py`** — NPK016 容器讀取 + LZ-RLE 解壓；可選擇 extract 為灰階 PGM。這是從 `kami-zh/tools/npk.py` 移植過來，但 `stride` 欄位語意改為「scanline 像素寬」、chunk 以 magic 掃描列出。
- **`tools/sjis_scan.py`** — 掃描檔案的 Shift-JIS 字串，支援 XOR key。從 kami-zh 移植。
- **`tools/ls11.py`** — KOEI LS11 解壓／重新壓縮（§3）。
- **`tools/unpack_exe.py`** — 把壓縮的 Main.exe 解成普通 MZ（§5.1）。
- **`tools/exe_text.py`** — Main/Open/End.exe 的 DGROUP 字串＋Main.exe 資料表 → TSV（去雜訊、合併重複）。
- **`tools/patch.py`** — TSV → EXE 原地回寫（多位置、控制碼與 printf 檢核）。
- **`tools/message.py`** — Message.gp ↔ TSV（抽字、回寫、printf 參數與 JIS 檢核）。
- **`tools/analyze_sndata_gp.py`** — Sndata.gp 武將紀錄 dumper，印出前 N 筆解析後的 record。

### 可從 kami-zh 直接移植的

對照 `~/works/kami-zh/tools/`：

- `jis.py`：Shift-JIS 翻譯檢核（缺字檢查、建議相近字），翻譯驗證階段會用到。
- `patch.py`、`mkpatch.py`：生成修補程式。
- `dosbox/*`：DOSBox-X 配置與自動化（本作可直接沿用）。
- `release.sh`：發佈流程。

### 待寫

- `tools/pld.py` — `.pld` palette 檔讀取 + 轉 RGB。
