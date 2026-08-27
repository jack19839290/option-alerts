const APP = Object.freeze({
  VERSION: '0.3.1',
  SHEETS: {
    DASHBOARD: '控制台',
    SCANS: '掃描設定',
    LEGACY_MONITORS: '監控清單',
    SETTINGS: '設定',
    ALERTS: '警示紀錄',
    SYSTEM: '系統紀錄',
  },
  SCAN_HEADERS: [
    '啟用', '掃描ID', '股票代號', '到期日', '顯示類型', 'Delta條件', 'Delta門檻',
    'Vega條件', 'Vega門檻', '年化報酬率條件', '年化報酬率門檻', 'CALL持股成本',
    '未平倉大於(口)', 'Email通知', '備註', '狀態', '標的股價', '合約數', '符合數',
    '最後抓取時間', '資料狀態', '待寄信', '最後通知時間', '錯誤訊息', '工作表',
    '已建立基準', '條件指紋'
  ],
  CHAIN_HEADERS: [
    '掃描ID', '類型', '履約價', '合約代號', '標的股價', 'Last', 'Bid', 'Ask', 'Mid',
    '賣出試算價', '試算價來源', 'IV', '無風險利率', '股息殖利率', 'Greeks模型',
    'Delta估算', '|Delta|', 'Vega估算(每1%)', 'Theta估算(每日)', 'DTE', '年化報酬率',
    '年化本金', '成交量', '未平倉', 'Delta條件結果', 'Vega條件結果',
    '年化報酬率條件結果', '未平倉條件結果', '全部條件符合', '通知狀態',
    '可再次通知', '連續有效不符合', '待寄信', '最後成交時間', '最後抓取時間', '資料狀態'
  ],
  ALERT_HEADERS: [
    '寄送時間', '掃描ID', '股票代號', '到期日', '類型', '履約價', 'Bid', 'Delta估算',
    'Vega估算(每1%)', '年化報酬率', '未平倉', 'DTE', '合約代號', '收件信箱', '寄送狀態'
  ],
});

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('選擇權警示')
    .addItem('新增／更新期權鍊掃描', 'showScanDialog')
    .addItem('要求下一輪立即更新', 'requestNextRefresh')
    .addSeparator()
    .addItem('初始化／升級系統', 'setupSystem')
    .addToUi();
}

function doGet() {
  ensureSystemSheets_();
  return HtmlService.createTemplateFromFile('Index')
    .evaluate()
    .setTitle('期權鍊掃描設定')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.DEFAULT);
}

function showScanDialog() {
  ensureSystemSheets_();
  const output = HtmlService.createTemplateFromFile('Index')
    .evaluate()
    .setWidth(650)
    .setHeight(860);
  SpreadsheetApp.getUi().showModalDialog(output, '新增／更新期權鍊掃描');
}

// 保留舊選單或舊連結的相容性。
function showMonitorDialog() {
  showScanDialog();
}

function getFormDefaults() {
  const settings = getSettings_();
  return {
    notificationEmail: String(settings['通知信箱'] || ''),
    emailEnabled: true,
  };
}

