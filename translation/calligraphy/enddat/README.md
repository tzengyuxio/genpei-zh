# 片尾的平家物語書法字

Enddat.gp 兩段，每個字一個檔：`<張號>-<第幾字>-<字>_<書家>_<法帖>.png`（工具只看開頭的 `<張號>-<第幾字>-`）。

- 68～71：詩句（驕者難長久、／恰如春夜夢。／猛者終必滅、／宛若風前塵。），字圖與標點沿用 `../maincmd2/`（出處見該處 README），樣式 `glyphs`。
- 72～77：卷軸（盛者久享榮華／治政掌握天下／驕者必不長久／恰如春夜一夢／願將浮世無常／託歌傳於後世），樣式 `ink`；與詩句重複的字沿用 68、69。
- 字圖取自全字庫法帖查詢（<https://www.cns11643.gov.tw/>）的 PNG。`alt/` 是備用字形、`parts/` 是拼字用的部件，都不會被套用。
- 大小、位置、字距記在 `layout.json`，用 `python3 tools/calligraphy_editor.py --target enddat --bg <空白卷軸的擷取畫面>` 調整（擷取畫面用 `tools/endview.py genji --record 180` 錄影，取第 7380 格左右）。卷軸在遊戲區的 x＝528、464、400，y＝48，72～74 寫完後清空再寫 75～77，編輯器並排兩份卷軸（右 72～74、左 75～77）。68～71 End.exe 不會顯示，編輯器不顯示也不能改，但匯出的 `layout.json` 會保留它們的值。片尾的圖有壓縮，每張不能超過原本的空間，編輯器會即時顯示。

## 出處（72～77）

