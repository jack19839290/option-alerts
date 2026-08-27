# 0.2.1 升級至 0.3.2

這份流程適用於已經能用 GitHub Actions 更新 Google Sheet 的既有使用者。升級不需要建立新的 Google Cloud Project，也不需要更換原本的 GitHub Secrets。

## 升級前會保留什麼

- 原本的「監控清單」不會刪除，會改名為「監控清單_舊版」。
- 原本的「警示紀錄」不會刪除，會改名為「警示紀錄_舊版」。
- 「設定」中的通知信箱、Spreadsheet ID 與執行紀錄會保留。
- 舊的權利金上限／下限不會自動轉換成 Delta、Vega 或年化條件。

## 第一階段：把新版程式推送到 GitHub

1. 開啟 GitHub Desktop。
2. 確認左上角 Current repository 是這個選擇權警示專案。
3. 左側 Changes 應該會看到本次修改的程式檔案。
4. 左下角 Summary 輸入：`Upgrade to option chain scanner v0.3.2`。
5. 按下 Commit to main。
6. 按上方 Push origin。

## 第二階段：更新 Google Apps Script

1. 開啟原本的 Google Sheet。
2. 選擇「擴充功能 → Apps Script」。
3. 開啟 `Code.gs`，全選舊內容後，貼上本專案 `apps-script/Code.gs` 的全部內容。
4. 開啟 `Index.html`，全選舊內容後，貼上本專案 `apps-script/Index.html` 的全部內容。
5. 確認 `appsscript.json` 仍包含 `script.container.ui`、`script.send_mail`、`script.scriptapp` 與 `spreadsheets` 四項權限。
6. 按「儲存專案」。

若先前部署過 Apps Script 網頁應用程式，請再選擇「部署 → 管理部署 → 編輯」，建立新版本並部署，網頁網址通常不會改變。

## 第三階段：執行升級

1. 在 Apps Script 上方的函式選單選擇 `setupSystem`。
2. 按「執行」。
3. 若出現授權畫面，選擇自己的 Google 帳號並允許權限。
4. 回到 Google Sheet 並重新整理網頁。
5. 確認出現「掃描設定」分頁。
6. 確認舊資料已放在「監控清單_舊版」與「警示紀錄_舊版」。

## 第四階段：新增第一個期權鍊掃描

1. 在 Google Sheet 上方選擇「選擇權警示 → 新增／更新期權鍊掃描」。
2. 輸入股票代號與到期日。
3. 顯示類型可選：
   - `ALL`：CALL 與 PUT 都顯示。
   - `CALL`：只顯示 CALL。
   - `PUT`：只顯示 PUT。
4. Delta、Vega、年化報酬率與未平倉量都可留空。
5. 年化報酬率門檻請輸入百分比數字，例如 `20` 代表 20%。
6. 若要計算 CALL 年化報酬率，填入每股持股成本。
7. 按「儲存期權鍊掃描」。

## 第五階段：第一次手動測試

1. 打開 GitHub repository 的 Actions。
2. 選擇 Option alerts refresh。
3. 按 Run workflow，再按綠色 Run workflow。
4. 等待執行出現綠色勾號。
5. 回到 Google Sheet，檢查：
   - 「掃描設定」的合約數、符合數、最後抓取時間與資料狀態。
   - 新建立的 `股票_到期日` 分頁是否列出所有履約價。
   - 每個合約是否有 Bid、Greeks、DTE、年化報酬率與條件結果。

第一次成功掃描只建立基準，不會寄 Email，這是正常行為。後續只有合約從不符合狀態轉為全部符合時，才會寄出通知。

## 常見狀況

- 顯示「Bid無效」：該合約沒有有效正數 Bid，系統不計算賣出年化報酬率。
- 顯示「CALL未填持股成本」：CALL 仍會顯示，但年化報酬率留白。
- 顯示「Greeks資料不足」：Yahoo IV 或標的價格不足，系統不猜測數值。
- 顯示「未平倉資料不足」：Yahoo 沒有回傳該合約的未平倉量；若有設定未平倉條件，該合約視為不符合。
- 修改任一掃描條件後，下一次成功抓取會重新建立基準，因此不會立即寄出一大批 Email。
