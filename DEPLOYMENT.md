# Cloud Run 選用部署指南

若不想綁定 Google Cloud 計費帳戶，請改用主要方案：[GitHub Actions 免費部署](GITHUB_ACTIONS.md)。本文件保留給未來選擇 Cloud Run 的情況。

目前的 Google Sheet 範本已建立。完成以下兩段設定後，報價與 Email 才會開始自動運作。

## A. 綁定 Apps Script

1. 開啟 Google Sheet，選擇「擴充功能 → Apps Script」。
2. 將 `apps-script/Code.gs` 全部貼到 Apps Script 的 `Code.gs`。
3. 新增 HTML 檔案 `Index`，貼入 `apps-script/Index.html`。
4. 在 Apps Script 專案設定中勾選「在編輯器中顯示 appsscript.json 資訊清單檔案」，再以 `apps-script/appsscript.json` 取代內容。
5. 儲存後執行 `setupSystem`，依畫面授權寄信、觸發器與目前試算表權限。
6. 回到試算表，在「設定」分頁的「通知信箱」填入唯一收件信箱。
7. 如要在獨立網頁輸入，於 Apps Script 選擇「部署 → 新部署 → 網頁應用程式」，設為「以我的身分執行」，存取者選擇自己的帳號，並把部署 URL 填入「設定 → Web App URL」。
8. 重新整理試算表；可直接開啟 Web App，或使用上方選單「選擇權警示 → 新增／更新監控」。

`setupSystem` 會建立每 1 分鐘檢查一次的 Email 觸發器。它只寄送雲端服務已標記為「待寄信」的跨越事件，不會每分鐘重複寄送。

## B. 部署 Cloud Run 與排程

### 前置條件

- 一個已啟用計費的 Google Cloud Project。
- 已安裝並登入 Google Cloud CLI：`gcloud auth login`。
- 執行者具備建立 Cloud Run、Cloud Scheduler、Service Account 與啟用 API 的權限。

在專案根目錄執行：

```powershell
.\infra\deploy.ps1 `
  -ProjectId "你的-GCP-PROJECT-ID" `
  -SpreadsheetId "<你的 Google Sheet ID>"
```

腳本會：

1. 啟用 Cloud Run、Cloud Build、Artifact Registry、Cloud Scheduler、IAM 與 Google Sheets API。
2. 建立專用的執行與排程 Service Account。
3. 將本專案部署成不公開的 Cloud Run 服務。
4. 只授權排程帳號呼叫該服務。
5. 建立每 5 分鐘呼叫 `/refresh` 的 OIDC 驗證排程。

### 必做的試算表分享

部署完成後，腳本會顯示類似以下的執行帳號：

```text
option-alert-runtime@你的專案.iam.gserviceaccount.com
```

請在 Google Sheet 的「共用」中把這個帳號加入為「編輯者」。若未分享，Cloud Run 無法寫入試算表。

接著執行一次測試更新：

```powershell
gcloud scheduler jobs run option-alert-refresh --location asia-east1 --project "你的-GCP-PROJECT-ID"
```

約一至兩分鐘後檢查：

- 「監控清單」的「最後抓取時間／資料狀態／警示狀態」。
- 對應的 `股票_到期日` 工作表是否出現行情與 Greeks。
- 「系統紀錄」是否新增成功或錯誤訊息。

## 更新既有部署

修改 Python 程式後，使用相同參數再次執行 `infra/deploy.ps1` 即可。腳本會更新 Cloud Run 與既有排程，不會建立重複排程。

## 成本與資料提醒

- Cloud Run、Cloud Build、Artifact Registry 與 Cloud Scheduler 可能依 Google Cloud 帳戶方案產生成本。
- Yahoo／`yfinance` 回傳不保證即時、完整或長期維持相同格式；服務會顯示錯誤並退避，但不會自行改用其他行情來源。
- 警示以成功抓取到的 `Mid` 或備援 `Last` 判斷，網路延遲可能使通知晚於市場變動。
