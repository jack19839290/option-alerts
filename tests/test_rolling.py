import copy
import json
import unittest
from datetime import date, datetime, timedelta, timezone

from app.constants import (AUTO_TARGET_HEADERS, AUTO_TARGET_SHEET, CHAIN_HEADERS,
    SCAN_HEADERS, SCAN_SHEET, SCAN_ARCHIVE_SHEET)
from app.models import ScanRecord
from app.rolling import plan_rolling, seed_targets
from app.rolling_repository import RollingRepositoryMixin
from app.provider import MarketDataError


TODAY = date(2026, 11, 17)
NOW = datetime(2026, 11, 17, 15, tzinfo=timezone.utc)


def scan(dte, ticker='MU', side='ALL', annual=.12, oi=498):
    values = {'啟用': True, '股票代號': ticker, '到期日': (TODAY + timedelta(days=dte)).isoformat(),
        '顯示類型': side, '第一門檻啟用': True, '第一Delta條件': '≤', '第一Delta門檻': .15,
        '第一年化報酬率條件': '≥', '第一年化報酬率門檻': .1,
        '第二門檻啟用': True, '第二Delta條件': '≤', '第二Delta門檻': .1,
        '第二年化報酬率條件': '≥', '第二年化報酬率門檻': annual,
        '第二未平倉大於(口)': oi, 'Email通知': True}
    values['掃描ID'] = ticker + '|' + values['到期日']
    result = ScanRecord.from_values(2, SCAN_HEADERS, [values.get(h, '') for h in SCAN_HEADERS])
    result.values['工作表'] = result.sheet_name
    return result


def props(scans):
    return {s.sheet_name: {'sheetId': 200 + i, 'title': s.sheet_name,
        'gridProperties': {'rowCount': 1000, 'columnCount': 45}} for i, s in enumerate(scans)}