function submitScan(payload) {
  const input = validateScanInput_(payload || {});
  const lock = LockService.getDocumentLock();
  lock.waitLock(30000);
  try {
    ensureSystemSheets_();
    const sheet = getSpreadsheet_().getSheetByName(APP.SHEETS.SCANS);
    const values = sheet.getDataRange().getValues();
    const idColumn = APP.SCAN_HEADERS.indexOf('掃描ID');
    let rowNumber = -1;
    let firstAvailableRow = -1;
    for (let row = 1; row < values.length; row += 1) {
      if (String(values[row][idColumn] || '') === input.scanId) {
        rowNumber = row + 1;
        break;
      }
      if (firstAvailableRow === -1 && !hasScanData_(values[row])) {
        firstAvailableRow = row + 1;
      }
    }

    const inputValues = [[
      true,
      input.scanId,
      input.ticker,
      input.expiry,
      input.displayType,
      input.deltaOperator,
      input.deltaThreshold === null ? '' : input.deltaThreshold,
      input.vegaOperator,
      input.vegaThreshold === null ? '' : input.vegaThreshold,
      input.annualReturnOperator,
      input.annualReturnThreshold === null ? '' : input.annualReturnThreshold,
      input.callCostBasis === null ? '' : input.callCostBasis,
      input.openInterestMin === null ? '' : input.openInterestMin,
      input.emailEnabled,
      input.note,
    ]];

    const isNew = rowNumber === -1;
    if (isNew) rowNumber = firstAvailableRow === -1
      ? Math.max(sheet.getLastRow() + 1, 2)
      : firstAvailableRow;
    if (rowNumber > sheet.getMaxRows()) {
      sheet.insertRowsAfter(sheet.getMaxRows(), rowNumber - sheet.getMaxRows());
    }
    sheet.getRange(rowNumber, 1, 1, APP.SCAN_HEADERS.length).clearContent();
    sheet.getRange(rowNumber, 1, 1, inputValues[0].length).setValues(inputValues);
    sheet.getRange(rowNumber, 16).setValue('待抓取');
    sheet.getRange(rowNumber, 21).setValue('等待雲端更新');
    sheet.getRange(rowNumber, 25).setValue(input.sheetName);
    sheet.getRange(rowNumber, 26).setValue(false);
    applyScanFormatting_();
    ensureChainSheet_(input.sheetName);
    requestNextRefresh();

    return {
      ok: true,
      scanId: input.scanId,
      sheetName: input.sheetName,
      message: isNew ? '掃描已新增；第一次抓取只建立基準，不寄信' : '掃描設定已更新；下一次抓取會重新建立基準',
    };
  } finally {
    lock.releaseLock();
  }
}

function submitMonitor(payload) {
  return submitScan(payload);
}

function setupSystem() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  if (!spreadsheet) throw new Error('請從綁定的 Google Sheet 執行初始化');
  PropertiesService.getScriptProperties().setProperty('SPREADSHEET_ID', spreadsheet.getId());
  migrateLegacySheets_();
  ensureSystemSheets_();
  const settingsSheet = spreadsheet.getSheetByName(APP.SHEETS.SETTINGS);
  const settings = settingsSheet.getRange(2, 1, settingsSheet.getLastRow() - 1, 2).getValues();
  const spreadsheetIdRow = settings.findIndex(row => row[0] === 'Spreadsheet ID');
  if (spreadsheetIdRow >= 0) settingsSheet.getRange(spreadsheetIdRow + 2, 2).setValue(spreadsheet.getId());
  const versionRow = settings.findIndex(row => row[0] === '系統版本');
  if (versionRow >= 0) settingsSheet.getRange(versionRow + 2, 2).setValue(APP.VERSION);
  installEmailTrigger_();
  applyScanFormatting_();
  spreadsheet.toast('系統已初始化／升級至 0.3.1；既有舊版資料如有存在會另外保留', '選擇權警示', 7);
}

function requestNextRefresh() {
  const spreadsheet = getSpreadsheet_();
  const settingsSheet = spreadsheet.getSheetByName(APP.SHEETS.SETTINGS);
  if (!settingsSheet) return;
  const values = settingsSheet.getRange(2, 1, settingsSheet.getLastRow() - 1, 2).getValues();
  values.forEach((row, index) => {
    if (row[0] === '最後成功抓取(UTC)' || row[0] === '下次允許抓取(UTC)') {
      settingsSheet.getRange(index + 2, 2).clearContent();
    }
  });
  spreadsheet.toast('雲端服務會在下一次排程更新', '已送出要求', 5);
}

