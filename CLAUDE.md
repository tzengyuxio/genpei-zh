# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

《源平合戦》(KOEI, 1994, IBM-PC DOS/V) 的繁體中文化專案，剛建立，尚無工具與譯文。

## 遊戲檔不在 repo

遊戲原檔放 `game/GENPEI/`（gitignored，版權因素**絕不 commit**）。`game/` 永遠保持原樣，修補輸出到 `build/`。

## 參考專案

姊妹專案 `~/works/kami-zh`（《神々の大地》，同為 KOEI DOS/V）已有完整流程：Shift-JIS 文字抽取／回寫、NPK 解壓、DOSBox-X DOS/V 執行與自動化、發佈用修補程式。開始分析前先參考它的 `docs/formats.md` 與 `docs/development.md`，可沿用的工具直接移植。

本作的檔案結構（`.gp` 資料檔）與 kami-zh 不同，格式需重新分析。`Main.exe` 與 `Main.ori` 不同、另附第三方日文字型載入器（`DOSJP.COM`、`FONT.DAT`），細節見 README。
