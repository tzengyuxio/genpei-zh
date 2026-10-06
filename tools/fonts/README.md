# Fonts

`jiskan24-fullwidth.bdf.gz`：24×24 點陣明朝體，`tools/textimg.py` 畫片頭／片尾旁白用。

- 來源：FontPixel 的 jiskan 包（<https://fontpixel.com/zh-Hant/fonts/jiskan/>），`JF-Dot-jiskan24h-24px.bdf.gz`，SHA-256 `784915a90e3388694dc413291450ac900725a3af08a2664adf3f7fca749cc98d`；上游為 jikasei.me 的 jfdotfont-20150527。
- 授權：全形字是 JIS 點陣字模（JEITA／小山尚久／八木達也），公有領域。原檔的半形字取自日比谷 24（SIL OFL 1.1），**這裡已全部移除**，只留 `DWIDTH 24` 的全形字（11,222 字），所以整個檔是公有領域。
- 不含直排標點（︐︑︒︙），`textimg.py` 用橫排字形移位／旋轉代替。
