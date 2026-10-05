# 字型／字庫政策評估

**狀態**：待決。本文件比較「沿用 JIS X 0208 字庫」vs「替換／擴充字型」兩條路線的利弊，供決定。目前未動手，Phase 1 的試譯回寫以 **JIS X 0208 + 必要時用 Japanese shinjitai 替代（抄 kami-zh 政策）** 為基準。

## 1. 現況

### 1.1 字型檔案

| 檔案 | 大小 | 推測結構 | 用途 |
|---|---|---|---|
| `FONT.DAT` | 366,976 B | 11,468 字 × 32 B（16×16 bitmap） | DOSJP.COM 載入的日文全形字型 |
| `JIS.FNT` | 286,336 B | 8,948 字 × 32 B（16×16 bitmap，接近 JIS X 0208 字數 8,836） | 標準 JIS X 0208 bitmap font |
| `FONT.CHR` | 4,096 B | 256 字 × 16 B（8×16 bitmap） | ASCII/半形假名 |

**關鍵事實**：所有字型都是 **16×16 pixel**（全形）。

### 1.2 兩條渲染路徑

這份遊戲在不同環境下用的字型來源不同：

- **原生 DOS/MS-DOS（真機或 DOSBox 預設）**：遊戲完全依賴 `DOSJP.COM -F:FONT.DAT -TJ` 掛的 INT 10h / INT 2Fh 字型 hook。此時字型來自 `FONT.DAT`，可被覆寫。
- **DOSBox-X 的 DOS/V 模式（`dosv=jp` + `getsysfont=true`）**：DOSBox-X 自己提供 DOS/V 日文字型（從 host OS 讀），`DOSJP.COM` 不需要跑；`FONT.DAT` 不被使用。這是我們現在 `tools/dosbox/run.sh` 的實際情境。

**結論**：在 DOSBox-X 現代玩法下，動 `FONT.DAT` 完全無效。

## 2. 政策選項

### A. 沿用 JIS X 0208（抄 kami-zh）✓ 預設

**做法**：
- 翻譯只用 JIS X 0208 範圍內的字。
- 遇到繁體有但 JIS 沒有的字（如「您」「檔」「擊」「嗎」），用 Japanese shinjitai 替代（「撃」）或改寫句型。詳見 `docs/translation-style.md`。
- `tools/patch.py` 已經在 `--check` 階段擋下非 JIS 字（跑 `translation/main.tsv` 第一版就擋了「您」「檔」）。

**優點**：
- 零改動，不碰字型／編碼／引擎。
- 兼容 DOSJP 原生玩法與 DOSBox-X 兩條路徑。
- 修補程式體積小、相容性最高（和 kami-zh 一樣可做發佈用 patcher）。
- kami-zh 已驗證繁中讀者可以接受。

**缺點**：
- JIS X 0208 缺約 3–5% 常用繁體字，集中在口語（「您」「嗎」「吧」「呢」）、現代字（「檔」「資」等）、與部分繁簡分字（「發／髮」合用「発」）。
- 譯文偶爾會出現「用詞不夠自然」或「混用繁簡字形」的情況。
- 「您」「嗎」等語氣詞改寫成「汝」「乎」「邪」等文言，風格會偏古拙（但考慮本作題材是源平時代古代日本，風格相襯）。

### B. 替換 FONT.DAT 成中文字型（**不建議**）

**做法**：
- 做一份 16×16 pixel 的繁體中文 bitmap font，置換 `FONT.DAT`。
- 強制玩家走 `DOSJP + FONT.DAT` 路徑（放棄 DOSBox-X dosv=jp 便利性）。

**優點**：
- 字形可以「看起來像繁中」而不是日系新字體。

**缺點**（多於優點）：
- **16×16 太小**：繁體中文漢字平均 15–20 筆畫，16 pixel 下筆畫會互相糊成一團，閱讀體驗差。日文 shinjitai 筆畫少才能在這解析度存活。
- **DOSBox-X 現代玩法失效**：`dosv=jp + getsysfont=true` 不用 FONT.DAT。要強制玩家切換到「真 DOS」或關閉 getsysfont，操作門檻大幅升高。
- **沒解決編碼問題**：遊戲用 Shift-JIS 定位字型 glyph，替換 FONT.DAT 只是改 glyph 畫面，不會新增 code points；「您」「檔」等本來就無 JIS 編碼的字，仍無法編入譯文。要用這些字必須**同時搞 B 和 C**。
- **DOSJP.COM 無原始碼**：是第三方 1997 年 TSR，不確定它怎麼讀 FONT.DAT 的 header／格式；要魯莽替換很可能壞字。

### C. 擴充字庫：Hijack 未使用的 JIS slot（**技術可行但不建議**）

**做法**：
- 挑 JIS X 0208 中「本作用不到的字」（如罕用漢字、舊字體），把它們的 glyph 替換成缺字（「您」「檔」等）。
- 譯文裡用這些 hijack 的 JIS code 來指涉繁中字。
- 工具層面建一個「繁中字 → hijacked JIS code」的對照表。

**優點**：
- 可以在 Shift-JIS 的框架內塞入全繁體字集（理論上）。

**缺點**：
- **仍需改 FONT.DAT**：同 B 的所有問題（16×16 太小、DOSBox-X 不吃）。
- **TSV 可讀性崩壞**：翻譯者編輯 TSV 時，看到的是「㳛」卻代表「您」（隨便舉例），完全無法人工 review，需要工具層一直做轉換。
- **移植成本高**：之後若 release，玩家下載到的補丁包必須換掉 FONT.DAT，Install 流程變複雜。

### D. 換更大解析度字型 + 改引擎（**超出範圍**）

**做法**：改 Main.exe / Open.exe 的字型渲染程式碼，支援 24×24 或 32×32 full color CJK font。本質上是把遊戲引擎 fork 掉。

**優點**：解決所有字型問題。

**缺點**：工程量巨大，等於新寫一個 game engine，脫離「本地化」範疇。

## 3. 建議

**採用 A（JIS X 0208 only）**，與 kami-zh 同策略。理由：

1. kami-zh 已驗證此策略在繁中讀者端可接受。
2. 本作題材是源平時代古代日本，用稍微偏古的中文（「汝」「乎」「亦」）反而契合氛圍。
3. 零引擎變動，相容兩條渲染路徑，修補程式最輕量。
4. B/C/D 的所有優勢都被 16×16 bitmap 的物理限制卡死，不划算。
5. 以後若真的想做「HD 繁中版」，直接開新 branch 走 D 的路線，和 Phase 1-N 的翻譯檔共享 TSV 即可（翻譯檔是正交資產）。

## 4. 待確認的細節

- [ ] 本作在遊戲過程中有無「畫面有留白、改用更大字體」的場合（例如對話框 title），可能需要用 24×24 字型。若有，則特殊畫面可能需另解。
- [ ] `tools/patch.py` 的 `--check` 檢核應擴充成「全 TSV 掃」命令，一次列出所有缺字並建議 shinjitai 替代（抄 `kami-zh/tools/jis.py` 的 `SUBSTITUTES` 表）。
- [ ] `FONT.DAT` 多出 `11468 - 8948 = 2520` 個 glyph，可能是 KOEI 自家擴充的罕用漢字／裝飾字；需另外調查其 encoding 範圍以確認原作有無用到。
