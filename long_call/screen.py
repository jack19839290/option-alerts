from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_FLOOR
from zoneinfo import ZoneInfo

from app.greeks import calculate_greeks
from app.models import ChainSnapshot, OptionQuote
from app.pricing import calculate_mid, valid_price

MARKET_ZONE = ZoneInfo("America/New_York")
CENT = Decimal("0.01")


def decimal(value):
    return Decimal(str(value))


@dataclass(frozen=True)
class Thresholds:
    min_dte: int
    max_dte: int
    min_delta: Decimal
    min_cash: Decimal
    min_oi: int
    max_spread: Decimal
    max_cost: Decimal
    price_source: str

    @classmethod
    def from_cells(cls, values):
        dte_min, dte_max, delta, cash, oi, spread, cost = map(decimal, values[:7])
        source = str(values[7]).strip().title()
        numbers = (dte_min, dte_max, delta, cash, oi, spread, cost)
        if not all(value.is_finite() for value in numbers):
            raise ValueError("門檻必須是有限數字")
        if not (1 <= dte_min <= dte_max and all(x == int(x) for x in (dte_min, dte_max, oi)) and oi >= 0):
            raise ValueError("DTE 與 OI 須為整數，且最大 DTE 不得低於最小 DTE")
        if not (0 <= delta <= 1 and 0 <= cash <= 1 and 0 <= spread <= 2 and cost >= 0):
            raise ValueError("請確認 Delta 與百分比門檻，例如 8% 輸入 8%")
        if source not in {"Bid", "Mid", "Ask"}:
            raise ValueError("試算價來源須為 Bid、Mid 或 Ask")
        return cls(int(dte_min), int(dte_max), delta, cash, int(oi), spread, cost, source)


@dataclass
class Result:
    row: list
    passed: bool


def evaluate(chain: ChainSnapshot, quote: OptionQuote, thresholds: Thresholds,
             now: datetime, fetched_at: datetime, risk_free_rate: float) -> Result:
    dte = (chain.expiry - now.astimezone(MARKET_ZONE).date()).days
    mid = calculate_mid(quote.bid, quote.ask)
    spread = price = time_value = released = cash = cost = ceiling = delta = None
    problems = []
    if not thresholds.min_dte <= dte <= thresholds.max_dte:
        problems.append("DTE 不在範圍內")
    standard_symbol = f"{chain.ticker.replace('.', '').replace('-', '')}{chain.expiry:%y%m%d}C"
    if quote.contract_size != "REGULAR" or not quote.contract_symbol.startswith(standard_symbol):
        problems.append("非標準或無法確認交割股數")
    if mid is None:
        problems.append("Bid／Ask 缺漏或異常")
    else:
        bid, ask = decimal(quote.bid), decimal(quote.ask)
        midpoint = (bid + ask) / 2
        spread = (ask - bid) / midpoint
        price = {"Bid": bid, "Mid": midpoint, "Ask": ask}[thresholds.price_source]
        if spread > thresholds.max_spread:
            problems.append("Spread 超標")
    if quote.open_interest is None:
        problems.append("缺 OI")
    elif quote.open_interest < thresholds.min_oi:
        problems.append("OI 不足")
    if not valid_price(chain.underlying_price) or not valid_price(quote.strike):
        problems.append("股價或履約價無效")
    else:
        spot, strike = decimal(chain.underlying_price), decimal(quote.strike)
        intrinsic = max(spot - strike, Decimal(0))
        if strike >= spot:
            problems.append("非價內買權")
        if valid_price(quote.implied_volatility):
            greeks = calculate_greeks(
                option_type="CALL", spot=chain.underlying_price, strike=quote.strike,
                volatility=quote.implied_volatility, risk_free_rate=risk_free_rate,
                dividend_yield=chain.dividend_yield, expiry=chain.expiry, now=now,
            )
            delta = greeks.delta if greeks else None
        if price is not None:
            released = spot - price
            cash = released / spot
            time_value = price - intrinsic
            if cash < thresholds.min_cash:
                problems.append("釋放現金比例不足")
            if time_value < 0:
                problems.append("試算價低於內含價值")
            elif released > 0 and dte > 0:
                cost = time_value * 365 / (released * dte)
                if time_value * 365 > thresholds.max_cost * released * dte:
                    problems.append("年化資金成本超標")
            else:
                problems.append("無可釋放現金或天期無效")
        if dte > 0 and strike < spot:
            cost_limit = (intrinsic * 365 + thresholds.max_cost * dte * spot) / (365 + thresholds.max_cost * dte)
            cap = min(spot * (1 - thresholds.min_cash), cost_limit)
            limit = cap.quantize(CENT, rounding=ROUND_FLOOR)
            if 0 < limit < spot and limit >= intrinsic:
                ceiling = limit
    if delta is None:
        problems.append("缺可用 IV 或 Delta")
    elif decimal(delta) < thresholds.min_delta:
        problems.append("Delta 不足")
    row = [
        chain.ticker, chain.expiry.isoformat(), dte, quote.strike, delta, quote.open_interest,
        spread, cash, cost, ceiling, thresholds.price_source, price, chain.underlying_price,
        quote.bid, mid, quote.ask, time_value, released * 100 if released is not None else None,
        quote.contract_symbol, "；".join(problems) or "符合", fetched_at.isoformat(timespec="seconds"),
    ]
    return Result([float(value) if isinstance(value, Decimal) else value for value in row], not problems)
