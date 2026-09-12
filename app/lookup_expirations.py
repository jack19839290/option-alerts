from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from .config import AppConfig
from .provider import MarketDataError, RateLimitError, YahooFinanceProvider
from .sheets import SheetsRepository


TICKER_PATTERN = re.compile(r"^[A-Z0-9.^-]{1,15}$")


def lookup(
    ticker: str,
    request_id: str,
    repository: Any,
    provider: YahooFinanceProvider,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    checked_at = now or datetime.now(timezone.utc)
    try:
        expirations = provider.fetch_expirations(ticker)
    except (RateLimitError, MarketDataError) as exc:
        repository.store_expiration_lookup(
            ticker=ticker,
            request_id=request_id,
            status="FAILED",
            checked_at=checked_at,
            error=str(exc),
        )
        return {"status": "error", "ticker": ticker, "reason": str(exc)}

    stored = repository.store_expiration_lookup(
        ticker=ticker,
        request_id=request_id,
        status="SUCCESS",
        checked_at=checked_at,
        expirations=expirations,
    )
    return {
        "status": "success" if stored else "superseded",
        "ticker": ticker,
        "expiration_count": len(expirations),
    }


def run() -> dict[str, Any]:
    ticker = os.environ.get("EXPIRATION_TICKER", "").strip().upper()
    request_id = os.environ.get("EXPIRATION_REQUEST_ID", "").strip()
    if not TICKER_PATTERN.fullmatch(ticker):
        return {"status": "error", "reason": "股票代號格式不正確"}
    if not request_id or len(request_id) > 100:
        return {"status": "error", "reason": "到期日查詢ID無效"}
    config = AppConfig.from_env()
    repository = SheetsRepository(config.spreadsheet_id, config.max_monitor_rows)
    return lookup(ticker, request_id, repository, YahooFinanceProvider())


def main() -> int:
    result = run()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    # Expected Yahoo lookup failures are written back for the dialog to show.
    # Unexpected exceptions still fail the workflow and remain visible in Actions.
    return 0 if result.get("status") in {"success", "superseded", "error"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
