from __future__ import annotations

import json
from datetime import date

from .constants import (AUTO_TARGET_HEADERS, AUTO_TARGET_SHEET, CHAIN_HEADERS,
    SCAN_ARCHIVE_HEADERS, SCAN_ARCHIVE_SHEET, SCAN_HEADERS, SCAN_SHEET)
from .models import ScanRecord, as_bool
from .provider import MarketDataError, RateLimitError
from .rolling import plan_rolling, seed_targets, validate_target


class RollingRepositoryMixin:
    def sync_rolling_scans(self, provider, now, market_timezone):
        from zoneinfo import ZoneInfo
        from .sheets import _sheet_range
        today = now.astimezone(ZoneInfo(market_timezone)).date()
        headers, scans, invalid = self.load_scans()
        if invalid:
            raise ValueError('掃描設定存在無效列，停止自動移轉')
        self._ensure_sheets([AUTO_TARGET_SHEET], min_columns=len(AUTO_TARGET_HEADERS))
        self._ensure_header(AUTO_TARGET_SHEET, AUTO_TARGET_HEADERS)
        self._ensure_sheets([SCAN_ARCHIVE_SHEET], min_columns=len(SCAN_ARCHIVE_HEADERS))
        self._ensure_header(SCAN_ARCHIVE_SHEET, SCAN_ARCHIVE_HEADERS)
        api = self.service.spreadsheets().values()
        target_range = _sheet_range(AUTO_TARGET_SHEET, 'A2:AC1000')
        raw_targets = self._execute(api.get(spreadsheetId=self.spreadsheet_id, range=target_range,
            valueRenderOption='UNFORMATTED_VALUE')).get('values', [])
        targets = [dict(zip(AUTO_TARGET_HEADERS, row + [''] * (len(AUTO_TARGET_HEADERS) - len(row))))
                   for row in raw_targets if len(row) > 1 and row[1]]
        meta = self._execute(self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id,
            fields='developerMetadata(metadataKey,metadataValue),sheets.properties(sheetId,title,gridProperties)'))
        bootstrap = not any(m.get('metadataKey') == 'OPTION_ALERTS_ROLLING_MIGRATED'
                            and m.get('metadataValue') == '1' for m in meta.get('developerMetadata', []))
        if not targets and not bootstrap:
            raise ValueError('自動追蹤標的為空，請新增標的；不會自動重新匯入已移除標的')
        if bootstrap:
            targets = list({**{t['股票代號']: t for t in seed_targets(scans)},
                            **{t['股票代號']: t for t in targets}}.values())
        if not targets:
            return {'errors': {}, 'added': 0, 'removed': 0}
        for target in targets:
            validate_target(target)
        props = {s['properties']['title']: s['properties'] for s in meta.get('sheets', [])}
        dates, errors = {}, {}
        for target in targets:
            ticker = target['股票代號']
            if not as_bool(target['啟用']):
                continue
            try:
                if target.get('最近查詢日期') == today.isoformat():
                    dates[ticker] = [date.fromisoformat(d) for d in json.loads(target.get('到期日JSON') or '[]')]
                else:
                    dates[ticker] = provider.fetch_expirations(ticker)
                    if not dates[ticker]:
                        raise MarketDataError('Yahoo到期日清單為空')
                    target['最近查詢日期'] = today.isoformat()
                    target['到期日JSON'] = json.dumps(sorted({d.isoformat() for d in dates[ticker]}))
            except (RateLimitError, MarketDataError, ValueError, TypeError) as exc:
                errors[ticker] = str(exc)[:500]
                # A rate limit stops further market requests in this run.
                if isinstance(exc, RateLimitError):
                    raise
        plan = plan_rolling(scans=scans, targets=targets, expirations=dates, errors=errors,
                            sheet_properties=props, today=today, bootstrap=bootstrap)
        requests, deletes = [], []
        # Validate immutable IDs, names and chain schema before any delete request.
        for owner in plan.remove:
            prop = props.get(owner['title'])
            if not prop:
                continue
            if prop['sheetId'] != owner['id']:
                raise ValueError(f"{owner['title']} 分頁ID已改變，停止刪除")
            response = self._execute(api.get(spreadsheetId=self.spreadsheet_id,
                range=_sheet_range(owner['title'], 'A1:AS2'), valueRenderOption='UNFORMATTED_VALUE'))
            rows = response.get('values', [])
            expected_id = f"{owner['ticker']}|{owner['expiry']}"
            if not rows or rows[0] != CHAIN_HEADERS or (len(rows) > 1 and rows[1]
                and (len(rows[1]) <= CHAIN_HEADERS.index('掃描ID')
                     or rows[1][CHAIN_HEADERS.index('掃描ID')] != expected_id)):
                raise ValueError(f"{owner['title']} 內容不是可確認的期權鍊，停止刪除")
            deletes.append(owner)

        used_ids = {p['sheetId'] for p in props.values()}
        next_id = 100000
        def reserve_id():
            nonlocal next_id
            while next_id in used_ids:
                next_id += 1
            used_ids.add(next_id)
            return next_id

        additions = []
        by_ticker = {t['股票代號']: t for t in targets}
        for values in plan.scans:
            ticker = values['股票代號']
            if ticker not in by_ticker or ticker in plan.errors:
                continue
            scan = ScanRecord.from_values(2, SCAN_HEADERS, [values.get(h, '') for h in SCAN_HEADERS])
            prop = props.get(scan.sheet_name)
            if not prop and as_bool(by_ticker[ticker]['啟用']):
                prop = {'sheetId': reserve_id(), 'title': scan.sheet_name,
                        'gridProperties': {'rowCount': 1000, 'columnCount': len(CHAIN_HEADERS),
                                           'frozenRowCount': 1, 'frozenColumnCount': 5}}
                additions.append(prop)
            if prop:
                plan.owners[scan.scan_id] = {'id': prop['sheetId'], 'title': scan.sheet_name,
                    'expiry': scan.expiry.isoformat(), 'ticker': ticker}
        if len(props) - len(deletes) + len(additions) + (SCAN_ARCHIVE_SHEET not in props) > 200:
            raise ValueError('自動追蹤超過程式200張分頁保護限制，未刪除或新增任何期權鍊')
        cells = sum(p.get('gridProperties', {}).get('rowCount', 1000)
                    * p.get('gridProperties', {}).get('columnCount', 26) for p in props.values())
        cells -= sum(props[o['title']].get('gridProperties', {}).get('rowCount', 1000)
                     * props[o['title']].get('gridProperties', {}).get('columnCount', 45) for o in deletes)
        if cells + len(additions) * 1000 * len(CHAIN_HEADERS) + 40000 > 10000000:
            raise ValueError('自動追蹤將超過試算表儲存格容量，停止整理')
        if len(plan.scans) >= self.max_monitor_rows:
            raise ValueError('自動掃描數超過讀取列數上限，停止整理')

        def cell(value, header=''):
            value = self._serializable(value, header)
            if isinstance(value, bool):
                return {'userEnteredValue': {'boolValue': value}}
            if isinstance(value, (int, float)):
                return {'userEnteredValue': {'numberValue': value}}
            return {'userEnteredValue': {'stringValue': str(value)}}

        def write(sheet_id, values, count=None, headers=SCAN_HEADERS):
            width = len(values[0]) if values else len(SCAN_HEADERS)
            height = max(len(values), count or 0)
            if height:
                requests.append({'updateCells': {'range': {'sheetId': sheet_id, 'startRowIndex': 1,
                    'endRowIndex': height + 1, 'startColumnIndex': 0, 'endColumnIndex': width},
                    'rows': [{'values': [cell(v, h) for h, v in zip(headers, row)]} for row in values], 'fields': 'userEnteredValue'}})

        # Seal against a concurrent form edit before publishing the planned changes.
        check = self._execute(api.get(spreadsheetId=self.spreadsheet_id, range=target_range,
            valueRenderOption='UNFORMATTED_VALUE')).get('values', [])
        _, latest, invalid = self.load_scans()
        if check != raw_targets or invalid or [s.values for s in latest] != [s.values for s in scans]:
            raise ValueError('整理期間設定已變更，停止寫入，請下次更新重試')

        changed = []
        planned = {v['掃描ID']: v for v in plan.scans}
        for scan in scans:
            after = planned.get(scan.scan_id)
            if after is None or any(scan.values.get(h, '') != after.get(h, '') for h in SCAN_HEADERS[:24]):
                changed.append([scan.values.get(h, '') for h in SCAN_HEADERS] + [now, '自動模式移轉／範圍調整'])
        if changed:
            archive_id = props[SCAN_ARCHIVE_SHEET]['sheetId']
            requests.append({'appendCells': {'sheetId': archive_id,
                'rows': [{'values': [cell(v, h) for h, v in zip(SCAN_ARCHIVE_HEADERS, row)]} for row in changed], 'fields': 'userEnteredValue'}})
        for owner in deletes:
            requests.append({'deleteSheet': {'sheetId': owner['id']}})
        for prop in additions:
            requests.append({'addSheet': {'properties': prop}})
            requests.extend(chain_sheet_requests(prop['sheetId']))
        scan_values = [[v.get(h, '') for h in SCAN_HEADERS] for v in plan.scans]
        last_scan_row = max((s.row_number - 1 for s in scans), default=0)
        if max(last_scan_row, len(scan_values)) >= props[SCAN_SHEET]['gridProperties']['rowCount']:
            requests.append({'updateSheetProperties': {'properties': {'sheetId': props[SCAN_SHEET]['sheetId'],
                'gridProperties': {'rowCount': max(last_scan_row, len(scan_values)) + 1}},
                'fields': 'gridProperties.rowCount'}})
        write(props[SCAN_SHEET]['sheetId'], scan_values, last_scan_row)
        for target in targets:
            ticker = target['股票代號']
            target['管理分頁JSON'] = json.dumps({key: value for key, value in plan.owners.items()
                if value['ticker'] == ticker}, ensure_ascii=False, separators=(',', ':'))
            target['最後同步時間(UTC)'] = now
            target['同步狀態'] = ('失敗：' + plan.errors[ticker]) if ticker in plan.errors else (
                '已停用' if not as_bool(target['啟用']) else '成功')
        write(props[AUTO_TARGET_SHEET]['sheetId'], [[t.get(h, '') for h in AUTO_TARGET_HEADERS] for t in targets],
              headers=AUTO_TARGET_HEADERS)
        target_id = props[AUTO_TARGET_SHEET]['sheetId']
        requests.extend([
            {'updateSheetProperties': {'properties': {'sheetId': target_id,
                'gridProperties': {'frozenRowCount': 1, 'frozenColumnCount': 2}},
                'fields': 'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'}},
            {'repeatCell': {'range': {'sheetId': target_id, 'startRowIndex': 0, 'endRowIndex': 1,
                'startColumnIndex': 0, 'endColumnIndex': len(AUTO_TARGET_HEADERS)},
                'cell': {'userEnteredFormat': {'backgroundColor': {'red': .86, 'green': .92, 'blue': 1},
                    'textFormat': {'bold': True}, 'wrapStrategy': 'WRAP'}}, 'fields': 'userEnteredFormat'}},
            {'updateDimensionProperties': {'range': {'sheetId': target_id, 'dimension': 'COLUMNS',
                'startIndex': 24, 'endIndex': 27}, 'properties': {'hiddenByUser': True}, 'fields': 'hiddenByUser'}},
        ])
        for index in (9, 11, 17, 19, 27):
            requests.append({'repeatCell': {'range': {'sheetId': target_id, 'startRowIndex': 1,
                'startColumnIndex': index, 'endColumnIndex': index + 1},
                'cell': {'userEnteredFormat': {'numberFormat': {
                    'type': 'DATE_TIME' if index == 27 else 'PERCENT',
                    'pattern': 'yyyy-mm-dd hh:mm:ss' if index == 27 else '0.00%'}}},
                'fields': 'userEnteredFormat.numberFormat'}})
        if bootstrap:
            requests.append({'createDeveloperMetadata': {'developerMetadata': {
                'metadataKey': 'OPTION_ALERTS_ROLLING_MIGRATED', 'metadataValue': '1',
                'visibility': 'DOCUMENT', 'location': {'spreadsheet': True}}}})
        self._execute(self.service.spreadsheets().batchUpdate(spreadsheetId=self.spreadsheet_id,
            body={'requests': requests}))
        self._sheet_properties_cache = None
        if additions or deletes or plan.errors:
            self.append_system_log('WARN' if plan.errors else 'INFO', '自動期權鍊整理',
                json.dumps({'added': [p['title'] for p in additions], 'deleted': [o['title'] for o in deletes],
                            'errors': plan.errors}, ensure_ascii=False))
        return {'errors': plan.errors, 'added': len(additions), 'removed': len(deletes)}


