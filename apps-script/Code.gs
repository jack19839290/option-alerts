const APP = Object.freeze({
  VERSION: '0.2.1',
  SHEETS: {
    DASHBOARD: '控制台',
    MONITORS: '監控清單',
    SETTINGS: '設定',
    ALERTS: '警示紀錄',
    SYSTEM: '系統紀錄',
  },
  MONITOR_HEADERS: [
    '啟用', '監控ID', '股票代號', '到期日', '類型', '履約價', '低於警示', '高於警示',
    'Email通知', '備註', '狀態', '合約代號', '標的股價', 'Last', 'Bid', 'Ask', 'Mid',
    '警示採用價', '價格來源', 'IV', 'Delta估算', 'Vega估算(每1%)', 'Theta估算(每日)',
    'DTE', '成交量', '未平倉', '最後成交時間', '最後抓取時間', '資料狀態', '警示狀態',
    '待寄信', '最後通知時間', '上次警示狀態', '錯誤訊息', '工作表'
  ],
  CONTRACT_HEADERS: [
    '監控ID', '啟用', '類型', '履約價', '合約代號', '標的股價', 'Last', 'Bid', 'Ask', 'Mid',
    '警示採用價', '價格來源', '低於警示', '高於警示', 'IV', '無風險利率',
    '股息殖利率', 'Greeks模型', 'Delta估算', 'Vega估算(每1%)', 'Theta估算(每日)',
    'DTE', '成交量', '未平倉', '最後成交時間', '最後抓取時間', '資料狀態', '警示狀態'
  ],
});

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('選擇權警示')
    .addItem('新增／更新監控', 'showMonitorDialog')
    .addItem('要求下一輪立即更新', 'requestNextRefresh')
    .addSeparator()
    .addItem('初始化／修復系統', 'setupSystem')
    .addToUi();
}

function doGet() {
  ensureSystemSheets_();
  return HtmlService.createTemplateFromFile('Index')
    .evaluate()
    .setTitle('選擇權警示設定')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.DEFAULT);
}

function showMonitorDialog() {
  ensureSystemSheets_();
  const output = HtmlService.createTemplateFromFile('Index')
    .evaluate()
    .setWidth(520)
    .setHeight(700);
  SpreadsheetApp.getUi().showModalDialog(output, '新增／更新選擇權監控');
}

function getFormDefaults() {
  const settings = getSettings_();
  return {
    notificationEmail: String(settings['通知信箱'] || ''),
    emailEnabled: true,
  };
}

