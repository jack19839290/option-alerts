const APP = Object.freeze({
  VERSION: '0.7.1',
  SHEETS: {
    DASHBOARD: '控制台',
    SCANS: '掃描設定',
    SETTINGS: '設定',
    ALERTS: '警示紀錄',
    SYSTEM: '系統紀錄',
    CLOSE_TRENDS: '收盤Delta趨勢',
    QUEUE: '通知佇列',
    CLOSE_STATE: '收盤門檻紀錄',
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
    '啟用', '掃描ID', '股票代號', '到期日', '顯示類型',
    '第一門檻啟用', '第一Delta條件', '第一Delta門檻', '第一Bid-Ask價差條件',
    '第一Bid-Ask價差門檻', '第一年化報酬率條件', '第一年化報酬率門檻', '第一未平倉大於(口)',
    '第二門檻啟用', '第二Delta條件', '第二Delta門檻', '第二Bid-Ask價差條件',
    '第二Bid-Ask價差門檻', '第二年化報酬率條件', '第二年化報酬率門檻', '第二未平倉大於(口)',
    'CALL持股成本', 'Email通知', '備註', '狀態', '標的股價', '合約數', '第一符合數',
    '第二符合數', '最後嘗試時間', '最後成功抓取時間', '資料狀態', '錯誤訊息', '工作表',
    '第一條件指紋', '第二條件指紋', '收盤狀態', '收盤最後成功交易日'
  ],
  CHAIN_HEADERS: [
    '符合門檻', '第一門檻結果', '第二門檻結果', '類型', '履約價', '標的股價', 'Bid',
    '年化報酬率', '第一年化報酬率結果', '第二年化報酬率結果', 'Delta估算', '第一Delta結果',
    '第二Delta結果', 'Bid-Ask價差率', '第一Bid-Ask價差結果', '第二Bid-Ask價差結果',
    '未平倉', '第一未平倉結果', '第二未平倉結果', 'DTE', '最後抓取時間', 'Ask', 'Mid',
    'Last', '成交量', '標的－履約價差', '最後成交時間', 'Gamma估算', 'Theta估算(每日)',
    'Vega估算(每1%)', 'IV', '年化本金', '賣出試算價', '試算價來源', '無風險利率',
    '股息殖利率', 'Greeks模型', '|Delta|', '合約代號', '掃描ID', '第二通知狀態',
    '第二可再次通知', '第二連續有效不符合', '第二通知序號', '資料狀態'
  ],
  ALERT_HEADERS: [
    '寄送時間', '掃描ID', '股票代號', '到期日', '類型', '履約價', 'Bid', 'Delta估算',
    '標的股價', '年化報酬率', '未平倉', 'DTE', '合約代號', '收件信箱', '寄送狀態',
    'Ask', 'Bid-Ask價差率', '事件ID', '事件類型', '門檻', '今日新增', '事件完整性',
    '失敗掃描', '紀錄ID'
  ],
  CLOSE_TREND_HEADERS: [
    '快照ID', '美東交易日', '官方收盤時間(UTC)', '實際抓取時間(UTC)', '掃描ID', '股票代號',
    '到期日', '類型', '目標|Delta|', '選取狀態', '合約代號', '履約價', 'Delta估算', '|Delta|',
    'Delta差距', '標的快照價', 'Last', 'Bid', 'Ask', 'Mid', 'Bid-Ask價差率', '賣出試算價',
    '試算價來源', '年化本金', 'DTE', '到期權利金報酬率', '年化報酬率', 'IV', 'Gamma估算',
    'Theta估算(每日)', 'Vega估算(每1%)', '成交量', '未平倉', '最後成交時間', '無風險利率',
    '無風險利率來源', '股息殖利率', 'Greeks模型', '資料狀態', '備註／未選取原因',
    '標的－履約價差', '標的－履約價差率'
  ],
  QUEUE_HEADERS: ['事件ID', '事件類型', '狀態', '建立時間(UTC)', '寄送時間', '重試次數',
    '下次重試時間', '掃描ID', '股票代號', '到期日', '美東交易日', '是否完整', '失敗掃描',
    '內容JSON', '最後錯誤'],
  CLOSE_STATE_HEADERS: ['記錄ID', '美東交易日', '掃描ID', '第一條件指紋', '狀態', '符合合約JSON',
    '最後嘗試時間(UTC)', '成功時間(UTC)', '錯誤訊息', '嘗試次數'],
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
      true, input.scanId, input.ticker, input.expiry, input.displayType,
      input.first.enabled, input.first.deltaOperator, input.first.deltaThreshold ?? '',
      input.first.spreadOperator, input.first.spreadThreshold ?? '',
      input.first.annualReturnOperator, input.first.annualReturnThreshold ?? '', input.first.openInterestMin ?? '',
      input.second.enabled, input.second.deltaOperator, input.second.deltaThreshold ?? '',
      input.second.spreadOperator, input.second.spreadThreshold ?? '',
      input.second.annualReturnOperator, input.second.annualReturnThreshold ?? '', input.second.openInterestMin ?? '',
      input.callCostBasis ?? '', input.emailEnabled, input.note,
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
    const output = Object.fromEntries(APP.SCAN_HEADERS.map((header, index) => [header, index + 1]));
    sheet.getRange(rowNumber, output['狀態']).setValue('待抓取');
    sheet.getRange(rowNumber, output['資料狀態']).setValue('等待雲端更新');
    sheet.getRange(rowNumber, output['工作表']).setValue(input.sheetName);
    applyScanFormatting_();
    ensureChainSheet_(input.sheetName);
    prepareNextRefresh_();

    return {
      ok: true,
      scanId: input.scanId,
      sheetName: input.sheetName,
      message: isNew
        ? '掃描已新增；第二門檻首次符合會即時通知，第一門檻於正式收盤彙總。'
        : '掃描設定已更新；條件變更會在下一次更新套用。',
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
  const displayTimezoneRow = settings.findIndex(row => row[0] === '顯示時區');
  const displayTimezone = displayTimezoneRow >= 0
    ? String(settings[displayTimezoneRow][1] || 'Asia/Taipei').trim()
    : 'Asia/Taipei';
  try {
    spreadsheet.setSpreadsheetTimeZone(displayTimezone);
  } catch (error) {
    throw new Error(`顯示時區「${displayTimezone}」無效，請在設定分頁填入 Asia/Taipei 等有效時區`);
  }
  const spreadsheetIdRow = settings.findIndex(row => row[0] === 'Spreadsheet ID');
  if (spreadsheetIdRow >= 0) settingsSheet.getRange(spreadsheetIdRow + 2, 2).setValue(spreadsheet.getId());
  const versionRow = settings.findIndex(row => row[0] === '系統版本');
  if (versionRow >= 0) settingsSheet.getRange(versionRow + 2, 2).setValue(APP.VERSION);
  installAutomationTriggers_();
  normalizeUserFacingTimestamps_();
  try {
    reconcileSentAlertLogs_();
  } catch (error) {
    appendSystemLog_('WARNING', '警示紀錄補登失敗', String(error.message || error).slice(0, 1000));
  }
  applyScanFormatting_();
  applyAlertLogFormatting_();
  applyAllChainFormatting_();
  applyCloseTrendFormatting_();
  refreshGitHubStatusSettings_();
  spreadsheet.toast(`系統已初始化／升級至 ${APP.VERSION}；工作表時間使用 ${displayTimezone}`, '選擇權警示', 7);
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
    const queue = spreadsheet.getSheetByName(APP.SHEETS.QUEUE);
    if (!queue || queue.getLastRow() < 2) return;
    const values = queue.getDataRange().getValues();
    const map = Object.fromEntries(values[0].map((header, index) => [header, index]));
    const now = new Date();
    for (let index = 1; index < values.length; index += 1) {
      const row = values[index];
      const currentStatus = String(row[map['狀態']] || '');
      if (currentStatus === 'SENDING') {
        const claimedAt = row[map['寄送時間']];
        if (claimedAt instanceof Date && now.getTime() - claimedAt.getTime() < 15 * 60 * 1000) continue;
      } else if (!['PENDING', 'FAILED'].includes(currentStatus)) continue;
      const nextRetry = row[map['下次重試時間']];
      if (nextRetry instanceof Date && nextRetry > now) continue;
      const rowNumber = index + 1;
      queue.getRange(rowNumber, map['狀態'] + 1).setValue('SENDING');
      queue.getRange(rowNumber, map['寄送時間'] + 1).setValue(now);
      SpreadsheetApp.flush();
      try {
        const payload = JSON.parse(String(row[map['內容JSON']] || '{}'));
        const eventType = String(row[map['事件類型']] || '');
        const message = buildQueueEmail_(eventType, payload, spreadsheet.getUrl());
        MailApp.sendEmail({to: recipient, subject: message.subject, body: message.body,
          htmlBody: message.htmlBody, name: '選擇權警示'});
        const sentAt = new Date();
        queue.getRange(rowNumber, map['狀態'] + 1).setValue('SENT');
        queue.getRange(rowNumber, map['寄送時間'] + 1).setValue(sentAt);
        queue.getRange(rowNumber, map['最後錯誤'] + 1).clearContent();
      } catch (error) {
        const retries = Number(row[map['重試次數']] || 0) + 1;
        const delayMinutes = Math.min(5 * Math.pow(2, retries - 1), 60);
        queue.getRange(rowNumber, map['狀態'] + 1).setValue('FAILED');
        queue.getRange(rowNumber, map['重試次數'] + 1).setValue(retries);
        queue.getRange(rowNumber, map['下次重試時間'] + 1).setValue(new Date(Date.now() + delayMinutes * 60000));
        queue.getRange(rowNumber, map['最後錯誤'] + 1).setValue(String(error.message || error).slice(0, 1000));
      }
    }
    try {
      reconcileSentAlertLogs_();
    } catch (error) {
      appendSystemLog_('WARNING', '警示紀錄補登失敗', String(error.message || error).slice(0, 1000));
    }
  } finally {
    lock.releaseLock();
  }
}

function buildQueueEmail_(eventType, payload, spreadsheetUrl) {
  const close = eventType.indexOf('FIRST_CLOSE') === 0;
  const supplement = eventType === 'FIRST_CLOSE_SUPPLEMENT';
  const groups = Array.isArray(payload.groups) ? payload.groups : [];
  const total = groups.reduce((sum, group) => sum + (group.items || []).length, 0);
  const subject = close
    ? `【選擇權收盤通知】${payload.market_date || ''}${supplement ? '（補充）' : ''}：${total} 個符合第一門檻`
    : `【選擇權即時通知】${groups[0]?.ticker || ''} ${groups[0]?.expiry || ''}：${total} 個符合第二門檻`;
  const lines = [subject.replace('【選擇權收盤通知】', '').replace('【選擇權即時通知】', ''), ''];
  const htmlSections = [];
  groups.forEach(group => {
    const items = group.items || [];
    const baseline = group.baseline_changed ? '（條件已變更，本日重建比較基準）' : '';
    lines.push(`${group.ticker} ${group.expiry}：${items.length} 筆${baseline}`);
    items.forEach(item => lines.push(`${item.is_new ? '【今日新增】' : ''}${item.option_type}｜履約價 ${formatNumber_(item.strike, 4)}｜標的 ${formatNumber_(item.underlying_price, 4)}｜Bid ${formatNumber_(item.bid, 4)}｜Delta ${formatNumber_(item.delta, 4)}｜Spread ${formatPercent_(item.spread_rate)}｜年化 ${formatPercent_(item.annual_return)}｜未平倉 ${formatNumber_(item.open_interest, 0)}｜DTE ${item.dte ?? '—'}`));
    const rows = items.map(item => `<tr>${[item.is_new ? '今日新增' : '', item.option_type || '', formatNumber_(item.strike, 4), formatNumber_(item.underlying_price, 4), formatNumber_(item.bid, 4), formatNumber_(item.delta, 4), formatPercent_(item.spread_rate), formatPercent_(item.annual_return), formatNumber_(item.open_interest, 0), item.dte ?? '—'].map(value => `<td style="padding:6px;border:1px solid #cbd5e1">${escapeHtml_(value)}</td>`).join('')}</tr>`).join('');
    htmlSections.push(`<h3>${escapeHtml_(group.ticker)} ${escapeHtml_(group.expiry)}：${items.length} 筆 ${escapeHtml_(baseline)}</h3><table style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:13px"><thead><tr style="background:#e5e7eb">${['狀態','類型','履約價','標的股價','Bid','Delta','Spread','年化報酬率','未平倉','DTE'].map(x => `<th style="padding:6px;border:1px solid #cbd5e1">${x}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table>`);
  });
  const failed = Array.isArray(payload.failed_scans) ? payload.failed_scans : [];
  if (failed.length) lines.push('', `本次收盤資料不完整，尚待補抓：${failed.join('、')}`);
  lines.push('', '年化報酬率＝Bid ÷ 年化本金 ÷ DTE × 365；不含手續費、稅金及指派風險。', `開啟試算表：${spreadsheetUrl}`);
  const warning = failed.length ? `<p style="color:#991b1b"><strong>本次資料不完整，尚待補抓：</strong>${escapeHtml_(failed.join('、'))}</p>` : '';
  return {subject, body: lines.join('\n'), htmlBody: `${htmlSections.join('')}${warning}<p style="color:#475569;font-size:12px">年化報酬率＝Bid ÷ 年化本金 ÷ DTE × 365；不含手續費、稅金及指派風險。</p><p><a href="${escapeHtml_(spreadsheetUrl)}">開啟 Google Sheet</a></p>`};
}

function alertThresholdLabel_(eventType) {
  if (String(eventType || '').indexOf('FIRST_CLOSE') === 0) return '第一門檻';
  if (String(eventType || '') === 'SECOND_REALTIME') return '第二門檻';
  return '舊版／其他';
}

function alertRecordId_(eventId, scanId, contractSymbol, summarySuffix) {
  return [eventId || 'NO_EVENT', scanId || 'NO_SCAN', contractSymbol || summarySuffix || 'NO_MATCH'].join('|');
}

function buildAlertLogRowsForEvent_(eventId, eventType, payload, recipient, sentAt) {
  const groups = Array.isArray(payload.groups) ? payload.groups : [];
  const threshold = alertThresholdLabel_(eventType);
  const completeness = payload.complete === false ? '資料不完整' : '完整';
  const failedScans = Array.isArray(payload.failed_scans) ? payload.failed_scans.join('、') : '';
  const rows = [];
  groups.forEach(group => {
    const items = Array.isArray(group.items) ? group.items : [];
    if (!items.length) {
      rows.push([
        sentAt, group.scan_id || '', group.ticker || '', group.expiry || '', '', '', '', '', '', '', '', '', '',
        recipient, '已寄送（0筆符合）', '', '', eventId || '', eventType || '', threshold, '', completeness,
        failedScans, alertRecordId_(eventId, group.scan_id, '', 'NO_MATCH')
      ]);
      return;
    }
    items.forEach(item => rows.push([
      sentAt, group.scan_id || '', group.ticker || '', group.expiry || '', item.option_type || '',
      item.strike ?? '', item.bid ?? '', item.delta ?? '', item.underlying_price ?? '', item.annual_return ?? '',
      item.open_interest ?? '', item.dte ?? '', item.contract_symbol || '', recipient, '已寄送', item.ask ?? '',
      item.spread_rate ?? '', eventId || '', eventType || '', threshold,
      threshold === '第一門檻' ? (item.is_new ? '是' : '否') : '', completeness, failedScans,
      alertRecordId_(eventId, group.scan_id, item.contract_symbol, 'NO_MATCH')
    ]));
  });
  if (!rows.length) {
    rows.push([
      sentAt, '', '', '', '', '', '', '', '', '', '', '', '', recipient, '已寄送（0筆符合）', '', '',
      eventId || '', eventType || '', threshold, '', completeness, failedScans,
      alertRecordId_(eventId, '', '', 'EVENT_SUMMARY')
    ]);
  }
  return rows;
}

function upsertAlertLogRows_(rows) {
  if (!rows.length) return 0;
  const log = getSpreadsheet_().getSheetByName(APP.SHEETS.ALERTS);
  if (!log) return 0;
  const idIndex = APP.ALERT_HEADERS.indexOf('紀錄ID');
  const existing = new Map();
  if (log.getLastRow() >= 2) {
    log.getRange(2, 1, log.getLastRow() - 1, APP.ALERT_HEADERS.length).getValues()
      .forEach((row, index) => {
        const recordId = String(row[idIndex] || '').trim();
        if (recordId) existing.set(recordId, {rowNumber: index + 2, values: row});
      });
  }
  const thresholdIndex = APP.ALERT_HEADERS.indexOf('門檻');
  const completenessIndex = APP.ALERT_HEADERS.indexOf('事件完整性');
  const todayNewIndex = APP.ALERT_HEADERS.indexOf('今日新增');
  const appendRows = [];
  let changed = 0;
  rows.forEach(row => {
    const recordId = String(row[idIndex] || '').trim();
    const prior = existing.get(recordId);
    if (!prior) {
      appendRows.push(row);
      existing.set(recordId, {rowNumber: 0, values: row});
      changed += 1;
      return;
    }
    const needsRepair = !prior.values[thresholdIndex] || !prior.values[completenessIndex]
      || (row[todayNewIndex] && prior.values[todayNewIndex] !== row[todayNewIndex]);
    if (needsRepair && prior.rowNumber) {
      log.getRange(prior.rowNumber, 1, 1, APP.ALERT_HEADERS.length).setValues([row]);
      changed += 1;
    }
  });
  if (appendRows.length) {
    log.getRange(log.getLastRow() + 1, 1, appendRows.length, APP.ALERT_HEADERS.length).setValues(appendRows);
  }
  return changed;
}

function reconcileSentAlertLogs_() {
  const spreadsheet = getSpreadsheet_();
  const queue = spreadsheet.getSheetByName(APP.SHEETS.QUEUE);
  const settings = getSettings_();
  const fallbackRecipient = String(settings['通知信箱'] || '').trim();
  if (!queue || queue.getLastRow() < 2) return 0;
  const values = queue.getDataRange().getValues();
  const map = Object.fromEntries(values[0].map((header, index) => [header, index]));
  const desiredRows = [];
  values.slice(1).forEach(row => {
    if (String(row[map['狀態']] || '') !== 'SENT') return;
    try {
      const payload = JSON.parse(String(row[map['內容JSON']] || '{}'));
      const recipient = String(payload.sent_to || fallbackRecipient);
      desiredRows.push(...buildAlertLogRowsForEvent_(
        row[map['事件ID']], row[map['事件類型']], payload, recipient, row[map['寄送時間']] || ''
      ));
    } catch (error) {
      appendSystemLog_('WARNING', '略過無法補登的警示事件', `${row[map['事件ID']] || ''}；${error.message || error}`);
    }
  });
  return upsertAlertLogRows_(desiredRows);
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

  const parseThreshold = (prefix, label) => {
    const delta = parseConditionPair_(payload[`${prefix}DeltaOperator`], payload[`${prefix}DeltaThreshold`], `${label} Delta`);
    if (delta.threshold !== null && delta.threshold > 1) throw new Error(`${label} Delta門檻必須介於 0 與 1`);
    const spread = parseConditionPair_(payload[`${prefix}SpreadOperator`], payload[`${prefix}SpreadThreshold`], `${label} Bid-Ask價差率`);
    if (spread.threshold !== null) spread.threshold /= 100;
    const annual = parseConditionPair_(payload[`${prefix}AnnualReturnOperator`], payload[`${prefix}AnnualReturnThreshold`], `${label}年化報酬率`);
    if (annual.threshold !== null) annual.threshold /= 100;
    const openInterestMin = parseOptionalNonNegativeNumber_(payload[`${prefix}OpenInterestMin`], `${label}未平倉口數`);
    if (openInterestMin !== null && !Number.isInteger(openInterestMin)) throw new Error(`${label}未平倉口數必須是整數`);
    const enabled = payload[`${prefix}Enabled`] === true;
    if (enabled && [delta.threshold, spread.threshold, annual.threshold, openInterestMin].every(value => value === null)) {
      throw new Error(`${label}已啟用，至少要設定一個條件`);
    }
    return {enabled, deltaOperator: delta.operator, deltaThreshold: delta.threshold,
      spreadOperator: spread.operator, spreadThreshold: spread.threshold,
      annualReturnOperator: annual.operator, annualReturnThreshold: annual.threshold, openInterestMin};
  };
  const first = parseThreshold('first', '第一門檻');
  const second = parseThreshold('second', '第二門檻');
  const callCostBasis = parseOptionalPositiveNumber_(payload.callCostBasis, 'CALL持股成本');

  const scanId = `${ticker}|${expiry}`;
  const sheetName = `${ticker.replace(/[^A-Z0-9._-]/g, '')}_${expiry}`.slice(0, 100);
  return {
    ticker,
    expiry,
    displayType,
    first,
    second,
    callCostBasis,
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
  migrateScanSchema070_(spreadsheet);
  migrateCloseTrendSchema070_(spreadsheet);
  migrateAlertLogSchema070_(spreadsheet);
  migrateSettingsSchema050_(spreadsheet);
  const definitions = [
    [APP.SHEETS.DASHBOARD, ['選擇權警示控制台']],
    [APP.SHEETS.SCANS, APP.SCAN_HEADERS],
    [APP.SHEETS.SETTINGS, ['設定項目', '設定值', '說明']],
    [APP.SHEETS.ALERTS, APP.ALERT_HEADERS],
    [APP.SHEETS.SYSTEM, ['時間(UTC)', '等級', '訊息', '詳細資料']],
    [APP.SHEETS.CLOSE_TRENDS, APP.CLOSE_TREND_HEADERS],
    [APP.SHEETS.QUEUE, APP.QUEUE_HEADERS],
    [APP.SHEETS.CLOSE_STATE, APP.CLOSE_STATE_HEADERS],
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
  const queue = spreadsheet.getSheetByName(APP.SHEETS.QUEUE);
  const closeState = spreadsheet.getSheetByName(APP.SHEETS.CLOSE_STATE);
  if (queue) queue.hideSheet();
  if (closeState) closeState.hideSheet();
}

function migrateScanSchema070_(spreadsheet) {
  const sheet = spreadsheet.getSheetByName(APP.SHEETS.SCANS);
  if (!sheet || sheet.getLastColumn() < 1) return;
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0].map(String);
  if (headers.slice(0, APP.SCAN_HEADERS.length).join('\u001f') === APP.SCAN_HEADERS.join('\u001f')) return;
  if (!headers.includes('股票代號') || !headers.includes('到期日')) return;
  const source = sheet.getLastRow() >= 2 ? sheet.getRange(2, 1, sheet.getLastRow() - 1, headers.length).getValues() : [];
  const oldIndex = Object.fromEntries(headers.map((header, index) => [header, index]));
  const oldValue = (row, name) => oldIndex[name] === undefined ? '' : row[oldIndex[name]];
  const migrated = source.map(row => {
    const output = Array(APP.SCAN_HEADERS.length).fill('');
    const set = (name, value) => { output[APP.SCAN_HEADERS.indexOf(name)] = value; };
    ['啟用','掃描ID','股票代號','到期日','顯示類型','CALL持股成本','Email通知','備註',
     '狀態','標的股價','合約數','資料狀態','錯誤訊息','工作表'].forEach(name => set(name, oldValue(row, name)));
    const mappings = {
      '第一Delta條件':'Delta條件', '第一Delta門檻':'Delta門檻',
      '第一Bid-Ask價差條件':'Bid-Ask價差條件', '第一Bid-Ask價差門檻':'Bid-Ask價差門檻',
      '第一年化報酬率條件':'年化報酬率條件', '第一年化報酬率門檻':'年化報酬率門檻',
      '第一未平倉大於(口)':'未平倉大於(口)', '第一符合數':'符合數',
      '最後嘗試時間':'最後抓取時間', '最後成功抓取時間':'最後抓取時間'
    };
    Object.entries(mappings).forEach(([target, sourceName]) => set(target, oldValue(row, sourceName)));
    const hasFirst = ['Delta門檻','Bid-Ask價差門檻','年化報酬率門檻','未平倉大於(口)']
      .some(name => oldValue(row, name) !== '' && oldValue(row, name) !== null);
    set('第一門檻啟用', hasFirst);
    set('第二門檻啟用', false);
    return output;
  });
  if (sheet.getMaxColumns() < APP.SCAN_HEADERS.length) sheet.insertColumnsAfter(sheet.getMaxColumns(), APP.SCAN_HEADERS.length - sheet.getMaxColumns());
  if (sheet.getLastRow() > 1) {
    const rewriteRange = sheet.getRange(2, 1, sheet.getLastRow() - 1, Math.max(headers.length, APP.SCAN_HEADERS.length));
    rewriteRange.clearDataValidations();
  }
  if (migrated.length) sheet.getRange(2, 1, migrated.length, APP.SCAN_HEADERS.length).setValues(migrated);
  sheet.getRange(1, 1, 1, APP.SCAN_HEADERS.length).setValues([APP.SCAN_HEADERS]);
  if (headers.length > APP.SCAN_HEADERS.length) {
    sheet.getRange(1, APP.SCAN_HEADERS.length + 1, Math.max(sheet.getLastRow(), 1),
      headers.length - APP.SCAN_HEADERS.length).clearContent();
  }
}

function migrateCloseTrendSchema070_(spreadsheet) {
  const sheet = spreadsheet.getSheetByName(APP.SHEETS.CLOSE_TRENDS);
  if (!sheet || sheet.getLastColumn() < 40 || sheet.getLastRow() < 2) return;
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0].map(String);
  if (headers.includes('標的－履約價差率')) return;
  const values = sheet.getRange(2, 12, sheet.getLastRow() - 1, 5).getValues();
  const backfill = values.map(row => {
    const strike = Number(row[0]);
    const spot = Number(row[4]);
    if (!Number.isFinite(strike) || !Number.isFinite(spot) || spot === 0) return ['', ''];
    const difference = spot - strike;
    return [difference, difference / spot];
  });
  if (sheet.getMaxColumns() < 42) sheet.insertColumnsAfter(sheet.getMaxColumns(), 42 - sheet.getMaxColumns());
  sheet.getRange(2, 41, backfill.length, 2).setValues(backfill);
}

function migrateAlertLogSchema070_(spreadsheet) {
  const sheet = spreadsheet.getSheetByName(APP.SHEETS.ALERTS);
  if (!sheet || sheet.getLastColumn() < 1) return;
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0].map(String);
  if (headers.slice(0, APP.ALERT_HEADERS.length).join('\u001f') === APP.ALERT_HEADERS.join('\u001f')) return;
  if (!headers.includes('寄送時間') || !headers.includes('合約代號')) return;
  const values = sheet.getLastRow() >= 2 ? sheet.getRange(2, 1, sheet.getLastRow() - 1, headers.length).getValues() : [];
  const index = Object.fromEntries(headers.map((header, position) => [header, position]));
  const migrated = values.map((row, rowIndex) => {
    const oldValue = header => index[header] === undefined ? '' : row[index[header]];
    const eventId = oldValue('事件ID');
    const eventType = oldValue('事件類型') || 'LEGACY';
    const scanId = oldValue('掃描ID');
    const contractSymbol = oldValue('合約代號');
    return APP.ALERT_HEADERS.map(header => {
      if (header === '事件類型') return eventType;
      if (header === '事件ID' || header === '標的股價') return oldValue(header);
      if (header === '門檻') return alertThresholdLabel_(eventType);
      if (header === '紀錄ID') return eventId
        ? alertRecordId_(eventId, scanId, contractSymbol, 'NO_MATCH')
        : `LEGACY|${rowIndex + 2}`;
      if (['今日新增', '事件完整性', '失敗掃描'].includes(header)) return '';
      return oldValue(header);
    });
  });
  if (sheet.getMaxColumns() < APP.ALERT_HEADERS.length) {
    sheet.insertColumnsAfter(sheet.getMaxColumns(), APP.ALERT_HEADERS.length - sheet.getMaxColumns());
  }
  if (migrated.length) sheet.getRange(2, 1, migrated.length, APP.ALERT_HEADERS.length).setValues(migrated);
  sheet.getRange(1, 1, 1, APP.ALERT_HEADERS.length).setValues([APP.ALERT_HEADERS]);
  if (headers.length > APP.ALERT_HEADERS.length) {
    sheet.getRange(1, APP.ALERT_HEADERS.length + 1, Math.max(sheet.getLastRow(), 1),
      headers.length - APP.ALERT_HEADERS.length).clearContent();
  }
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
    ['顯示時區', 'Asia/Taipei', '使用者介面與工作表；修改後請重新執行初始化／升級系統'],
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
  sheet.getRange('D5').setFormula('=SUM(\'掃描設定\'!$AB$2:$AB$1000)+SUM(\'掃描設定\'!$AC$2:$AC$1000)');
  sheet.getRange('F5').setFormula('=COUNTIF(\'掃描設定\'!$AF$2:$AF$1000,"*不足*")+COUNTIF(\'掃描設定\'!$AF$2:$AF$1000,"*失敗*")+COUNTIF(\'掃描設定\'!$AF$2:$AF$1000,"*限制*")');
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
  sheet.getRange('B7:B10').setFontColor('#111827');
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
  sheet.getRange('H8:H10').setFontColor('#111827').setWrap(true);
  sheet.getRange('H7').setBackground('#DBEAFE').setHorizontalAlignment('center');
  const dashboardRules = [
    SpreadsheetApp.newConditionalFormatRule().whenTextEqualTo('成功').setFontColor('#166534').setBackground('#DCFCE7').setRanges([sheet.getRange('B7')]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=REGEXMATCH(B7,"部分|限制|等待")').setFontColor('#92400E').setBackground('#FEF3C7').setRanges([sheet.getRange('B7')]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=REGEXMATCH(B7,"錯誤|失敗")').setFontColor('#991B1B').setBackground('#FEE2E2').setRanges([sheet.getRange('B7')]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=REGEXMATCH(H10,"資料更新成功")').setFontColor('#166534').setBackground('#DCFCE7').setRanges([sheet.getRange('H10')]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=REGEXMATCH(H10,"等待|已接受")').setFontColor('#92400E').setBackground('#FEF3C7').setRanges([sheet.getRange('H10')]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=REGEXMATCH(H10,"失敗|異常")').setFontColor('#991B1B').setBackground('#FEE2E2').setRanges([sheet.getRange('H10')]).build(),
  ];
  sheet.setConditionalFormatRules(dashboardRules);
  sheet.getRange('A12:H12').merge().setValue('使用方式');
  sheet.getRange('A13:H18').mergeAcross();
  sheet.getRange('A13:A18').setValues([
    ['1. 從選單「選擇權警示」執行「初始化／升級系統」。'],
    ['2. 在「設定」確認固定通知信箱，再從選單設定 90 天 GitHub 金鑰。'],
    ['3. 用表單輸入股票、到期日及選填條件；程式會列出 Yahoo 回傳的完整期權鍊。'],
    ['4. 開盤、盤中整點與收盤自動更新；正式收盤會同步保存 Delta 0.10／0.15／0.20 趨勢。'],
    ['5. 第一門檻每天收盤彙總全部符合項目；第二門檻首次符合時即時通知。'],
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
  sheet.setFrozenColumns(5);
  sheet.getRange(1, 1, 1, APP.CHAIN_HEADERS.length)
    .setBackground('#E5E7EB')
    .setFontWeight('bold')
    .setFontColor('#111827')
    .setWrap(true);
  sheet.getRange('E:G').setNumberFormat('0.0000');
  sheet.getRange('H:H').setNumberFormat('0.00%');
  sheet.getRange('K:K').setNumberFormat('0.0000');
  sheet.getRange('N:N').setNumberFormat('0.00%');
  sheet.getRange('Q:Q').setNumberFormat('#,##0');
  sheet.getRange('T:T').setNumberFormat('0');
  sheet.getRange('U:U').setNumberFormat('yyyy-mm-dd hh:mm:ss');
  sheet.getRange('V:X').setNumberFormat('0.0000');
  sheet.getRange('Y:Y').setNumberFormat('#,##0');
  sheet.getRange('Z:Z').setNumberFormat('0.0000');
  sheet.getRange('AA:AA').setNumberFormat('yyyy-mm-dd hh:mm:ss');
  sheet.getRange('AB:AE').setNumberFormat('0.0000');
  sheet.getRange('AF:AG').setNumberFormat('0.0000');
  sheet.getRange('AI:AJ').setNumberFormat('0.00%');
  sheet.getRange('AL:AL').setNumberFormat('0.0000');
  sheet.setColumnWidths(1, APP.CHAIN_HEADERS.length, 105);
  sheet.setColumnWidth(1, 115);
  sheet.setColumnWidths(2, 2, 110);
  sheet.setColumnWidth(5, 90);
  sheet.setColumnWidth(21, 145);
  sheet.hideColumns(22, 6);
  sheet.hideColumns(28, 11);
  sheet.hideColumns(39, 7);
  if (sheet.getFilter()) sheet.getFilter().remove();
  const filter = sheet.getRange(1, 1, Math.max(sheet.getMaxRows(), 2), APP.CHAIN_HEADERS.length).createFilter();
  filter.setColumnFilterCriteria(1, SpreadsheetApp.newFilterCriteria().setHiddenValues(['未符合', '資料不足']).build());
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
  ['F', 'N', 'W'].forEach(column => sheet.getRange(`${column}2:${column}1000`).setDataValidation(checkboxRule));
  sheet.getRange('E2:E1000').setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(['ALL', 'CALL', 'PUT'], true).setAllowInvalid(false).build()
  );
  ['G', 'I', 'K', 'O', 'Q', 'S'].forEach(column => sheet.getRange(`${column}2:${column}1000`).setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(['≥', '≤'], true).setAllowInvalid(false).build()
  ));
  sheet.getRange('D:D').setNumberFormat('yyyy-mm-dd');
  sheet.getRange('H:H').setNumberFormat('0.0000');
  sheet.getRange('J:L').setNumberFormat('0.00%');
  sheet.getRange('M:M').setNumberFormat('#,##0');
  sheet.getRange('P:P').setNumberFormat('0.0000');
  sheet.getRange('R:T').setNumberFormat('0.00%');
  sheet.getRange('U:U').setNumberFormat('#,##0');
  sheet.getRange('V:V').setNumberFormat('0.0000');
  sheet.getRange('Z:Z').setNumberFormat('0.0000');
  sheet.getRange('AA:AC').setNumberFormat('#,##0');
  sheet.getRange('AD:AE').setNumberFormat('yyyy-mm-dd hh:mm:ss');
  sheet.getRange('AL:AL').setNumberFormat('yyyy-mm-dd');
  const range = sheet.getRange('A2:AL1000');
  const rules = [
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=$A2=FALSE').setBackground('#F3F4F6').setRanges([range]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=OR($AB2>0,$AC2>0)').setBackground('#DCFCE7').setFontColor('#166534').setRanges([range]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=REGEXMATCH($AF2,"不足|過期|限制|失敗|無資料")').setBackground('#FEF3C7').setFontColor('#92400E').setRanges([range]).build(),
  ];
  sheet.setConditionalFormatRules(rules);
}

function applyAlertLogFormatting_() {
  const sheet = getSpreadsheet_().getSheetByName(APP.SHEETS.ALERTS);
  if (!sheet) return;
  sheet.setFrozenRows(1);
  sheet.setFrozenColumns(4);
  sheet.getRange(1, 1, 1, APP.ALERT_HEADERS.length)
    .setBackground('#E5E7EB')
    .setFontWeight('bold')
    .setFontColor('#111827')
    .setWrap(true);
  sheet.getRange('A:A').setNumberFormat('yyyy-mm-dd hh:mm:ss');
  sheet.getRange('D:D').setNumberFormat('yyyy-mm-dd');
  sheet.getRange('F:I').setNumberFormat('0.0000');
  sheet.getRange('J:J').setNumberFormat('0.00%');
  sheet.getRange('K:L').setNumberFormat('#,##0');
  sheet.getRange('P:P').setNumberFormat('0.0000');
  sheet.getRange('Q:Q').setNumberFormat('0.00%');
  sheet.setColumnWidths(1, APP.ALERT_HEADERS.length, 110);
  sheet.setColumnWidth(1, 155);
  sheet.setColumnWidth(2, 180);
  sheet.setColumnWidth(13, 210);
  sheet.setColumnWidth(14, 220);
  sheet.setColumnWidth(18, 260);
  sheet.setColumnWidths(19, 4, 115);
  sheet.setColumnWidth(23, 220);
  sheet.setColumnWidth(24, 320);
}

function applyCloseTrendFormatting_() {
  const sheet = getSpreadsheet_().getSheetByName(APP.SHEETS.CLOSE_TRENDS);
  if (!sheet) return;
  sheet.setFrozenRows(1);
  sheet.setFrozenColumns(10);
  sheet.getRange(1, 1, 1, APP.CLOSE_TREND_HEADERS.length)
    .setBackground('#E5E7EB')
    .setFontWeight('bold')
    .setFontColor('#111827')
    .setWrap(true);
  sheet.getRange('B:B').setNumberFormat('yyyy-mm-dd');
  sheet.getRange('C:D').setNumberFormat('yyyy-mm-dd hh:mm:ss');
  sheet.getRange('G:G').setNumberFormat('yyyy-mm-dd');
  sheet.getRange('I:I').setNumberFormat('0.0000');
  sheet.getRange('L:T').setNumberFormat('0.0000');
  sheet.getRange('U:U').setNumberFormat('0.00%');
  sheet.getRange('V:V').setNumberFormat('0.0000');
  sheet.getRange('X:X').setNumberFormat('0.0000');
  sheet.getRange('Y:Y').setNumberFormat('0');
  sheet.getRange('Z:AB').setNumberFormat('0.00%');
  sheet.getRange('AC:AE').setNumberFormat('0.0000');
  sheet.getRange('AF:AG').setNumberFormat('#,##0');
  sheet.getRange('AH:AH').setNumberFormat('yyyy-mm-dd hh:mm:ss');
  sheet.getRange('AI:AI').setNumberFormat('0.00%');
  sheet.getRange('AK:AK').setNumberFormat('0.00%');
  sheet.getRange('AO:AO').setNumberFormat('0.0000');
  sheet.getRange('AP:AP').setNumberFormat('0.00%');
  sheet.setColumnWidths(1, APP.CLOSE_TREND_HEADERS.length, 110);
  sheet.setColumnWidth(1, 300);
  sheet.setColumnWidth(5, 180);
  sheet.setColumnWidth(11, 210);
  sheet.setColumnWidth(36, 190);
  sheet.setColumnWidth(38, 220);
  sheet.setColumnWidth(39, 260);
  sheet.setColumnWidth(40, 320);
  sheet.setColumnWidths(41, 2, 130);
  const rowCount = Math.max(sheet.getMaxRows() - 1, 1);
  const range = sheet.getRange(2, 1, rowCount, APP.CLOSE_TREND_HEADERS.length);
  const rules = [
    SpreadsheetApp.newConditionalFormatRule()
      .whenFormulaSatisfied('=AND($J2="已選取",$AM2="正常")')
      .setBackground('#DCFCE7').setFontColor('#166534').setRanges([range]).build(),
    SpreadsheetApp.newConditionalFormatRule()
      .whenFormulaSatisfied('=REGEXMATCH($J2&$AM2,"不足|無效|無符合|無資料|未執行")')
      .setBackground('#FEF3C7').setFontColor('#92400E').setRanges([range]).build(),
    SpreadsheetApp.newConditionalFormatRule()
      .whenFormulaSatisfied('=REGEXMATCH($J2&$AM2,"失敗|流量限制")')
      .setBackground('#FEE2E2').setFontColor('#991B1B').setRanges([range]).build(),
  ];
  sheet.setConditionalFormatRules(rules);
}

function hasScanData_(row) {
  const meaningfulIndexes = APP.SCAN_HEADERS.slice(0, 24)
    .map((header, index) => ({header, index}))
    .filter(item => !['啟用', '第一門檻啟用', '第二門檻啟用', 'Email通知'].includes(item.header))
    .map(item => item.index);
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
    ranges.push(`A${start}:A${previous}`, `F${start}:F${previous}`, `N${start}:N${previous}`, `W${start}:W${previous}`);
    start = current;
    previous = current;
  }
  sheet.getRangeList(ranges).clearContent();
}

function applyChainConditionalFormatting_(sheet) {
  const range = sheet.getRange(2, 1, Math.max(sheet.getMaxRows() - 1, 1), APP.CHAIN_HEADERS.length);
  const rules = [
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=REGEXMATCH($A2,"第二")').setBackground('#D1FAE5').setFontColor('#065F46').setRanges([range]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=$A2="第一門檻"').setBackground('#DCFCE7').setFontColor('#166534').setRanges([range]).build(),
    SpreadsheetApp.newConditionalFormatRule().whenFormulaSatisfied('=OR($A2="資料不足",REGEXMATCH($AS2,"不足|無效"))').setBackground('#FEF3C7').setFontColor('#92400E').setRanges([range]).build(),
  ];
  sheet.setConditionalFormatRules(rules);
}

function applyAllChainFormatting_() {
  const spreadsheet = getSpreadsheet_();
  const scans = spreadsheet.getSheetByName(APP.SHEETS.SCANS);
  if (!scans || scans.getLastRow() < 2) return;
  const headers = scans.getRange(1, 1, 1, scans.getLastColumn()).getValues()[0].map(String);
  const sheetNameIndex = headers.indexOf('工作表');
  if (sheetNameIndex < 0) return;
  const sheetNames = scans
    .getRange(2, sheetNameIndex + 1, scans.getLastRow() - 1, 1)
    .getValues()
    .flat()
    .map(value => String(value || '').trim())
    .filter(Boolean);
  [...new Set(sheetNames)].forEach(sheetName => {
    const sheet = spreadsheet.getSheetByName(sheetName);
    if (sheet) applyChainConditionalFormatting_(sheet);
  });
}

function normalizeUserFacingTimestamps_() {
  const spreadsheet = getSpreadsheet_();
  const scans = spreadsheet.getSheetByName(APP.SHEETS.SCANS);
  if (scans) normalizeTimestampColumns_(scans, ['最後嘗試時間', '最後成功抓取時間']);

  const alerts = spreadsheet.getSheetByName(APP.SHEETS.ALERTS);
  if (alerts) normalizeTimestampColumns_(alerts, ['寄送時間']);

  const closeTrends = spreadsheet.getSheetByName(APP.SHEETS.CLOSE_TRENDS);
  if (closeTrends) normalizeTimestampColumns_(closeTrends, ['最後成交時間']);

  if (!scans || scans.getLastRow() < 2) return;
  const headers = scans.getRange(1, 1, 1, scans.getLastColumn()).getValues()[0].map(String);
  const sheetNameIndex = headers.indexOf('工作表');
  if (sheetNameIndex < 0) return;
  const sheetNames = scans
    .getRange(2, sheetNameIndex + 1, scans.getLastRow() - 1, 1)
    .getValues()
    .flat()
    .map(value => String(value || '').trim())
    .filter(Boolean);
  [...new Set(sheetNames)].forEach(sheetName => {
    const sheet = spreadsheet.getSheetByName(sheetName);
    if (sheet) normalizeTimestampColumns_(sheet, ['最後成交時間', '最後抓取時間']);
  });
}

function normalizeTimestampColumns_(sheet, headerNames) {
  if (sheet.getLastRow() < 2 || sheet.getLastColumn() < 1) return;
  const headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0].map(String);
  headerNames.forEach(headerName => {
    const columnIndex = headers.indexOf(headerName);
    if (columnIndex < 0) return;
    const range = sheet.getRange(2, columnIndex + 1, sheet.getLastRow() - 1, 1);
    let changed = false;
    const values = range.getValues().map(([value]) => {
      const normalized = parseIsoTimestamp_(value);
      if (normalized !== value) changed = true;
      return [normalized];
    });
    if (changed) range.setValues(values);
  });
}

function parseIsoTimestamp_(value) {
  if (value instanceof Date || typeof value !== 'string') return value;
  const text = value.trim();
  const match = text.match(/^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:\d{2})$/);
  if (!match) return value;
  const milliseconds = match[2]
    ? `.${match[2].slice(0, 3).padEnd(3, '0')}`
    : '';
  const parsed = new Date(`${match[1]}${milliseconds}${match[3]}`);
  return Number.isNaN(parsed.getTime()) ? value : parsed;
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
    'GitHub 最後要求狀態': mode === 'automatic'
      ? '自動要求已接受，等待資料更新完成'
      : '手動要求已接受，等待資料更新完成',
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
  if (value === '' || value === null || value === undefined) return '—';
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return number.toFixed(digits).replace(/\.0+$/, '').replace(/(\.\d*?)0+$/, '$1');
}

function formatPercent_(value) {
  if (value === '' || value === null || value === undefined) return '—';
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
