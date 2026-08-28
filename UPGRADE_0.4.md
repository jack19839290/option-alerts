# 升級至 0.4.0

0.4.0 將自動更新改為由 Google Apps Script 每小時啟動 GitHub Actions，並新增真正會立即啟動 GitHub 工作流程的手動更新控制。

## 升級前須知

- 程式不會尋找、重新命名、刪除或修改 `監控清單_舊版`、`警示紀錄_舊版` 或其他舊分頁。
- 請等確認新版掃描資料與警示紀錄正常後，再自行決定是否刪除舊分頁。
- GitHub 金鑰只存於執行設定的 Google 帳號之 Apps Script 個人屬性，不會顯示在 Sheet。

## 更新 Apps Script 檔案

1. 在 Google Sheet 開啟「擴充功能 → Apps Script」。
2. 用本專案的 `apps-script/Code.gs` 完整取代原本的 `Code.gs`。
3. 保留並更新 `Index.html`。
4. 新增 HTML 檔案，名稱輸入 `GitHubSetup`，貼入 `apps-script/GitHubSetup.html`。
5. 在「專案設定」開啟顯示資訊清單檔案，再用本專案的 `apps-script/appsscript.json` 取代原內容。
6. 儲存所有檔案，回到 Google Sheet 重新整理頁面。

## 初始化與授權

1. 選擇「選擇權警示 → 初始化／升級系統」。
2. Google 顯示新權限時完成授權。外部連線權限只用於呼叫 GitHub API。
3. 確認「設定 → 系統版本」顯示 `0.4.0`。
4. 確認原有分頁仍保持原狀；程式不會替你刪除舊分頁。

## 建立 90 天 GitHub 金鑰

1. 開啟 GitHub「Settings → Developer settings → Personal access tokens → Fine-grained tokens」。
2. 建立新金鑰，有效期選 90 天。
3. Repository access 選 **Only select repositories**，只勾選 `option-alerts`。
4. Repository permissions 將 **Actions** 設為 **Read and write**，其他權限維持預設。
5. 建立後先複製金鑰；GitHub 離開頁面後不會再次顯示完整金鑰。
6. 回到 Google Sheet，選擇「選擇權警示 → 設定 GitHub 自動更新金鑰」。
7. 貼上金鑰、確認到期日，按「驗證並儲存」。不要把金鑰貼到聊天或 Sheet。

## 驗證更新

1. 選擇「選擇權警示 → 立即手動更新」，或勾選控制台 `H7`。
2. 通常數分鐘內 GitHub Actions 會出現新執行，完成後資料寫回 Google Sheet。
3. 等待兩個整點，確認「Apps Script 成功啟動次數」至少為 2。
4. 達到 2 次前保留 GitHub 原生每小時排程；達到後再移除 workflow 的 `schedule` 區塊。

金鑰到期前 7 天會寄送提醒。更新要求第一次失敗會立即通知；若持續失敗，24 小時內最多再通知一次，恢復時另寄一封通知。