| 位置 | 字 | 書家 | 法帖 | 全字庫 |
|---|---|---|---|---|
| 72-1 | 盛 | 王羲之 | 臨鍾繇千字文 | [ID=89142&ID2=50345](https://www.cns11643.gov.tw/wordWrite.jsp?ID=89142&ID2=50345) |
| 72-2 | 者 | 吳琚 | 跋李氏誥 | [ID=85807&ID2=34367](https://www.cns11643.gov.tw/wordWrite.jsp?ID=85807&ID2=34367) |
| 72-3 | 久 | 陸游 | 與原伯帖 | [ID=83004&ID2=3131](https://www.cns11643.gov.tw/wordWrite.jsp?ID=83004&ID2=3131) |
| 72-4 | 享 | 趙孟頫 | 無逸帖 | [ID=84842&ID2=27748](https://www.cns11643.gov.tw/wordWrite.jsp?ID=84842&ID2=27748) |
| 72-5 | 榮 | 米芾 | 苕溪詩 | [ID=92458&ID2=60913](https://www.cns11643.gov.tw/wordWrite.jsp?ID=92458&ID2=60913) |
| 72-6 | 華 | 蔡襄 | 與彥猷帖 | [ID=90462&ID2=55226](https://www.cns11643.gov.tw/wordWrite.jsp?ID=90462&ID2=55226) |
| 73-1 | 治 | 王羲之 | 臨鍾繇千字文 | [ID=85593&ID2=33572](https://www.cns11643.gov.tw/wordWrite.jsp?ID=85593&ID2=33572) |
| 73-2 | 政 | 王羲之 | 臨鍾繇千字文 | [ID=86345&ID2=37793](https://www.cns11643.gov.tw/wordWrite.jsp?ID=86345&ID2=37793) |
| 73-3 | 掌 | 趙孟頫 | 感興詩並序 | [ID=89919&ID2=53097](https://www.cns11643.gov.tw/wordWrite.jsp?ID=89919&ID2=53097) |
| 73-4 | 握 | 趙孟頫 | 「才」與德俊帖＋「屋」臨右軍帖（拼字，部件在 `parts/`） | [ID=83039&ID2=5286](https://www.cns11643.gov.tw/wordWrite.jsp?ID=83039&ID2=5286)、[ID=86128&ID2=36974](https://www.cns11643.gov.tw/wordWrite.jsp?ID=86128&ID2=36974) |
| 73-5 | 天 | 王羲之 | 臨鍾繇千字文 | [ID=83250&ID2=9814](https://www.cns11643.gov.tw/wordWrite.jsp?ID=83250&ID2=9814) |
| 73-6 | 下 | 王羲之 | 臨鍾繇千字文 | [ID=82998&ID2=2522](https://www.cns11643.gov.tw/wordWrite.jsp?ID=82998&ID2=2522) |
| 74-1 | 驕 | 趙孟頫 | 絕交書 | 同 68-1 |
| 74-2 | 者 | 朱熹 | 與彥脩帖 | 同 68-2 |
| 74-3 | 必 | 王羲之 | 瞻近帖 | [ID=83538&ID2=15651](https://www.cns11643.gov.tw/wordWrite.jsp?ID=83538&ID2=15651) |
| 74-4 | 不 | 王羲之 | 臨鍾繇千字文 | [ID=83042&ID2=5324](https://www.cns11643.gov.tw/wordWrite.jsp?ID=83042&ID2=5324) |
| 74-5 | 長 | 宋高宗 | 洛神賦 | 同 68-4 |
| 74-6 | 久 | 康里子山 | 顏魯公論書帖 | 同 68-5 |
| 75-1 | 恰 | 趙孟頫 | 襄陽歌 | 同 69-1 |
| 75-2 | 如 | 王羲之 | 臨鍾繇千字文 | 同 69-2 |
| 75-3 | 春 | 米芾 | 跋褚遂良臨蘭亭序 | 同 69-3 |
| 75-4 | 夜 | 王羲之 | 臨鍾繇千字文 | 同 69-4 |
| 75-5 | 一 | 王羲之 | 秋月帖 | [ID=82977&ID2=3](https://www.cns11643.gov.tw/wordWrite.jsp?ID=82977&ID2=3) |
| 75-6 | 夢 | 黃山谷 | 苦筍賦 | 同 69-5 |
| 76-1 | 願 | 王羲之 | 臨鍾繇千字文 | [ID=96588&ID2=70560](https://www.cns11643.gov.tw/wordWrite.jsp?ID=96588&ID2=70560) |
| 76-2 | 將 | 王羲之 | 臨鍾繇千字文 | [ID=88434&ID2=47686](https://www.cns11643.gov.tw/wordWrite.jsp?ID=88434&ID2=47686) |
| 76-3 | 浮 | 王羲之 | 臨鍾繇千字文 | [ID=87621&ID2=44491](https://www.cns11643.gov.tw/wordWrite.jsp?ID=87621&ID2=44491) |
| 76-4 | 世 | 王羲之 | 臨鍾繇千字文 | [ID=83296&ID2=12426](https://www.cns11643.gov.tw/wordWrite.jsp?ID=83296&ID2=12426) |
| 76-5 | 無 | 王獻之 | 新埭帖 | [ID=90194&ID2=53771](https://www.cns11643.gov.tw/wordWrite.jsp?ID=90194&ID2=53771) |
| 76-6 | 常 | 米芾 | 紫金帖 | [ID=88614&ID2=47857](https://www.cns11643.gov.tw/wordWrite.jsp?ID=88614&ID2=47857) |
| 77-1 | 託 | 蘇軾 | 赤壁賦 | [ID=88122&ID2=46077](https://www.cns11643.gov.tw/wordWrite.jsp?ID=88122&ID2=46077) |
| 77-2 | 歌 | 王羲之 | 臨鍾繇千字文 | [ID=92474&ID2=60975](https://www.cns11643.gov.tw/wordWrite.jsp?ID=92474&ID2=60975) |
| 77-3 | 傳 | 王羲之 | 臨鍾繇千字文 | [ID=90926&ID2=56529](https://www.cns11643.gov.tw/wordWrite.jsp?ID=90926&ID2=56529) |
| 77-4 | 於 | 王羲之 | 臨鍾繇千字文 | [ID=85365&ID2=32261](https://www.cns11643.gov.tw/wordWrite.jsp?ID=85365&ID2=32261) |
| 77-5 | 後 | 王羲之 | 臨鍾繇千字文 | [ID=86309&ID2=37172](https://www.cns11643.gov.tw/wordWrite.jsp?ID=86309&ID2=37172) |
| 77-6 | 世 | 米芾 | 天馬賦 | [ID=83296&ID2=12442](https://www.cns11643.gov.tw/wordWrite.jsp?ID=83296&ID2=12442) |
| alt 73-1 | 治 | 黃山谷 | 報雲夫帖 | [ID=85593&ID2=33584](https://www.cns11643.gov.tw/wordWrite.jsp?ID=85593&ID2=33584) |
