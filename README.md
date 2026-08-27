# 選擇權警示

目前版本：`0.2.1`

以 Google Sheets 作為操作介面，GitHub Actions 透過 `yfinance` 讀取 Yahoo Finance 選擇權鏈，計算警示採用價與 Greeks，再把結果寫回試算表。Email 由綁定試算表的 Apps Script 寄出。

## 已實作功能

- 一個「股票＋到期日」對應一張合約工作表，可放多個 CALL／PUT 與履約價。
- 「履約價」、「低於警示」、「高於警示」分開輸入；上下限可只填一個或同時填寫。
- 警示價優先採 `Mid = (Bid + Ask) / 2`；Bid／Ask 無效時改用 `Last`。
- 警示狀態會在表內變色，並可寄到設定頁中的同一個 Email。
- Delta、Vega（每 1% IV）、Theta（每日）由 Black-Scholes-Merton 模型估算，並在合約頁顯示無風險利率、股息殖利率與模型名稱。
- GitHub Actions 每 5 分鐘喚醒一次；服務依美股交易日曆判斷，開盤每 5 分鐘更新、盤外每 10 分鐘更新。
- 遇到 Yahoo 流量限制時採 15／30／60 分鐘退避，不繞過限制。
- 相同股票與到期日只抓一次期權鏈，再批次更新所有監控列。

## 專案結構

```text
app/                 Python 行情與警示服務
apps-script/         Google Sheets 綁定式 Apps Script 與輸入介面
infra/deploy.ps1     選用的 Google Cloud 部署腳本
scripts/             Google Sheets 範本產生器
tests/               價格、Greeks、警示與更新流程測試
GITHUB_ACTIONS.md     建議的免費部署與授權步驟
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
- Greeks 是模型估算，不是 Yahoo 原始欄位；輸入包含標的價格、Yahoo IV、利率、股息殖利率與剩餘時間。
- 自動更新與 Email 需要先完成 [GITHUB_ACTIONS.md](GITHUB_ACTIONS.md) 的 GitHub Secrets、試算表分享與 Apps Script 授權。
- 本工具只提供資料整理與條件通知，不會下單，也不構成投資建議。
