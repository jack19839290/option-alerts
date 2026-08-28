import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const outputDir = path.resolve(scriptDir, "../outputs/option-alerts");
await fs.mkdir(outputDir, { recursive: true });

const workbook = Workbook.create();
workbook.comments.setSelf({ displayName: "User" });

const dashboard = workbook.worksheets.add("控制台");
const scans = workbook.worksheets.add("掃描設定");
const settings = workbook.worksheets.add("設定");
const alertLog = workbook.worksheets.add("警示紀錄");
const systemLog = workbook.worksheets.add("系統紀錄");

const scanHeaders = [
  "啟用", "掃描ID", "股票代號", "到期日", "顯示類型", "Delta條件", "Delta門檻",
  "Vega條件", "Vega門檻", "年化報酬率條件", "年化報酬率門檻", "CALL持股成本",
  "未平倉大於(口)", "Email通知", "備註", "狀態", "標的股價", "合約數", "符合數",
  "最後抓取時間", "資料狀態", "待寄信", "最後通知時間", "錯誤訊息", "工作表",
  "已建立基準", "條件指紋",
];

const alertHeaders = [
  "寄送時間", "掃描ID", "股票代號", "到期日", "類型", "履約價", "Bid", "Delta估算",
  "Vega估算(每1%)", "年化報酬率", "未平倉", "DTE", "合約代號", "收件信箱", "寄送狀態",
];

// 控制台
dashboard.getRange("A1:H1").merge();
dashboard.getRange("A1").values = [["選擇權警示控制台"]];
dashboard.getRange("A1:H1").format = {
  fill: "#F1F5F9",
  font: { bold: true, color: "#1D4ED8", size: 18 },
  rowHeight: 34,
  verticalAlignment: "center",
};
dashboard.getRange("A2:H2").merge();
dashboard.getRange("A2").values = [["Yahoo Finance + yfinance｜完整期權鍊｜Greeks 為 Black-Scholes-Merton 估算值"]];
dashboard.getRange("A2:H2").format = { font: { color: "#475569", italic: true }, rowHeight: 24 };

dashboard.getRange("A4:H4").values = [["啟用掃描", "數量", "符合合約", "數量", "資料異常", "數量", "最後成功抓取", "時間"]];
dashboard.getRange("A4:H4").format = {
  fill: "#E5E7EB",
  font: { bold: true, color: "#111827" },
  horizontalAlignment: "center",
  borders: { preset: "outside", style: "thin", color: "#CBD5E1" },
};
dashboard.getRange("B5").formulas = [["=COUNTIF('掃描設定'!$A$2:$A$1000,TRUE)"]];
dashboard.getRange("D5").formulas = [["=SUM('掃描設定'!$S$2:$S$1000)"]];
dashboard.getRange("F5").formulas = [["=COUNTIF('掃描設定'!$U$2:$U$1000,\"*不足*\")+COUNTIF('掃描設定'!$U$2:$U$1000,\"*失敗*\")+COUNTIF('掃描設定'!$U$2:$U$1000,\"*限制*\")"]];
dashboard.getRange("H5").formulas = [["='設定'!$B$17"]];
dashboard.getRange("A5:H5").format = {
  fill: "#FFFFFF",
  font: { size: 12 },
  rowHeight: 30,
  horizontalAlignment: "center",
  borders: { preset: "outside", style: "thin", color: "#CBD5E1" },
};
dashboard.getRange("B5:F5").format.numberFormat = "#,##0";
dashboard.getRange("H5").format.numberFormat = "yyyy-mm-dd hh:mm";

dashboard.getRange("A7:B10").values = [
  ["系統狀態", ""],
  ["最後執行", ""],
  ["下次允許抓取", ""],
  ["系統版本", ""],
];
dashboard.getRange("B7").formulas = [["='設定'!$B$19"]];
dashboard.getRange("B8").formulas = [["='設定'!$B$18"]];
dashboard.getRange("B9").formulas = [["='設定'!$B$15"]];
dashboard.getRange("B10").formulas = [["='設定'!$B$14"]];
dashboard.getRange("A7:A10").format = { fill: "#F8FAFC", font: { bold: true } };
dashboard.getRange("B7:B10").format = { font: { color: "#008000" } };
dashboard.getRange("A7:B10").format.borders = { preset: "outside", style: "thin", color: "#CBD5E1" };

