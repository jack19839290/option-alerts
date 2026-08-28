# 升級至 0.5.1

0.5.1 包含 0.5.0 的 Bid–Ask Spread、Gamma 與開盤時段更新功能，並修正新版 `yfinance` 無法讀取 `^IRX`、持續誤用 5% 備援利率的問題。

## 升級前須知

- 程式不會刪除或重新命名任何 Google Sheet 分頁。
- 「掃描設定」原本的 Vega 條件與門檻會清空，再改成 Spread 條件與門檻，避免把 Vega 數值誤當成百分比價差。
- 因篩選條件改變，既有掃描會重新建立第一次基準；第一次新版掃描不寄信。
- 既有期權鍊分頁的舊資料列會在初始化時清除，下一次更新會用新版 38 欄完整重建。
- `GOOGLE_CREDENTIALS`、`SPREADSHEET_ID`、服務帳戶與已儲存的 GitHub 金鑰都不必重建。

## 1. 取得新版程式

1. 在 GitHub Desktop 選擇 `option-alerts` repository。
2. 按上方 **Fetch origin**；若按鈕變成 **Pull origin**，再按一次下載新版。
3. 等待 GitHub Desktop 顯示目前分支為 `main` 且已與遠端同步。

## 2. 更新 Apps Script

1. 開啟你的 Google Sheet，選擇「擴充功能 → Apps Script」。
2. 開啟本機專案的 `apps-script/Code.gs`，全選並複製，完整取代 Apps Script 裡的 `Code.gs`。
3. 用同樣方式更新 `Index.html` 與 `GitHubSetup.html`。
4. 在 Apps Script 左側「專案設定」開啟資訊清單檔案後，以新版 `apps-script/appsscript.json` 取代原內容。
5. 按上方「儲存專案」。

## 3. 執行安全升級

1. 回到 Google Sheet 並重新整理網頁。
2. 選擇「選擇權警示 → 初始化／升級系統」。
3. 若 Google 要求新權限，依畫面完成授權。
4. 確認「設定」分頁的「系統版本」顯示 `0.5.1`。
5. 確認「掃描設定」的 H、I 欄已變成「Bid-Ask價差條件／門檻」。

## 4. 重新設定 Spread 條件

1. 選擇「選擇權警示 → 新增／更新期權鍊掃描」。
2. 輸入原本的股票代號與到期日。
3. 視需要設定 Bid–Ask Spread；例如選擇 `≤` 並輸入 `10`，代表只接受價差率不高於 10%。
4. 儲存後，程式會把這次條件視為新基準。

## 5. 手動驗證

1. 選擇「選擇權警示 → 立即手動更新」。盤外也可以執行。
2. 到 GitHub repository 的 **Actions**，確認新執行為綠色勾勾。
3. 回到 Google Sheet 重新整理，確認期權鍊欄位依序包含：
   - Bid-Ask價差率
   - Delta估算
   - Gamma估算
   - Theta估算(每日)
   - Vega估算(每1%)
   - |Delta|
4. 確認「設定」中的最後執行狀態為成功。

第一次新版掃描只建立基準、不寄信。之後只有新符合所有已設定條件的合約才會寄信。