class PlannerTests(unittest.TestCase):
    def test_migration_resolves_all_requested_conditions(self):
        old = [scan(200), scan(220, annual=.10, oi=500)]
        targets = seed_targets(old)
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]['顯示類型'], 'PUT')
        self.assertEqual(targets[0]['第二年化報酬率門檻'], .10)
        for h in ('第一未平倉大於(口)', '第二未平倉大於(口)'):
            self.assertEqual(targets[0][h], 500)

    def test_dte_inclusive_and_owned_delete_only(self):
        old = [scan(179), scan(180), scan(360), scan(361)]
        p = plan_rolling(scans=old, targets=seed_targets(old),
            expirations={'MU': [TODAY + timedelta(days=d) for d in (179, 180, 200, 360, 361)]},
            errors={}, sheet_properties=props(old), today=TODAY, bootstrap=True)
        self.assertEqual({v['到期日'] for v in p.scans},
            {(TODAY + timedelta(days=d)).isoformat() for d in (180, 200, 360)})
        self.assertEqual({o['expiry'] for o in p.remove},
            {(TODAY + timedelta(days=d)).isoformat() for d in (179, 361)})
        self.assertTrue(all(v['顯示類型'] == 'PUT' for v in p.scans))

    def test_query_failure_or_empty_window_never_deletes(self):
        old = [scan(179)]
        for dates, errors in (({}, {'MU': 'network'}), ({'MU': []}, {})):
            p = plan_rolling(scans=old, targets=seed_targets(old), expirations=dates, errors=errors,
                sheet_properties=props(old), today=TODAY, bootstrap=True)
            self.assertEqual(p.remove, [])
            self.assertIn('MU', p.errors)
            self.assertEqual(len(p.scans), 1)

    def test_unregistered_collision_blocks_overwrite(self):
        s = scan(200)
        with self.assertRaisesRegex(ValueError, '尚未登記'):
            plan_rolling(scans=[s], targets=seed_targets([s]), expirations={'MU': [s.expiry]},
                errors={}, sheet_properties=props([s]), today=TODAY, bootstrap=False)

    def test_ownership_cannot_target_system_sheet(self):
        s = scan(179)
        targets = seed_targets([s])
        targets[0]['管理分頁JSON'] = json.dumps({s.scan_id: {'id': 7, 'title': '波動率趨勢',
            'ticker': 'MU', 'expiry': s.expiry.isoformat()}})
        with self.assertRaisesRegex(ValueError, '身份不符'):
            plan_rolling(scans=[s], targets=targets, expirations={'MU': [TODAY + timedelta(days=200)]},
                errors={}, sheet_properties=props([s]), today=TODAY, bootstrap=False)

    def test_unknown_condition_conflict_does_not_choose_silently(self):
        a, b = scan(200), scan(220)
        b.values['第二Delta門檻'] = .08
        with self.assertRaisesRegex(ValueError, '條件差異'):
            seed_targets([a, b])

    def test_a_new_expiration_enters_on_360_and_old_leaves_on_179(self):
        old = scan(180)
        target = seed_targets([old])[0]
        owner = {'id': 200, 'title': old.sheet_name, 'ticker': old.ticker, 'expiry': old.expiry.isoformat()}
        target['管理分頁JSON'] = json.dumps({old.scan_id: owner})
        entering = TODAY + timedelta(days=361)
        p = plan_rolling(scans=[old], targets=[target], expirations={'MU': [old.expiry, entering]},
            errors={}, sheet_properties=props([old]), today=TODAY + timedelta(days=1), bootstrap=False)
        self.assertEqual([v['到期日'] for v in p.scans], [entering.isoformat()])
        self.assertEqual(p.remove, [owner])

    def test_removing_target_does_not_revive_old_manual_scan(self):
        old = scan(200)
        p = plan_rolling(scans=[old], targets=[], expirations={}, errors={},
            sheet_properties=props([old]), today=TODAY, bootstrap=False)
        self.assertFalse(p.scans[0]['啟用'])

    def test_recreated_in_range_sheet_is_not_overwritten(self):
        old = scan(200)
        target = seed_targets([old])[0]
        target['管理分頁JSON'] = json.dumps({old.scan_id: {'id': 999, 'title': old.sheet_name,
            'ticker': old.ticker, 'expiry': old.expiry.isoformat()}})
        with self.assertRaisesRegex(ValueError, 'ID已改變'):
            plan_rolling(scans=[old], targets=[target], expirations={'MU': [old.expiry]},
                errors={}, sheet_properties=props([old]), today=TODAY, bootstrap=False)

    def test_open_interest_500_fails_501_passes(self):
        from app.alerts import evaluate_conditions
        target = seed_targets([scan(200)])[0]
        target['到期日'] = (TODAY + timedelta(days=200)).isoformat()
        s = ScanRecord.from_values(2, SCAN_HEADERS, [target.get(h, '') for h in SCAN_HEADERS])
        for stage in (s.first_threshold, s.second_threshold):
            for oi, passed in ((500, False), (501, True)):
                result = evaluate_conditions(conditions=stage, delta=-.05, spread_rate=.01,
                    annual_return=.10, open_interest=oi)
                self.assertEqual(result.matched, passed)


class Request:
    def __init__(self, value):
        self.value = value
    def execute(self):
        return self.value


class FakeRepository(RollingRepositoryMixin):
    def __init__(self, old):
        self.old = old
        for i, s in enumerate(old, 2): s.row_number = i
        self.spreadsheet_id = 'test'
        self.max_monitor_rows = 1000
        self.targets = []
        self.settings = {}
        self.properties = props(old)
        self.properties[SCAN_SHEET] = {'sheetId': 10, 'title': SCAN_SHEET,
            'gridProperties': {'rowCount': 1000, 'columnCount': 38}}
        self.service = self
        self.batches = []
        self.chain_header = CHAIN_HEADERS
    def spreadsheets(self): return self
    def values(self): return self
    def _execute(self, request): return request.execute()
    def get(self, **kwargs):
        if 'range' not in kwargs:
            return Request({'sheets': [{'properties': p} for p in self.properties.values()],
                'developerMetadata': [{'metadataKey': 'OPTION_ALERTS_ROLLING_MIGRATED', 'metadataValue': '1'}]
                    if self.settings.get('自動追蹤已移轉') else []})
        if AUTO_TARGET_SHEET in kwargs['range']:
            return Request({'values': copy.deepcopy(self.targets)})
        return Request({'values': [self.chain_header]})
    def batchUpdate(self, **kwargs):
        self.batches.append(kwargs['body']['requests'])
        return Request({})
    def load_scans(self): return SCAN_HEADERS, copy.deepcopy(self.old), []
    def load_settings(self): return self.settings
    def update_settings(self, values): self.settings.update(values)
    def _ensure_sheets(self, names, **kwargs):
        for name in names:
            if name not in self.properties:
                self.properties[name] = {'sheetId': len(self.properties) + 50, 'title': name,
                    'gridProperties': {'rowCount': 1000, 'columnCount': 40}}
    def _ensure_header(self, *args): pass
    def _serializable(self, value, header=''): return '' if value is None else value.isoformat() if isinstance(value, (date, datetime)) else value
    def append_system_log(self, *args): pass