dashboard.getRange("F7:H10").values = [
  ["立即手動更新", "勾選右側核取方塊", false],
  ["GitHub 自動更新", "", "='設定'!$B$20"],
  ["金鑰到期日", "", "='設定'!$B$21"],
  ["最後要求狀態", "", "='設定'!$B$23"],
];
dashboard.getRange("H8").formulas = [["='設定'!$B$20"]];
dashboard.getRange("H9").formulas = [["='設定'!$B$21"]];
dashboard.getRange("H10").formulas = [["='設定'!$B$23"]];
dashboard.getRange("F7:F10").format = { fill: "#F8FAFC", font: { bold: true } };
dashboard.getRange("G7:G10").format = { font: { color: "#475569", size: 9 }, wrapText: true };
dashboard.getRange("H7").format = { fill: "#DBEAFE", horizontalAlignment: "center" };
dashboard.getRange("H8:H10").format = { font: { color: "#008000" }, wrapText: true };
dashboard.getRange("H7").dataValidation = { rule: { type: "list", values: ["TRUE", "FALSE"] } };

dashboard.getRange("A12:H12").merge();
dashboard.getRange("A12").values = [["使用方式"]];
dashboard.getRange("A12:H12").format = { fill: "#E5E7EB", font: { bold: true } };
dashboard.getRange("A13:H18").merge(true);
dashboard.getRange("A13:A18").values = [
  ["1. 在 Google Sheets 選單「選擇權警示」執行「初始化／升級系統」。"],
  ["2. 在「設定」填入固定通知信箱，再從選單設定 90 天 GitHub 金鑰。"],
  ["3. 透過表單輸入股票、到期日及選填條件；程式會列出 Yahoo 回傳的完整期權鍊。"],
  ["4. 每小時整點後約 0～5 分鐘自動更新；也可勾選 H7 立即手動更新。"],
  ["5. 第一次掃描只建立基準；之後只有新符合全部條件的合約才寄信。"],
  ["6. 年化報酬率只用有效 Bid；本工具只供研究監控，不會執行交易。"],
];
dashboard.getRange("A13:H18").format = { wrapText: true, rowHeight: 27, verticalAlignment: "center" };

dashboard.getRange("A20:D23").values = [
  ["色彩圖例", "用途", "資料性質", "說明"],
  ["藍字", "可編輯", "使用者輸入", "掃描條件與設定"],
  ["綠字", "跨工作表", "工作簿連結", "控制台從設定表取值"],
  ["黑字", "系統輸出", "來源或計算", "Yahoo 原始資料與系統估算"],
];
dashboard.getRange("A20:D20").format = { fill: "#E5E7EB", font: { bold: true } };
dashboard.getRange("A21").format.font = { color: "#0000FF" };
dashboard.getRange("A22").format.font = { color: "#008000" };

dashboard.getRange("A25:H29").merge(true);
dashboard.getRange("A25:A29").values = [
  ["資料來源：https://finance.yahoo.com/"],
  ["程式庫：https://github.com/ranaroussi/yfinance"],
  ["賣出試算價只採有效 Bid；Bid 無效時不計算年化報酬率。"],
  ["年化報酬率＝Bid ÷ 年化本金 ÷ DTE × 365。"],
  ["Delta、Vega、Theta 為模型估算；Yahoo 未平倉量可能不是即時更新。"],
];
dashboard.getRange("A25:H29").format = { font: { color: "#475569", size: 9 }, wrapText: true };
dashboard.freezePanes.freezeRows(2);
dashboard.getRange("A:H").format.columnWidthPx = 118;
dashboard.getRange("A:A").format.columnWidthPx = 150;
dashboard.getRange("B:B").format.columnWidthPx = 210;

