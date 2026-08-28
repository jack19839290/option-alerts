# 選擇權警示

目前版本：`0.5.1`

以 Google Sheets 作為操作介面，GitHub Actions 透過 `yfinance` 讀取 Yahoo Finance 選擇權鏈，計算 Greeks 與賣出權利金年化報酬率，再把結果寫回試算表。Email 由綁定試算表的 Apps Script 寄出。

## 已實作功能

- 一個「股票＋到期日」對應一張期權鍊工作表，顯示 Yahoo／`yfinance` 當次回傳的所有 CALL、PUT 與履約價。
- 可選擇顯示全部合約、只顯示 CALL 或只顯示 PUT。
- 可設定選填的 Delta、Bid–Ask Spread、年化報酬率與未平倉量條件；所有已設定條件採 AND 邏輯。
- Delta 條件實際比較 `|Delta|` 絕對值；Delta、Spread 與年化報酬率可選擇 `≥` 或 `≤`，未平倉量採嚴格大於設定口數。
- `Spread% = (Ask − Bid) ÷ Mid`；表單輸入 `10` 代表 10%。Bid、Ask 或 Mid 無效時，Spread 條件視為資料不足。
- 賣出試算價只使用有效 Bid；Bid 無效時不以 Last 代替，也不計算年化報酬率。
- PUT 年化報酬率為 `Bid ÷ 履約價 ÷ DTE × 365`。
- CALL 年化報酬率為 `Bid ÷ 持股成本 ÷ DTE × 365`；未填持股成本時留白。
- Delta、Gamma、Theta（每日）與 Vega（每 1% IV）由 Black-Scholes-Merton 模型估算，期權鍊依此順序顯示，最後再列出 `|Delta|`。
- Yahoo 的 `trailingAnnualDividendYield` 與 `dividendYield` 採各自單位正規化；不合理的股息率不會直接帶入 Greeks。
- 無風險利率優先讀取 Yahoo `^IRX` 的即時 `lastPrice`，其次採最近交易日 `Close`；兩者都失敗才使用設定中的備援值並在資料狀態標示。
- 第一次成功掃描只建立基準、不寄信；之後僅在合約新符合全部條件時通知。
- 同一輪的多個新符合合約合併成一封 Email，信中列出 CALL／PUT、履約價、Bid、Spread、Greeks、年化報酬率、未平倉量與 DTE。
- 連續兩次有效不符合後才重新啟用該合約的通知，降低邊界值反覆寄信。
- 條件變更會自動重新建立基準，避免新條件一儲存就大量寄信。
- Apps Script 在美股股票期權開盤、盤中每個整點與收盤各啟動一次；Python 端使用 CBOE 股票期權交易日曆判斷假日與提早收盤。
- 盤外不會自動寫入期權鍊；可從「選擇權警示 → 立即手動更新」，或勾選控制台 `H7`，隨時強制更新。
- GitHub 金鑰保存在 Apps Script 個人屬性，不寫入試算表；預設採 90 天有效期，並於到期前 7 天寄信提醒。
- 更新要求第一次失敗會立即寄信；持續失敗期間每 24 小時最多提醒一次，恢復時再通知一次。
- 遇到 Yahoo 流量限制時採 15／30／60 分鐘退避，不繞過限制。

## 升級至 0.5.1

請依照 [UPGRADE_0.5.md](UPGRADE_0.5.md) 操作。執行 Apps Script 的 `setupSystem` 時：

- 不會刪除或重新命名任何分頁。
- 舊 Vega 篩選欄位會改為 Spread 篩選欄位；舊 Vega 門檻不會被誤當成 Spread，會安全清空並重新建立警示基準。
- 既有期權鍊會在欄位升級時清除舊資料列，下一次更新再依新版欄位完整重建。

## 專案結構

```text
app/                 Python 行情、條件與警示服務
apps-script/         Google Sheets 綁定式 Apps Script 與輸入介面
infra/deploy.ps1     選用的 Google Cloud 部署腳本
scripts/             Google Sheets 範本產生器
tests/               定價、Greeks、條件、基準與更新流程測試
GITHUB_ACTIONS.md     GitHub Actions 免費部署與授權步驟
UPGRADE_0.5.md        0.5.1 升級與驗證說明
DEPLOYMENT.md         選用的 Cloud Run 部署步驟
```

## 本機測試

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## 重要限制

- `yfinance` 是非官方 Yahoo Finance 介面，資料可能延遲、缺漏、變更或暫時無法取得，不應視為交易所即時行情。
- Yahoo 未平倉量可能不是即時更新；系統只使用當次實際取得的數值。
- Greeks 是模型估算，不是 Yahoo 原始欄位；輸入包含標的價格、Yahoo IV、利率、股息殖利率與剩餘時間。
- 年化報酬率未扣除手續費、稅金、股息、融資成本、滑價及提前指派風險。
- 自動更新與 Email 需要先完成 [GITHUB_ACTIONS.md](GITHUB_ACTIONS.md) 的 GitHub Secrets、試算表分享與 Apps Script 授權。
- 本工具只提供資料整理與條件通知，不會下單，也不構成投資建議。
