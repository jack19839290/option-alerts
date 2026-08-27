# 選擇權警示

目前版本：`0.3.0`

以 Google Sheets 作為操作介面，GitHub Actions 透過 `yfinance` 讀取 Yahoo Finance 選擇權鏈，計算 Greeks 與賣出權利金年化報酬率，再把結果寫回試算表。Email 由綁定試算表的 Apps Script 寄出。

## 已實作功能

- 一個「股票＋到期日」對應一張期權鍊工作表，顯示 Yahoo／`yfinance` 當次回傳的所有 CALL、PUT 與履約價。
- 可選擇顯示全部合約、只顯示 CALL 或只顯示 PUT。
- 可設定選填的 `|Delta|`、Vega、年化報酬率與未平倉量條件；所有已設定條件採 AND 邏輯。
- `|Delta|` 與 Vega 可選擇 `≥` 或 `≤`；未平倉量採嚴格大於設定口數。
- 賣出試算價只使用有效 Bid；Bid 無效時不以 Last 代替，也不計算年化報酬率。
- PUT 年化報酬率為 `Bid ÷ 履約價 ÷ DTE × 365`。
- CALL 年化報酬率為 `Bid ÷ 持股成本 ÷ DTE × 365`；未填持股成本時留白。
- Delta、Vega（每 1% IV）、Theta（每日）由 Black-Scholes-Merton 模型估算。
- 第一次成功掃描只建立基準、不寄信；之後僅在合約新符合全部條件時通知。
- 同一輪的多個新符合合約合併成一封 Email，信中列出 CALL／PUT、履約價、Bid、Delta、Vega、年化報酬率、未平倉量與 DTE。
- 連續兩次有效不符合後才重新啟用該合約的通知，降低邊界值反覆寄信。
- 條件變更會自動重新建立基準，避免新條件一儲存就大量寄信。
- GitHub Actions 每 5 分鐘喚醒一次；服務依美股交易日曆判斷，開盤每 5 分鐘更新、盤外每 10 分鐘更新。
- 遇到 Yahoo 流量限制時採 15／30／60 分鐘退避，不繞過限制。

## 升級既有 0.2.1 系統

請依照 [UPGRADE_0.3.md](UPGRADE_0.3.md) 操作。執行 Apps Script 的 `setupSystem` 時：

- 原「監控清單」會改名為「監控清單_舊版」並保留。
- 原「警示紀錄」會改名為「警示紀錄_舊版」並保留。
- 新系統會建立「掃描設定」與新版「警示紀錄」。
- 舊權利金上下限不會自動轉成新條件，避免錯誤通知。

## 專案結構

```text
app/                 Python 行情、條件與警示服務
apps-script/         Google Sheets 綁定式 Apps Script 與輸入介面
infra/deploy.ps1     選用的 Google Cloud 部署腳本
scripts/             Google Sheets 範本產生器
tests/               定價、Greeks、條件、基準與更新流程測試
GITHUB_ACTIONS.md     GitHub Actions 免費部署與授權步驟
UPGRADE_0.3.md        既有系統升級操作說明
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
