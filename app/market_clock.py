from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class OptionSessionState:
    is_open: bool
    just_closed: bool
    market_open: datetime | None
    market_close: datetime | None


class MarketCalendarError(RuntimeError):
    """Official exchange-calendar lookup failed; automation must stop safely."""


def get_us_option_session_state(now: datetime | None = None,
                                market_timezone: str = "America/New_York",
                                close_grace_minutes: int = 90) -> OptionSessionState:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now_utc = now.astimezone(timezone.utc)
    local_now = now.astimezone(ZoneInfo(market_timezone))
    try:
        import pandas_market_calendars as mcal

        calendar = mcal.get_calendar("CBOE_Equity_Options")
        schedule = calendar.schedule(start_date=local_now.date().isoformat(),
                                     end_date=local_now.date().isoformat())
        if schedule.empty:
            return OptionSessionState(False, False, None, None)
        market_open = schedule.iloc[0]["market_open"].to_pydatetime()
        market_close = schedule.iloc[0]["market_close"].to_pydatetime()
        return OptionSessionState(
            market_open <= now_utc <= market_close,
            market_close < now_utc <= market_close + timedelta(minutes=close_grace_minutes),
            market_open,
            market_close,
        )
    except Exception as exc:
        raise MarketCalendarError(str(exc)) from exc