function processPendingEmails() {
  const lock = LockService.getDocumentLock();
  if (!lock.tryLock(25000)) return;
  try {
    const settings = getSettings_();
    const recipient = String(settings['通知信箱'] || '').trim();
    if (!recipient) return;

    const spreadsheet = getSpreadsheet_();
    const sheet = spreadsheet.getSheetByName(APP.SHEETS.SCANS);
    const values = sheet.getDataRange().getValues();
    if (values.length < 2) return;
    const headerMap = Object.fromEntries(values[0].map((header, index) => [header, index]));
    const alertLog = spreadsheet.getSheetByName(APP.SHEETS.ALERTS);

    for (let index = 1; index < values.length; index += 1) {
      const row = values[index];
      const pendingText = String(row[headerMap['待寄信']] || '').trim();
      const enabled = row[headerMap['Email通知']] === true;
      const scanEnabled = row[headerMap['啟用']] === true;
      if (!pendingText || !enabled || !scanEnabled) continue;

      let payload;
      try {
        payload = JSON.parse(pendingText);
      } catch (error) {
        console.error(`無法解析待寄信資料：${error}`);
        continue;
      }
      const items = Array.isArray(payload.items) ? payload.items : [];
      if (!items.length) continue;
      const ticker = row[headerMap['股票代號']];
      const expiry = formatSheetDate_(row[headerMap['到期日']]);
      const total = Number(payload.total || items.length);
      const subject = `【選擇權警示】${ticker} ${expiry}：${total} 個履約價格符合條件`;
      const message = buildScanAlertEmail_(ticker, expiry, payload, spreadsheet.getUrl());
      MailApp.sendEmail({
        to: recipient,
        subject: subject,
        body: message.body,
        htmlBody: message.htmlBody,
        name: '選擇權警示',
      });

      const sentAt = new Date();
      sheet.getRange(index + 1, headerMap['待寄信'] + 1).clearContent();
      sheet.getRange(index + 1, headerMap['最後通知時間'] + 1).setValue(sentAt);
      const logRows = items.map(item => [
        sentAt,
        row[headerMap['掃描ID']],
        ticker,
        row[headerMap['到期日']],
        item.option_type || '',
        item.strike ?? '',
        item.bid ?? '',
        item.delta ?? '',
        item.vega ?? '',
        item.annual_return ?? '',
        item.open_interest ?? '',
        item.dte ?? '',
        item.contract_symbol || '',
        recipient,
        '已寄送',
      ]);
      if (logRows.length) {
        alertLog.getRange(alertLog.getLastRow() + 1, 1, logRows.length, APP.ALERT_HEADERS.length).setValues(logRows);
      }
    }
  } finally {
    lock.releaseLock();
  }
}

