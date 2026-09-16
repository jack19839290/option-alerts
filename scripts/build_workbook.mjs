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
const closeTrend = workbook.worksheets.add("收盤Delta趨勢");
const volatilityTrend = workbook.worksheets.add("波動率趨勢");
const queue = workbook.worksheets.add("通知佇列");
const closeState = workbook.worksheets.add("收盤門檻紀錄");
const expirationCache = workbook.worksheets.add("到期日快取");
const sampleChain = workbook.worksheets.add("MU_2027-01-15");

const scanHeaders = [
  "啟用", "掃描ID", "股票代號", "到期日", "顯示類型",
  "第一門檻啟用", "第一Delta條件", "第一Delta門檻", "第一Bid-Ask價差條件", "第一Bid-Ask價差門檻",
  "第一年化報酬率條件", "第一年化報酬率門檻", "第一未平倉大於(口)",
  "第二門檻啟用", "第二Delta條件", "第二Delta門檻", "第二Bid-Ask價差條件", "第二Bid-Ask價差門檻",
  "第二年化報酬率條件", "第二年化報酬率門檻", "第二未平倉大於(口)",
  "CALL持股成本", "Email通知", "備註", "狀態", "標的股價", "合約數", "第一符合數", "第二符合數",
  "最後嘗試時間", "最後成功抓取時間", "資料狀態", "錯誤訊息", "工作表", "第一條件指紋",
  "第二條件指紋", "收盤狀態", "收盤最後成功交易日",
];

const alertHeaders = [
  "紀錄時間", "掃描ID", "股票代號", "到期日", "類型", "履約價", "Bid", "Delta估算",
  "標的股價", "年化報酬率", "未平倉", "DTE", "合約代號", "收件信箱", "寄送狀態",
  "Ask", "Bid-Ask價差率", "事件ID", "事件類型", "門檻", "今日新增", "事件完整性",
  "失敗掃描", "紀錄ID",
];

const closeTrendHeaders = [
  "快照ID", "美東交易日", "官方收盤時間(UTC)", "實際抓取時間(UTC)", "掃描ID", "股票代號",
  "到期日", "類型", "目標|Delta|", "選取狀態", "合約代號", "履約價", "Delta估算", "|Delta|",
  "Delta差距", "標的快照價", "Last", "Bid", "Ask", "Mid", "Bid-Ask價差率", "賣出試算價",
  "試算價來源", "年化本金", "DTE", "到期權利金報酬率", "年化報酬率", "IV", "Gamma估算",
  "Theta估算(每日)", "Vega估算(每1%)", "成交量", "未平倉", "最後成交時間", "無風險利率",
  "無風險利率來源", "股息殖利率", "Greeks模型", "資料狀態", "備註／未選取原因",
  "標的－履約價差", "標的－履約價差率",
];

const volatilityTrendHeaders = [
  "美東交易日", "股票代號", "到期日", "類型", "DTE", "標的快照價",
  "10Δ IV", "25Δ IV", "ATM IV", "10Δ − 25Δ", "10Δ − ATM", "資料狀態",
  "官方收盤時間(UTC)", "實際抓取時間(UTC)", "IV取樣說明", "快照ID",
];
volatilityTrend.getRange("A1:P1").values = [volatilityTrendHeaders];
volatilityTrend.getRange("A1:P1").format = {fill: "#DBEAFE", font: {bold: true}, wrapText: true};
volatilityTrend.getRange("A:P").format.columnWidthPx = 115;
volatilityTrend.getRange("G:I").format.numberFormat = "0.00%";
volatilityTrend.getRange("J:K").format.numberFormat = '0.00" 點"';
volatilityTrend.getRange("M:N").format.numberFormat = "yyyy-mm-dd hh:mm:ss";
volatilityTrend.freezePanes.freezeRows(1);
volatilityTrend.freezePanes.freezeColumns(4);

const expirationCacheHeaders = [
  "股票代號", "狀態", "查詢ID", "查詢時間(UTC)", "到期日JSON", "到期日數量", "錯誤訊息",
];

