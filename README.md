# genpei-zh

《源平合戦》(KOEI, 1994, IBM-PC DOS/V 版) 繁體中文化專案。

沿用原本 DOS/V 的漢字編碼（Shift-JIS／JIS X 0208），不修改編碼、不替換字型、不擴充字庫，譯文只使用原字庫涵蓋得到的字。
姊妹作：[kami-zh](https://github.com/tzengyuxio/kami-zh)（《神々の大地 ～古事記外伝～》），本專案沿用其做法與工具骨架。

## 安裝與遊玩

到 [Releases](https://github.com/tzengyuxio/genpei-zh/releases) 下載修補程式（Windows／macOS）。

1. 把 `genpei-zh-patch` 放進自備的 DOS/V 原版 `GENPEI` 資料夾（或旁邊）執行，旁邊會產生中文版的 `GENPEIZH` 資料夾，原資料夾不動。
2. 用 [DOSBox-X](https://dosbox-x.com/) 的 DOS/V 模式遊玩：打開附的 `genpei-zh.conf`，把 `mount c` 那行改成 `GENPEIZH` 所在的資料夾，再執行 `dosbox-x -conf genpei-zh.conf`。

修補程式只含譯文，不含遊戲本體。只支援原版檔案，寫入前會先檢查；片頭、結局等可獨立的檔案不符時可選擇跳過。詳細說明見壓縮檔內的 `README.txt`（原文在 [`patcher/README.txt`](patcher/README.txt)）。

DOSBox-X 設定要點：`dosv = jp`（顯示漢字，不需要遊戲附的 `DOSJP.COM`）；遊戲需要 EMS，但 XMS 同時開著會在選完棟梁後當住，所以 `xms = false`、`ems = emsboard`；從 `Genpei.com` 啟動。

## 翻譯內容

| 範圍 | 數量 |
|---|---|
| 劇情（`translation/message.tsv`，Message.gp，含和歌 40 首） | 1,305 則 |
| 介面（`translation/main.tsv`、`open.tsv`、`end.tsv`） | 494＋21＋23 條 |
| 片頭／片尾文字圖（`translation/images.tsv`） | Opendat 12 張、Enddat 16 張 |
| 勢力滅亡畫面的書法（Maincmd2.gp） | 4 行 |
| 系統用語詞彙表（`translation/glossary.tsv`） | 182 條 |

- 人名、地名、名物、官位保留日文漢字原樣（`頼朝`、`義経`），與遊戲資料表一致。
- 字庫缺「你、嗎、吧」等口語字，語氣偏文言（「汝」「可否？」「乎？」）；規則見 [`docs/translation-style.md`](docs/translation-style.md)。
- 片頭、勢力滅亡畫面、結局卷軸上的書法字，是從歷代法帖逐字挑選拼成，字圖取自[全字庫](https://www.cns11643.gov.tw/)法帖查詢，每個字的書家與出處列在 `translation/calligraphy/*/README.md`。

## 開發

遊戲檔不在 repo 內（版權因素，`.gitignore` 已排除 `game/`）。請自備並解壓到 `game/GENPEI/`；`game/` 永遠保持原樣，所有輸出都到 `build/`。工具只用 Python 標準庫，另需 DOSBox-X、ffmpeg；書法重繪需要 ImageMagick；修補程式需要 Go。

```bash
# 從 game/ 重建中文版到 build/GENPEI（Main.exe 是 RLE 壓縮的，先解包）
cp game/GENPEI/* build/GENPEI/
python3 tools/unpack_exe.py game/GENPEI/Main.exe build/GENPEI/Main.exe
python3 tools/patch.py --apply translation/main.tsv translation/main_data.tsv --target build/GENPEI/Main.exe
python3 tools/patch.py --apply translation/sndata.tsv --target build/GENPEI/Sndata.gp
python3 tools/patch.py --apply translation/open.tsv --target build/GENPEI/Open.exe
python3 tools/patch.py --apply translation/end.tsv  --target build/GENPEI/End.exe
python3 tools/message.py apply game/GENPEI/Message.gp translation/message.tsv build/GENPEI/Message.gp
python3 tools/textimg.py build/GENPEI   # 片頭／片尾文字圖、滅亡畫面書法

tools/dosbox/run.sh                     # 在 DOSBox-X 執行（帶秒數則錄影後退出）
python3 tools/endview.py genji          # 不必破關就能看結局（genji／heike／other）
tools/release.sh v1.0.0                 # 編出玩家用的修補程式 → patcher/dist/
```

- 回寫方式：EXE 是原地覆寫（譯文不得超過原字串 bytes）；Message.gp 整檔重建再 LS11 壓縮（只受訊息視窗行寬限制）；文字圖原位換 chunk。
- 修補程式（`patcher/`，Go，移植自 kami-zh）內嵌 `tools/mkpatch.py` 產生的 `genpei-zh.kzp`：只記錄與原檔的差異，不含原作資料。
- 環境、工具一覽、存檔快照、實機驗證方式、踩過的坑與決議見 [`docs/development.md`](docs/development.md)。

## 文件

- [`docs/development.md`](docs/development.md) — 開發紀錄：建置流程、工具、重要發現、模擬器踩坑
- [`docs/formats.md`](docs/formats.md) — 檔案格式分析（LS11、NPK016、EXE 壓縮、資料表、頭像組合、結局機制）
- [`docs/translation-style.md`](docs/translation-style.md) — 翻譯風格指南（語域、稱謂、缺字替代）
- [`docs/font-policy.md`](docs/font-policy.md) — 字庫政策：為何只用 JIS X 0208
- [`docs/guide/`](docs/guide/strategy.md) — 遊玩攻略：[攻略建議](docs/guide/strategy.md)、[劇本](docs/guide/scenarios.md)、[武將](docs/guide/generals.md)、[據點](docs/guide/bases.md)、[寶物](docs/guide/treasures.md)、[官位](docs/guide/ranks.md)
- [大眾臉探索器](https://tzengyuxio.github.io/fc-sangokushi/genpei-mob-kao-explorer.html) — 組合頭像（Montage）的部件與頭像碼

## 致謝

- 書法字取自[全字庫](https://www.cns11643.gov.tw/)的法帖字形。
- NPK 圖形解壓經由 kami-zh 移植自 [tzengyuxio/kaodata-re](https://github.com/tzengyuxio/kaodata-re) 對早期光榮遊戲資料格式的研究。
