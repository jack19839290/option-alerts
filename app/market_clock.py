from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo


def is_us_regular_session(
    now: datetime | None = None, market_timezone: str = "America/New_York"
) -> bool:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    local_now = now.astimezone(ZoneInfo(market_timezone))

    try:
        import pandas_market_calendars as mcal

        calendar = mcal.get_calendar("NYSE")
        schedule = calendar.schedule(
            start_date=local_now.date().isoformat(), end_date=local_now.date().isoformat()
        )
        if schedule.empty:
            return False
        market_open = schedule.iloc[0]["market_open"].to_pydatetime()
        market_close = schedule.iloc[0]["market_close"].to_pydatetime()
        return market_open <= now.astimezone(timezone.utc) <= market_close
    except Exception:
        return (
            local_now.weekday() < 5
            and time(9, 30) <= local_now.time().replace(tzinfo=None) <= time(16, 0)
        )