def chain_sheet_requests(sheet_id):
    """Batch formatting so adding many expirations does not require slow UI calls."""
    requests = [
        {'updateCells': {'start': {'sheetId': sheet_id, 'rowIndex': 0, 'columnIndex': 0},
            'rows': [{'values': [{'userEnteredValue': {'stringValue': h}} for h in CHAIN_HEADERS]}],
            'fields': 'userEnteredValue'}},
        {'repeatCell': {'range': {'sheetId': sheet_id, 'startRowIndex': 0, 'endRowIndex': 1},
            'cell': {'userEnteredFormat': {'backgroundColor': {'red': .89, 'green': .92, 'blue': .97},
                     'textFormat': {'bold': True}, 'wrapStrategy': 'WRAP'}}, 'fields': 'userEnteredFormat'}},
        {'setBasicFilter': {'filter': {'range': {'sheetId': sheet_id, 'startRowIndex': 0,
            'endRowIndex': 1000, 'startColumnIndex': 0, 'endColumnIndex': len(CHAIN_HEADERS)},
            'criteria': {'0': {'hiddenValues': ['未符合', '資料不足']}}}}},
    ]
    for field, fmt, kind in [('年化報酬率', '0.00%', 'PERCENT'), ('Bid-Ask價差率', '0.00%', 'PERCENT'),
        ('IV', '0.00%', 'PERCENT'), ('Delta估算', '0.0000', 'NUMBER'), ('Bid', '0.0000', 'NUMBER'),
        ('最後抓取時間', 'yyyy-mm-dd hh:mm:ss', 'DATE_TIME')]:
        index = CHAIN_HEADERS.index(field)
        requests.append({'repeatCell': {'range': {'sheetId': sheet_id, 'startRowIndex': 1,
            'startColumnIndex': index, 'endColumnIndex': index + 1},
            'cell': {'userEnteredFormat': {'numberFormat': {'type': kind, 'pattern': fmt}}},
            'fields': 'userEnteredFormat.numberFormat'}})
    requests.append({'addConditionalFormatRule': {'index': 0, 'rule': {
        'ranges': [{'sheetId': sheet_id, 'startRowIndex': 1, 'endRowIndex': 1000,
                    'startColumnIndex': 0, 'endColumnIndex': len(CHAIN_HEADERS)}],
        'booleanRule': {'condition': {'type': 'CUSTOM_FORMULA', 'values': [
            {'userEnteredValue': '=OR($B2="符合",$C2="符合")'}]},
            'format': {'backgroundColor': {'red': .86, 'green': .97, 'blue': .89}}}}}})
    return requests