function buildScanAlertEmail_(ticker, expiry, payload, spreadsheetUrl) {
  const items = payload.items || [];
  const lines = [
    `${ticker} ${expiry} 有 ${payload.total || items.length} 個新符合條件的合約：`,
    '',
  ];
  items.forEach(item => {
    lines.push(
      `${item.option_type}｜履約價 ${formatNumber_(item.strike, 4)}｜Bid ${formatNumber_(item.bid, 4)}｜` +
      `Delta ${formatNumber_(item.delta, 4)}｜Vega ${formatNumber_(item.vega, 4)}｜` +
      `年化 ${formatPercent_(item.annual_return)}｜未平倉 ${formatNumber_(item.open_interest, 0)}｜DTE ${item.dte ?? '—'}`
    );
  });
  if (Number(payload.total || 0) > items.length) lines.push('', `其餘 ${Number(payload.total) - items.length} 個請開啟工作表查看。`);
  lines.push('', '年化報酬率＝Bid ÷ 年化本金 ÷ DTE × 365；不含手續費、稅金及指派風險。');
  lines.push('Greeks 為 Black-Scholes-Merton 估算值，不是 Yahoo 原始欄位。');
  lines.push(`開啟試算表：${spreadsheetUrl}`);

  const tableRows = items.map(item => `
    <tr>
      <td>${escapeHtml_(item.option_type || '')}</td>
      <td>${escapeHtml_(formatNumber_(item.strike, 4))}</td>
      <td>${escapeHtml_(formatNumber_(item.bid, 4))}</td>
      <td>${escapeHtml_(formatNumber_(item.delta, 4))}</td>
      <td>${escapeHtml_(formatNumber_(item.vega, 4))}</td>
      <td>${escapeHtml_(formatPercent_(item.annual_return))}</td>
      <td>${escapeHtml_(formatNumber_(item.open_interest, 0))}</td>
      <td>${escapeHtml_(item.dte ?? '—')}</td>
    </tr>`).join('');
  const more = Number(payload.total || 0) > items.length
    ? `<p>其餘 ${Number(payload.total) - items.length} 個請開啟工作表查看。</p>`
    : '';
  const htmlBody = `
    <p><strong>${escapeHtml_(ticker)} ${escapeHtml_(expiry)}</strong> 有 ${escapeHtml_(payload.total || items.length)} 個新符合條件的合約：</p>
    <table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px">
      <thead><tr style="background:#e5e7eb">
        <th style="padding:7px;border:1px solid #cbd5e1">類型</th>
        <th style="padding:7px;border:1px solid #cbd5e1">履約價</th>
        <th style="padding:7px;border:1px solid #cbd5e1">Bid</th>
        <th style="padding:7px;border:1px solid #cbd5e1">Delta</th>
        <th style="padding:7px;border:1px solid #cbd5e1">Vega</th>
        <th style="padding:7px;border:1px solid #cbd5e1">年化報酬率</th>
        <th style="padding:7px;border:1px solid #cbd5e1">未平倉</th>
        <th style="padding:7px;border:1px solid #cbd5e1">DTE</th>
      </tr></thead><tbody>${tableRows}</tbody>
    </table>
    ${more}
    <p style="color:#475569;font-size:12px">年化報酬率＝Bid ÷ 年化本金 ÷ DTE × 365；不含手續費、稅金及指派風險。<br>
    Greeks 為 Black-Scholes-Merton 估算值，不是 Yahoo 原始欄位。</p>
    <p><a href="${escapeHtml_(spreadsheetUrl)}">開啟 Google Sheet</a></p>`;
  return {body: lines.join('\n'), htmlBody: htmlBody};
}

function validateScanInput_(payload) {
  const ticker = String(payload.ticker || '').trim().toUpperCase();
  const expiry = String(payload.expiry || '').trim();
  const displayType = String(payload.displayType || 'ALL').trim().toUpperCase();
  if (!/^[A-Z0-9.^-]{1,15}$/.test(ticker)) throw new Error('股票代號格式不正確');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(expiry) || isNaN(new Date(`${expiry}T12:00:00Z`).getTime())) {
    throw new Error('到期日格式不正確');
  }
  if (!['ALL', 'CALL', 'PUT'].includes(displayType)) throw new Error('顯示類型必須是 ALL、CALL 或 PUT');

  const delta = parseConditionPair_(payload.deltaOperator, payload.deltaThreshold, 'Delta');
  if (delta.threshold !== null && delta.threshold > 1) throw new Error('Delta門檻必須介於 0 與 1');
  const vega = parseConditionPair_(payload.vegaOperator, payload.vegaThreshold, 'Vega');
  const annual = parseConditionPair_(payload.annualReturnOperator, payload.annualReturnThreshold, '年化報酬率');
  if (annual.threshold !== null) annual.threshold /= 100;
  const callCostBasis = parseOptionalPositiveNumber_(payload.callCostBasis, 'CALL持股成本');
  const openInterestMin = parseOptionalNonNegativeNumber_(payload.openInterestMin, '未平倉口數');
  if (openInterestMin !== null && !Number.isInteger(openInterestMin)) throw new Error('未平倉口數必須是整數');

  const scanId = `${ticker}|${expiry}`;
  const sheetName = `${ticker.replace(/[^A-Z0-9._-]/g, '')}_${expiry}`.slice(0, 100);
  return {
    ticker,
    expiry,
    displayType,
    deltaOperator: delta.operator,
    deltaThreshold: delta.threshold,
    vegaOperator: vega.operator,
    vegaThreshold: vega.threshold,
    annualReturnOperator: annual.operator,
    annualReturnThreshold: annual.threshold,
    callCostBasis,
    openInterestMin,
    emailEnabled: payload.emailEnabled !== false,
    note: String(payload.note || '').trim().slice(0, 500),
    scanId,
    sheetName,
  };
}