function submitMonitor(payload) {
  const input = validateMonitorInput_(payload || {});
  const lock = LockService.getDocumentLock();
  lock.waitLock(30000);
  try {
    ensureSystemSheets_();
    const sheet = getSpreadsheet_().getSheetByName(APP.SHEETS.MONITORS);
    const values = sheet.getDataRange().getValues();
    const idColumn = APP.MONITOR_HEADERS.indexOf('監控ID');
    let rowNumber = -1;
    for (let row = 1; row < values.length; row += 1) {
      if (String(values[row][idColumn] || '') === input.monitorId) {
        rowNumber = row + 1;
        break;
      }
    }

    const inputValues = [[
      true,
      input.monitorId,
      input.ticker,
      input.expiry,
      input.optionType,
      input.strike,
      input.lowThreshold === null ? '' : input.lowThreshold,
      input.highThreshold === null ? '' : input.highThreshold,
      input.emailEnabled,
      input.note,
    ]];

    if (rowNumber === -1) {
      rowNumber = Math.max(sheet.getLastRow() + 1, 2);
      sheet.getRange(rowNumber, 1, 1, APP.MONITOR_HEADERS.length).clearContent();
    }
    sheet.getRange(rowNumber, 1, 1, inputValues[0].length).setValues(inputValues);
    sheet.getRange(rowNumber, 11).setValue('待抓取');
    sheet.getRange(rowNumber, 29).setValue('等待雲端更新');
    sheet.getRange(rowNumber, 35).setValue(input.sheetName);
    ensureContractSheet_(input.sheetName);
    requestNextRefresh();

    return {
      ok: true,
      monitorId: input.monitorId,
      sheetName: input.sheetName,
      message: rowNumber === values.length + 1 ? '監控已新增' : '監控已儲存',
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
  if (spreadsheetIdRow >= 0) {
    settingsSheet.getRange(spreadsheetIdRow + 2, 2).setValue(spreadsheet.getId());
  }
  const versionRow = settings.findIndex(row => row[0] === '系統版本');
  if (versionRow >= 0) {
    settingsSheet.getRange(versionRow + 2, 2).setValue(APP.VERSION);
  }
  installEmailTrigger_();
  applyMonitorFormatting_();
  spreadsheet.toast('系統初始化完成', '選擇權警示', 5);
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
    ensureSystemSheets_();
    const settings = getSettings_();
    const recipient = String(settings['通知信箱'] || '').trim();
    if (!recipient) return;

    const spreadsheet = getSpreadsheet_();
    const sheet = spreadsheet.getSheetByName(APP.SHEETS.MONITORS);
    const values = sheet.getDataRange().getValues();
    if (values.length < 2) return;
    const headerMap = Object.fromEntries(values[0].map((header, index) => [header, index]));
    const alertLog = spreadsheet.getSheetByName(APP.SHEETS.ALERTS);

    for (let index = 1; index < values.length; index += 1) {
      const row = values[index];
      const pending = String(row[headerMap['待寄信']] || '').trim();
      const enabled = row[headerMap['Email通知']] === true;
      const dataStatus = String(row[headerMap['資料狀態']] || '');
      if (!pending || !enabled || /報價不足|抓取失敗|流量限制|找不到合約/.test(dataStatus)) continue;

      const subject = `[選擇權警示] ${row[headerMap['股票代號']]} ${row[headerMap['類型']]} ${row[headerMap['履約價']]} ${pending}`;
      const body = buildAlertEmail_(row, headerMap, pending, spreadsheet.getUrl());
      MailApp.sendEmail({to: recipient, subject: subject, body: body, name: '選擇權警示'});
      const sentAt = new Date();
      sheet.getRange(index + 1, headerMap['待寄信'] + 1).clearContent();
      sheet.getRange(index + 1, headerMap['最後通知時間'] + 1).setValue(sentAt);
      alertLog.appendRow([
        sentAt,
        row[headerMap['監控ID']],
        row[headerMap['股票代號']],
        row[headerMap['到期日']],
        row[headerMap['類型']],
        row[headerMap['履約價']],
        pending,
        row[headerMap['警示採用價']],
        row[headerMap['價格來源']],
        pending === '高於上限' ? row[headerMap['高於警示']] : row[headerMap['低於警示']],
        recipient,
        '已寄送',
      ]);
    }
  } finally {
    lock.releaseLock();
  }
}

function buildAlertEmail_(row, headerMap, pending, spreadsheetUrl) {
  const field = name => row[headerMap[name]] === '' ? '—' : row[headerMap[name]];
  return [
    `觸發狀態：${pending}`,
    `股票：${field('股票代號')}`,
    `到期日：${field('到期日')}`,
    `類型／履約價：${field('類型')} ${field('履約價')}`,
    `目前權利金：${field('警示採用價')} (${field('價格來源')})`,
    `低於／高於門檻：${field('低於警示')} / ${field('高於警示')}`,
    `Delta／Vega／Theta：${field('Delta估算')} / ${field('Vega估算(每1%)')} / ${field('Theta估算(每日)')}`,
    `DTE：${field('DTE')}`,
    `最後成交時間：${field('最後成交時間')}`,
    `系統抓取時間：${field('最後抓取時間')}`,
    '',
    'Greeks 為 Black-Scholes-Merton 估算值，不是 Yahoo 原始欄位。',
    `開啟試算表：${spreadsheetUrl}`,
  ].join('\n');
}

function validateMonitorInput_(payload) {
  const ticker = String(payload.ticker || '').trim().toUpperCase();
  const expiry = String(payload.expiry || '').trim();
  const optionType = String(payload.optionType || '').trim().toUpperCase();
  const strike = parsePositiveNumber_(payload.strike, '履約價');
  const lowThreshold = parseOptionalPositiveNumber_(payload.lowThreshold, '低於警示價');
  const highThreshold = parseOptionalPositiveNumber_(payload.highThreshold, '高於警示價');
  if (!/^[A-Z0-9.^-]{1,15}$/.test(ticker)) throw new Error('股票代號格式不正確');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(expiry) || isNaN(new Date(`${expiry}T12:00:00Z`).getTime())) {
    throw new Error('到期日格式不正確');
  }
  if (!['CALL', 'PUT'].includes(optionType)) throw new Error('類型必須是 CALL 或 PUT');
  if (lowThreshold === null && highThreshold === null) throw new Error('至少輸入一個權利金警示價');
  if (lowThreshold !== null && highThreshold !== null && lowThreshold >= highThreshold) {
    throw new Error('低於警示價必須小於高於警示價');
  }
  const strikeText = String(Number(strike.toFixed(6)));
  const monitorId = `${ticker}|${expiry}|${optionType}|${strikeText}`;
  const sheetName = `${ticker.replace(/[^A-Z0-9._-]/g, '')}_${expiry}`.slice(0, 100);
  return {
    ticker,
    expiry,
    optionType,
    strike,
    lowThreshold,
    highThreshold,
    emailEnabled: payload.emailEnabled !== false,
    note: String(payload.note || '').trim().slice(0, 500),
    monitorId,
    sheetName,
  };
}