// 掃描設定：普通儲存格加驗證，不建立原生表格，避免指定類型欄限制 Apps Script。
scans.getRange("A1:AA1").values = [scanHeaders];
const sampleRow = Array(scanHeaders.length).fill("");
Object.assign(sampleRow, {
  0: false,
  1: "MU|2027-01-15",
  2: "MU",
  3: new Date("2027-01-15T12:00:00Z"),
  4: "ALL",
  5: "≥",
  6: 0.2,
  7: "≤",
  8: 0.5,
  9: "≥",
  10: 0.15,
  11: 60,
  12: 100,
  13: true,
  14: "停用範例；20% 年化門檻在儲存格中是 0.20",
  15: "範例（停用）",
  20: "尚未抓取",
  24: "MU_2027-01-15",
  25: false,
});
scans.getRange("A2:AA2").values = [sampleRow];
scans.getRange("A1:AA1").format = {
  fill: "#E5E7EB",
  font: { bold: true, color: "#111827" },
  rowHeight: 34,
  wrapText: true,
  verticalAlignment: "center",
};
scans.getRange("A2:O1000").format.font = { color: "#0000FF" };
scans.getRange("D2:D1000").format.numberFormat = "yyyy-mm-dd";
scans.getRange("G2:G1000").format.numberFormat = "0.0000";
scans.getRange("I2:I1000").format.numberFormat = "0.0000";
scans.getRange("K2:K1000").format.numberFormat = "0.00%";
scans.getRange("L2:L1000").format.numberFormat = "0.0000";
scans.getRange("M2:M1000").format.numberFormat = "#,##0";
scans.getRange("Q2:Q1000").format.numberFormat = "0.0000";
scans.getRange("R2:S1000").format.numberFormat = "#,##0";
scans.getRange("T2:T1000").format.numberFormat = "yyyy-mm-dd hh:mm:ss";
scans.getRange("W2:W1000").format.numberFormat = "yyyy-mm-dd hh:mm:ss";
scans.getRange("A2:A1000").dataValidation = { rule: { type: "list", values: ["TRUE", "FALSE"] } };
scans.getRange("N2:N1000").dataValidation = { rule: { type: "list", values: ["TRUE", "FALSE"] } };
scans.getRange("E2:E1000").dataValidation = { rule: { type: "list", values: ["ALL", "CALL", "PUT"] } };
for (const column of ["F", "H", "J"]) {
  scans.getRange(`${column}2:${column}1000`).dataValidation = { rule: { type: "list", values: ["≥", "≤"] } };
}
scans.getRange("A2:AA1000").conditionalFormats.addCustom('=$A2=FALSE', { fill: "#F3F4F6", font: { color: "#6B7280" } });
scans.getRange("A2:AA1000").conditionalFormats.addCustom('=$S2>0', { fill: "#DCFCE7", font: { color: "#166534", bold: true } });
scans.getRange("A2:AA1000").conditionalFormats.addCustom('=OR(ISNUMBER(SEARCH("不足",$U2)),ISNUMBER(SEARCH("失敗",$U2)),ISNUMBER(SEARCH("限制",$U2)))', { fill: "#FEF3C7", font: { color: "#92400E" } });
scans.freezePanes.freezeRows(1);
scans.freezePanes.freezeColumns(5);
scans.getRange("A:A").format.columnWidthPx = 65;
scans.getRange("B:B").format.columnWidthPx = 185;
scans.getRange("C:C").format.columnWidthPx = 80;
scans.getRange("D:D").format.columnWidthPx = 105;
scans.getRange("E:E").format.columnWidthPx = 95;
scans.getRange("F:M").format.columnWidthPx = 110;
scans.getRange("N:N").format.columnWidthPx = 95;
scans.getRange("O:O").format.columnWidthPx = 260;
scans.getRange("P:AA").format.columnWidthPx = 115;
scans.getRange("V:V").format.columnWidthPx = 260;
scans.getRange("X:X").format.columnWidthPx = 260;

