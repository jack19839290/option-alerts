const LONG_CALL_FIELDS = [
  ['最小 DTE', 1, Infinity, true], ['最大 DTE', 1, Infinity, true],
  ['最低 Delta', 0, 1], ['最低釋放現金比例', 0, 1],
  ['最低 OI', 0, Infinity, true], ['最高 Spread', 0, 2],
  ['最高年化資金成本', 0, Infinity], ['試算價來源'],
];

function doGet() {
  return HtmlService.createHtmlOutputFromFile('Web').setTitle('買入買權追蹤設定')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

function loadLongCallForm(tickerValue) {
  const ticker = longCallTicker_(tickerValue);
  const sheet = longCallWebSheet_();
  return longCallFormState_(sheet, ticker);
}

function saveLongCallForm(payload) {
  if (!payload || typeof payload.enabled !== 'boolean' || typeof payload.revision !== 'string') {
    throw new Error('表單資料無效。');
  }
  const ticker = longCallTicker_(payload.ticker);
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const sheet = longCallWebSheet_();
    const state = longCallFormState_(sheet, ticker);
    if (payload.revision !== state.revision) {
      throw new Error('設定已更新，請按「重新載入」後再儲存。');
    }
    const proposed = longCallValues_(payload.values, Boolean(ticker));
    if (ticker) {
      longCallEffective_(proposed, state.defaults);
      const row = state.row || Math.max(10, sheet.getLastRow() + 1);
      if (row > sheet.getMaxRows()) sheet.insertRowsAfter(sheet.getMaxRows(), 1);
      sheet.getRange(row, 1, 1, 10).setValues([[payload.enabled, ticker, ...proposed]]);
    } else {
      longCallEffective_(proposed, proposed);
      const rows = longCallRows_(sheet);
      for (const row of rows) {
        if (!longCallEnabled_(row[0]) || !row[1]) continue;
        try {
          longCallEffective_(row.slice(2), proposed);
        } catch (error) {
          throw new Error(`${row[1]} 套用新預設後：${error.message}`);
        }
      }
      sheet.getRange('C5:J5').setValues([proposed]);
    }
    SpreadsheetApp.flush();
    return longCallFormState_(sheet, ticker);
  } finally {
    lock.releaseLock();
  }
}

function longCallWebSheet_() {
  const book = SpreadsheetApp.openById(LONG_CALL_WEB_SHEET_ID);
  const sheet = book.getSheetByName('設定與標的');
  if (!sheet || !book.getSheetByName('符合條件') ||
      JSON.stringify(sheet.getRange('C9:J9').getValues()[0]) !==
      JSON.stringify(LONG_CALL_FIELDS.map(field => field[0]))) {
    throw new Error('買入買權試算表的欄位不符。');
  }
  return sheet;
}

function longCallRows_(sheet) {
  const length = sheet.getLastRow() - 9;
  return length > 0 ? sheet.getRange(10, 1, length, 10).getValues() : [];
}

function longCallFormState_(sheet, ticker) {
  const defaults = sheet.getRange('C5:J5').getValues()[0];
  const rows = longCallRows_(sheet);
  const tickerOf = row => String(row[1]).trim().toUpperCase();
  const matching = ticker ? rows.map((row, i) => tickerOf(row) === ticker ? i : -1).filter(i => i >= 0) : [];
  if (matching.length > 1) throw new Error(`${ticker} 在試算表有重複設定，請先合併。`);
  const index = matching[0];
  const entry = index === undefined ? null : rows[index];
  const book = sheet.getParent();
  const revision = Utilities.base64EncodeWebSafe(Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256, JSON.stringify([ticker, defaults, entry])
  ));
  return {
    defaults, values: ticker ? entry?.slice(2) ?? Array(8).fill('') : defaults,
    row: entry ? index + 10 : null, enabled: entry ? longCallEnabled_(entry[0]) : true,
    revision, tickers: [...new Set(rows.map(tickerOf).filter(Boolean))].sort(),
    sheetUrl: book.getUrl(), resultsUrl: book.getUrl() + '#gid=' + book.getSheetByName('符合條件').getSheetId(),
  };
}

function longCallEnabled_(value) {
  return value === true || ['true', '1', 'yes', 'y', '是', '啟用'].includes(String(value).trim().toLowerCase());
}

function longCallTicker_(value) {
  if (typeof value !== 'string') throw new Error('股票代號無效。');
  const ticker = value.trim().toUpperCase();
  if (ticker && !/^[A-Z][A-Z0-9.-]{0,11}$/.test(ticker)) {
    throw new Error('請輸入有效的股票代號。');
  }
  return ticker;
}

function longCallValues_(values, allowBlank) {
  if (!Array.isArray(values) || values.length !== LONG_CALL_FIELDS.length) throw new Error('門檻欄位不完整。');
  return values.map((raw, i) => {
    const [label, min, max, integer] = LONG_CALL_FIELDS[i];
    if (raw === '' && allowBlank) return '';
    if (i === 7) {
      if (!['Bid', 'Mid', 'Ask'].includes(raw)) throw new Error('請選擇 Bid、Mid 或 Ask。');
      return raw;
    }
    if (typeof raw !== 'number' || !Number.isFinite(raw) || raw < min || raw > max ||
        (integer && !Number.isSafeInteger(raw))) throw new Error(`${label} 請輸入有效數值。`);
    return raw;
  });
}

function longCallEffective_(values, defaults) {
  const effective = longCallValues_(values.map((value, i) => value === '' ? defaults[i] : value), false);
  if (effective[0] > effective[1]) throw new Error('最小 DTE 不得大於最大 DTE。');
}
