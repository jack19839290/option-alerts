"""Pure planning for rolling option expirations. No writes or market requests here."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from .constants import AUTO_TARGET_HEADERS, SCAN_HEADERS
from .models import ScanRecord, as_bool


@dataclass
class RollingPlan:
    targets: list[dict[str, Any]]
    scans: list[dict[str, Any]]
    owners: dict[str, dict[str, Any]]
    remove: list[dict[str, Any]]
    errors: dict[str, str]
    bootstrap: bool


def put_conditions(values: dict[str, Any]) -> dict[str, Any]:
    result = dict(values)
    result.update({"顯示類型": "PUT", "CALL持股成本": "",
        "第二年化報酬率條件": "≥", "第二年化報酬率門檻": .10,
        "第一未平倉大於(口)": 500, "第二未平倉大於(口)": 500})
    return result


def seed_targets(scans: list[ScanRecord]) -> list[dict[str, Any]]:
    groups: dict[str, list[ScanRecord]] = {}
    for scan in scans:
        groups.setdefault(scan.ticker, []).append(scan)
    targets = []
    for ticker, group in sorted(groups.items()):
        normalized = [put_conditions(scan.values) for scan in group]
        # Conflicts the user resolved above are normalized before comparison.
        fields = [h for h in SCAN_HEADERS[4:23]]
        signatures = {json.dumps([row.get(h, "") for h in fields], ensure_ascii=False)
                      for row in normalized}
        if len(signatures) != 1:
            raise ValueError(f"{ticker} 仍有未確認的條件差異，請先統一設定")
        target = {h: normalized[0].get(h, "") for h in AUTO_TARGET_HEADERS}
        target.update({"股票代號": ticker, "啟用": any(s.enabled for s in group),
                       "最小DTE": 180, "最大DTE": 360})
        targets.append(target)
    return targets


def validate_target(target: dict[str, Any]) -> None:
    import re
    ticker = str(target.get("股票代號", ""))
    if not re.fullmatch(r"[A-Z0-9.^-]{1,15}", ticker):
        raise ValueError("自動追蹤股票代號格式不正確")
    if target.get("最小DTE") != 180 or target.get("最大DTE") != 360:
        raise ValueError(f"{ticker} 自動範圍須為180～360天")
    normalized = put_conditions(target)
    if any(target.get(h, "") != normalized.get(h, "") for h in (
        "顯示類型", "CALL持股成本", "第二年化報酬率條件", "第二年化報酬率門檻",
        "第一未平倉大於(口)", "第二未平倉大於(口)")):
        raise ValueError(f"{ticker} 須使用PUT、第二年化至少10%、兩階段未平倉大於500")
    values = dict(target, 到期日="2099-01-01")
    ScanRecord.from_values(2, SCAN_HEADERS, [values.get(h, "") for h in SCAN_HEADERS])


def plan_rolling(*, scans: list[ScanRecord], targets: list[dict[str, Any]],
                 expirations: dict[str, list[date]], errors: dict[str, str],
                 sheet_properties: dict[str, dict[str, Any]], today: date,
                 bootstrap: bool) -> RollingPlan:
    existing = {scan.scan_id: scan for scan in scans}
    if len(existing) != len(scans):
        raise ValueError("掃描ID重複，停止自動整理")
    if any(s.scan_id != f'{s.ticker}|{s.expiry.isoformat()}' for s in scans):
        raise ValueError('掃描ID與股票／到期日不符，停止自動移轉')
    if len({t['股票代號'] for t in targets}) != len(targets):
        raise ValueError("自動追蹤標的重複")
    owners, remove, output = {}, [], []
    target_tickers = {t['股票代號'] for t in targets}
    for target in targets:
        validate_target(target)
        ticker = target['股票代號']
        old = [scan for scan in scans if scan.ticker == ticker]
        owned = json.loads(target.get('管理分頁JSON') or '{}')
        if not isinstance(owned, dict):
            raise ValueError(f"{ticker} 管理分頁紀錄無效")
        if bootstrap:
            # Adopt only worksheets referenced by existing scan records.
            for scan in old:
                prop = sheet_properties.get(scan.sheet_name)
                if prop:
                    owned[scan.scan_id] = {'id': prop['sheetId'], 'title': scan.sheet_name,
                                          'expiry': scan.expiry.isoformat(), 'ticker': ticker}
        if ticker in errors or not as_bool(target['啟用']):
            output.extend(dict(s.values, 啟用=s.enabled and as_bool(target['啟用'])) for s in old)
            owners.update(owned)
            continue
        dates = sorted(set(expirations[ticker]))
        desired = {f"{ticker}|{d.isoformat()}": d for d in dates if 180 <= (d - today).days <= 360}
        if not desired:
            # Empty, even if Yahoo answered, is not proof that all pages should be deleted.
            errors[ticker] = '範圍內無可用到期日，保留舊分頁並暫停警示'
            output.extend(dict(s.values) for s in old)
            owners.update(owned)
            continue
        for key, owner in owned.items():
            expiry = date.fromisoformat(owner['expiry'])
            expected = ScanRecord.from_values(2, SCAN_HEADERS, [
                {"股票代號": ticker, "到期日": expiry, "顯示類型": "PUT"}.get(h, "")
                for h in SCAN_HEADERS])
            if key != f"{ticker}|{expiry.isoformat()}" or owner.get('title') != expected.sheet_name or owner.get('ticker') != ticker:
                raise ValueError(f"{ticker} 管理分頁身份不符，停止刪除")
            prop = sheet_properties.get(owner['title'])
            if prop and prop['sheetId'] != owner.get('id'):
                raise ValueError(f"{owner['title']} 分頁ID已改變，停止自動整理")
            if not 180 <= (expiry - today).days <= 360:
                remove.append(owner)
            else:
                owners[key] = owner
        for key, expiry in desired.items():
            prior = existing.get(key)
            values = dict(prior.values) if prior else {}
            for h in SCAN_HEADERS[:24]:
                if h in target:
                    values[h] = target[h]
            values.update({'啟用': True, '掃描ID': key, '股票代號': ticker, '到期日': expiry.isoformat()})
            parsed = ScanRecord.from_values(2, SCAN_HEADERS, [values.get(h, '') for h in SCAN_HEADERS])
            if prior is None:
                values.update({'狀態': '待抓取', '資料狀態': '等待雲端更新', '工作表': parsed.sheet_name})
            prop = sheet_properties.get(parsed.sheet_name)
            if prop and key not in owned:
                # An unregistered sheet with the same name belongs to the user.
                raise ValueError(f"{parsed.sheet_name} 尚未登記自動管理，停止以避免覆寫")
            output.append(values)
    # This version migrates all scans. Deleting a target row is not an instruction to delete its pages.
    output.extend(dict(s.values, 啟用=False) for s in scans if s.ticker not in target_tickers)
    return RollingPlan(targets, output, owners, remove, errors, bootstrap)