function parsePositiveNumber_(value, label) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) throw new Error(`${label}必須大於 0`);
  return number;
}

function parseOptionalPositiveNumber_(value, label) {
  if (value === '' || value === null || value === undefined) return null;
  return parsePositiveNumber_(value, label);
}

function ensureSystemSheets_() {
  const spreadsheet = getSpreadsheet_();
  const definitions = [
    [APP.SHEETS.DASHBOARD, ['選擇權警示控制台']],
    [APP.SHEETS.MONITORS, APP.MONITOR_HEADERS],
    [APP.SHEETS.SETTINGS, ['設定項目', '設定值', '說明']],
    [APP.SHEETS.ALERTS, ['寄送時間', '監控ID', '股票代號', '到期日', '類型', '履約價', '觸發狀態', '當時價格', '價格來源', '觸發門檻', '收件信箱', '寄送狀態']],
    [APP.SHEETS.SYSTEM, ['時間(UTC)', '等級', '訊息', '詳細資料']],
  ];
  definitions.forEach(([name, headers]) => {
    let sheet = spreadsheet.getSheetByName(name);
    if (!sheet) sheet = spreadsheet.insertSheet(name);
    if (sheet.getLastRow() === 0 || sheet.getRange(1, 1).getValue() === '') {
      sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    }
    sheet.setFrozenRows(1);
  });
  seedSettings_();
  seedDashboard_();
}

function seedSettings_() {
  const sheet = getSpreadsheet_().getSheetByName(APP.SHEETS.SETTINGS);
  if (sheet.getLastRow() > 1) return;
  const rows = [
    ['Spreadsheet ID', '', '初始化時自動填入；GitHub Actions 也需設定相同 ID'],
    ['通知信箱', '', '全系統固定收件信箱'],
    ['開盤更新間隔(分鐘)', 5, 'GitHub Actions 最短排程為 5 分鐘'],
    ['盤外更新間隔(分鐘)', 10, '盤前、盤後、休市'],
    ['資料過期門檻(分鐘)', 10, '超過後在表內標示異常'],
    ['警示回復緩衝', 0.02, '回到門檻內 2% 後才重新啟用'],
    ['無風險利率代號', '^IRX', 'Yahoo 13 週國庫券指標'],
    ['備援無風險利率', 0.05, '^IRX 失敗時採用'],
    ['預設股息殖利率', 0, 'Yahoo 缺失時採用'],
    ['顯示時區', 'Asia/Taipei', '使用者介面與工作表'],
    ['市場時區', 'America/New_York', '到期與市場時段判斷'],
    ['Cloud Run URL', '', '部署後填入'],
    ['Web App URL', '', 'Apps Script 部署後填入'],
    ['系統版本', APP.VERSION, '目前規格版本'],
    ['下次允許抓取(UTC)', '', '系統管理：流量限制退避'],
    ['連續失敗次數', 0, '系統管理'],
    ['最後成功抓取(UTC)', '', '系統管理'],
    ['最後執行(UTC)', '', '系統管理'],
    ['最後狀態', '尚未執行', '系統管理'],
  ];
  sheet.getRange(2, 1, rows.length, 3).setValues(rows);
}

function seedDashboard_() {
  const sheet = getSpreadsheet_().getSheetByName(APP.SHEETS.DASHBOARD);
  if (sheet.getLastRow() > 1) return;
  sheet.getRange('A1:H1').merge().setValue('選擇權警示控制台');
  sheet.getRange('A2:H2').merge().setValue('Yahoo Finance + yfinance｜Mid 優先｜Greeks 為模型估算值');
  sheet.getRange('A4:H4').setValues([['啟用監控', '數量', '目前警示', '數量', '資料異常', '數量', '最後成功抓取', '時間']]);
  sheet.getRange('B5').setFormula('=COUNTIF(\'監控清單\'!$A$2:$A$1000,TRUE)');
  sheet.getRange('D5').setFormula('=COUNTIF(\'監控清單\'!$AD$2:$AD$1000,"高於上限")+COUNTIF(\'監控清單\'!$AD$2:$AD$1000,"低於下限")');
  sheet.getRange('F5').setFormula('=COUNTIF(\'監控清單\'!$AC$2:$AC$1000,"*不足*")+COUNTIF(\'監控清單\'!$AC$2:$AC$1000,"*失敗*")+COUNTIF(\'監控清單\'!$AC$2:$AC$1000,"*限制*")');
  sheet.getRange('H5').setFormula('=\'設定\'!$B$18');
}