function parseConditionPair_(operatorValue, thresholdValue, label) {
  const operator = String(operatorValue || '').trim();
  const hasThreshold = !(thresholdValue === '' || thresholdValue === null || thresholdValue === undefined);
  if (!!operator !== hasThreshold) throw new Error(`${label}的比較方式與門檻必須同時填寫或同時留空`);
  if (!operator) return {operator: '', threshold: null};
  if (!['≥', '≤'].includes(operator)) throw new Error(`${label}比較方式必須是 ≥ 或 ≤`);
  return {operator: operator, threshold: parseNonNegativeNumber_(thresholdValue, `${label}門檻`)};
}

function parseNonNegativeNumber_(value, label) {
  const number = Number(value);
  if (!Number.isFinite(number) || number < 0) throw new Error(`${label}必須大於或等於 0`);
  return number;
}

function parseOptionalNonNegativeNumber_(value, label) {
  if (value === '' || value === null || value === undefined) return null;
  return parseNonNegativeNumber_(value, label);
}

function parseOptionalPositiveNumber_(value, label) {
  if (value === '' || value === null || value === undefined) return null;
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) throw new Error(`${label}必須大於 0`);
  return number;
}

function ensureSystemSheets_() {
  const spreadsheet = getSpreadsheet_();
  migrateLegacySheets_();
  const definitions = [
    [APP.SHEETS.DASHBOARD, ['選擇權警示控制台']],
    [APP.SHEETS.SCANS, APP.SCAN_HEADERS],
    [APP.SHEETS.SETTINGS, ['設定項目', '設定值', '說明']],
    [APP.SHEETS.ALERTS, APP.ALERT_HEADERS],
    [APP.SHEETS.SYSTEM, ['時間(UTC)', '等級', '訊息', '詳細資料']],
  ];
  definitions.forEach(([name, headers]) => {
    let sheet = spreadsheet.getSheetByName(name);
    if (!sheet) sheet = spreadsheet.insertSheet(name);
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    sheet.setFrozenRows(1);
  });
  seedSettings_();
  seedDashboard_();
}

function migrateLegacySheets_() {
  const spreadsheet = getSpreadsheet_();
  const legacyMonitor = spreadsheet.getSheetByName(APP.SHEETS.LEGACY_MONITORS);
  if (legacyMonitor) legacyMonitor.setName(nextAvailableSheetName_('監控清單_舊版'));

  const alertSheet = spreadsheet.getSheetByName(APP.SHEETS.ALERTS);
  if (alertSheet && alertSheet.getLastColumn() > 0) {
    const headers = alertSheet.getRange(1, 1, 1, alertSheet.getLastColumn()).getValues()[0];
    if (headers.includes('監控ID') && !headers.includes('掃描ID')) {
      alertSheet.setName(nextAvailableSheetName_('警示紀錄_舊版'));
    }
  }
}

function nextAvailableSheetName_(baseName) {
  const spreadsheet = getSpreadsheet_();
  if (!spreadsheet.getSheetByName(baseName)) return baseName;
  let number = 2;
  while (spreadsheet.getSheetByName(`${baseName}_${number}`)) number += 1;
  return `${baseName}_${number}`;
}

