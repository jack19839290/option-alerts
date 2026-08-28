from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import Any

from .models import ChainSnapshot, OptionQuote


MAX_REASONABLE_DIVIDEND_YIELD = 0.20
YAHOO_PERCENT_POINT_RATE_SYMBOLS = {"^IRX", "^FVX", "^TNX", "^TYX"}


class MarketDataError(RuntimeError):
    pass


class RateLimitError(MarketDataError):
    pass


def _safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _safe_int(value: Any) -> int | None:
    number = _safe_float(value)
    return int(number) if number is not None else None


def _normalize_yahoo_rate(value: Any, symbol: str) -> float | None:
    """Convert Yahoo yield-index quotes into a decimal annual rate."""
    number = _safe_float(value)
    if number is None:
        return None
    if symbol.strip().upper() in YAHOO_PERCENT_POINT_RATE_SYMBOLS:
        return number / 100.0
    return number / 100.0 if abs(number) > 1.0 else number


def _select_dividend_yield(
    underlying: dict[str, Any], fallback: float
) -> tuple[float, str]:
    """Normalize Yahoo yield fields that use different units.

    ``trailingAnnualDividendYield`` is a decimal ratio, while
    ``dividendYield`` is expressed in percentage points.
    """
    candidates = [
        _safe_float(underlying.get("trailingAnnualDividendYield")),
        (
            value / 100.0
            if (value := _safe_float(underlying.get("dividendYield"))) is not None
            else None
        ),
    ]
    saw_invalid = False
    for candidate in candidates:
        if candidate is None:
            continue
        if 0 <= candidate <= MAX_REASONABLE_DIVIDEND_YIELD:
            return candidate, ""
        saw_invalid = True
    if saw_invalid:
        return fallback, "股息率資料異常，採用預設值"
    return fallback, ""


class YahooFinanceProvider:
    """Thin yfinance adapter. Imports yfinance lazily so core tests stay isolated."""

    def __init__(self, default_dividend_yield: float = 0.0):
        self.default_dividend_yield = default_dividend_yield
        self.risk_free_rate_source = "尚未取得"
        self.risk_free_rate_note = ""

    @staticmethod
    def _yf():
        import yfinance as yf

        return yf

    def fetch_risk_free_rate(self, symbol: str, fallback: float) -> float:
        self.risk_free_rate_source = "設定備援值"
        self.risk_free_rate_note = ""
        try:
            ticker = self._yf().Ticker(symbol)
        except Exception as exc:  # yfinance exposes several transport exceptions
            if self._is_rate_limit(exc):
                raise RateLimitError(str(exc)) from exc
            self.risk_free_rate_note = f"{symbol} 無法建立行情連線，採用備援利率"
            return fallback

        try:
            fast_info = ticker.fast_info
            for key in ("lastPrice", "last_price"):
                rate = _normalize_yahoo_rate(fast_info.get(key), symbol)
                if rate is not None:
                    self.risk_free_rate_source = f"{symbol} fast_info.{key}"
                    return rate
        except Exception as exc:
            if self._is_rate_limit(exc):
                raise RateLimitError(str(exc)) from exc

        try:
            history = ticker.history(period="5d", auto_adjust=False)
            close = history.get("Close") if history is not None else None
            if close is not None:
                valid_close = close.dropna()
                if not valid_close.empty:
                    rate = _normalize_yahoo_rate(valid_close.iloc[-1], symbol)
                    if rate is not None:
                        self.risk_free_rate_source = f"{symbol} 最近交易日 Close"
                        return rate
        except Exception as exc:
            if self._is_rate_limit(exc):
                raise RateLimitError(str(exc)) from exc

        self.risk_free_rate_note = f"{symbol} 即時值與最近收盤均無法取得，採用備援利率"
        return fallback

    def fetch_chain(self, ticker_symbol: str, expiry: date) -> ChainSnapshot:
        try:
            ticker = self._yf().Ticker(ticker_symbol)
            chain = ticker.option_chain(expiry.isoformat())
            underlying = chain.underlying or {}
            spot = self._underlying_price(ticker, underlying)
            dividend_yield, dividend_yield_note = _select_dividend_yield(
                underlying, self.default_dividend_yield
            )
            quotes = self._convert_frame(chain.calls, "CALL")
            quotes.extend(self._convert_frame(chain.puts, "PUT"))
            return ChainSnapshot(
                ticker=ticker_symbol,
                expiry=expiry,
                underlying_price=spot,
                dividend_yield=dividend_yield,
                quotes=quotes,
                dividend_yield_note=dividend_yield_note,
            )
        except Exception as exc:
            if self._is_rate_limit(exc):
                raise RateLimitError(str(exc)) from exc
            raise MarketDataError(f"{ticker_symbol} {expiry}: {exc}") from exc

    def _underlying_price(self, ticker: Any, underlying: dict[str, Any]) -> float | None:
        for key in ("regularMarketPrice", "postMarketPrice", "preMarketPrice"):
            value = _safe_float(underlying.get(key))
            if value is not None and value > 0:
                return value
        try:
            for key in ("lastPrice", "last_price"):
                value = _safe_float(ticker.fast_info.get(key))
                if value is not None and value > 0:
                    return value
            return None
        except Exception:
            return None

    def _convert_frame(self, frame: Any, option_type: str) -> list[OptionQuote]:
        if frame is None:
            return []
        quotes: list[OptionQuote] = []
        for _, row in frame.iterrows():
            last_trade = row.get("lastTradeDate")
            if hasattr(last_trade, "to_pydatetime"):
                last_trade = last_trade.to_pydatetime()
            if isinstance(last_trade, datetime) and last_trade.tzinfo is None:
                last_trade = last_trade.replace(tzinfo=timezone.utc)
            quotes.append(
                OptionQuote(
                    contract_symbol=str(row.get("contractSymbol") or ""),
                    option_type=option_type,
                    strike=_safe_float(row.get("strike")) or 0.0,
                    last_price=_safe_float(row.get("lastPrice")),
                    bid=_safe_float(row.get("bid")),
                    ask=_safe_float(row.get("ask")),
                    implied_volatility=_safe_float(row.get("impliedVolatility")),
                    volume=_safe_int(row.get("volume")),
                    open_interest=_safe_int(row.get("openInterest")),
                    last_trade_time=last_trade if isinstance(last_trade, datetime) else None,
                )
            )
        return quotes

    @staticmethod
    def _is_rate_limit(exc: Exception) -> bool:
        text = str(exc).lower()
        return "429" in text or "too many requests" in text or "rate limit" in text
