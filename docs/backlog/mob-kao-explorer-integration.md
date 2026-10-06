---
status: planned
created: 2026-10-07
---

# 大眾臉探索器：跨遊戲整合

目前發布版：<https://tzengyuxio.github.io/fc-sangokushi/genpei-mob-kao-explorer.html>（fc-sangokushi repo `docs/`，2026-10-07 手動複製）。

## 目標

1. **縮小檔案**：`build/mob-kao-explorer.html` 目前約 816 KB，其中圖像約 773 KB（58 萬 pixel，每 pixel 1 byte 色號，再 base64）。
2. **多遊戲共用**：把源平合戰與 FC 三國志（<https://tzengyuxio.github.io/fc-sangokushi/mob-kao-explorer.html>）等遊戲的大眾臉探索器整合，抽出共通部分，遊戲差異做成可抽換的介面。

## 現況比較

| | fc-sangokushi | genpei-zh（`tools/mob_kao_explorer.py`） |
|---|---|---|
| 嵌入資料 | FC 原始 8×8 tile bytes（hex），JS 解 2bpp | Python 先解好的色號陣列（base64），JS 只查色盤 |
| 組法 | tile 依模板（`TEMPLATES`）排成格子 | 整塊零件依座標疊在 128×160 緩衝區，mask 決定透明 |
| 色數 | 4 | 16 |
| 頁面大小 | 約 63 KB | 約 816 KB |

## 決議：建置時解碼成統一格式，壓縮後嵌入

不存各遊戲的原始格式（如 planar bytes）。原始格式差異大（FC 2bpp tile、源平 3bpp planar＋1bpp mask、其他作品可能是 RLE／4bpp），存原始 bytes 就得每個遊戲寫一份 JS 解碼器，而且要和 Python 版的解碼保持一致。改成：

- 各遊戲的 Python 轉換器（遊戲專屬，沿用既有 dump 工具）負責解碼，輸出**統一的資料 JSON**。
- 共用頁面只認統一格式，不知道原始格式。
- 容量交給壓縮：色號陣列 deflate 後 base64，瀏覽器用 `DecompressionStream` 解（非同步，載入流程多一層 await）。透明值大量重複，預期比存 planar（約 4 bits/pixel，整頁約 430 KB）更小。

## 分層

```
各遊戲 Python 轉換器（遊戲專屬：dump_gfx.py、FC tile 解碼…）
        ↓ 統一資料 JSON（deflate＋base64 內嵌，或另存 .bin）
共用頁面（單一 HTML/JS，與遊戲無關）
  ├─ 渲染器：依圖層順序把零件色號疊到畫布、套色盤
  ├─ UI：部件格、預覽、隨機、下載、武將清單、搜尋、網址 hash
  └─ 遊戲外掛（少量 JS）：只處理資料描述不了的規則
```

### 統一資料 JSON（草案）

- `meta`：遊戲名、畫布大小（源平 128×160）、顯示窗大小與位置（源平 64×80，依類型）、預設放大倍率
- `palettes`：一或多組色盤；色號 255＝透明
- `slots`：部位與疊圖順序（源平：身 → 頭 → 眼 → 口；FC：頭 → 眼 → 鼻 → 口）
- `variants`：類型／模板（源平類型 1–3），每個類型下各部位的零件 `{w, h, pixels}`，部位或零件帶擺放座標 `x, y`
- `backgrounds`：可選
- `characters`：武將名、編號、讀音、頭像碼

### 遊戲外掛（只放資料描述不了的規則）

1. **頭像碼 ↔ 部件**：源平是單純位元欄位，可宣告式描述，例如 `[{slot: 'head', bits: [13, 11]}, …]`，不用寫程式；FC 有 `HEAD_TO_PATTERN`、`KNOWN_COMBINATIONS` 查表，需要 `decode(code)` / `encode(parts)` hook。
2. **背景規則**：源平 `(id >> 1) % 5`（formats.md §10.3），其他遊戲可能固定或沒有，用 `background(character)` hook。
3. **部件互相依賴**（如 FC 的頭決定模板、模板決定眼口位置）：建置時把「頭×模板」預先畫成完整零件，渲染器只看到「零件＋座標」，不進外掛。

原則：能宣告就寫進 JSON，外掛越小越好。

## 步驟

1. **源平版改架構**：定義資料格式（寫成文件）→ `mob_kao_explorer.py` 只輸出資料 → 頁面拆成共用渲染器＋UI＋源平外掛 → 加 deflate → 重跑 310 人逐 pixel 比對（與 `build/dump/portraits/generals/`），量測縮小幅度。
2. **接上 FC 三國志當第二個遊戲**，驗證介面切得對不對；介面在這一步之後才定案。

## 待決定

- 共用頁面放哪：先放本 repo 之後再搬，或一開始就獨立成一個 repo，各遊戲專案只負責產生資料 JSON。會影響第 1 步的檔案配置。