function seedSettings_() {
  const sheet = getSpreadsheet_().getSheetByName(APP.SHEETS.SETTINGS);
  const rows = [
    ['Spreadsheet ID', '', '初始化時自動填入；GitHub Actions 也需設定相同 ID'],
    ['通知信箱', '', '全系統固定收件信箱'],
    ['開盤更新間隔(分鐘)', 5, 'GitHub Actions 最短排程為 5 分鐘'],
    ['盤外更新間隔(分鐘)', 10, '盤前、盤後、休市'],
    ['資料過期門檻(分鐘)', 10, '超過後在表內標示異常'],
    ['無風險利率代號', '^IRX', 'Yahoo 13 週國庫券指標'],
    ['備援無風險利率', 0.05, '^IRX 失敗時採用'],
    ['預設股息殖利率', 0, 'Yahoo 缺失時採用'],
    ['顯示時區', 'Asia/Taipei', '使用者介面與工作表'],
    ['市場時區', 'America/New_York', '到期與市場時段判斷'],
    ['Cloud Run URL', '', '選用部署後填入'],
    ['Web App URL', '', 'Apps Script 部署後填入'],
    ['系統版本', APP.VERSION, '目前規格版本'],
    ['下次允許抓取(UTC)', '', '系統管理：流量限制退避'],
    ['連續失敗次數', 0, '系統管理'],
    ['最後成功抓取(UTC)', '', '系統管理'],
    ['最後執行(UTC)', '', '系統管理'],
    ['最後狀態', '尚未執行', '系統管理'],
  ];
  const existing = sheet.getLastRow() >= 2
    ? sheet.getRange(2, 1, sheet.getLastRow() - 1, 3).getValues()
    : [];
  const existingNames = new Set(existing.map(row => String(row[0] || '')));
  const missing = rows.filter(row => !existingNames.has(row[0]));
  if (missing.length) sheet.getRange(sheet.getLastRow() + 1, 1, missing.length, 3).setValues(missing);
  sheet.getRange(1, 1, 1, 3).setBackground('#E5E7EB').setFontWeight('bold');
  sheet.setColumnWidth(1, 190);
  sheet.setColumnWidth(2, 250);
  sheet.setColumnWidth(3, 330);
}

function seedDashboard_() {
  const sheet = getSpreadsheet_().getSheetByName(APP.SHEETS.DASHBOARD);
  sheet.getRange('A1:H1').merge().setValue('選擇權警示控制台');
  sheet.getRange('A2:H2').merge().setValue('Yahoo Finance + yfinance｜完整期權鍊｜Greeks 為模型估算值');
  sheet.getRange('A4:H4').setValues([['啟用掃描', '數量', '符合合約', '數量', '資料異常', '數量', '最後成功抓取', '時間']]);
  sheet.getRange('B5').setFormula('=COUNTIF(\'掃描設定\'!$A$2:$A$1000,TRUE)');
  sheet.getRange('D5').setFormula('=SUM(\'掃描設定\'!$S$2:$S$1000)');
  sheet.getRange('F5').setFormula('=COUNTIF(\'掃描設定\'!$U$2:$U$1000,"*不足*")+COUNTIF(\'掃描設定\'!$U$2:$U$1000,"*失敗*")+COUNTIF(\'掃描設定\'!$U$2:$U$1000,"*限制*")');
  sheet.getRange('H5').setFormula('=IFERROR(INDEX(\'設定\'!$B$2:$B$40,MATCH("最後成功抓取(UTC)",\'設定\'!$A$2:$A$40,0)),"")');
  sheet.getRange('A7:B10').setValues([
    ['系統狀態', ''],
    ['最後執行', ''],
    ['下次允許抓取', ''],
    ['系統版本', ''],
  ]);
  sheet.getRange('B7').setFormula('=IFERROR(INDEX(\'設定\'!$B$2:$B$40,MATCH("最後狀態",\'設定\'!$A$2:$A$40,0)),"")');
  sheet.getRange('B8').setFormula('=IFERROR(INDEX(\'設定\'!$B$2:$B$40,MATCH("最後執行(UTC)",\'設定\'!$A$2:$A$40,0)),"")');
  sheet.getRange('B9').setFormula('=IFERROR(INDEX(\'設定\'!$B$2:$B$40,MATCH("下次允許抓取(UTC)",\'設定\'!$A$2:$A$40,0)),"")');
  sheet.getRange('B10').setFormula('=IFERROR(INDEX(\'設定\'!$B$2:$B$40,MATCH("系統版本",\'設定\'!$A$2:$A$40,0)),"")');
  sheet.getRange('A7:A10').setBackground('#F8FAFC').setFontWeight('bold');
  sheet.getRange('B7:B10').setFontColor('#008000');
  sheet.getRange('A12:H12').merge().setValue('使用方式');
  sheet.getRange('A13:H18').mergeAcross();
  sheet.getRange('A13:A18').setValues([
    ['1. 從選單「選擇權警示」執行「初始化／升級系統」。'],
    ['2. 在「設定」確認固定通知信箱。'],
    ['3. 用表單輸入股票、到期日及選填條件；程式會列出 Yahoo 回傳的完整期權鍊。'],
    ['4. 第一次掃描只建立基準；之後只有新符合全部條件的合約才寄信。'],
    ['5. 年化報酬率只用有效 Bid；PUT 以履約價、CALL 以持股成本作為本金。'],
    ['6. 本工具只供個人研究與監控，不會執行任何交易。'],
  ]);
  sheet.getRange('A1:H1').setBackground('#F1F5F9').setFontColor('#1D4ED8').setFontWeight('bold').setFontSize(18);
  sheet.getRange('A4:H4').setBackground('#E5E7EB').setFontWeight('bold');
  sheet.getRange('A12:H12').setBackground('#E5E7EB').setFontWeight('bold');
  sheet.getRange('A13:H18').setWrap(true);
}