const chainHeaders = [
  "符合門檻", "第一門檻結果", "第二門檻結果", "類型", "履約價", "標的股價", "Bid",
  "年化報酬率", "第一年化報酬率結果", "第二年化報酬率結果", "Delta估算", "第一Delta結果",
  "第二Delta結果", "Bid-Ask價差率", "第一Bid-Ask價差結果", "第二Bid-Ask價差結果",
  "未平倉", "第一未平倉結果", "第二未平倉結果", "DTE", "最後抓取時間", "Ask", "Mid",
  "Last", "成交量", "標的－履約價差", "最後成交時間", "Gamma估算", "Theta估算(每日)",
  "Vega估算(每1%)", "IV", "年化本金", "賣出試算價", "試算價來源", "無風險利率",
  "股息殖利率", "Greeks模型", "|Delta|", "合約代號", "掃描ID", "第二通知狀態",
  "第二可再次通知", "第二連續有效不符合", "第二通知序號", "資料狀態",
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
dashboard.getRange("D5").formulas = [["=SUM('掃描設定'!$AB$2:$AB$1000)+SUM('掃描設定'!$AC$2:$AC$1000)"]];
dashboard.getRange("F5").formulas = [["=COUNTIF('掃描設定'!$AF$2:$AF$1000,\"*不足*\")+COUNTIF('掃描設定'!$AF$2:$AF$1000,\"*失敗*\")+COUNTIF('掃描設定'!$AF$2:$AF$1000,\"*限制*\")"]];
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
dashboard.getRange("B7:B10").format = { font: { color: "#475569" } };
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
dashboard.getRange("H8:H10").format = { font: { color: "#475569" }, wrapText: true };
dashboard.getRange("H7").dataValidation = { rule: { type: "list", values: ["TRUE", "FALSE"] } };

dashboard.getRange("A12:H12").merge();
dashboard.getRange("A12").values = [["使用方式"]];
dashboard.getRange("A12:H12").format = { fill: "#E5E7EB", font: { bold: true } };
dashboard.getRange("A13:H18").merge(true);
dashboard.getRange("A13:A18").values = [
  ["1. 在 Google Sheets 選單「選擇權警示」執行「初始化／升級系統」。"],
  ["2. 在「設定」填入固定通知信箱，再從選單設定 90 天 GitHub 金鑰。"],
  ["3. 表單輸入股票後可勾選未來一年內多個到期日，並套用同一組掃描條件。"],
  ["4. 開盤、盤中整點與收盤自動更新；正式收盤會保存 Delta 0.10／0.15／0.20 趨勢。"],
  ["5. 第一門檻每天收盤彙總全部符合項目；第二門檻首次符合時即時通知。"],
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
  ["Delta、Gamma、Theta、Vega 為模型估算；Yahoo 未平倉量可能不是即時更新。"],
];
dashboard.getRange("A25:H29").format = { font: { color: "#475569", size: 9 }, wrapText: true };
dashboard.freezePanes.freezeRows(2);
dashboard.getRange("A:H").format.columnWidthPx = 118;
dashboard.getRange("A:A").format.columnWidthPx = 150;
dashboard.getRange("B:B").format.columnWidthPx = 210;

// 掃描設定：普通儲存格加驗證，不建立原生表格，避免指定類型欄限制 Apps Script。
scans.getRange("A1:AL1").values = [scanHeaders];
const sampleRow = Array(scanHeaders.length).fill("");
Object.assign(sampleRow, {
  0: false,
  1: "MU|2027-01-15",
  2: "MU",
  3: new Date("2027-01-15T12:00:00Z"),
  4: "ALL",
  5: true, 6: "≥", 7: 0.2, 8: "≤", 9: 0.10, 10: "≥", 11: 0.15, 12: 100,
  13: false, 21: 60, 22: true, 23: "停用範例；第一門檻為舊條件遷移位置",
  24: "範例（停用）", 31: "尚未抓取", 33: "MU_2027-01-15",
});
scans.getRange("A2:AL2").values = [sampleRow];
scans.getRange("A1:AL1").format = {
  fill: "#E5E7EB",
  font: { bold: true, color: "#111827" },
  rowHeight: 34,
  wrapText: true,
  verticalAlignment: "center",
};
scans.getRange("A2:X1000").format.font = { color: "#0000FF" };
scans.getRange("D2:D1000").format.numberFormat = "yyyy-mm-dd";
scans.getRange("H2:H1000").format.numberFormat = "0.0000";
scans.getRange("J2:L1000").format.numberFormat = "0.00%";
scans.getRange("M2:M1000").format.numberFormat = "#,##0";
scans.getRange("P2:P1000").format.numberFormat = "0.0000";
scans.getRange("R2:T1000").format.numberFormat = "0.00%";
scans.getRange("U2:U1000").format.numberFormat = "#,##0";
scans.getRange("V2:V1000").format.numberFormat = "0.0000";
scans.getRange("Z2:Z1000").format.numberFormat = "0.0000";
scans.getRange("AA2:AC1000").format.numberFormat = "#,##0";
scans.getRange("AD2:AE1000").format.numberFormat = "yyyy-mm-dd hh:mm:ss";
scans.getRange("A2:A1000").dataValidation = { rule: { type: "list", values: ["TRUE", "FALSE"] } };
for (const column of ["F", "N", "W"]) scans.getRange(`${column}2:${column}1000`).dataValidation = { rule: { type: "list", values: ["TRUE", "FALSE"] } };
scans.getRange("E2:E1000").dataValidation = { rule: { type: "list", values: ["ALL", "CALL", "PUT"] } };
for (const column of ["G", "I", "K", "O", "Q", "S"]) {
  scans.getRange(`${column}2:${column}1000`).dataValidation = { rule: { type: "list", values: ["≥", "≤"] } };
}
scans.getRange("A2:AL1000").conditionalFormats.addCustom('=$A2=FALSE', { fill: "#F3F4F6", font: { color: "#6B7280" } });
scans.getRange("A2:AL1000").conditionalFormats.addCustom('=OR($AB2>0,$AC2>0)', { fill: "#DCFCE7", font: { color: "#166534", bold: true } });
scans.getRange("A2:AL1000").conditionalFormats.addCustom('=REGEXMATCH($AF2,"不足|失敗|限制")', { fill: "#FEF3C7", font: { color: "#92400E" } });
scans.freezePanes.freezeRows(1);
scans.freezePanes.freezeColumns(5);
scans.getRange("A:A").format.columnWidthPx = 65;
scans.getRange("B:B").format.columnWidthPx = 185;
scans.getRange("C:C").format.columnWidthPx = 80;
scans.getRange("D:D").format.columnWidthPx = 105;
scans.getRange("E:E").format.columnWidthPx = 95;
scans.getRange("F:W").format.columnWidthPx = 110;
scans.getRange("X:X").format.columnWidthPx = 260;
scans.getRange("Y:AL").format.columnWidthPx = 115;
scans.getRange("AG:AG").format.columnWidthPx = 260;

// 收盤 Delta 趨勢：長表格，每個交易日／掃描／類型／目標 Delta 一列。
closeTrend.getRange("A1:AP1").values = [closeTrendHeaders];
closeTrend.getRange("A1:AP1").format = {
  fill: "#E5E7EB",
  font: { bold: true, color: "#111827" },
  rowHeight: 42,
  wrapText: true,
  verticalAlignment: "center",
};
closeTrend.freezePanes.freezeRows(1);
closeTrend.freezePanes.freezeColumns(10);
closeTrend.getRange("A:AP").format.columnWidthPx = 110;
closeTrend.getRange("A:A").format.columnWidthPx = 300;
closeTrend.getRange("E:E").format.columnWidthPx = 180;
closeTrend.getRange("K:K").format.columnWidthPx = 210;
closeTrend.getRange("AJ:AJ").format.columnWidthPx = 190;
closeTrend.getRange("AL:AL").format.columnWidthPx = 220;
closeTrend.getRange("AM:AM").format.columnWidthPx = 260;
closeTrend.getRange("AN:AN").format.columnWidthPx = 320;
closeTrend.getRange("B:B").format.numberFormat = "yyyy-mm-dd";
closeTrend.getRange("C:D").format.numberFormat = "yyyy-mm-dd hh:mm:ss";
closeTrend.getRange("G:G").format.numberFormat = "yyyy-mm-dd";
closeTrend.getRange("I:I").format.numberFormat = "0.0000";
closeTrend.getRange("L:T").format.numberFormat = "0.0000";
closeTrend.getRange("U:U").format.numberFormat = "0.00%";
closeTrend.getRange("V:V").format.numberFormat = "0.0000";
closeTrend.getRange("X:X").format.numberFormat = "0.0000";
closeTrend.getRange("Y:Y").format.numberFormat = "0";
closeTrend.getRange("Z:AB").format.numberFormat = "0.00%";
closeTrend.getRange("AC:AE").format.numberFormat = "0.0000";
closeTrend.getRange("AF:AG").format.numberFormat = "#,##0";
closeTrend.getRange("AH:AH").format.numberFormat = "yyyy-mm-dd hh:mm:ss";
closeTrend.getRange("AI:AI").format.numberFormat = "0.00%";
closeTrend.getRange("AK:AK").format.numberFormat = "0.00%";
closeTrend.getRange("AO:AO").format.numberFormat = "0.0000";
closeTrend.getRange("AP:AP").format.numberFormat = "0.00%";
closeTrend.getRange("A2:AP1000").conditionalFormats.addCustom(
  '=AND($J2="已選取",$AM2="正常")',
  { fill: "#DCFCE7", font: { color: "#166534" } },
);
closeTrend.getRange("A2:AP1000").conditionalFormats.addCustom(
  '=REGEXMATCH($J2&$AM2,"不足|無效|無符合|無資料|未執行")',
  { fill: "#FEF3C7", font: { color: "#92400E" } },
);
closeTrend.getRange("A2:AP1000").conditionalFormats.addCustom(
  '=REGEXMATCH($J2&$AM2,"失敗|流量限制")',
  { fill: "#FEE2E2", font: { color: "#991B1B" } },
);

// 期權鍊示意：把判斷結果放在數值旁，常用欄位集中於 A:U。
sampleChain.getRange("A1:AS1").values = [chainHeaders];
const makeChainRow = values => chainHeaders.map(header => values[header] ?? "");
sampleChain.getRange("A2:AS4").values = [
  makeChainRow({"符合門檻":"第一＋第二","第一門檻結果":"符合","第二門檻結果":"符合","類型":"PUT","履約價":55,"標的股價":60,"Bid":3.8,"年化報酬率":0.18,"第一年化報酬率結果":"通過","第二年化報酬率結果":"通過","Delta估算":-0.25,"第一Delta結果":"通過","第二Delta結果":"通過","Bid-Ask價差率":0.10,"第一Bid-Ask價差結果":"通過","第二Bid-Ask價差結果":"通過","未平倉":350,"第一未平倉結果":"通過","第二未平倉結果":"通過","DTE":100,"資料狀態":"正常"}),
  makeChainRow({"符合門檻":"第一門檻","第一門檻結果":"符合","第二門檻結果":"未符合","類型":"PUT","履約價":50,"標的股價":60,"Bid":2.1,"年化報酬率":0.153,"第一年化報酬率結果":"通過","第二年化報酬率結果":"未通過","Delta估算":-0.18,"第一Delta結果":"通過","第二Delta結果":"未通過","Bid-Ask價差率":0.08,"第一Bid-Ask價差結果":"通過","第二Bid-Ask價差結果":"通過","未平倉":210,"第一未平倉結果":"通過","第二未平倉結果":"通過","DTE":100,"資料狀態":"正常"}),
  makeChainRow({"符合門檻":"未符合","第一門檻結果":"未符合","第二門檻結果":"未符合","類型":"CALL","履約價":65,"標的股價":60,"Bid":1.2,"年化報酬率":0.073,"第一年化報酬率結果":"未通過","第二年化報酬率結果":"未通過","Delta估算":0.20,"第一Delta結果":"通過","第二Delta結果":"通過","Bid-Ask價差率":0.25,"第一Bid-Ask價差結果":"未通過","第二Bid-Ask價差結果":"未通過","未平倉":80,"第一未平倉結果":"未通過","第二未平倉結果":"未通過","DTE":100,"資料狀態":"正常"}),
];
sampleChain.getRange("A1:AS1").format = {fill:"#E5E7EB",font:{bold:true},wrapText:true,rowHeight:42};
sampleChain.getRange("A2:AS2").format = {fill:"#D1FAE5",font:{color:"#065F46",bold:true}};
sampleChain.getRange("A3:AS3").format = {fill:"#DCFCE7",font:{color:"#166534"}};
sampleChain.freezePanes.freezeRows(1); sampleChain.freezePanes.freezeColumns(5);
sampleChain.getRange("A:AS").format.columnWidthPx = 105;
sampleChain.getRange("E:G").format.numberFormat = "0.0000";
sampleChain.getRange("H:H").format.numberFormat = "0.00%";
sampleChain.getRange("K:K").format.numberFormat = "0.0000";
sampleChain.getRange("N:N").format.numberFormat = "0.00%";
sampleChain.getRange("Q:Q").format.numberFormat = "#,##0";

// 設定
const settingsRows = [
  ["設定項目", "設定值", "說明"],
  ["Spreadsheet ID", "", "初始化時自動填入；GitHub Actions 也需設定相同 ID"],
  ["通知信箱", "", "全系統固定收件信箱"],
  ["自動更新規則", "開盤、盤中整點、收盤", "CBOE 美股股票期權正常交易時段"],
  ["盤外自動更新", "停用", "盤外只允許使用者手動更新"],
  ["資料過期門檻(分鐘)", 10, "超過後在表內標示異常"],
  ["無風險利率代號", "^IRX", "Yahoo 13 週國庫券指標"],
  ["備援無風險利率", 0.05, "^IRX 失敗時採用"],
  ["預設股息殖利率", 0, "Yahoo 缺失時採用；0 代表不調整"],
  ["顯示時區", "Asia/Taipei", "使用者介面與工作表；修改後請重新執行初始化／升級系統"],
  ["市場時區", "America/New_York", "到期與市場時段判斷"],
  ["Cloud Run URL", "", "選用部署後填入"],
  ["Web App URL", "", "Apps Script 部署後填入"],
  ["系統版本", "0.9.0", "目前規格版本"],
  ["下次允許抓取(UTC)", "", "系統管理：流量限制退避"],
  ["連續失敗次數", 0, "系統管理"],
  ["最後成功抓取(UTC)", "", "系統管理"],
  ["最後執行(UTC)", "", "系統管理"],
  ["最後狀態", "尚未執行", "系統管理"],
  ["GitHub 自動更新", "尚未設定", "金鑰只存於 Apps Script 個人屬性，不會寫入儲存格"],
  ["GitHub 金鑰到期日", "", "只記錄使用者輸入的到期日，用於提前 7 天提醒"],
  ["GitHub 最後要求(UTC)", "", "Apps Script 最近一次要求 GitHub 執行的時間"],
  ["GitHub 最後要求狀態", "尚未執行", "成功、失敗或尚未設定"],
  ["Apps Script 成功啟動次數", 0, "Apps Script 自動啟動 GitHub Actions 的累計次數"],
  ["GitHub 原生排程", "已移除（0.5.0）", "只由 Apps Script 在開盤更新時點啟動"],
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
alertLog.getRange("A1:X1").values = [alertHeaders];
alertLog.getRange("A1:X1").format = { fill: "#E5E7EB", font: { bold: true }, wrapText: true };
alertLog.getRange("A2:X5").values = [
  [new Date("2026-09-09T20:05:00+08:00"), "MU|2027-01-15", "MU", new Date("2027-01-15T12:00:00Z"), "PUT", 55, 3.8, -0.25, 60, 0.18, 350, 100, "MU270115P00055000", "alerts@example.com", "已寄送", 4.2, 0.10, "CLOSE|2026-09-09|INITIAL", "FIRST_CLOSE", "第一門檻", "是", "完整", "", "CLOSE|2026-09-09|INITIAL|MU|2027-01-15|MU270115P00055000"],
  [new Date("2026-09-09T21:02:00+08:00"), "MU|2027-01-15", "MU", new Date("2027-01-15T12:00:00Z"), "PUT", 55, 3.9, -0.25, 60.2, 0.185, 355, 100, "MU270115P00055000", "alerts@example.com", "已寄送（本次新增）", 4.3, 0.0976, "RT|MU|2027-01-15|2", "SECOND_REALTIME", "第二門檻", "", "完整", "", "RT|MU|2027-01-15|2|MU|2027-01-15|MU270115P00055000"],
  [new Date("2026-09-09T21:02:00+08:00"), "MU|2027-01-15", "MU", new Date("2027-01-15T12:00:00Z"), "CALL", 65, 2.1, 0.28, 60.2, 0.128, 420, 100, "MU270115C00065000", "alerts@example.com", "持續符合（未重複寄信）", 2.3, 0.091, "RT|MU|2027-01-15|2", "SECOND_REALTIME", "第二門檻", "", "完整", "", "RT|MU|2027-01-15|2|MU|2027-01-15|MU270115C00065000"],
  [new Date("2026-09-10T20:05:00+08:00"), "NVDA|2027-03-19", "NVDA", new Date("2027-03-19T12:00:00Z"), "", "", "", "", "", "", "", "", "", "alerts@example.com", "已寄送（0筆符合）", "", "", "CLOSE|2026-09-10|INITIAL", "FIRST_CLOSE", "第一門檻", "", "完整", "", "CLOSE|2026-09-10|INITIAL|NVDA|2027-03-19|NO_MATCH"],
];
alertLog.getRange("A:B").format.columnWidthPx = 180;
alertLog.getRange("C:L").format.columnWidthPx = 105;
alertLog.getRange("M:M").format.columnWidthPx = 190;
alertLog.getRange("N:N").format.columnWidthPx = 230;
alertLog.getRange("O:O").format.columnWidthPx = 100;
alertLog.getRange("A2:A5").format.numberFormat = "yyyy-mm-dd hh:mm:ss";
alertLog.getRange("D2:D5").format.numberFormat = "yyyy-mm-dd";
alertLog.getRange("J:J").format.numberFormat = "0.00%";
alertLog.getRange("Q:Q").format.numberFormat = "0.00%";
alertLog.getRange("R:R").format.columnWidthPx = 260;
alertLog.getRange("S:V").format.columnWidthPx = 115;
alertLog.getRange("W:W").format.columnWidthPx = 220;
alertLog.getRange("X:X").format.columnWidthPx = 320;
alertLog.freezePanes.freezeRows(1);
alertLog.freezePanes.freezeColumns(4);

systemLog.getRange("A1:D1").values = [["時間(UTC)", "等級", "訊息", "詳細資料"]];
systemLog.getRange("A1:D1").format = { fill: "#E5E7EB", font: { bold: true } };
expirationCache.getRange("A1:G1").values = [expirationCacheHeaders];
expirationCache.getRange("A1:G1").format = { fill: "#E5E7EB", font: { bold: true } };
expirationCache.freezePanes.freezeRows(1);
systemLog.getRange("A:A").format.columnWidthPx = 190;
systemLog.getRange("B:B").format.columnWidthPx = 80;
systemLog.getRange("C:C").format.columnWidthPx = 180;
systemLog.getRange("D:D").format = { columnWidthPx: 520, wrapText: true };
systemLog.freezePanes.freezeRows(1);

queue.getRange("A1:O1").values = [["事件ID", "事件類型", "狀態", "建立時間(UTC)", "寄送時間", "重試次數", "下次重試時間", "掃描ID", "股票代號", "到期日", "美東交易日", "是否完整", "失敗掃描", "內容JSON", "最後錯誤"]];
queue.getRange("A1:O1").format = { fill: "#E5E7EB", font: { bold: true }, wrapText: true };
closeState.getRange("A1:J1").values = [["記錄ID", "美東交易日", "掃描ID", "第一條件指紋", "狀態", "符合合約JSON", "最後嘗試時間(UTC)", "成功時間(UTC)", "錯誤訊息", "嘗試次數"]];
closeState.getRange("A1:J1").format = { fill: "#E5E7EB", font: { bold: true }, wrapText: true };

workbook.recalculate();
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
  "警示紀錄": "A1:X5",
  "系統紀錄": "A1:D5",
  "收盤Delta趨勢": "A1:AP5",
  "MU_2027-01-15": "A1:U5",
};
for (const [sheetName, range] of Object.entries(previewRanges)) {
  const preview = await workbook.render({ sheetName, range, scale: 1.4, format: "png" });
  await fs.writeFile(`${outputDir}/${sheetName}.png`, new Uint8Array(await preview.arrayBuffer()));
}
for (const [suffix, range] of [["前段", "A1:T5"], ["後段", "U1:AP5"]]) {
  const preview = await workbook.render({ sheetName: "收盤Delta趨勢", range, scale: 1.4, format: "png" });
  await fs.writeFile(`${outputDir}/收盤Delta趨勢_${suffix}.png`, new Uint8Array(await preview.arrayBuffer()));
}
const scanOutputPreview = await workbook.render({ sheetName: "掃描設定", range: "Y1:AL5", scale: 1.4, format: "png" });
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
  range: "掃描設定!A1:AL2",
  include: "values,formulas",
  tableMaxRows: 3,
  tableMaxCols: 30,
});
console.log(scanCheck.ndjson);
const trendCheck = await workbook.inspect({
  kind: "table",
  range: "收盤Delta趨勢!A1:AP3",
  include: "values,formulas",
  tableMaxRows: 4,
  tableMaxCols: 42,
});
console.log(trendCheck.ndjson);

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(`${outputDir}/選擇權警示.xlsx`);
