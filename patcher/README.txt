《源平合戦》繁體中文化修補程式 @VERSION@
https://github.com/tzengyuxio/genpei-zh

本程式只含譯文，不含遊戲本體。需要自備 KOEI 1994 年 DOS/V 版的遊戲檔
（安裝後的 GENPEI 資料夾，裡面有 Main.exe、Message.gp、Genpei.com 等檔案）。

== 修補 ==

1. 把 genpei-zh-patch 放進 GENPEI 資料夾（或放在它旁邊），直接執行。
   也可以把 GENPEI 資料夾拖到程式圖示上。
2. 程式會在 GENPEI 旁邊建立 GENPEIZH 資料夾，裡面就是中文版。
   原本的 GENPEI 資料夾不會被修改。

只支援原版檔案。寫入前會先檢查所有檔案，一次列出不符的檔案與原因
（其他版本、已改過，或複製時就已損毀）：
  - Main.exe（介面）、Message.gp（劇情）不符時無法修補，不會寫入任何東西。
  - Open.exe、Opendat.gp（片頭）、End.exe、Enddat.gp（結局）、
    Maincmd2.gp（勢力滅亡畫面）、Sndata.gp（劇本資料）不符時，可以選擇跳過：
    其他檔案照常中文化，跳過的檔案原樣複製。
    換成完好的原版檔後重新執行，就能完整中文化。

Windows：首次執行若出現「Windows 已保護您的電腦」，按「其他資訊」→「仍要執行」。
macOS：在終端機執行；若被系統擋下，先執行
       xattr -d com.apple.quarantine genpei-zh-patch

== 用 DOSBox-X 遊玩 ==

這是 DOS/V（日文 DOS）遊戲，一般的 DOSBox 不支援 DOS/V 的漢字顯示，
請用 DOSBox-X（https://dosbox-x.com/）。

1. 用記事本打開 genpei-zh.conf，把 mount c 那行的路徑改成「GENPEIZH 所在的資料夾」，
   例如 GENPEIZH 在 D:\Games\GENPEIZH，就寫 mount c "D:\Games"。
2. 以這份設定啟動 DOSBox-X：
     dosbox-x -conf genpei-zh.conf
   Windows 也可以建立 dosbox-x.exe 的捷徑，在「目標」後面加上
     -conf "D:\Games\genpei-zh.conf"

設定檔做的事（也可以在 DOSBox-X 裡手動輸入）：
  - [dosv] dosv = jp：開啟日文 DOS/V 模式，才能顯示漢字。
    不需要遊戲附的 DOSJP.COM。
  - [dos] xms = false、ems = emsboard：遊戲需要 EMS；但同時開著 XMS 時，
    選完棟梁後會當住，所以關掉 XMS。
  - 從 Genpei.com 啟動（不要直接執行 Main.exe）。

遊戲以滑鼠操作。
