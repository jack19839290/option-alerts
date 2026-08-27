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
const monitors = workbook.worksheets.add("監控清單");
const settings = workbook.worksheets.add("設定");
const alertLog = workbook.worksheets.add("警示紀錄");
const systemLog = workbook.worksheets.add("系統紀錄");

const monitorHeaders = [
  "啟用", "監控ID", "股票代號", "到期日", "類型", "履約價", "低於警示", "高於警示",
  "Email通知", "備註", "狀態", "合約代號", "標的股價", "Last", "Bid", "Ask", "Mid",
  "警示採用價", "價格來源", "IV", "Delta估算", "Vega估算(每1%)", "Theta估算(每日)",
  "DTE", "成交量", "未平倉", "最後成交時間", "最後抓取時間", "資料狀態", "警示狀態",
  "待寄信", "最後通知時間", "上次警示狀態", "錯誤訊息", "工作表",
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
dashboard.getRange("A2").values = [["Yahoo Finance + yfinance｜GitHub Actions｜Mid 優先｜Greeks 為 Black-Scholes-Merton 估算值"]];
dashboard.getRange("A2:H2").format = { font: { color: "#475569", italic: true }, rowHeight: 24 };

dashboard.getRange("A4:H4").values = [["啟用監控", "數量", "目前警示", "數量", "資料異常", "數量", "最後成功抓取", "時間"]];
dashboard.getRange("A4:H4").format = {
  fill: "#E5E7EB",
  font: { bold: true, color: "#111827" },
  horizontalAlignment: "center",
  borders: { preset: "outside", style: "thin", color: "#CBD5E1" },
};
dashboard.getRange("B5").formulas = [["=COUNTIF('監控清單'!$A$2:$A$1000,TRUE)"]];
dashboard.getRange("D5").formulas = [["=COUNTIF('監控清單'!$AD$2:$AD$1000,\"高於上限\")+COUNTIF('監控清單'!$AD$2:$AD$1000,\"低於下限\")"]];
dashboard.getRange("F5").formulas = [["=COUNTIF('監控清單'!$AC$2:$AC$1000,\"*不足*\")+COUNTIF('監控清單'!$AC$2:$AC$1000,\"*失敗*\")+COUNTIF('監控清單'!$AC$2:$AC$1000,\"*限制*\")"]];
dashboard.getRange("H5").formulas = [["='設定'!$B$18"]];
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
dashboard.getRange("B7").formulas = [["='設定'!$B$20"]];
dashboard.getRange("B8").formulas = [["='設定'!$B$19"]];
dashboard.getRange("B9").formulas = [["='設定'!$B$16"]];
dashboard.getRange("B10").formulas = [["='設定'!$B$15"]];
dashboard.getRange("A7:A10").format = { fill: "#F8FAFC", font: { bold: true } };
dashboard.getRange("B7:B10").format = { font: { color: "#008000" } };
dashboard.getRange("A7:B10").format.borders = { preset: "outside", style: "thin", color: "#CBD5E1" };

dashboard.getRange("A12:H12").merge();
dashboard.getRange("A12").values = [["使用方式"]];
dashboard.getRange("A12:H12").format = { fill: "#E5E7EB", font: { bold: true } };
dashboard.getRange("A13:H18").merge(true);
dashboard.getRange("A13:A18").values = [
  ["1. 在 Google Sheets 選單「選擇權警示」執行「初始化／修復系統」。"],
  ["2. 在「設定」填入固定通知信箱，再部署 Apps Script Web App。"],
  ["3. 透過表單新增股票、到期日、CALL／PUT、履約價及上下限。"],
  ["4. GitHub Actions 依排程取得 Yahoo 期權鏈並更新所有相同股票＋到期日的合約。"],
  ["5. 紅色代表觸發上下限；黃色代表報價／Greeks 不足或更新異常。"],
  ["6. 本工具只供個人研究與監控，不會執行任何交易。"],
];
dashboard.getRange("A13:H18").format = { wrapText: true, rowHeight: 27, verticalAlignment: "center" };

dashboard.getRange("A20:D23").values = [
  ["色彩圖例", "用途", "資料性質", "說明"],
  ["藍字", "可編輯", "使用者輸入", "監控條件與設定"],
  ["綠字", "跨工作表", "工作簿連結", "控制台從設定表取值"],
  ["黑字", "系統輸出", "來源或計算", "Yahoo 原始資料與系統估算"],
];
dashboard.getRange("A20:D20").format = { fill: "#E5E7EB", font: { bold: true } };
dashboard.getRange("A21").format.font = { color: "#0000FF" };
dashboard.getRange("A22").format.font = { color: "#008000" };

dashboard.getRange("A25:H28").merge(true);
dashboard.getRange("A25:A28").values = [
  ["資料來源：https://finance.yahoo.com/"],
  ["程式庫：https://github.com/ranaroussi/yfinance"],
  ["Last 可能是舊成交；警示優先使用有效 Bid／Ask 的 Mid。"],
  ["Delta、Vega、Theta 為模型估算，IV 缺失時留白，不猜值。"],
];
dashboard.getRange("A25:H28").format = { font: { color: "#475569", size: 9 }, wrapText: true };
dashboard.freezePanes.freezeRows(2);
dashboard.getRange("A:H").format.columnWidthPx = 118;
dashboard.getRange("A:A").format.columnWidthPx = 150;
dashboard.getRange("B:B").format.columnWidthPx = 210;

// 監控清單：第一列標題，第二列為停用範例，讓原生表格與資料驗證有有效樣本。
monitors.getRange("A1:AI1").values = [monitorHeaders];
const sampleRow = Array(monitorHeaders.length).fill("");
Object.assign(sampleRow, {
  0: false,
  1: "MU|2027-01-15|PUT|55",
  2: "MU",
  3: new Date("2027-01-15T12:00:00Z"),
  4: "PUT",
  5: 55,
  6: 2.5,
  7: 4,
  8: true,
  9: "停用範例；可透過網頁表單更新或刪除",
  10: "範例（停用）",
  28: "尚未抓取",
  29: "停用",
  32: "停用",
  34: "MU_2027-01-15",
});
monitors.getRange("A2:AI2").values = [sampleRow];
monitors.getRange("A1:AI1").format = {
  fill: "#E5E7EB",
  font: { bold: true, color: "#111827" },
  rowHeight: 30,
  wrapText: true,
  verticalAlignment: "center",
};
monitors.getRange("A2:J1000").format.font = { color: "#0000FF" };
monitors.getRange("D2:D1000").format.numberFormat = "yyyy-mm-dd";
monitors.getRange("F2:H1000").format.numberFormat = "0.00";
monitors.getRange("M2:R1000").format.numberFormat = "0.0000";
monitors.getRange("T2:W1000").format.numberFormat = "0.0000";
monitors.getRange("Y2:Z1000").format.numberFormat = "#,##0";
monitors.getRange("AA2:AF1000").format.numberFormat = "yyyy-mm-dd hh:mm:ss";
monitors.getRange("E2:E1000").dataValidation = { rule: { type: "list", values: ["CALL", "PUT"] } };
monitors.getRange("A2:A1000").dataValidation = { rule: { type: "list", values: ["TRUE", "FALSE"] } };
monitors.getRange("I2:I1000").dataValidation = { rule: { type: "list", values: ["TRUE", "FALSE"] } };
monitors.getRange("A2:AI1000").conditionalFormats.addCustom('=$A2=FALSE', { fill: "#F3F4F6", font: { color: "#6B7280" } });
monitors.getRange("A2:AI1000").conditionalFormats.addCustom('=OR($AD2="高於上限",$AD2="低於下限")', { fill: "#FECACA", font: { color: "#991B1B", bold: true } });
monitors.getRange("A2:AI1000").conditionalFormats.addCustom('=OR(ISNUMBER(SEARCH("不足",$AC2)),ISNUMBER(SEARCH("失敗",$AC2)),ISNUMBER(SEARCH("限制",$AC2)))', { fill: "#FEF3C7", font: { color: "#92400E" } });
monitors.tables.add("A1:AI2", true, "MonitorTable");
monitors.freezePanes.freezeRows(1);
monitors.freezePanes.freezeColumns(10);
monitors.getRange("A:A").format.columnWidthPx = 65;
monitors.getRange("B:B").format.columnWidthPx = 235;
monitors.getRange("C:C").format.columnWidthPx = 80;
monitors.getRange("D:D").format.columnWidthPx = 105;
monitors.getRange("E:E").format.columnWidthPx = 75;
monitors.getRange("F:I").format.columnWidthPx = 95;
monitors.getRange("J:J").format.columnWidthPx = 240;
monitors.getRange("K:AI").format.columnWidthPx = 105;
monitors.getRange("L:L").format.columnWidthPx = 190;
monitors.getRange("AA:AB").format.columnWidthPx = 165;
monitors.getRange("AH:AH").format.columnWidthPx = 260;

// 設定
const settingsRows = [
  ["設定項目", "設定值", "說明"],
  ["Spreadsheet ID", "", "初始化時自動填入；GitHub Actions 也需設定相同 ID"],
  ["通知信箱", "", "全系統固定收件信箱"],
  ["開盤更新間隔(分鐘)", 5, "GitHub Actions 最短排程為 5 分鐘"],
  ["盤外更新間隔(分鐘)", 10, "盤前、盤後、休市"],
  ["資料過期門檻(分鐘)", 10, "超過後在表內標示異常"],
  ["警示回復緩衝", 0.02, "回到門檻內 2% 後才重新啟用"],
  ["無風險利率代號", "^IRX", "Yahoo 13 週國庫券指標"],
  ["備援無風險利率", 0.05, "^IRX 失敗時採用"],
  ["預設股息殖利率", 0, "Yahoo 缺失時採用；0 代表不調整"],
  ["顯示時區", "Asia/Taipei", "使用者介面與工作表"],
  ["市場時區", "America/New_York", "到期與市場時段判斷"],
  ["Cloud Run URL", "", "部署後填入"],
  ["Web App URL", "", "Apps Script 部署後填入"],
  ["系統版本", "0.2.0", "目前規格版本"],
  ["下次允許抓取(UTC)", "", "系統管理：流量限制退避"],
  ["連續失敗次數", 0, "系統管理"],
  ["最後成功抓取(UTC)", "", "系統管理"],
  ["最後執行(UTC)", "", "系統管理"],
  ["最後狀態", "尚未執行", "系統管理"],
];
settings.getRange("A1:C20").values = settingsRows;
settings.getRange("A1:C1").format = { fill: "#E5E7EB", font: { bold: true } };
settings.getRange("B2:B14").format.font = { color: "#0000FF" };
settings.getRange("B7:B10").format.numberFormat = "0.0%";
settings.getRange("A1:C20").format.borders = { preset: "outside", style: "thin", color: "#CBD5E1" };
settings.getRange("C2:C20").format = { wrapText: true, font: { color: "#475569" } };
settings.getRange("A:A").format.columnWidthPx = 190;
settings.getRange("B:B").format.columnWidthPx = 250;
settings.getRange("C:C").format.columnWidthPx = 330;
settings.freezePanes.freezeRows(1);

// 日誌
const alertHeaders = ["寄送時間", "監控ID", "股票代號", "到期日", "類型", "履約價", "觸發狀態", "當時價格", "價格來源", "觸發門檻", "收件信箱", "寄送狀態"];
alertLog.getRange("A1:L1").values = [alertHeaders];
alertLog.getRange("A1:L1").format = { fill: "#E5E7EB", font: { bold: true }, wrapText: true };
alertLog.getRange("A:B").format.columnWidthPx = 190;
alertLog.getRange("C:J").format.columnWidthPx = 105;
alertLog.getRange("K:K").format.columnWidthPx = 230;
alertLog.getRange("L:L").format.columnWidthPx = 100;
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

for (const sheetName of ["控制台", "監控清單", "設定", "警示紀錄", "系統紀錄"]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1.4, format: "png" });
  const fileName = `${sheetName}.png`;
  await fs.writeFile(`${outputDir}/${fileName}`, new Uint8Array(await preview.arrayBuffer()));
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(`${outputDir}/選擇權警示.xlsx`);

const dashboardCheck = await workbook.inspect({
  kind: "table",
  range: "控制台!A1:H28",
  include: "values,formulas",
  tableMaxRows: 30,
  tableMaxCols: 10,
});
console.log(dashboardCheck.ndjson);
