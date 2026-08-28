const APP = Object.freeze({
  VERSION: '0.5.0',
  SHEETS: {
    DASHBOARD: '控制台',
    SCANS: '掃描設定',
    SETTINGS: '設定',
    ALERTS: '警示紀錄',
    SYSTEM: '系統紀錄',
  },
  GITHUB: {
    OWNER: 'jack19839290',
    REPOSITORY: 'option-alerts',
    WORKFLOW: 'option-alerts.yml',
    REF: 'main',
  },
  MARKET_TIMEZONE: 'America/New_York',
  PROPERTIES: {
    TOKEN: 'GITHUB_ACTIONS_TOKEN',
    TOKEN_EXPIRES_ON: 'GITHUB_ACTIONS_TOKEN_EXPIRES_ON',
    SETUP_NONCE: 'GITHUB_SETUP_NONCE',
    LAST_AUTO_EVENT: 'GITHUB_LAST_AUTO_MARKET_EVENT',
    LAST_DISPATCH_AT: 'GITHUB_LAST_DISPATCH_AT',
    LAST_DISPATCH_STATUS: 'GITHUB_LAST_DISPATCH_STATUS',
    AUTOMATIC_SUCCESS_COUNT: 'GITHUB_AUTOMATIC_SUCCESS_COUNT',
    FAILURE_ACTIVE: 'GITHUB_FAILURE_ACTIVE',
    LAST_FAILURE_NOTICE_AT: 'GITHUB_LAST_FAILURE_NOTICE_AT',
    LAST_EXPIRY_NOTICE_DATE: 'GITHUB_LAST_EXPIRY_NOTICE_DATE',
  },
  SCAN_HEADERS: [
    '啟用', '掃描ID', '股票代號', '到期日', '顯示類型', 'Delta條件', 'Delta門檻',
    'Bid-Ask價差條件', 'Bid-Ask價差門檻', '年化報酬率條件', '年化報酬率門檻', 'CALL持股成本',
    '未平倉大於(口)', 'Email通知', '備註', '狀態', '標的股價', '合約數', '符合數',
    '最後抓取時間', '資料狀態', '待寄信', '最後通知時間', '錯誤訊息', '工作表',
    '已建立基準', '條件指紋'
  ],
  CHAIN_HEADERS: [
    '掃描ID', '類型', '履約價', '合約代號', '標的股價', 'Last', 'Bid', 'Ask', 'Mid',
    'Bid-Ask價差率', '賣出試算價', '試算價來源', 'IV', '無風險利率', '股息殖利率', 'Greeks模型',
    'Delta估算', 'Gamma估算', 'Theta估算(每日)', 'Vega估算(每1%)', '|Delta|', 'DTE', '年化報酬率',
    '年化本金', '成交量', '未平倉', 'Delta條件結果', 'Bid-Ask價差條件結果',
    '年化報酬率條件結果', '未平倉條件結果', '全部條件符合', '通知狀態',
    '可再次通知', '連續有效不符合', '待寄信', '最後成交時間', '最後抓取時間', '資料狀態'
  ],
  ALERT_HEADERS: [
    '寄送時間', '掃描ID', '股票代號', '到期日', '類型', '履約價', 'Bid', 'Delta估算',
    'Vega估算(每1%)', '年化報酬率', '未平倉', 'DTE', '合約代號', '收件信箱', '寄送狀態',
    'Ask', 'Bid-Ask價差率', 'Gamma估算', 'Theta估算(每日)'
  ],
});

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('選擇權警示')
    .addItem('新增／更新期權鍊掃描', 'showScanDialog')
    .addItem('立即手動更新', 'runManualRefresh')
    .addItem('設定 GitHub 自動更新金鑰', 'showGitHubSetupDialog')
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
      input.spreadOperator,
      input.spreadThreshold === null ? '' : input.spreadThreshold,
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
    prepareNextRefresh_();

    return {
      ok: true,
      scanId: input.scanId,
      sheetName: input.sheetName,
      message: isNew
        ? '掃描已新增；第一次抓取只建立基準、不寄信。可按「立即手動更新」或等待下一個開盤更新時點。'
        : '掃描設定已更新；下一次抓取會重新建立基準。可按「立即手動更新」或等待下一個開盤更新時點。',
    };
  } finally {
    lock.releaseLock();
  }
}

