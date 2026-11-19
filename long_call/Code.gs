/** @OnlyCurrentDoc */

function onOpen() {
  SpreadsheetApp.getUi().createMenu('買入買權')
    .addItem('啟用收盤 Email', 'installLongCallEmail')
    .addToUi();
}

function installLongCallEmail() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const settings = spreadsheet.getSheetByName('設定與標的');
  const log = spreadsheet.getSheetByName('掃描紀錄');
  if (!settings || !log) throw new Error('請在買入買權篩選器試算表執行。');
  const recipient = Session.getEffectiveUser().getEmail();
  if (!recipient) throw new Error('無法取得執行帳號的 Email。');
  MailApp.getRemainingDailyQuota();
  const props = PropertiesService.getScriptProperties();
  const existing = props.getProperty('LONG_CALL_RECIPIENT');
  if (existing && existing !== recipient) throw new Error('收盤 Email 已由另一個帳號啟用。');
  props.setProperties({ LONG_CALL_SHEET: spreadsheet.getId(), LONG_CALL_RECIPIENT: recipient });
  if (!ScriptApp.getProjectTriggers().some(trigger => trigger.getHandlerFunction() === 'sendLongCallEmail')) {
    ScriptApp.newTrigger('sendLongCallEmail').timeBased().everyMinutes(5).create();
  }
  settings.getRange('B7').setValue('已啟用，寄至授權帳號');
}

function sendLongCallEmail() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    const props = PropertiesService.getScriptProperties();
    const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
    if (!spreadsheet || spreadsheet.getId() !== props.getProperty('LONG_CALL_SHEET')) {
      throw new Error('無法確認買入買權試算表。');
    }
    const recipient = props.getProperty('LONG_CALL_RECIPIENT');
    const log = spreadsheet.getSheetByName('掃描紀錄');
    const count = log.getLastRow() - 1;
    if (count < 1 || MailApp.getRemainingDailyQuota() < 1) return;
    const rows = log.getRange(2, 1, count, 11).getDisplayValues();
    const todayET = Utilities.formatDate(new Date(), 'America/New_York', 'yyyy-MM-dd');
    for (let i = rows.length - 1; i >= 0; i--) {
      const [, day, mode, status, targets, expected, received, matches, notes, mail, summary] = rows[i];
      if (day !== todayET || mode !== '收盤' || mail !== '待寄') continue;
      const cell = log.getRange(i + 2, 10);
      cell.setValue('寄送中');
      SpreadsheetApp.flush();
      const body = [
        `美東 ${day} 收盤掃描｜${status}`,
        `標的 ${targets} 檔，已掃到期日 ${received}／${expected}，符合 ${matches} 筆。`,
        notes, summary, spreadsheet.getUrl(),
      ].filter(Boolean).join('\n\n');
      try {
        MailApp.sendEmail(recipient, `買入買權｜${day} 收盤｜${status}`, body);
      } catch (error) {
        cell.setValue('寄送失敗');
        throw error;
      }
      cell.setValue('已寄送');
      break;
    }
  } finally {
    lock.releaseLock();
  }
}