function ensureContractSheet_(sheetName) {
  const spreadsheet = getSpreadsheet_();
  let sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) sheet = spreadsheet.insertSheet(sheetName);
  sheet.getRange(1, 1, 1, APP.CONTRACT_HEADERS.length).setValues([APP.CONTRACT_HEADERS]);
  sheet.setFrozenRows(1);
  sheet.setFrozenColumns(4);
  sheet.getRange(1, 1, 1, APP.CONTRACT_HEADERS.length)
    .setBackground('#E5E7EB')
    .setFontWeight('bold')
    .setFontColor('#111827');
  sheet.getRange('D:D').setNumberFormat('0.00');
  sheet.getRange('F:Q').setNumberFormat('0.0000');
  sheet.getRange('S:U').setNumberFormat('0.0000');
  applyContractConditionalFormatting_(sheet);
}

function applyMonitorFormatting_() {
  const sheet = getSpreadsheet_().getSheetByName(APP.SHEETS.MONITORS);
  if (!sheet) return;
  sheet.setFrozenRows(1);
  sheet.setFrozenColumns(10);
  sheet.getRange(1, 1, 1, APP.MONITOR_HEADERS.length)
    .setBackground('#E5E7EB')
    .setFontWeight('bold')
    .setFontColor('#111827');
  // 匯入範本的 A／I／E 已是原生 BOOLEAN／BOOLEAN／DROPDOWN 表格欄。
  // Google Sheets 不允許 Apps Script 重設指定類型欄；普通工作表才補套驗證。
  const isPlainGrid = applyUnlessTypedColumn_(() => sheet.getRange('A2:A1000').insertCheckboxes());
  if (isPlainGrid) {
    sheet.getRange('I2:I1000').insertCheckboxes();
    sheet.getRange('E2:E1000').setDataValidation(
      SpreadsheetApp.newDataValidation().requireValueInList(['CALL', 'PUT'], true).setAllowInvalid(false).build()
    );
    const range = sheet.getRange('A2:AI1000');
    const rules = [
      SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=$A2=FALSE').setBackground('#F3F4F6').setRanges([range]).build(),
      SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=OR($AD2="高於上限",$AD2="低於下限")').setBackground('#FECACA').setFontColor('#991B1B').setRanges([range]).build(),
      SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=OR(REGEXMATCH($AC2,"不足|過期|限制|失敗"),$K2="錯誤")').setBackground('#FEF3C7').setFontColor('#92400E').setRanges([range]).build(),
    ];
    sheet.setConditionalFormatRules(rules);
  }
}

function applyContractConditionalFormatting_(sheet) {
  const range = sheet.getRange('A2:AB1000');
  const rules = [
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=$B2=FALSE').setBackground('#F3F4F6').setRanges([range]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=OR($AB2="高於上限",$AB2="低於下限")').setBackground('#FECACA').setFontColor('#991B1B').setRanges([range]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=REGEXMATCH($AA2,"不足|過期|限制|失敗")').setBackground('#FEF3C7').setFontColor('#92400E').setRanges([range]).build(),
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

function applyUnlessTypedColumn_(operation) {
  try {
    operation();
    return true;
  } catch (error) {
    const message = String(error && error.message ? error.message : error);
    if (!/指定類型欄|typed column/i.test(message)) throw error;
    console.log(`保留 Google Sheets 原生指定類型欄：${message}`);
    return false;
  }
}

function getSpreadsheet_() {
  const active = SpreadsheetApp.getActiveSpreadsheet();
  if (active) {
    PropertiesService.getScriptProperties().setProperty('SPREADSHEET_ID', active.getId());
    return active;
  }
  const spreadsheetId = PropertiesService.getScriptProperties().getProperty('SPREADSHEET_ID');
  if (!spreadsheetId) {
    throw new Error('尚未設定 Spreadsheet ID；請先從 Google Sheet 執行 setupSystem');
  }
  return SpreadsheetApp.openById(spreadsheetId);
}
