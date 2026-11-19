# 買入買權篩選器

Google Sheet 的「設定與標的」第 5 列是預設值。從第 10 列起輸入標的並啟用，個別條件留白就沿用預設值。比率欄請輸入百分比，例如 `8%`。試算價可以選 Mid、Bid 或 Ask。手動更新從同一頁的連結開啟 GitHub Actions，再按 **Run workflow**。

最高買價以每股美元顯示，取「維持最低釋放現金比例」及「年化時間價值成本不超標」兩者的較低上限，向下取至小數點後兩位。此欄是當次股價及 DTE 下的試算值。券商接受的報價跳動單位可能大於一美分。篩選只採標準股票 Call，股息和手續費未納入年化資金成本。Spread 全程以 Mid 為分母。

## 部署

1. 以 `schema.json` 與 `build_sheet.mjs` 建好獨立 Google Sheet。將表分享給 Actions 的 Google 服務帳戶。
2. 在 GitHub Actions 設定 `LONG_CALL_SPREADSHEET_ID`。現有 `GOOGLE_CREDENTIALS` 供服務帳戶驗證。原有 `SPREADSHEET_ID` 用於驗證兩份表的 ID 各自獨立。
3. 將 `Code.gs` 放入新表的「擴充功能 → Apps Script」。執行 `installLongCallEmail` 並授權，寄件與收件都是授權帳號。表內「掃描紀錄」會顯示寄送狀態。
4. GitHub Actions 於美東 13:23 和 16:23 檢查當天股票選擇權收盤時間。休市略過，提早收盤與平常收盤各只產生一筆當日收盤結果。手動執行可在盤外更新。