function setupSystem() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  if (!spreadsheet) throw new Error('請從綁定的 Google Sheet 執行初始化');
  PropertiesService.getScriptProperties().setProperty('SPREADSHEET_ID', spreadsheet.getId());
  ensureSystemSheets_();
  const settingsSheet = spreadsheet.getSheetByName(APP.SHEETS.SETTINGS);
  const settings = settingsSheet.getRange(2, 1, settingsSheet.getLastRow() - 1, 2).getValues();
  const spreadsheetIdRow = settings.findIndex(row => row[0] === 'Spreadsheet ID');
  if (spreadsheetIdRow >= 0) settingsSheet.getRange(spreadsheetIdRow + 2, 2).setValue(spreadsheet.getId());
  const versionRow = settings.findIndex(row => row[0] === '系統版本');
  if (versionRow >= 0) settingsSheet.getRange(versionRow + 2, 2).setValue(APP.VERSION);
  installAutomationTriggers_();
  applyScanFormatting_();
  refreshGitHubStatusSettings_();
  spreadsheet.toast('系統已初始化／升級至 0.5.0；Vega 篩選已改為 Bid-Ask Spread', '選擇權警示', 7);
}

function prepareNextRefresh_() {
  const spreadsheet = getSpreadsheet_();
  const settingsSheet = spreadsheet.getSheetByName(APP.SHEETS.SETTINGS);
  if (!settingsSheet) return;
  const values = settingsSheet.getRange(2, 1, settingsSheet.getLastRow() - 1, 2).getValues();
  values.forEach((row, index) => {
    if (row[0] === '最後成功抓取(UTC)' || row[0] === '下次允許抓取(UTC)') {
      settingsSheet.getRange(index + 2, 2).clearContent();
    }
  });
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
        item.ask ?? '',
        item.spread_rate ?? '',
        item.gamma ?? '',
        item.theta ?? '',
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
      `Spread ${formatPercent_(item.spread_rate)}｜Delta ${formatNumber_(item.delta, 4)}｜Gamma ${formatNumber_(item.gamma, 4)}｜` +
      `Theta ${formatNumber_(item.theta, 4)}｜Vega ${formatNumber_(item.vega, 4)}｜` +
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
      <td>${escapeHtml_(formatPercent_(item.spread_rate))}</td>
      <td>${escapeHtml_(formatNumber_(item.delta, 4))}</td>
      <td>${escapeHtml_(formatNumber_(item.gamma, 4))}</td>
      <td>${escapeHtml_(formatNumber_(item.theta, 4))}</td>
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
        <th style="padding:7px;border:1px solid #cbd5e1">Spread</th>
        <th style="padding:7px;border:1px solid #cbd5e1">Delta</th>
        <th style="padding:7px;border:1px solid #cbd5e1">Gamma</th>
        <th style="padding:7px;border:1px solid #cbd5e1">Theta</th>
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
  const spread = parseConditionPair_(payload.spreadOperator, payload.spreadThreshold, 'Bid-Ask價差率');
  if (spread.threshold !== null) spread.threshold /= 100;
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
    spreadOperator: spread.operator,
    spreadThreshold: spread.threshold,
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
  migrateScanSchema050_(spreadsheet);
  migrateSettingsSchema050_(spreadsheet);
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
    if (sheet.getMaxColumns() < headers.length) {
      sheet.insertColumnsAfter(sheet.getMaxColumns(), headers.length - sheet.getMaxColumns());
    }
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    sheet.setFrozenRows(1);
  });
  seedSettings_();
  seedDashboard_();
}

