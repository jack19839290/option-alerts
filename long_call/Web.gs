const LONG_CALL_FIELDS = [
  ['最小 DTE', 1, Infinity, true], ['最大 DTE', 1, Infinity, true],
  ['最低 Delta', 0, 1], ['最低釋放現金比例', 0, 1],
  ['最低 OI', 0, Infinity, true], ['最高 Spread', 0, 2],
  ['最高年化資金成本', 0, Infinity], ['試算價來源'],
];

function doGet() {
  return HtmlService.createHtmlOutputFromFile('Web').setTitle('美股選擇權篩選')
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
    const rows = longCallRows_(sheet);
    const state = longCallFormState_(sheet, ticker, rows);
    if (payload.revision !== state.revision) {
      throw new Error('設定已更新，請按「重新載入」後再儲存。');
    }
    const proposed = longCallValues_(payload.values, Boolean(ticker));
    if (ticker) {
      longCallEffective_(proposed, state.defaults);
      const row = state.row || longCallNewTargetRow_(rows);
      if (row > sheet.getMaxRows()) sheet.insertRowsAfter(sheet.getMaxRows(), 1);
      sheet.getRange(row, 1, 1, 10).setValues([[payload.enabled, ticker, ...proposed]]);
    } else {
      longCallEffective_(proposed, proposed);
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

function longCallNewTargetRow_(rows) {
  // A preformatted target row has an unchecked checkbox and no other values.
  const index = rows.findIndex(([enabled, ...values]) =>
    (enabled === false || enabled === '') && values.every(value => value === '')
  );
  return 10 + (index < 0 ? rows.length : index);
}

function longCallFormState_(sheet, ticker, rows = longCallRows_(sheet)) {
  const defaults = sheet.getRange('C5:J5').getValues()[0];
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

const PUT_FILTERS = [
  ['DTE', [['最小 DTE', 0, null, 'int'], ['最大 DTE', 0, null, 'int']]],
  ['Delta', [['最低 Delta', -1, 0], ['最高 Delta', -1, 0]]],
  ['OI', [['最低 OI', 0, null, 'int']]],
  ['Spread', [['最高 Spread', 0, 2, '%']]],
  ['保費率', [['最高保費率', 0, null, '%']]],
  ['年化成本', [['最高年化成本', 0, null, '%']]],
  ['最大跌幅', [['最大到期跌幅', 0, null, '%']]],
];
const PUT_SETTING_HEADERS = ['啟用標的', '股票代號', ...PUT_FILTERS.flatMap(
  ([name, fields]) => ['啟用 ' + name, ...fields.map(field => field[0])]
)];

function putSettings_() {
  const book = SpreadsheetApp.openById(LONG_CALL_WEB_SHEET_ID);
  const sheet = book.getSheetByName('Put 設定與標的');
  if (!sheet) throw new Error('Put 分頁尚未初始化，請先執行一次掃描。');
  if (JSON.stringify(sheet.getRange(9, 1, 1, PUT_SETTING_HEADERS.length).getValues()[0]) !==
      JSON.stringify(PUT_SETTING_HEADERS)) throw new Error('Put 設定欄位不符。');
  return sheet;
}

function putFormState_(sheet, ticker, rows) {
  const width = PUT_SETTING_HEADERS.length;
  const defaults = sheet.getRange(5, 3, 1, width - 2).getValues()[0];
  const matches = rows.map((row, i) => String(row[1]).trim().toUpperCase() === ticker ? i : -1)
    .filter(i => ticker && i >= 0);
  if (matches.length > 1) throw new Error(ticker + ' 有重複設定，請在試算表合併。');
  const index = matches[0];
  const entry = rows[index];
  const book = sheet.getParent();
  const link = name => book.getUrl() + '#gid=' + book.getSheetByName(name).getSheetId();
  return {
    defaults, filters: PUT_FILTERS, values: ticker ? entry?.slice(2) ?? Array(width - 2).fill('') : defaults,
    enabled: entry ? longCallEnabled_(entry[0]) : true, row: entry ? 10 + index : null,
    tickers: rows.filter(row => row[1]).map(row => [String(row[1]).trim().toUpperCase(), longCallEnabled_(row[0])])
      .sort((a, b) => a[0].localeCompare(b[0])),
    revision: Utilities.base64EncodeWebSafe(Utilities.computeDigest(
      Utilities.DigestAlgorithm.SHA_256, JSON.stringify([ticker, defaults, entry])
    )),
    settingsUrl: link('Put 設定與標的'), resultsUrl: link('Put 符合條件'), detailUrl: link('Put 期權鏈明細'),
  };
}

function putRows_(sheet) {
  const count = sheet.getLastRow() - 9;
  return count > 0 ? sheet.getRange(10, 1, count, PUT_SETTING_HEADERS.length).getValues() : [];
}

function loadPutForm(tickerValue) {
  const sheet = putSettings_();
  return putFormState_(sheet, longCallTicker_(tickerValue), putRows_(sheet));
}

function putValidate_(values, defaults) {
  if (!Array.isArray(values) || values.length !== PUT_SETTING_HEADERS.length - 2) {
    throw new Error('Put 門檻欄位不完整。');
  }
  const effective = values.map((value, i) => value === '' && defaults ? defaults[i] : value);
  let i = 0;
  for (const [name, fields] of PUT_FILTERS) {
    if (typeof effective[i++] !== 'boolean') throw new Error(name + ' 開關無效。');
    const numbers = fields.map(([label, min, max, unit]) => {
      const value = effective[i++];
      if (!Number.isFinite(value) || value < min || (max !== null && value > max) ||
          (unit === 'int' && !Number.isSafeInteger(value))) throw new Error(label + ' 數值無效。');
      return value;
    });
    if (numbers.length === 2 && numbers[0] > numbers[1]) throw new Error(name + ' 下限不得大於上限。');
  }
}

function savePutForm(payload) {
  const ticker = longCallTicker_(payload.ticker);
  if (typeof payload.enabled !== 'boolean') throw new Error('標的狀態無效。');
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const sheet = putSettings_();
    const rows = putRows_(sheet);
    const state = putFormState_(sheet, ticker, rows);
    if (state.revision !== payload.revision) throw new Error('設定已有更新，請重新載入。');
    putValidate_(payload.values, ticker ? state.defaults : null);
    if (ticker) {
      const row = state.row || longCallNewTargetRow_(rows);
      if (row > sheet.getMaxRows()) sheet.insertRowsAfter(sheet.getMaxRows(), 1);
      sheet.getRange(row, 1, 1, PUT_SETTING_HEADERS.length)
        .setValues([[payload.enabled, ticker, ...payload.values]]);
    } else {
      for (const row of rows.filter(row => row[1] && longCallEnabled_(row[0]))) {
        try {
          putValidate_(row.slice(2), payload.values);
        } catch (error) {
          throw new Error(row[1] + ' 套用新預設後，' + error.message);
        }
      }
      sheet.getRange(5, 3, 1, payload.values.length).setValues([payload.values]);
    }
    SpreadsheetApp.flush();
    return putFormState_(sheet, ticker, putRows_(sheet));
  } finally {
    lock.releaseLock();
  }
}

function loadPutResults(options) {
  const ticker = longCallTicker_(options.ticker);
  const book = SpreadsheetApp.openById(LONG_CALL_WEB_SHEET_ID);
  const detail = book.getSheetByName('Put 期權鏈明細');
  const log = book.getSheetByName('Put 掃描紀錄');
  if (!detail || !log) throw new Error('Put 分頁尚未初始化。');
  const readLog = () => {
    const last = log.getLastRow();
    return last > 1 ? log.getRange(last, 1, 1, 11).getDisplayValues()[0] : [];
  };
  const before = readLog();
  const headers = detail.getRange(1, 1, 1, detail.getLastColumn()).getDisplayValues()[0];
  const column = label => headers.indexOf(label);
  const state = column('狀態');
  const reason = column('篩選原因');
  const wanted = {
    preview: row => row[state] === '行情待確認' && !row[reason],
    official: row => row[state] === '符合條件',
    pending: row => row[state] === '行情待確認',
    failed: row => row[state] === '未符合',
    all: () => true,
  }[options.filter];
  const rows = [];
  const count = detail.getLastRow() - 1;
  if (ticker && count > 0 && wanted) {
    const symbols = detail.getRange(2, 1, count, 1).getDisplayValues().flat();
    for (let i = 0; i < symbols.length; i++) {
      if (symbols[i] !== ticker) continue;
      let end = i + 1;
      while (symbols[end] === ticker) end++;
      rows.push(...detail.getRange(i + 2, 1, end - i, headers.length).getValues()
        .filter(wanted).map(row => row.map(value => value instanceof Date ? value.toISOString() : value)));
      i = end - 1;
    }
  }
  const efficiency = column('跌 ' + ([10, 20, 30, 40].includes(options.drop) ? options.drop : 20) + '% 避險效率');
  const orders = {
    premium: [['每口保費', 1]], efficiency: [[headers[efficiency], -1]],
    liquidity: [['Spread', 1], ['OI', -1]], best: [],
  };
  const sort = (orders[options.sort] || []).concat([
    ['最大到期跌幅', 1], ['保費率', 1], ['DTE', -1], ['Delta', 1], ['Spread', 1], ['OI', -1],
  ]).map(([label, direction]) => [column(label), direction]);
  rows.sort((a, b) => {
    for (const [i, direction] of sort) {
      if (a[i] === b[i]) continue;
      if (a[i] === '') return 1;
      if (b[i] === '') return -1;
      return direction * (a[i] - b[i]);
    }
    return String(a[column('合約代號')]).localeCompare(String(b[column('合約代號')]));
  });
  if (JSON.stringify(before) !== JSON.stringify(readLog())) throw new Error('剛完成一批掃描，請重新載入結果。');
  const pageSize = 40;
  const page = Math.max(0, Math.min(Math.ceil(rows.length / pageSize) - 1, Math.floor(Number(options.page) || 0)));
  return {headers, rows: rows.slice(page * pageSize, (page + 1) * pageSize), total: rows.length, page, pageSize, log: before};
}