// 設定
const settingsRows = [
  ["設定項目", "設定值", "說明"],
  ["Spreadsheet ID", "", "初始化時自動填入；GitHub Actions 也需設定相同 ID"],
  ["通知信箱", "", "全系統固定收件信箱"],
  ["開盤更新間隔(分鐘)", 5, "GitHub Actions 最短排程為 5 分鐘"],
  ["盤外更新間隔(分鐘)", 10, "盤前、盤後、休市"],
  ["資料過期門檻(分鐘)", 10, "超過後在表內標示異常"],
  ["無風險利率代號", "^IRX", "Yahoo 13 週國庫券指標"],
  ["備援無風險利率", 0.05, "^IRX 失敗時採用"],
  ["預設股息殖利率", 0, "Yahoo 缺失時採用；0 代表不調整"],
  ["顯示時區", "Asia/Taipei", "使用者介面與工作表"],
  ["市場時區", "America/New_York", "到期與市場時段判斷"],
  ["Cloud Run URL", "", "選用部署後填入"],
  ["Web App URL", "", "Apps Script 部署後填入"],
  ["系統版本", "0.4.0", "目前規格版本"],
  ["下次允許抓取(UTC)", "", "系統管理：流量限制退避"],
  ["連續失敗次數", 0, "系統管理"],
  ["最後成功抓取(UTC)", "", "系統管理"],
  ["最後執行(UTC)", "", "系統管理"],
  ["最後狀態", "尚未執行", "系統管理"],
  ["GitHub 自動更新", "尚未設定", "金鑰只存於 Apps Script 個人屬性，不會寫入儲存格"],
  ["GitHub 金鑰到期日", "", "只記錄使用者輸入的到期日，用於提前 7 天提醒"],
  ["GitHub 最後要求(UTC)", "", "Apps Script 最近一次要求 GitHub 執行的時間"],
  ["GitHub 最後要求狀態", "尚未執行", "成功、失敗或尚未設定"],
  ["Apps Script 成功啟動次數", 0, "自動更新成功累計；達 2 次後可移除 GitHub 原生 cron"],
  ["GitHub 原生排程", "保留中", "Apps Script 自動更新成功 2 次前保留作為安全網"],
];
settings.getRange("A1:C25").values = settingsRows;
settings.getRange("A1:C1").format = { fill: "#E5E7EB", font: { bold: true } };
settings.getRange("B2:B14").format.font = { color: "#0000FF" };
settings.getRange("B8:B9").format.numberFormat = "0.0%";
settings.getRange("A1:C25").format.borders = { preset: "outside", style: "thin", color: "#CBD5E1" };
settings.getRange("C2:C25").format = { wrapText: true, font: { color: "#475569" } };
settings.getRange("A:A").format.columnWidthPx = 190;
settings.getRange("B:B").format.columnWidthPx = 250;
settings.getRange("C:C").format.columnWidthPx = 330;
settings.freezePanes.freezeRows(1);

// 日誌
alertLog.getRange("A1:O1").values = [alertHeaders];
alertLog.getRange("A1:O1").format = { fill: "#E5E7EB", font: { bold: true }, wrapText: true };
alertLog.getRange("A:B").format.columnWidthPx = 180;
alertLog.getRange("C:L").format.columnWidthPx = 105;
alertLog.getRange("M:M").format.columnWidthPx = 190;
alertLog.getRange("N:N").format.columnWidthPx = 230;
alertLog.getRange("O:O").format.columnWidthPx = 100;
alertLog.getRange("J:J").format.numberFormat = "0.00%";
alertLog.freezePanes.freezeRows(1);

systemLog.getRange("A1:D1").values = [["時間(UTC)", "等級", "訊息", "詳細資料"]];
systemLog.getRange("A1:D1").format = { fill: "#E5E7EB", font: { bold: true } };
systemLog.getRange("A:A").format.columnWidthPx = 190;
systemLog.getRange("B:B").format.columnWidthPx = 80;
systemLog.getRange("C:C").format.columnWidthPx = 180;
systemLog.getRange("D:D").format = { columnWidthPx: 520, wrapText: true };
systemLog.freezePanes.freezeRows(1);

const formulaScan = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
console.log(formulaScan.ndjson);

const previewRanges = {
  "控制台": "A1:H29",
  "掃描設定": "A1:O5",
  "設定": "A1:C19",
  "警示紀錄": "A1:O5",
  "系統紀錄": "A1:D5",
};
for (const [sheetName, range] of Object.entries(previewRanges)) {
  const preview = await workbook.render({ sheetName, range, scale: 1.4, format: "png" });
  await fs.writeFile(`${outputDir}/${sheetName}.png`, new Uint8Array(await preview.arrayBuffer()));
}
const scanOutputPreview = await workbook.render({ sheetName: "掃描設定", range: "P1:AA5", scale: 1.4, format: "png" });
await fs.writeFile(`${outputDir}/掃描設定_系統欄.png`, new Uint8Array(await scanOutputPreview.arrayBuffer()));

const dashboardCheck = await workbook.inspect({
  kind: "table",
  range: "控制台!A1:H29",
  include: "values,formulas",
  tableMaxRows: 32,
  tableMaxCols: 10,
});
console.log(dashboardCheck.ndjson);
const scanCheck = await workbook.inspect({
  kind: "table",
  range: "掃描設定!A1:AA2",
  include: "values,formulas",
  tableMaxRows: 3,
  tableMaxCols: 30,
});
console.log(scanCheck.ndjson);

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(`${outputDir}/選擇權警示.xlsx`);