function migrateScanSchema050_(spreadsheet) {
  const sheet = spreadsheet.getSheetByName(APP.SHEETS.SCANS);
  if (!sheet || sheet.getLastColumn() < 1) return;
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0].map(String);
  const vegaOperatorIndex = headers.indexOf('Vega條件');
  const vegaThresholdIndex = headers.indexOf('Vega門檻');
  if (vegaOperatorIndex < 0 && vegaThresholdIndex < 0) return;

  const lastRow = sheet.getLastRow();
  if (lastRow >= 2) {
    const values = sheet.getRange(2, 1, lastRow - 1, headers.length).getValues();
    const scanIdIndex = headers.indexOf('掃描ID');
    const tickerIndex = headers.indexOf('股票代號');
    const baselineIndex = headers.indexOf('已建立基準');
    const fingerprintIndex = headers.indexOf('條件指紋');
    values.forEach(row => {
      const hasScan = String(row[scanIdIndex] || '').trim() || String(row[tickerIndex] || '').trim();
      if (!hasScan) return;
      if (vegaOperatorIndex >= 0) row[vegaOperatorIndex] = '';
      if (vegaThresholdIndex >= 0) row[vegaThresholdIndex] = '';
      if (baselineIndex >= 0) row[baselineIndex] = false;
      if (fingerprintIndex >= 0) row[fingerprintIndex] = '';
    });
    sheet.getRange(2, 1, values.length, headers.length).setValues(values);
  }
}

function migrateSettingsSchema050_(spreadsheet) {
  const sheet = spreadsheet.getSheetByName(APP.SHEETS.SETTINGS);
  if (!sheet || sheet.getLastRow() < 2) return;
  const values = sheet.getRange(2, 1, sheet.getLastRow() - 1, 3).getValues();
  values.forEach((row, index) => {
    if (row[0] === '開盤更新間隔(分鐘)') {
      sheet.getRange(index + 2, 1, 1, 3).setValues([[
        '自動更新規則', '開盤、盤中整點、收盤', 'CBOE 美股股票期權正常交易時段'
      ]]);
    } else if (row[0] === '盤外更新間隔(分鐘)') {
      sheet.getRange(index + 2, 1, 1, 3).setValues([[
        '盤外自動更新', '停用', '盤外只允許使用者手動更新'
      ]]);
    }
  });
}