function ensureChainSheet_(sheetName) {
  const spreadsheet = getSpreadsheet_();
  let sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) sheet = spreadsheet.insertSheet(sheetName);
  sheet.getRange(1, 1, 1, APP.CHAIN_HEADERS.length).setValues([APP.CHAIN_HEADERS]);
  sheet.setFrozenRows(1);
  sheet.setFrozenColumns(4);
  sheet.getRange(1, 1, 1, APP.CHAIN_HEADERS.length)
    .setBackground('#E5E7EB')
    .setFontWeight('bold')
    .setFontColor('#111827')
    .setWrap(true);
  sheet.getRange('C:J').setNumberFormat('0.0000');
  sheet.getRange('L:N').setNumberFormat('0.00%');
  sheet.getRange('P:S').setNumberFormat('0.0000');
  sheet.getRange('T:T').setNumberFormat('0');
  sheet.getRange('U:U').setNumberFormat('0.00%');
  sheet.getRange('V:V').setNumberFormat('0.0000');
  sheet.getRange('W:X').setNumberFormat('#,##0');
  sheet.getRange('AH:AI').setNumberFormat('yyyy-mm-dd hh:mm:ss');
  applyChainConditionalFormatting_(sheet);
}

function applyScanFormatting_() {
  const sheet = getSpreadsheet_().getSheetByName(APP.SHEETS.SCANS);
  if (!sheet) return;
  sheet.setFrozenRows(1);
  sheet.setFrozenColumns(5);
  sheet.getRange(1, 1, 1, APP.SCAN_HEADERS.length)
    .setBackground('#E5E7EB')
    .setFontWeight('bold')
    .setFontColor('#111827')
    .setWrap(true);
  clearPlaceholderCheckboxValues_(sheet);
  const checkboxRule = SpreadsheetApp.newDataValidation()
    .requireCheckbox()
    .setAllowInvalid(false)
    .build();
  sheet.getRange('A2:A1000').setDataValidation(checkboxRule);
  sheet.getRange('N2:N1000').setDataValidation(checkboxRule);
  sheet.getRange('E2:E1000').setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(['ALL', 'CALL', 'PUT'], true).setAllowInvalid(false).build()
  );
  ['F', 'H', 'J'].forEach(column => sheet.getRange(`${column}2:${column}1000`).setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(['≥', '≤'], true).setAllowInvalid(false).build()
  ));
  sheet.getRange('D:D').setNumberFormat('yyyy-mm-dd');
  sheet.getRange('G:G').setNumberFormat('0.0000');
  sheet.getRange('I:I').setNumberFormat('0.0000');
  sheet.getRange('K:K').setNumberFormat('0.00%');
  sheet.getRange('L:L').setNumberFormat('0.0000');
  sheet.getRange('M:M').setNumberFormat('#,##0');
  sheet.getRange('Q:Q').setNumberFormat('0.0000');
  sheet.getRange('R:S').setNumberFormat('#,##0');
  sheet.getRange('T:T').setNumberFormat('yyyy-mm-dd hh:mm:ss');
  sheet.getRange('W:W').setNumberFormat('yyyy-mm-dd hh:mm:ss');
  const range = sheet.getRange('A2:AA1000');
  const rules = [
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=$A2=FALSE').setBackground('#F3F4F6').setRanges([range]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=$S2>0').setBackground('#DCFCE7').setFontColor('#166534').setRanges([range]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=REGEXMATCH($U2,"不足|過期|限制|失敗|無資料")').setBackground('#FEF3C7').setFontColor('#92400E').setRanges([range]).build(),
  ];
  sheet.setConditionalFormatRules(rules);
}

