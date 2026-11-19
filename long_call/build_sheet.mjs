import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [schemaPath, outputPath] = process.argv.slice(2);
const schema = JSON.parse(await fs.readFile(schemaPath, "utf8"));
const book = Workbook.create();
const labels = { fill: "#eeeeee", font: { bold: true }, wrapText: true };
const settings = book.worksheets.add(schema.settings);

settings.getRange("A1").values = [["買入買權篩選器"]];
settings.getRange("A1:J1").format = labels;
settings.getRange("A2").values = [["選取標的後啟用。標的列留白的門檻沿用第 5 列的預設值。"]];
settings.getRange("A3").values = [["收盤 Email 由 Apps Script 寄出。最高買價為行情快照試算上限。"]];
settings.getRange("A4:J4").values = [["套用範圍", "股票代號", ...schema.thresholds]];
settings.getRange("A5:J5").values = [["全表預設", "", ...schema.defaults]];
settings.getRange("A6").values = [["手動更新"]];
settings.getRange("B6").formulas = [['=HYPERLINK("https://github.com/jack19839290/option-alerts/actions/workflows/long-call.yml","開啟 GitHub Actions")']];
settings.getRange("A7").values = [["收盤 Email"]];
settings.getRange("B7").values = [[""]];
settings.getRange("A9:J9").values = [["啟用", "股票代號", ...schema.thresholds]];
settings.getRange("A10:B10").values = [[false, ""]];
for (const row of [4, 9]) {
  settings.getRange(`A${row}:J${row}`).format = labels;
  settings.getRange(`A${row}:J${row}`).format.rowHeightPx = 34;
}
settings.getRange("A1:J1").format.columnWidthPx = 112;
settings.getRange("B1:B9").format.columnWidthPx = 205;
for (const column of ["F", "H", "I"]) {
  settings.getRange(`${column}5:${column}200`).format.numberFormat = "0.00%";
}
settings.freezePanes.freezeRows(9);

for (const [title, headers, end] of [
  [schema.results, schema.contracts, "U"],
  [schema.detail, schema.contracts, "U"],
  [schema.log, schema.logs, "L"],
]) {
  const tab = book.worksheets.add(title);
  const header = tab.getRange(`A1:${end}1`);
  header.values = [headers];
  header.format = labels;
  header.format.columnWidthPx = 107;
  header.format.rowHeightPx = 34;
  tab.freezePanes.freezeRows(1);
  if (end === "U") {
    tab.getRange("G2:I200").format.numberFormat = "0.00%";
    tab.getRange("S1:U1").format.columnWidthPx = 195;
    tab.freezePanes.freezeColumns(2);
  } else {
    tab.getRange("A1").format.columnWidthPx = 184;
    tab.getRange("I1").format.columnWidthPx = 300;
  }
}

const workbook = await SpreadsheetFile.exportXlsx(book);
await workbook.save(outputPath);
const preview = await book.render({ sheetName: schema.settings, range: "A1:J10", scale: 1, format: "png" });
await fs.writeFile(outputPath.replace(/\.xlsx$/, ".png"), new Uint8Array(await preview.arrayBuffer()));