class Provider:
    def __init__(self, dates, failure=False): self.dates, self.calls, self.failure = dates, 0, failure
    def fetch_expirations(self, ticker):
        self.calls += 1
        if self.failure: raise MarketDataError('unavailable')
        return self.dates


class RepositoryTests(unittest.TestCase):
    def test_atomic_archive_and_page_rotation(self):
        repo = FakeRepository([scan(179), scan(200)])
        result = repo.sync_rolling_scans(Provider([TODAY + timedelta(days=200), TODAY + timedelta(days=360)]), NOW, 'America/New_York')
        self.assertEqual((result['added'], result['removed']), (1, 1))
        batch = repo.batches[-1]
        self.assertTrue(any('appendCells' in r for r in batch))
        self.assertTrue(any('deleteSheet' in r for r in batch))
        self.assertEqual(sum('addSheet' in r for r in batch), 1)
        self.assertTrue(any('createDeveloperMetadata' in r for r in batch))
        forbidden = {'警示紀錄', '收盤Delta趨勢', '波動率趨勢', '通知佇列'}
        self.assertFalse(any(p['title'] in forbidden for p in repo.properties.values()
            if any(r.get('deleteSheet', {}).get('sheetId') == p['sheetId'] for r in batch)))

    def test_cached_expirations_do_not_requery_within_same_market_date(self):
        s = scan(200)
        repo = FakeRepository([s]); repo.settings['自動追蹤已移轉'] = True
        t = seed_targets([s])[0]
        t.update({'最近查詢日期': TODAY.isoformat(), '到期日JSON': json.dumps([s.expiry.isoformat()]),
            '管理分頁JSON': json.dumps({s.scan_id: {'id': 200, 'title': s.sheet_name,
                'expiry': s.expiry.isoformat(), 'ticker': 'MU'}})})
        repo.targets = [[t.get(h, '') for h in AUTO_TARGET_HEADERS]]
        provider = Provider([])
        result = repo.sync_rolling_scans(provider, NOW, 'America/New_York')
        self.assertEqual(provider.calls, 0)
        self.assertEqual(result['errors'], {})

    def test_changed_header_blocks_any_deletion_batch(self):
        repo = FakeRepository([scan(179)]); repo.chain_header = ['personal notes']
        with self.assertRaisesRegex(ValueError, '不是可確認'):
            repo.sync_rolling_scans(Provider([TODAY + timedelta(days=200)]), NOW, 'America/New_York')
        self.assertEqual(repo.batches, [])

    def test_recreated_same_name_sheet_is_not_deleted(self):
        s = scan(179)
        repo = FakeRepository([s]); repo.settings['自動追蹤已移轉'] = True
        target = seed_targets([s])[0]
        target['管理分頁JSON'] = json.dumps({s.scan_id: {'id': 999, 'title': s.sheet_name,
            'ticker': s.ticker, 'expiry': s.expiry.isoformat()}})
        repo.targets = [[target.get(h, '') for h in AUTO_TARGET_HEADERS]]
        with self.assertRaisesRegex(ValueError, 'ID已改變'):
            repo.sync_rolling_scans(Provider([TODAY + timedelta(days=200)]), NOW, 'America/New_York')
        self.assertEqual(repo.batches, [])

    def test_failed_yahoo_keeps_pages_and_reports_blocked_ticker(self):
        repo = FakeRepository([scan(179)])
        result = repo.sync_rolling_scans(Provider([], failure=True), NOW, 'America/New_York')
        self.assertIn('MU', result['errors'])
        self.assertFalse(any('deleteSheet' in r for r in repo.batches[-1]))

    def test_capacity_failure_does_not_delete_first(self):
        repo = FakeRepository([scan(179)])
        for i in range(200):
            repo.properties[f'personal{i}'] = {'sheetId': 1000 + i, 'title': f'personal{i}'}
        with self.assertRaisesRegex(ValueError, '200張'):
            repo.sync_rolling_scans(Provider([TODAY + timedelta(days=200)]), NOW, 'America/New_York')
        self.assertEqual(repo.batches, [])
