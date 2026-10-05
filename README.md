# genpei-zh

《源平合戦》(KOEI, 1994, IBM-PC DOS/V 版) 繁體中文化專案。

## 本 repo 不包含遊戲檔案

遊戲 binary 與素材皆未納入版控。請自備遊戲，解壓到 `game/GENPEI/`：

```
game/GENPEI/Main.exe
game/GENPEI/Message.gp
...
```

## 手上這份遊戲檔的狀況

來源：`源平合戰.zip`（53 個檔案）。

- `Version`：『源平合戦』For IBM-PC，Ver. 1.0（1994-11-16）。
- `Main.exe`（384,322 bytes，1994-12-28）與 `Main.ori`（357,780 bytes，1994-11-14）
  內容不同：`.ori` 應是原始版本，`Main.exe` 來源未明（官方更新或第三方修改），待確認。
- 附有非原版的檔案：`DOSJP.COM`（1997）、`JIS.FNT`、`FONT.DAT`、`FONT.CHR`、
  `Play.bat`、`DOSV.BAT`——用來在一般 DOS 下載入日文字型（`DOSJP -F:font.dat -TJ`），
  不是 KOEI 原版內容。
- `Savedata.gp` 日期為 2004 年，是玩過的存檔。
- 遊戲資料多為 `.gp` 副檔名（`Message.gp`、`Mainevt.gp` 等），格式待分析。

## 翻譯進度

尚未開始。
