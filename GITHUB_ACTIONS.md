# GitHub Actions 免費部署

這是目前建議的主要部署方式。Python 與 `yfinance` 會在 GitHub Actions 執行，Google Sheet 與 Apps Script Email 流程維持不變。

## 執行頻率

- GitHub Actions 每 5 分鐘啟動一次。
- 美股開盤時，每次都更新，因此實際頻率約 5 分鐘。
- 盤外由程式檢查「設定 → 盤外更新間隔」，預設 10 分鐘；中間的工作流程會安全跳過。
- GitHub 排程不是即時服務，繁忙時可能延遲或偶爾漏跑。

## 0. 確認 Google Sheet 與 Apps Script

1. 在目標 Google Sheet 的「擴充功能 → Apps Script」放入本專案 `apps-script/Code.gs` 與 `apps-script/Index.html`。
2. 重新整理 Google Sheet，從「選擇權警示」選單執行「初始化／修復系統」。
3. 第一次執行時完成 Google 授權；這會建立每分鐘處理待寄 Email 的 Apps Script 觸發器。

若先前已完成上述設定，只要確認 Apps Script 的 `APP.VERSION` 為 `0.2.1`，不需重建試算表。

## 1. 建立不綁計費的 Google Cloud Project

Google Sheets API 的標準用量不需要額外付費，也不需要啟用 Cloud Run。

1. 前往 Google Cloud Console，建立一個新 Project；不要連結 Billing Account。
2. 在「API 和服務 → 程式庫」啟用 **Google Sheets API**。
3. 在「IAM 與管理 → 服務帳戶」建立 `option-alert-github`。
4. 進入服務帳戶的「金鑰」，建立 JSON 金鑰並下載。
5. 複製服務帳戶 Email，例如：

   ```text
   option-alert-github@你的專案.iam.gserviceaccount.com
   ```

6. 把「選擇權警示」Google Sheet 分享給這個 Email，權限設為「編輯者」。

服務帳戶 JSON 是密碼，請勿放進專案、Google Sheet、Email 或公開訊息。

## 2. 建立 GitHub 公開 Repository

1. 在 GitHub 建立一個新的 **Public repository**。
2. 將本專案上傳到該 repository。
3. 前往「Settings → Secrets and variables → Actions」。
4. 建立兩個 Repository secrets：

   - `GOOGLE_CREDENTIALS`：貼上完整的服務帳戶 JSON。
   - `SPREADSHEET_ID`：填入 Google Sheet 網址 `/d/` 與下一個 `/` 之間的 ID。

公開 repository 只會公開程式碼。服務帳戶 JSON、Spreadsheet ID 與執行環境中的資料不會因為使用 GitHub Secrets 而顯示在程式碼中。

## 3. 第一次測試

1. 開啟 GitHub repository 的「Actions」。
2. 選擇 **Option alerts refresh**。
3. 按「Run workflow」。
4. 等待綠色勾號後，回到 Google Sheet 檢查：

   - 「設定」的最後執行與狀態。
   - 「監控清單」的價格、Greeks 與資料狀態。
   - 「系統紀錄」的新紀錄。

若出現 `PERMISSION_DENIED`，通常是尚未把 Sheet 分享給服務帳戶，或分享的 Email 與 JSON 內的 `client_email` 不一致。

## 注意事項

- GitHub 公開 repository 使用標準執行器目前免費；私人 repository 會消耗每月免費分鐘。
- GitHub 公開 repository 若連續 60 天沒有活動，排程可能自動停用；屆時可在 Actions 頁面重新啟用。
- `GOOGLE_CREDENTIALS` 是長期金鑰。若懷疑外洩，立即在 Google Cloud Console 刪除該金鑰並建立新金鑰。
- 不要在 workflow 中輸出 secret，也不要把 `gha-creds-*.json` 加入版本控制。
