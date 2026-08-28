from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class OptionSessionState:
    is_open: bool
    just_closed: bool
    market_open: datetime | None
    market_close: datetime | None


def get_us_option_session_state(
    now: datetime | None = None,
    market_timezone: str = "America/New_York",
    close_grace_minutes: int = 60,
) -> OptionSessionState:
    """Return the CBOE equity-options session state, including a close grace window."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now_utc = now.astimezone(timezone.utc)
    local_now = now.astimezone(ZoneInfo(market_timezone))

    try:
        import pandas_market_calendars as mcal

        calendar = mcal.get_calendar("CBOE_Equity_Options")
        schedule = calendar.schedule(
            start_date=local_now.date().isoformat(), end_date=local_now.date().isoformat()
        )
        if schedule.empty:
            return OptionSessionState(False, False, None, None)
        market_open = schedule.iloc[0]["market_open"].to_pydatetime()
        market_close = schedule.iloc[0]["market_close"].to_pydatetime()
        is_open = market_open <= now_utc <= market_close
        just_closed = market_close < now_utc <= market_close + timedelta(
            minutes=close_grace_minutes
        )
        return OptionSessionState(is_open, just_closed, market_open, market_close)
    except Exception:
        weekday = local_now.weekday() < 5
        local_time = local_now.time().replace(tzinfo=None)
        open_time = time(9, 30)
        close_time = time(16, 0)
        is_open = weekday and open_time <= local_time <= close_time
        local_close = datetime.combine(local_now.date(), close_time, tzinfo=local_now.tzinfo)
        just_closed = weekday and local_close < local_now <= local_close + timedelta(
            minutes=close_grace_minutes
        )
        return OptionSessionState(is_open, just_closed, None, None)


def is_us_regular_session(
    now: datetime | None = None, market_timezone: str = "America/New_York"
) -> bool:
    return get_us_option_session_state(now, market_timezone).is_open