function hasScanData_(row) {
  const meaningfulIndexes = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14];
  return meaningfulIndexes.some(index => row[index] !== '' && row[index] !== null);
}

function clearPlaceholderCheckboxValues_(sheet) {
  const endRow = Math.min(1000, sheet.getMaxRows());
  if (endRow < 2) return;
  const values = sheet.getRange(2, 1, endRow - 1, APP.SCAN_HEADERS.length).getValues();
  const blankRows = [];
  values.forEach((row, index) => {
    if (!hasScanData_(row)) blankRows.push(index + 2);
  });
  if (!blankRows.length) return;

  const ranges = [];
  let start = blankRows[0];
  let previous = start;
  for (let index = 1; index <= blankRows.length; index += 1) {
    const current = blankRows[index];
    if (current === previous + 1) {
      previous = current;
      continue;
    }
    ranges.push(`A${start}:A${previous}`, `N${start}:N${previous}`);
    start = current;
    previous = current;
  }
  sheet.getRangeList(ranges).clearContent();
}

function applyChainConditionalFormatting_(sheet) {
  const range = sheet.getRange('A2:AJ1000');
  const rules = [
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=$AC2="符合"').setBackground('#DCFCE7').setFontColor('#166534').setRanges([range]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=OR($AC2="資料不足",REGEXMATCH($AJ2,"不足|無效"))').setBackground('#FEF3C7').setFontColor('#92400E').setRanges([range]).build(),
  ];
  sheet.setConditionalFormatRules(rules);
}

function getSettings_() {
  const sheet = getSpreadsheet_().getSheetByName(APP.SHEETS.SETTINGS);
  if (!sheet || sheet.getLastRow() < 2) return {};
  return Object.fromEntries(
    sheet.getRange(2, 1, sheet.getLastRow() - 1, 2).getValues().filter(row => row[0] !== '')
  );
}

function installEmailTrigger_() {
  const exists = ScriptApp.getProjectTriggers().some(trigger => trigger.getHandlerFunction() === 'processPendingEmails');
  if (!exists) ScriptApp.newTrigger('processPendingEmails').timeBased().everyMinutes(1).create();
}

function formatSheetDate_(value) {
  if (value instanceof Date) return Utilities.formatDate(value, 'UTC', 'yyyy-MM-dd');
  return String(value || '').slice(0, 10);
}

function formatNumber_(value, digits) {
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return number.toFixed(digits).replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1');
}

function formatPercent_(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `${(number * 100).toFixed(2)}%` : '—';
}

function escapeHtml_(value) {
  return String(value ?? '').replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[character]);
}

function getSpreadsheet_() {
  const active = SpreadsheetApp.getActiveSpreadsheet();
  if (active) {
    PropertiesService.getScriptProperties().setProperty('SPREADSHEET_ID', active.getId());
    return active;
  }
  const spreadsheetId = PropertiesService.getScriptProperties().getProperty('SPREADSHEET_ID');
  if (!spreadsheetId) throw new Error('尚未設定 Spreadsheet ID；請先從 Google Sheet 執行 setupSystem');
  return SpreadsheetApp.openById(spreadsheetId);
}