function seedSettings_() {
  const sheet = getSpreadsheet_().getSheetByName(APP.SHEETS.SETTINGS);
  const rows = [
    ['Spreadsheet ID', '', '初始化時自動填入；GitHub Actions 也需設定相同 ID'],
    ['通知信箱', '', '全系統固定收件信箱'],
    ['自動更新規則', '開盤、盤中整點、收盤', 'CBOE 美股股票期權正常交易時段'],
    ['盤外自動更新', '停用', '盤外只允許使用者手動更新'],
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
    ['GitHub 自動更新', '尚未設定', '金鑰只存於 Apps Script 個人屬性，不會寫入儲存格'],
    ['GitHub 金鑰到期日', '', '只記錄使用者輸入的到期日，用於提前 7 天提醒'],
    ['GitHub 最後要求(UTC)', '', 'Apps Script 最近一次要求 GitHub 執行的時間'],
    ['GitHub 最後要求狀態', '尚未執行', '成功、失敗或尚未設定'],
    ['Apps Script 成功啟動次數', 0, 'Apps Script 自動啟動 GitHub Actions 的累計次數'],
    ['GitHub 原生排程', '已移除（0.5.0）', '只由 Apps Script 在開盤更新時點啟動'],
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
  sheet.getRange('F7:G10').setValues([
    ['立即手動更新', '勾選右側核取方塊'],
    ['GitHub 自動更新', ''],
    ['金鑰到期日', ''],
    ['最後要求狀態', ''],
  ]);
  const manualCell = sheet.getRange('H7');
  manualCell.setDataValidation(SpreadsheetApp.newDataValidation().requireCheckbox().build());
  if (manualCell.getValue() !== true) manualCell.setValue(false);
  sheet.getRange('H8').setFormula('=IFERROR(INDEX(\'設定\'!$B$2:$B$50,MATCH("GitHub 自動更新",\'設定\'!$A$2:$A$50,0)),"")');
  sheet.getRange('H9').setFormula('=IFERROR(INDEX(\'設定\'!$B$2:$B$50,MATCH("GitHub 金鑰到期日",\'設定\'!$A$2:$A$50,0)),"")');
  sheet.getRange('H10').setFormula('=IFERROR(INDEX(\'設定\'!$B$2:$B$50,MATCH("GitHub 最後要求狀態",\'設定\'!$A$2:$A$50,0)),"")');
  sheet.getRange('F7:F10').setBackground('#F8FAFC').setFontWeight('bold');
  sheet.getRange('G7:G10').setFontColor('#475569').setFontSize(9).setWrap(true);
  sheet.getRange('H8:H10').setFontColor('#008000').setWrap(true);
  sheet.getRange('H7').setBackground('#DBEAFE').setHorizontalAlignment('center');
  sheet.getRange('A12:H12').merge().setValue('使用方式');
  sheet.getRange('A13:H18').mergeAcross();
  sheet.getRange('A13:A18').setValues([
    ['1. 從選單「選擇權警示」執行「初始化／升級系統」。'],
    ['2. 在「設定」確認固定通知信箱，再從選單設定 90 天 GitHub 金鑰。'],
    ['3. 用表單輸入股票、到期日及選填條件；程式會列出 Yahoo 回傳的完整期權鍊。'],
    ['4. 開盤、盤中整點與收盤自動更新；盤外可勾選 H7 手動更新。'],
    ['5. 第一次掃描只建立基準；之後只有新符合全部條件的合約才寄信。'],
    ['6. 年化報酬率只用有效 Bid；本工具只供研究監控，不會執行交易。'],
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
  if (sheet.getMaxColumns() < APP.CHAIN_HEADERS.length) {
    sheet.insertColumnsAfter(sheet.getMaxColumns(), APP.CHAIN_HEADERS.length - sheet.getMaxColumns());
  }
  const existingHeaders = sheet.getLastColumn() > 0
    ? sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0].map(String)
    : [];
  const schemaChanged = existingHeaders.join('\u001f') !== APP.CHAIN_HEADERS.join('\u001f');
  if (schemaChanged && sheet.getLastRow() > 1) {
    sheet.getRange(2, 1, sheet.getLastRow() - 1, Math.max(sheet.getLastColumn(), APP.CHAIN_HEADERS.length)).clearContent();
  }
  sheet.getRange(1, 1, 1, APP.CHAIN_HEADERS.length).setValues([APP.CHAIN_HEADERS]);
  sheet.setFrozenRows(1);
  sheet.setFrozenColumns(4);
  sheet.getRange(1, 1, 1, APP.CHAIN_HEADERS.length)
    .setBackground('#E5E7EB')
    .setFontWeight('bold')
    .setFontColor('#111827')
    .setWrap(true);
  sheet.getRange('C:C').setNumberFormat('0.0000');
  sheet.getRange('E:I').setNumberFormat('0.0000');
  sheet.getRange('J:J').setNumberFormat('0.00%');
  sheet.getRange('K:K').setNumberFormat('0.0000');
  sheet.getRange('M:O').setNumberFormat('0.00%');
  sheet.getRange('Q:U').setNumberFormat('0.0000');
  sheet.getRange('V:V').setNumberFormat('0');
  sheet.getRange('W:W').setNumberFormat('0.00%');
  sheet.getRange('X:X').setNumberFormat('0.0000');
  sheet.getRange('Y:Z').setNumberFormat('#,##0');
  sheet.getRange('AJ:AK').setNumberFormat('yyyy-mm-dd hh:mm:ss');
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
  sheet.getRange('I:I').setNumberFormat('0.00%');
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
  const range = sheet.getRange('A2:AL1000');
  const rules = [
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=$AE2="符合"').setBackground('#DCFCE7').setFontColor('#166534').setRanges([range]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=OR($AE2="資料不足",REGEXMATCH($AL2,"不足|無效"))').setBackground('#FEF3C7').setFontColor('#92400E').setRanges([range]).build(),
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

function showGitHubSetupDialog() {
  ensureSystemSheets_();
  const properties = PropertiesService.getUserProperties();
  const nonce = Utilities.getUuid();
  properties.setProperty(APP.PROPERTIES.SETUP_NONCE, JSON.stringify({
    value: nonce,
    createdAt: Date.now(),
  }));
  const template = HtmlService.createTemplateFromFile('GitHubSetup');
  template.setupNonce = nonce;
  template.defaultExpiry = Utilities.formatDate(
    new Date(Date.now() + 90 * 24 * 60 * 60 * 1000),
    'Asia/Taipei',
    'yyyy-MM-dd'
  );
  template.isConfigured = Boolean(properties.getProperty(APP.PROPERTIES.TOKEN));
  template.currentExpiry = properties.getProperty(APP.PROPERTIES.TOKEN_EXPIRES_ON) || '';
  SpreadsheetApp.getUi().showModalDialog(
    template.evaluate().setWidth(620).setHeight(650),
    '設定 GitHub 自動更新金鑰'
  );
}

function saveGitHubAutomationConfig(payload) {
  const input = payload || {};
  validateGitHubSetupNonce_(input.nonce);
  const token = String(input.token || '').trim();
  const expiresOn = String(input.expiresOn || '').trim();
  if (!/^(github_pat_|ghp_)[A-Za-z0-9_]+$/.test(token)) {
    throw new Error('金鑰格式不正確；請貼上 GitHub fine-grained personal access token');
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(expiresOn)) throw new Error('請填寫金鑰到期日');
  const expiry = new Date(`${expiresOn}T23:59:59+08:00`);
  if (isNaN(expiry.getTime()) || expiry.getTime() <= Date.now()) throw new Error('金鑰到期日必須晚於今天');
  if (expiry.getTime() - Date.now() > 91 * 24 * 60 * 60 * 1000) {
    throw new Error('依目前設定，金鑰有效期請勿超過 90 天');
  }

  testGitHubAccess_(token);
  const properties = PropertiesService.getUserProperties();
  properties.setProperties({
    [APP.PROPERTIES.TOKEN]: token,
    [APP.PROPERTIES.TOKEN_EXPIRES_ON]: expiresOn,
    [APP.PROPERTIES.AUTOMATIC_SUCCESS_COUNT]: '0',
  }, false);
  properties.deleteProperty(APP.PROPERTIES.LAST_AUTO_EVENT);
  properties.deleteProperty(APP.PROPERTIES.SETUP_NONCE);
  properties.deleteProperty(APP.PROPERTIES.FAILURE_ACTIVE);
  properties.deleteProperty(APP.PROPERTIES.LAST_FAILURE_NOTICE_AT);
  properties.deleteProperty(APP.PROPERTIES.LAST_EXPIRY_NOTICE_DATE);
  installAutomationTriggers_();
  refreshGitHubStatusSettings_();
  appendSystemLog_('INFO', 'GitHub 自動更新已設定', `金鑰到期日 ${expiresOn}；金鑰內容未寫入工作表`);
  return {
    ok: true,
    message: '設定完成。系統會在美股期權開盤、盤中整點與收盤啟動更新；盤外仍可手動更新。',
  };
}

function validateGitHubSetupNonce_(nonce) {
  const raw = PropertiesService.getUserProperties().getProperty(APP.PROPERTIES.SETUP_NONCE);
  if (!raw) throw new Error('設定視窗已失效，請關閉後重新開啟');
  let saved;
  try {
    saved = JSON.parse(raw);
  } catch (error) {
    throw new Error('設定驗證資料無效，請關閉後重新開啟');
  }
  if (String(nonce || '') !== String(saved.value || '') || Date.now() - Number(saved.createdAt || 0) > 15 * 60 * 1000) {
    throw new Error('設定視窗已逾時，請關閉後重新開啟');
  }
}

function testGitHubAccess_(token) {
  const response = UrlFetchApp.fetch(gitHubWorkflowUrl_(), {
    method: 'get',
    headers: gitHubHeaders_(token),
    muteHttpExceptions: true,
  });
  const code = response.getResponseCode();
  if (code !== 200) throw new Error(describeGitHubError_(code, '無法驗證 GitHub 金鑰'));
}

function runManualRefresh() {
  return runManualRefresh_(true);
}

function runManualRefresh_(showToast) {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(3000)) {
    if (showToast) getSpreadsheet_().toast('另一個更新要求正在處理，請稍候再試', '手動更新', 5);
    return {ok: false, message: '另一個更新要求正在處理'};
  }
  try {
    const result = dispatchGitHubWorkflow_('manual');
    if (showToast) getSpreadsheet_().toast('GitHub 已接受要求；通常數分鐘後寫回資料', '手動更新已送出', 7);
    return result;
  } catch (error) {
    if (showToast) getSpreadsheet_().toast(error.message || String(error), '手動更新失敗', 10);
    return {ok: false, message: error.message || String(error)};
  } finally {
    lock.releaseLock();
  }
}

function handleDashboardAction(event) {
  if (!event || !event.range) return;
  const range = event.range;
  if (range.getSheet().getName() !== APP.SHEETS.DASHBOARD || range.getA1Notation() !== 'H7') return;
  if (range.getValue() !== true) return;
  range.setValue(false);
  runManualRefresh_(true);
}

function processHourlyGitHubDispatch() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(25000)) return;
  try {
    const now = new Date();
    checkGitHubTokenExpiry_(now);
    const properties = PropertiesService.getUserProperties();
    if (!properties.getProperty(APP.PROPERTIES.TOKEN)) {
      setSettingsValues_({
        'GitHub 自動更新': '尚未設定',
        'GitHub 最後要求狀態': '尚未設定金鑰',
      });
      return;
    }
    const eventKey = scheduledMarketEventKey_(now);
    if (!eventKey) return;
    if (properties.getProperty(APP.PROPERTIES.LAST_AUTO_EVENT) === eventKey) return;
    dispatchGitHubWorkflow_('automatic');
    properties.setProperty(APP.PROPERTIES.LAST_AUTO_EVENT, eventKey);
  } catch (error) {
    console.error(`GitHub 開盤時段更新失敗：${error.message || error}`);
  } finally {
    lock.releaseLock();
  }
}

function scheduledMarketEventKey_(now) {
  const weekday = Utilities.formatDate(now, APP.MARKET_TIMEZONE, 'EEE');
  if (weekday === 'Sat' || weekday === 'Sun') return '';
  const dateKey = Utilities.formatDate(now, APP.MARKET_TIMEZONE, 'yyyy-MM-dd');
  const hour = Number(Utilities.formatDate(now, APP.MARKET_TIMEZONE, 'H'));
  const minute = Number(Utilities.formatDate(now, APP.MARKET_TIMEZONE, 'm'));

  if (hour === 9 && minute >= 30) return `${dateKey}:open`;
  if (hour >= 10 && hour <= 15) return `${dateKey}:hour:${String(hour).padStart(2, '0')}`;
  if (hour === 16 && minute < 30) return `${dateKey}:close`;
  return '';
}

function dispatchGitHubWorkflow_(mode) {
  const properties = PropertiesService.getUserProperties();
  const token = properties.getProperty(APP.PROPERTIES.TOKEN);
  if (!token) throw new Error('尚未設定 GitHub 金鑰；請從選單執行「設定 GitHub 自動更新金鑰」');
  const now = new Date();
  let response;
  try {
    response = UrlFetchApp.fetch(`${gitHubWorkflowUrl_()}/dispatches`, {
      method: 'post',
      contentType: 'application/json',
      headers: gitHubHeaders_(token),
      payload: JSON.stringify({
        ref: APP.GITHUB.REF,
        inputs: {force: mode === 'manual' ? 'true' : 'false'},
      }),
      muteHttpExceptions: true,
    });
  } catch (error) {
    const message = `無法連線至 GitHub：${error.message || error}`;
    recordGitHubDispatchFailure_(now, mode, 0, message);
    throw new Error(message);
  }
  const code = response.getResponseCode();
  if (code !== 200 && code !== 204) {
    const message = describeGitHubError_(code, 'GitHub 拒絕更新要求');
    recordGitHubDispatchFailure_(now, mode, code, message);
    throw new Error(message);
  }
  recordGitHubDispatchSuccess_(now, mode);
  return {ok: true, mode: mode, statusCode: code};
}

function gitHubWorkflowUrl_() {
  return `https://api.github.com/repos/${APP.GITHUB.OWNER}/${APP.GITHUB.REPOSITORY}/actions/workflows/${APP.GITHUB.WORKFLOW}`;
}

function gitHubHeaders_(token) {
  return {
    Accept: 'application/vnd.github+json',
    Authorization: `Bearer ${token}`,
    'X-GitHub-Api-Version': '2022-11-28',
  };
}

function describeGitHubError_(code, prefix) {
  const advice = {
    401: '金鑰無效或已到期，請重新建立並儲存',
    403: '金鑰權限不足；請確認此 repository 的 Actions 權限為 Read and write',
    404: '找不到 repository 或 workflow；請確認金鑰可存取 jack19839290/option-alerts',
    422: 'GitHub 無法在 main 分支啟動這個 workflow',
  }[code] || '請稍後重試並查看 GitHub Actions 狀態';
  return `${prefix}（HTTP ${code}）：${advice}`;
}

function recordGitHubDispatchSuccess_(now, mode) {
  const properties = PropertiesService.getUserProperties();
  const wasFailing = properties.getProperty(APP.PROPERTIES.FAILURE_ACTIVE) === 'true';
  const timestamp = now.toISOString();
  properties.setProperty(APP.PROPERTIES.LAST_DISPATCH_AT, timestamp);
  properties.setProperty(APP.PROPERTIES.LAST_DISPATCH_STATUS, '成功');
  properties.deleteProperty(APP.PROPERTIES.FAILURE_ACTIVE);
  properties.deleteProperty(APP.PROPERTIES.LAST_FAILURE_NOTICE_AT);

  let successCount = Number(properties.getProperty(APP.PROPERTIES.AUTOMATIC_SUCCESS_COUNT) || 0);
  if (mode === 'automatic') {
    successCount += 1;
    properties.setProperty(APP.PROPERTIES.AUTOMATIC_SUCCESS_COUNT, String(successCount));
  }
  setSettingsValues_({
    'GitHub 自動更新': '已啟用（開盤／盤中整點／收盤）',
    'GitHub 最後要求(UTC)': timestamp,
    'GitHub 最後要求狀態': mode === 'automatic' ? '自動要求成功' : '手動要求成功',
    'Apps Script 成功啟動次數': successCount,
    'GitHub 原生排程': '已移除（0.5.0）',
  });

  if (wasFailing) {
    appendSystemLog_('INFO', 'GitHub 更新要求已恢復', `${mode}；${timestamp}`);
    sendSystemEmail_('【選擇權警示】自動更新已恢復', `GitHub 更新要求已在 ${timestamp} 恢復成功。`);
  }
}

function recordGitHubDispatchFailure_(now, mode, code, message) {
  const properties = PropertiesService.getUserProperties();
  const timestamp = now.toISOString();
  const wasFailing = properties.getProperty(APP.PROPERTIES.FAILURE_ACTIVE) === 'true';
  const lastNoticeAt = Number(properties.getProperty(APP.PROPERTIES.LAST_FAILURE_NOTICE_AT) || 0);
  const shouldNotify = !wasFailing || now.getTime() - lastNoticeAt >= 24 * 60 * 60 * 1000;
  properties.setProperty(APP.PROPERTIES.FAILURE_ACTIVE, 'true');
  properties.setProperty(APP.PROPERTIES.LAST_DISPATCH_AT, timestamp);
  properties.setProperty(APP.PROPERTIES.LAST_DISPATCH_STATUS, `失敗（HTTP ${code}）`);
  setSettingsValues_({
    'GitHub 自動更新': '異常',
    'GitHub 最後要求(UTC)': timestamp,
    'GitHub 最後要求狀態': message,
  });
  appendSystemLog_('ERROR', 'GitHub 更新要求失敗', `${mode}；${message}`);
  if (shouldNotify && sendSystemEmail_('【選擇權警示】GitHub 自動更新失敗', `${message}\n\n發生時間：${timestamp}`)) {
    properties.setProperty(APP.PROPERTIES.LAST_FAILURE_NOTICE_AT, String(now.getTime()));
  }
}

function checkGitHubTokenExpiry_(now) {
  const properties = PropertiesService.getUserProperties();
  const expiresOn = properties.getProperty(APP.PROPERTIES.TOKEN_EXPIRES_ON);
  if (!expiresOn) return;
  const expiry = new Date(`${expiresOn}T23:59:59+08:00`);
  if (isNaN(expiry.getTime())) return;
  const daysLeft = Math.ceil((expiry.getTime() - now.getTime()) / (24 * 60 * 60 * 1000));
  if (daysLeft < 0 || daysLeft > 7) return;
  if (properties.getProperty(APP.PROPERTIES.LAST_EXPIRY_NOTICE_DATE) === expiresOn) return;
  const sent = sendSystemEmail_(
    `【選擇權警示】GitHub 金鑰將在 ${daysLeft} 天內到期`,
    `GitHub 自動更新金鑰預計於 ${expiresOn} 到期。請在到期前建立新金鑰，並從 Google Sheet 選單重新儲存。`
  );
  if (sent) properties.setProperty(APP.PROPERTIES.LAST_EXPIRY_NOTICE_DATE, expiresOn);
}

function sendSystemEmail_(subject, body) {
  try {
    const recipient = String(getSettings_()['通知信箱'] || '').trim();
    if (!recipient) return false;
    MailApp.sendEmail({to: recipient, subject: subject, body: body, name: '選擇權警示'});
    return true;
  } catch (error) {
    console.error(`系統通知寄送失敗：${error.message || error}`);
    return false;
  }
}

function setSettingsValues_(updates) {
  const sheet = getSpreadsheet_().getSheetByName(APP.SHEETS.SETTINGS);
  if (!sheet) return;
  const rowCount = Math.max(sheet.getLastRow() - 1, 0);
  const names = rowCount ? sheet.getRange(2, 1, rowCount, 1).getValues().map(row => String(row[0] || '')) : [];
  Object.entries(updates).forEach(([name, value]) => {
    const index = names.indexOf(name);
    if (index >= 0) {
      sheet.getRange(index + 2, 2).setValue(value);
    } else {
      sheet.appendRow([name, value, '系統管理']);
      names.push(name);
    }
  });
}

function refreshGitHubStatusSettings_() {
  const properties = PropertiesService.getUserProperties();
  const configured = Boolean(properties.getProperty(APP.PROPERTIES.TOKEN));
  const successCount = Number(properties.getProperty(APP.PROPERTIES.AUTOMATIC_SUCCESS_COUNT) || 0);
  setSettingsValues_({
    'GitHub 自動更新': configured ? '已啟用（開盤／盤中整點／收盤）' : '尚未設定',
    'GitHub 金鑰到期日': properties.getProperty(APP.PROPERTIES.TOKEN_EXPIRES_ON) || '',
    'GitHub 最後要求(UTC)': properties.getProperty(APP.PROPERTIES.LAST_DISPATCH_AT) || '',
    'GitHub 最後要求狀態': properties.getProperty(APP.PROPERTIES.LAST_DISPATCH_STATUS) || '尚未執行',
    'Apps Script 成功啟動次數': successCount,
    'GitHub 原生排程': '已移除（0.5.0）',
  });
}

function appendSystemLog_(level, message, detail) {
  const sheet = getSpreadsheet_().getSheetByName(APP.SHEETS.SYSTEM);
  if (!sheet) return;
  sheet.appendRow([new Date(), level, message, detail || '']);
}

function installAutomationTriggers_() {
  const spreadsheet = getSpreadsheet_();
  const handlers = new Set(ScriptApp.getProjectTriggers().map(trigger => trigger.getHandlerFunction()));
  if (!handlers.has('processPendingEmails')) {
    ScriptApp.newTrigger('processPendingEmails').timeBased().everyMinutes(1).create();
  }
  if (!handlers.has('processHourlyGitHubDispatch')) {
    ScriptApp.newTrigger('processHourlyGitHubDispatch').timeBased().everyMinutes(5).create();
  }
  if (!handlers.has('handleDashboardAction')) {
    ScriptApp.newTrigger('handleDashboardAction').forSpreadsheet(spreadsheet).onEdit().create();
  }
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
