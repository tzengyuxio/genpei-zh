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
- `portraits`：可選，每人一張的完整頭像 `{w, h, pixels}`，給沒有組合頭像、臉是逐人一張的作品（如三國志 II／III，見 koei-wiki 的人物顏頁）；一款遊戲可以只有 `variants`、只有 `portraits`，或兩者都有
- `characters`：武將名、編號、讀音，以及頭像碼或 `portraits` 的索引

### 遊戲外掛（只放資料描述不了的規則）

1. **頭像碼 ↔ 部件**：源平是單純位元欄位，可宣告式描述，例如 `[{slot: 'head', bits: [13, 11]}, …]`，不用寫程式；FC 有 `HEAD_TO_PATTERN`、`KNOWN_COMBINATIONS` 查表，需要 `decode(code)` / `encode(parts)` hook。
2. **背景規則**：源平 `(id >> 1) % 5`（formats.md §10.3），其他遊戲可能固定或沒有，用 `background(character)` hook。
3. **部件互相依賴**（如 FC 的頭決定模板、模板決定眼口位置）：建置時把「頭×模板」預先畫成完整零件，渲染器只看到「零件＋座標」，不進外掛。

原則：能宣告就寫進 JSON，外掛越小越好。

## 步驟

1. **源平版改架構**（在網站 repo `kaodata` 進行）：定義資料格式（寫成文件）→ `mob_kao_explorer.py` 只輸出資料 → 頁面拆成共用渲染器＋UI＋源平外掛 → 加 deflate → 重跑 310 人逐 pixel 比對（與 `build/dump/portraits/generals/`），量測縮小幅度。
2. **接上 FC 三國志當第二個遊戲**，驗證介面切得對不對；介面在這一步之後才定案。

## 決議：獨立 repo、擴大成臉譜工具（2026-10-09）

- **獨立 repo**（放 Forgejo），一開始就獨立，不先放在本 repo 再搬。
- **用途拆成兩個 repo**（2026-10-09 再議定）：
  - **`kaodata-re`**：格式研究＋解碼程式。由 GitHub `kaodata` 改名而來，`dekoei` 併回。留在 GitHub（公開），可以雜亂、有臨時資料，但不放遊戲原檔。
    解碼 library 的獨立價值已不大（genpei-zh 就沒有引用 `dekoei/genpei.py`，而是另寫了一份），
    留著是當作可執行的格式說明，並負責輸出網站資料。
  - **`kaodata`**（新建，網站 `kaodata.simagame.me`）：臉譜網站，保持乾淨、可自動部署。統一資料格式的規格放這裡，提供資料的一方配合。
  - 網站資料來源：`kaodata-re` 的輸出、fc-sangokushi（FC 版自己輸出）、`koei-images` 的 PNG。源平合戰的資料之後改由 `kaodata-re` 輸出。
- **範圍擴大**：不只大眾臉，還有光榮武將臉譜的查看、編輯等工具。repo 與網站名稱不綁「大眾臉」，
  大眾臉探索器是其中一個工具。資料格式因此要同時容納組合零件與逐人完整頭像（上面的 `portraits`）。
- **不和網頁版遊玩合併**：遊玩網站只放譯文差異、原版檔玩家自備；這裡的資料是解出來的原作美術，版權性質不同，
  分開放，萬一要下架或調整時互不牽連。兩站的受眾、更新節奏與技術（模擬器 vs. 畫布渲染）也幾乎沒有重疊。
- **部署到自己的 VPS**（與遊玩網站相同，見 kami-zh `docs/web-port.md`）：Forgejo Actions 建置後 rsync 上去，用自己的網域。
  不放 GitHub Pages，因為下架要求會落在放翻譯專案的 GitHub 帳號上。
  fc-sangokushi Pages 上的兩個探索器頁面，搬家後改成轉址。

## 既有資產與從頭規劃（2026-10-09）

網站 `kaodata` **從頭寫、重新做整體規劃**，不直接接手舊程式；連同本 repo 與 fc-sangokushi 的兩個大眾臉探索器、
2023 年的顏 CG 編輯器，都只當參考。上面的資料格式、分層與步驟是規劃的起點，不是定案。可參考的既有資產：

| 位置 | 內容 |
|---|---|
| GitHub `tzengyuxio/kaodata-re`（2023，原名 `kaodata`，2026-10-09 改名） | 早期光榮遊戲資料研究；`kaocgeditor/` 是顏 CG 編輯器原始碼（React／Create React App，讀使用者的原版頭像檔：水滸傳、三國志 II～V、項劉記、拿破崙，三國志 III 與項劉記可編輯存檔），部署成品在 metacontext `static/kaocgeditor/`；`montage/` 是早期的大眾臉網頁 |
| GitHub `tzengyuxio/dekoei`（2023，將併回 `kaodata-re`） | 從 kaodata 拆出的 Python 解碼：三國志 I～III、信長、源平（`genpei.py`）、LS11 等 |
| Forgejo `koei-images` | 已擷取的圖片（純存放，約 5.3 GB），可當逐 pixel 比對的標準答案，或直接轉成查看器的資料 |
| 本 repo `tools/mob_kao_explorer.py`、fc-sangokushi | 兩個現行的大眾臉探索器 |

## 待決定

- **編輯器輸出什麼**（做編輯器前決定）：只輸出 PNG／頭像碼，現有分層不變；要寫回遊戲檔，就得每款遊戲在瀏覽器端寫編碼器，
  推翻「不在 JS 寫各遊戲解碼器」的決議。
- **是否加「自備原版檔」模式**：像遊玩網站那樣由使用者選原版檔、在瀏覽器裡解析，網站就完全不含原作美術，
  也適合寫回遊戲檔的編輯器；代價是沒有原版的人用不了，且每款遊戲要有與 Python 版一致的 JS 解碼器。
  可以並存：展示型工具（大眾臉探索器）內嵌資料，編輯器讀使用者的檔案。
- 網站的子網域。
