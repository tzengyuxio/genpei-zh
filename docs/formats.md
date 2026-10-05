# 《源平合戦》(KOEI, 1994, IBM-PC DOS/V) 檔案格式分析

本文件描述遊戲資料檔的格式，整理「哪些檔案含劇情／UI 文字必翻、哪些是純圖形／音樂可跳過」，並附上已可用的解包工具與尚待破解的部分。

分析對象為 `game/GENPEI/` 下 1994 年 KOEI DOS/V 版的原始檔案（版權因素不入 repo）。

目錄：

- [1. 檔案一覽](#1-檔案一覽)
- [2. NPK016 容器（圖形壓縮）](#2-npk016-容器圖形壓縮)
- [3. Message.gp（KOEI LS11 壓縮，已破解）](#3-messagegpkoei-ls11-壓縮已破解)
- [4. Sndata.gp（4 個劇本的初始資料）](#4-sndatagp4-個劇本的初始資料)
- [5. 執行檔內嵌的 UI 文字](#5-執行檔內嵌的-ui-文字)
- [6. 單檔格式速查](#6-單檔格式速查)
- [7. 翻譯優先序與必翻清單](#7-翻譯優先序與必翻清單)
- [8. TODO](#8-todo)
- [9. 工具](#9-工具)
- [10. 圖形格式與全檔 dump](#10-圖形格式與全檔-dump)

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

### 2.2 Chunk header（48 bytes）

```
+0x00  char[6]  "NPK016"
+0x06  u16      planes      (固定為 4，即 4bpp / 16 色)
+0x08  u16      canvas_w    (固定 640)
+0x0a  u16      canvas_h    (固定 400)
+0x0c  u16      width       (影像寬，也是解壓演算法的 `line`)
+0x0e  u16      height      (影像高)
+0x10  u16[16]  palette     0x0RGB；所有檔案、所有 chunk 都是同一張制式色表
                            (000 00f 0f0 0ff f00 f0f ff0 fff 777 00a …)，
                            遊戲不用它，真正的色盤見 §10.2
+0x30  ...      LZ-RLE 壓縮 payload；剛好解出 width × height 個 4-bit 色號
```

- 先前把 header 當成 14 bytes、把 +0x0e 之後全當 payload，會把高度與色表也拿去解壓（前 34 bytes 變雜訊，結尾多出幾個 pixel）。修正後所有 chunk 都剛好解出 width × height。
- 有些檔案在 payload 之後、下一個 magic 之前還有資料：`Opendat.gp` 的 chunk 13–17 後面各有 8 bytes 的 `u16 x, y, w, h`，是**下一張圖的擺放座標**（w、h 與下一張的尺寸相同）；`Maincmd2.gp` 的 chunk 2、3 後面接的是非 NPK 的圖（§10.6）。

### 2.3 Payload 解壓演算法（和 kami-zh 完全相同）

```python
# 每讀 1 byte flag → 以 LSB 優先、8 bits 控制接下來的 8 單元
# bit = 0 → literal：讀 2 bytes，解交織成 4 pixels（planar bits 分散佈局）
#         b1 的 bit 7 → plane 0 bit, bit 3 → plane 0 下一 bit; 
#         b2 的 bit 7 → plane 2 bit, bit 3 → plane 2 下一 bit; 以此類推
# bit = 1 → back-reference：讀 1 byte b
#     run_size   = (b & 0x1F) + 1          # 1..32，單位是「4 pixels」
#     run_offset = ((b >> 5) & 3) + 1      # 1..4
#     run_offset *= width if (b & 0x80) else 4
#     從 (dest 尾端 - run_offset) 複製 run_size * 4 個 pixel
```

### 2.3.1 重新壓縮（`npk.pack()`）的限制

遊戲（Open.exe／End.exe）的解碼器是**逐行**的。Python 版 `unpack()` 可以解的串流，遊戲不一定能解。原版壓縮器從不違反以下三條（實測 Opendat、Enddat、Mainevt、Logo 全部 chunk），自己壓的時候也必須遵守：

1. 回溯參照的 run 不跨行尾。
2. 水平參照（bit 7 = 0）的位移不超過「目前位置在該行內的偏移」，也就是不退到行首之前。
3. 不參照圖的起點之前（Python 版把那裡當 0，遊戲會讀到記憶體裡的垃圾）。

違反任何一條，畫面就會出現條紋。遵守這些限制的 greedy 壓縮仍然比原版略小。

### 2.3.2 Open.exe／End.exe 怎麼找 chunk

程式裡有 u32 offset 表和 size 表，例如 Open.exe 0x12160 是 chunk 14–17 的 offset，0x12170 起是它們的大小（不含 8-byte 座標），0x121F8 是 chunk 44–51 的 offset。帶擺放座標的 chunk，程式另外從「下一個 chunk 的 offset − 8」讀那 8 bytes。

所以換圖時 chunk 的位置與 slot 大小都不能變：新 header＋payload，補 0，最後放回原本的 8-byte 座標（`tools/textimg.py`）。解碼器只解 寬×高 個 pixel，補的 0 不會被讀到。

### 2.4 哪些檔案是 NPK016 容器

全部用 magic scan 確認過（11 個）：

| 檔案 | chunks | 尺寸 | 內容判讀 |
|---|---|---|---|
| `Logo.gp` | 5 | 208×112 等 | KOEI 商標、版權、「KOEI PRESENTS」「歴史シミュレーションゲーム」字樣 |
| `Mainevt.gp` | 13 | 160×128 ×4、128×128 ×4、32×64 ×5 | 事件 CG |
| `Maincmd2.gp` | 4 | 640×400 ×3、160×128 | 全螢幕場景；後面接非 NPK 資料（§10.6） |
| `Mainitem.gp` | 19 | 64×64 | 名物圖（馬、刀、鎧…） |
| `Mainstl.gp` | 13 | 64×152 ×12、520×168 | 12 個月的月令花草圖（睦月…師走）＋小地圖 |
| `Mainmap.gp` | 20 | 88×360 | 世界地圖直條（拼法見 §10.4） |
| `Hikback.gp` | 1 | 288×176 | 一騎討ち背景 |
| `Hkeshiki.gp` | 4 | 640×400 | 合戰畫面外框景色（4 種地形） |
| `Hkumi.gp` | 5 | 208×160 | 一騎討ち武將組合畫 |
| `Opendat.gp` | 52 | 多種 | 片頭 CG（前面 1,968 bytes = 41 組色盤） |
| `Enddat.gp` | 84 | 多種 | 片尾 CG（前面 672 bytes = 14 組色盤） |

`Opendat.gp` 與 `Enddat.gp` 前面的 prefix 是 48-byte 色盤（§10.2），**不是 NPK chunk 的一部分**，magic scan 自動跳過即可。

### 2.5 用法

```bash
# 列出 chunk
python3 tools/npk.py game/GENPEI/Mainevt.gp

# 解壓並存成 PNG（Mainpal.pld 第 0 組色盤）
python3 tools/npk.py game/GENPEI/Mainevt.gp --extract build/dump/tmp
```

輸出範例：

```
game/GENPEI/Mainevt.gp: 13 chunks (57891 bytes)
  [000] off=0x000000 size=   8141 160x128 trailer=0
  [001] off=0x001fcd size=   8334 160x128 trailer=0
  ...
```

chunk 內的色表是制式表、遊戲不用；實際色盤見 §10.2。全部圖檔一次輸出成彩色 PNG 用 `tools/dump_gfx.py`（§10）。

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

## 4. Sndata.gp（4 個劇本的初始資料）

**檔名誤導**：不是 sound，`Sn` 應是 scenario。整檔是 **4 個劇本 × 41,266 bytes**（165,064 = 4 × 41,266），每個劇本＝0x26 bytes 檔頭＋41,228 bytes 的資料表。音樂在 `Music.gp` / `Opmusic.gp` / `Edmusic.gp`。

先前以為「0x24 起是 71-byte record、第一筆以 u16 0x017C 開頭」是錯的：0x017C 屬於檔頭，record 從 0x26 開始、以姓開頭。

### 4.1 劇本檔頭（0x26 bytes）

| 位置 | 型別 | 內容 |
|---|---|---|
| +0x00 | u16 | 年（1180、1183、1184、1185） |
| +0x02 | u8 | 月 − 1（9 → 10 月，與實機「1180年10月」一致） |
| +0x03 | u8 | 未詳（2、1、2、2） |
| +0x04 | u16[16] | 登場勢力編號，−1 結尾（1180 年 15 個、1185 年 5 個） |
| +0x24 | u16 | 未詳（四個劇本都是 380） |

### 4.2 資料表 layout（相對於劇本資料起點）

| 位置 | 筆數 × 大小 | 內容 |
|---|---|---|
| 0x0000 | 400 × 71 | 武將／人物（0–389 武將，390–399 是かむろ、賊、商人、静、政子、後白河法皇等非武將角色） |
| 0x6EF0 | 16 × 20 | 勢力（最後一筆空） |
| 0x7030 | 39 × 76 | 據點（肥後国府…平泉） |
| 0x7BA4 | 32 bytes | 未詳 |
| 0x7BC4 | 8 × 9 | 地方（九州、四国、山陽、近畿、中部、東海、坂東、奥州） |
| 0x7C0C | 256 × 19 | 官位（同名官位有多筆＝名額） |
| 0x8F0C | 256 × 18 | 名物（同一名物每件一筆） |
| 0xA10C | — | 結束 |

**Main.exe 0x4A570–0x54690（41,248 bytes）是同一套表**，武將、勢力、據點與 1180 年劇本逐 byte 相同，但後段順序不同：0x7BA4 的 32 bytes 後多 12 bytes，地方在 0x7BD0、之後 8 bytes、**名物在 0x7C20、官位在 0x8E20**（官位與名物內容和 Sndata 劇本 0 相同）。

### 4.3 武將 record（71 bytes）

| 位置 | 型別 | 內容 | 依據 |
|---|---|---|---|
| +0x00 | char[7] | 姓（SJIS，NUL 補齊；長名會溢到下一欄） | 確定 |
| +0x07 | char[7] | 姓讀音（半形片假名） | 確定 |
| +0x0E | char[5] | 名 | 確定 |
| +0x13 | char[5] | 名讀音 | 確定 |
| +0x1E | u8 | 年齡 | 頼朝 34、義経 22、清盛 63 |
| +0x1F | u8 | 據點編號（本據？） | 頼朝 30＝鎌倉、義仲 25＝木曽谷、清盛 16＝福原 |
| +0x25 | u16 | 主君（武將編號） | 行家→義仲、清盛→宗盛（勢力 1 的首領） |
| +0x27 | u8 | 身分？（0–5） | 推測 |
| +0x31–0x39 | u8 × 9 | 能力值（0–100）；+0x31 疑為武力（義仲 98、義経 90），+0x34 疑為知才（頼朝 95、清盛 96、義仲 21），其餘對應 UI 的体力／菩提／加護／忠節…尚未對上 | 推測 |
| +0x3C | u16 | 所屬勢力（−1＝無） | 義経 3＝奥州藤原、城長茂 10，與勢力表首領一致 |
| +0x3E | u16 | 所在據點 | 義経 38＝平泉 |
| 其他 | | +0x18、+0x1A、+0x1C（400 起跳的 u16）、+0x20–0x24、+0x28–0x30、+0x3A、+0x40（多為 −1）、+0x42（多為 100）未詳 | |

### 4.4 其他 record

- **勢力（20 bytes）**：u16 × 10：首領武將、類型？、對勢力 0–3 的關係值？（對自己 100）、勢力編號、…。
- **據點（76 bytes）**：名稱 9、讀音 9，之後 u16 × 29：鄰接據點 × 7（−1 結尾，鎌倉→27,28,29,31,34,35）、領主武將、2 個未詳、地方編號、所屬勢力，其後是數值欄（疑為農業、治安、財貨、兵糧、雑兵等，未逐一對上）。
- **地方（9 bytes）**：名稱 6、u8、u16（25–50）。
- **官位（19 bytes）**：名稱 13、u8（0x50 或 0xFF）、u8 位階？（10…50，太政大臣 50）、u8、u8、u16。
- **名物（18 bytes）**：名稱 11、u16（多為 −1）、u8 種類？（0＝馬、2＝鎧、6＝歌集…）、u8 × 4。

### 4.5 工具

```bash
python3 tools/dump_data.py game/GENPEI build/dump/data
```

輸出 `sndata_{scenarios,generals,clans,places,regions,ranks,treasures}.tsv`（`scenario` 欄 0–3）與 `mainexe_*.tsv`。未解欄位以 `wXX`／`bXX`（record 內 offset）命名，欄名帶 `?` 的是推測，每列另附整筆 `raw` hex。`tools/analyze_sndata_gp.py` 是舊的快速檢視工具：它以 0x24 為起點、名字取 +2，所以姓名正確，但印出的「id」其實是前一筆 record 的最後 2 bytes，stats 也錯位 2 bytes。

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
| 0x4A570–0x54690 | 劇本資料表（far data）：武將（71-byte record，與 Sndata.gp 同格式：姓 7、姓讀音 7、名 5、名讀音 5 bytes…）、院／法皇等、據點（76-byte，名稱＋讀音）、名物（18-byte，同一名物每件一筆）、官位（19-byte）；確切 layout 見 §4.2 |
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
| `Sndata.gp` | 165,064 | 資料 | 4 個劇本 × 41,266 bytes（§4） | 選翻（姓名、讀法） |
| `Mainevt.gp` | 57,891 | 圖形 | NPK016 (13 chunks) | 不翻（事件 CG） |
| `Maincmd.gp` | 61,216 | 圖形 | 4bpp planar UI 零件（§10.6，邊界部分估計） | 不翻（含「統治」「行軍」字樣圖） |
| `Maincmd2.gp` | 313,971 | 圖形 | NPK016 ×4＋planar＋RLE3（§10.6） | 不翻（含平家物語書法圖） |
| `Mainitem.gp` | 20,801 | 圖形 | NPK016 (19 chunks, 64px) | 不翻（道具 sprite） |
| `Mainstl.gp` | 60,633 | 圖形 | NPK016 (13 chunks) | 不翻（月令圖、小地圖；月名是圖） |
| `Mainmap.gp` | 257,913 | 圖形 | NPK016 (20 條 88×360，§10.4) | 不翻（世界地圖；地名是圖） |
| `Mainobj.gp` | 24,544 | 圖形 | 4bpp planar 地圖物件（§10.6） | 不翻 |
| `Mainanm.gp` | 220,040 | 圖形 | 3bpp 背景＋4bpp sprite（§10.6） | 不翻（指令動畫） |
| `Hikback.gp` | 9,643 | 圖形 | NPK016 (1 chunk, 288px) | 不翻（一騎討背景） |
| `Hikuchi.gp` | 51,840 | 圖形 | 3bpp planar＋mask，一騎討ち騎馬（§10.5） | 不翻 |
| `Hunitpat.gp` | 151,936 | 圖形 | 3bpp planar＋mask，合戰部隊（§10.5） | 不翻 |
| `Hchikei.gp` | 10,060 | 資料 | 合戰地圖高度＋物件（§10.5） | 不翻 |
| `Hkei.gp` | 6,912 | 圖形 | 3bpp 96×96 ×2（§10.5） | 不翻 |
| `Hkeshiki.gp` | 208,531 | 圖形 | NPK016 (4 chunks, 640px) | 不翻（景色 CG） |
| `Hkumi.gp` | 41,563 | 圖形 | NPK016 (5 chunks, 208px) | 不翻（角色組合） |
| `Haikei.gp` | 47,680 | 圖形 | 3bpp 材質＋montage 眼口零件（§10.3） | 不翻 |
| `Kaodata.gp` | 495,435 | 圖形 | RLE3，90 張 128×160 頭像＋剪影（§10.3） | 不翻 |
| `Kisetsu.gp` | 66,428 | 圖形 | RLE3，11 張 160×128 季節事件圖 | 不翻 |
| `Montage.gp` | 239,072 | 圖形 | 3bpp＋mask 頭像組合零件（§10.3） | 不翻 |
| `Logo.gp` | 8,043 | 圖形 | NPK016 (5 chunks) | 不翻 |
| `Opendat.gp` | 853,233 | 圖形 | NPK016 (52 chunks + palette 前綴) | 不翻（片頭 CG） |
| `Enddat.gp` | 1,037,151 | 圖形 | NPK016 (84 chunks + palette 前綴) | 不翻（片尾 CG） |
| `Music.gp` | 44,640 | 音樂 | FM 音源曲譜（entropy 6.5） | 不翻 |
| `Opmusic.gp` | 3,760 | 音樂 | FM（片頭） | 不翻 |
| `Edmusic.gp` | 3,477 | 音樂 | FM（片尾） | 不翻 |
| `Mainpal.pld` | 192 | palette | 4 組 × 48 bytes（B,R,G nibble；四季，§10.2） | 不翻 |
| `Losepal.pld` | 192 | palette | 同上（變暗四階，用途未詳） | 不翻 |
| `Savedata.gp` | 434,030 | 存檔 | 玩家存檔（含 SJIS 姓名） | 不翻 |
| `Disk-1.gp` ... `Disk-5.gp` | 18 | 磁片標籤 | `源平合戦 DISK-N\r` SJIS | 不翻 |
| `Install.exe`, `Install.sys` | — | 安裝 | — | 不翻（安裝選單） |
| `Open.exe` | 79,605 | 執行檔 | ~200 字 UI | **選翻**（環境設定 UI） |
| `Main.exe` | 384,322 | 執行檔（RLE 壓縮，§5.1） | UI ~3,500 字＋資料表 ~4,900 字 | **必翻**（主程式 UI） |
| `End.exe` | 92,121 | 執行檔 | ~210 字 UI | **選翻**（結尾程式 UI） |
| `Main.ori` | 357,780 | 執行檔 | 磁片版 Main.exe（同一份壓縮資料，§5.1） | 不用 |

> 「planar」= 無壓縮、byte-interleaved 的位元平面（§10.1）。要替換成翻譯過的畫面才會動到。

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

- `Sndata.gp`：4 個劇本 × 400 筆人物（多數重複）。日文漢字姓名通常直接保留即可；若要繁簡轉換（如「頼」→「賴」），要全檔案逐 record 處理，注意 71-byte 固定長度。

### 7.3 不翻（純圖形／音樂）

全部的 NPK016 圖形檔、planar 圖形檔、音樂檔。

**已重繪成中文的圖**（`tools/textimg.py`、`translation/images.tsv`）：Opendat 14–17（祇園精舍…書法）、44–51（片頭旁白）；Enddat 68–77（平家物語書法）、78–83（片尾旁白）。

**仍含日文字樣的圖**：`Logo.gp`（KOEI PRESENTS、歴史シミュレーションゲーム）、`Opendat.gp` 的「源平合戦」標題（保留）、`Mainmap.gp`（地圖地名）、`Mainstl.gp`（睦月…師走）、`Maincmd.gp`（統治、行軍等標籤）、`Maincmd2.gp`（平家物語書法）。dump 見 §10。這些檔案的內容是**畫面美術與音效**，不含文字；真的要本地化圖像（如把 CG 裡的日文看板畫新圖），再另外處理。

---

## 8. TODO

- [ ] **確認各類訊息視窗的實際寬度／行數上限**（目前以原文行寬當 warning 門檻）。
- [ ] **搞清楚 Sndata.gp 剩下的欄位**（§4.3–4.4 標「推測／未詳」的部分，需實機對照武將情報畫面）。要修改武將屬性時才需要。
- [x] ~~palette 檔案格式~~（§10.2：48 bytes/組，B,R,G nibble）、~~planar 圖形檔 layout~~（§10）。
- [ ] **Opendat／Enddat 每張圖用哪組色盤**：要讀 Open.exe／End.exe 的動畫腳本；目前是啟發式（§10.2）。
- [ ] **未完全切開的圖**：Mainanm.gp 108,300 之後的 sprite 幀與兩小段、Maincmd.gp 的段落邊界、Haikei 的 64×400 材質用途、Montage 零件的組合座標（DGROUP:0x59CE +0x1C 起）、Hunitpat mask 與幀的對應、Kaodata 每組後的 2 bytes、Losepal 的用途、Maincmd2 640×400 屏風畫的色盤。
- [ ] **音樂檔格式**（`Music.gp` 等）：entropy ~6.3，應該是 YM2608 OPNA / MDX 類的音符資料。若要重做 BGM 才需要解。

---

## 9. 工具

### 已完成（`tools/`）

- **`tools/npk.py`** — NPK016 容器讀取 + LZ-RLE 解壓（48-byte header，§2.2）；`--extract` 存成 PNG。從 `kami-zh/tools/npk.py` 移植，chunk 以 magic 掃描列出。
- **`tools/gfx.py`** — 共用圖形函式：48-byte BRG 色盤、byte-interleaved planar 解碼、1bpp mask、RLE3 解壓、純標準庫 PNG 輸出（§10）。
- **`tools/dump_gfx.py`** — 全部圖檔 → `build/dump/<分類>/<檔名>/*.png`＋`_sheet.png`＋`index.tsv`（§10）。
- **`tools/dump_data.py`** — Sndata.gp 4 個劇本＋Main.exe 內建表 → `build/dump/data/*.tsv`（§4）。
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

- （`.pld` 色盤已由 `tools/gfx.py` 處理，§10.2）

---

## 10. 圖形格式與全檔 dump

`tools/dump_gfx.py` 把所有圖檔輸出成索引色 PNG（mask 掉的像素寫成透明的第 17 色），每個來源檔一個資料夾，內含逐張 PNG、`_sheet.png`（總覽）與 `index.tsv`（offset、大小、用的色盤、備註）：

```bash
python3 tools/dump_gfx.py game/GENPEI build/dump            # 全部（約 15 秒）
python3 tools/dump_gfx.py game/GENPEI build/dump Kaodata    # 只跑某幾個
python3 tools/dump_data.py game/GENPEI build/dump/data      # 資料表（§4）
```

### 10.1 像素格式

本作用到四種編碼：

| 編碼 | 說明 | 用在 |
|---|---|---|
| NPK016 | §2，4bpp | 11 個 NPK 檔 |
| RLE3 | `u16 w, u16 h`＋3bpp 壓縮串流（下述） | Kaodata、Kisetsu、Maincmd2 中段 |
| byte-interleaved planar | 每 N bytes 表示 8 個 pixel，**byte k 是色號的 bit k**（LSB plane 在前），MSB＝最左 pixel；N＝3（8 色）或 4（16 色） | 其餘未壓縮圖檔 |
| 1bpp mask | 逐列、MSB＝最左，**bit 1＝透明** | 帶 mask 的 sprite |

plane 順序的依據：Grpdrv.exe 的 blitter（檔案 0x37EF）把第 0–3 byte 寫到 VGA map mask 1、4、2、8，色盤設定函式（0x2AD8）再經 0x24FA 的對照表 `00 01 04 05 02 03 06 07 …`（對調 bit 1/2）寫 DAC，兩次對調抵銷，所以以邏輯色號（Mainpal）看就是 byte k＝bit k。kaodata repo 舊程式碼用 MSB plane 在前，顏色會藍綠、膚色黃對調。

**RLE3**（取自 kaodata repo `unpack_npk_3bits`）：

```python
b = 讀 1 byte
if b & 0x80:   # copy
    n = (b & 0x0F) + 1                    # 單位 4 pixels
    back = ((b >> 4) & 3) + 1
    back *= width if b & 0x40 else 4
    從 (尾端 - back) 複製 n*4 pixels
else:          # literal，再讀 b2
    4 pixels：bit2 取 b 低 nibble、bit1 取 b2 高 nibble、bit0 取 b2 低 nibble（各 MSB 在左）
    重複 (b >> 4) + 1 次
```

### 10.2 色盤

`.pld` 與 Opendat/Enddat 的 prefix 都是 **48 bytes 一組：16 色 × 3 bytes，每 byte 一個 4-bit 值，順序 B、R、G**（和 kami-zh 的場景色盤同順序）。驗證：Mainpal 色 1–7 讀成 BRG 是 PC-98 數位 8 色的排列（藍、紅、洋紅、綠、青、黃、白），Kaodata 頭像以此上色與實機截圖（`docs/screenshots/phase1-message-chinese-1.png` 的源頼朝）相同；也和 kaodata repo 從截圖量出來的 genpei 色表一致。

| 檔案 | 組數 | 用途 |
|---|---|---|
| `Mainpal.pld` | 4 | 主遊戲。四組只差色 9 與 15，是**四季**（0 春、1 夏、2 秋、3 冬）：地圖、合戰景色依季節換色。色 0–7 固定，3bpp 圖（頭像、montage、sprite）只用這 8 色 |
| `Losepal.pld` | 4 | 整組變暗／褪色的四階（暮色或淡出用？），用途未確認，dump 不採用 |
| `Opendat.gp` prefix | 41 | 片頭；含色 8–15 輪轉（水波、火焰動畫）與淡入淡出的各階段 |
| `Enddat.gp` prefix | 14 | 片尾 |

dump 的選色：Main 系列用 Mainpal 第 0 組（世界地圖與 Hkeshiki 另外四季各出一張）。**Opendat/Enddat 每張圖用哪組色盤由 Open/End.exe 的程式決定，尚未解出**；dump 以啟發式挑選（先挑點亮最多 pixel 的組，再挑相鄰 pixel 亮度差最小者），`index.tsv` 記下挑到的組號，**屬猜測**，例如片頭清盛臉（chunk 8–11）應是火焰色盤，啟發式選成綠色調。

### 10.3 頭像

- **Kaodata.gp**：90 組 ×（128×160 頭像 RLE3＋128×160 剪影 RLE3＋2 bytes），剛好用完整個檔。剪影是同一頭像的輪廓（白底黑影），用途未詳；2 bytes 多為 (0x20,0x10)、(0x18,0x10) 一類，疑為座標偏移。Main.exe（解包後）0x55F04 有 90 個 u32 offset、0x5606C 起是兩段各 90 個 u16 大小。
- **Montage.gp**：無專屬頭像的武將用的組合頭像零件。6 段 × 8 件，每件＝3bpp 顏色＋1bpp mask，依序：類型 2 頭部 72×77、身體 128×99；類型 1 頭部 72×88、身體 128×103；類型 0（武裝）頭部 120×78、身體 128×99。頭部的眼、口位置是黑洞，由 Haikei.gp 的零件補上。
- **Haikei.gp**：檔名是「背景」但內容主要是 montage 零件。0–9,599 是 64×400 的 3bpp 無 mask 區塊（看起來是 5 塊 64×80 的材質，用途未詳）；之後 6 段 × 16 件 40 px 寬的眼睛／口鼻零件（3bpp＋mask）：類型 2 眼 40×14、口 40×25，類型 1 眼 40×11、口 40×30，類型 0 眼 40×12、口 40×27。
- 零件表在 Main.exe DGROUP:0x59CE（解包檔 0x5C23E），3 筆 × 0x26 bytes：u32 頭部／身體在 Montage 的 offset、u16 眼／口在 Haikei 的 offset、各零件的 (寬 bytes, 高)；+0x1C 之後的欄位應是組合座標，未解，所以 dump 只出零件、沒有組好的臉。

### 10.4 地圖

- **Mainmap.gp**：20 條 88×360 直條；每 4 條（352 px）一組，組與組之間重疊 16 px（逐 pixel 比對確認），拼起來是 1696×360 的世界地圖，最右邊是蝶與鶴的裝飾。dump 另出 `worldmap_{0..3}_*.png` 四季版。
- **Mainstl.gp**：12 張 64×152 月令圖（睦月…師走，每月一種花草）＋520×168 的小地圖。

### 10.5 合戰

- **Hkeshiki.gp**：4 張 640×400 合戰畫面外框景色（4 種地形，中央菱形是 hex 盤面的位置），四季色盤各出一張。
- **Hground.gp**：hex 地形 tile，4bpp、寬 48、無 mask（色 0 透明）。3 組 × 37,440 bytes，每組 65 片：9 片 48×36、14 片 48×30、19 片 48×24、14 片 48×18、9 片 48×12；第 4 組（112,320 起）是 3 片 48×24 水面（水戰）。Main.exe 0x55918 有 129 個 u16 tile offset；tile 由 hex 四角高度算出。組別意義（地形？）未確認。
- **Hchikei.gp**：不是圖，是合戰地圖資料。0 起 40 筆 × 196 bytes：14×14 u8 角點高度（0–8），對應 13×13 hex；0x1EA0 起 37 筆 × 60 bytes：物件清單，u8 三元組 (type, a, b)、type 0 結尾，格子＝a×13＋b；type 1/2 疑為柵欄、type 3 為樹（依季節換圖）。dump 成 `heightmaps.tsv`、`objects.tsv` 與高度灰階預覽。
- **Hunitpat.gp**：合戰部隊 sprite，3bpp、寬 32。陸戰組（0）與水戰組（74,048 起）各：騎馬武者 26 張 32×36、旗 5 色 × 13 張 32×36、39 個 32×36 mask（對應前兩者，順序未驗證）、步兵／弓兵 52 張 32×40（26 姿勢 × 2 色）、26 個 32×40 mask（兩色共用）。148,096 起：柵欄 2 張 32×24＋mask、樹 4 張 32×48（春夏秋冬）＋mask。
- **Hikuchi.gp**：一騎討ち騎馬武者，3bpp、寬 80：23 張 80×48＋23 個 mask（33,120 起）、12 張 80×16 馬腳＋12 個 mask（44,160、49,920 起）。
- **Hkei.gp**：2 張 96×96 3bpp 合戰事件圖（陣中、從城坡滾石）。
- **Hikback.gp / Hkumi.gp**（NPK）：一騎討ち背景與武將組合畫。

### 10.6 主畫面其他圖

皆為 byte-interleaved planar（§10.1）、無檔頭、無 mask（色 0 透明）。

- **Maincmd2.gp**（全部 bytes 都有歸屬）：NPK chunk 0–3；chunk 2 之後 0x1507C 是 1,152 bytes 的 4bpp 96×24 名牌框；chunk 3 之後 0x165A7–0x25033 是 10 張 RLE3 160×128 場景（騎射、宴席、獵熊、水中…）；0x25033 是 4bpp 640×400 屏風畫（色 8–15 的色盤未確認，目前看起來很雜）；0x44433 是 3bpp 64×1432＝4 條 64×358 的毛筆字（「驕れる者も久しからず」等平家物語開頭）。
- **Mainobj.gp**（4bpp）：0 起 5 張 24×32 武者（5 色）；1920 起 32 張 16×32 旗；10112 起 16 張 24×27 扇（27 列週期由間隔量得，中等信心）；15296–23648 寬 24 的地圖圖示（城、燒城、田、交叉刀、火、骷髏…，高度不一，整條輸出）；23648 起 7 張 16×16 圓環。
- **Mainanm.gp**：內政等指令的動畫小窗。每場景是一張 3bpp 160×128 背景（7,680 bytes），後面接 4bpp 人物 sprite／動畫幀。0–108,300 的切法已逐張確認（中庭、田野城門、城牆、道場 4 幀動畫、殿內公卿…）；99,328 起 540 bytes 與 107,548 起 752 bytes 未解。108,300 之後背景起點誤差約 ±2 列，sprite 區段只知主要寬度，dump 成整條（`index.tsv` 註明 approximate）。
- **Maincmd.gp**（4bpp UI 零件）：只有 0–3,200（16×400 柱飾）確定；之後依寬度分段：192（窗格、框）、24（材質）、64（「統治」「行軍」字樣與指令圖示）、40、216、16、160，段落邊界是估計值，整段輸出。

### 10.7 其他

- **Kisetsu.gp**：11 張 160×128 RLE3，季節事件插圖（洪水、豐收、疫病、雪…），整檔剛好用完。
- **Mainevt.gp**：事件 CG；**Mainitem.gp**：19 張 64×64 名物圖；**Logo.gp**：KOEI 商標與字樣。
