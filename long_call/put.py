import json
from decimal import Decimal
from pathlib import Path

from app.greeks import calculate_greeks, time_to_expiry_years
from app.pricing import calculate_mid, valid_price

from .screen import MARKET_ZONE, decimal

SCHEMA = json.loads(Path(__file__).with_name("put_schema.json").read_text(encoding="utf-8"))
FILTERS = SCHEMA["filters"]
SETTINGS = ["啟用標的", "股票代號"] + [
    header for name, fields in FILTERS for header in [f"啟用 {name}", *(field[0] for field in fields)]
]
DEFAULTS = [item for _, fields in FILTERS for item in [True, *(field[1] for field in fields)]]
HEADERS = SCHEMA["contracts"] + [
    f"跌 {drop}% {name}" for drop in SCHEMA["drops"] for name in SCHEMA["scenario"]
]
PENDING = "行情待確認"
FAILED = "未符合"
PASSED = "符合條件"


def thresholds(values):
    result = {}
    i = 0
    for name, fields in FILTERS:
        enabled, *raw = values[i:i + len(fields) + 1]
        if not isinstance(enabled, bool):
            raise ValueError(f"{name} 開關須為核取方塊")
        numbers = []
        for value, (label, _, low, high, *kind) in zip(raw, fields, strict=True):
            number = decimal(value)
            if (not number.is_finite() or number < decimal(low)
                    or (high is not None and number > decimal(high))
                    or (kind == ["int"] and number != number.to_integral_value())):
                raise ValueError(f"{label} 無效")
            numbers.append(number)
        if len(numbers) == 2 and numbers[0] > numbers[1]:
            raise ValueError(f"{name} 下限不得大於上限")
        result[name] = tuple(numbers) if enabled else None
        i += len(fields) + 1
    return result


def timestamp(value, zone=None):
    if value is None:
        return None
    return (value.astimezone(zone) if zone else value).isoformat(timespec="seconds")


def evaluate(chain, quote, limits, now, fetched, rate):
    spot = decimal(chain.underlying_price) if valid_price(chain.underlying_price) else None
    strike = decimal(quote.strike) if valid_price(quote.strike) else None
    ask = decimal(quote.ask) if valid_price(quote.ask) else None
    bid = decimal(quote.bid) if valid_price(quote.bid) else None
    years, dte = time_to_expiry_years(chain.expiry, now)
    expected = f"{chain.ticker.replace('.', '').replace('-', '')}{chain.expiry:%y%m%d}P"
    standard = (quote.contract_size == "REGULAR" and quote.contract_symbol.startswith(expected)
                and len(quote.contract_symbol) == len(expected) + 8
                and quote.contract_symbol[-8:].isdigit())
    spread = (ask - bid) * 2 / (ask + bid) if calculate_mid(quote.bid, quote.ask) is not None else None
    greeks = None
    if spot and strike and valid_price(quote.implied_volatility):
        greeks = calculate_greeks(
            option_type="PUT", spot=float(spot), strike=float(strike),
            volatility=quote.implied_volatility, risk_free_rate=rate,
            dividend_yield=chain.dividend_yield, expiry=chain.expiry, now=now,
        )

    notes = ["Yahoo 未提供 Put Bid／Ask 報價時間"]
    if chain.underlying_time is None:
        notes.append("缺正股報價時間")
    if spread is None:
        notes.append("Bid／Ask 缺漏、無正 Bid 或報價倒掛")
    if greeks is None:
        notes.append("無可用模型 Greeks")
    if quote.open_interest is None:
        notes.append("缺 OI")
    else:
        notes.append("Yahoo 未提供 OI 日期")

    quality = []
    if not standard:
        quality.append("無法確認標準 100 股交割")
    if not spot or not strike or not ask:
        quality.append("股價、履約價或 Ask 無效")
    if years <= 0:
        quality.append("合約已到期")
    if spot and strike and ask and ask < strike - spot:
        quality.append("Ask 低於內含價值，請核對不同步報價")
    crossed = ask is not None and bid is not None and ask < bid
    if crossed:
        quality.append("Bid 高於 Ask")

    premium = annual = maximum = None
    scenarios = [None] * (len(SCHEMA["drops"]) * len(SCHEMA["scenario"]))
    if not quality:
        premium = ask / spot
        annual = premium * 365 / dte if dte > 0 else None
        maximum = (spot - strike + ask) / spot if strike <= spot else None
        scenarios = []
        for drop in SCHEMA["drops"]:
            expiry_spot = spot * (1 - Decimal(drop) / 100)
            stock_pl = (expiry_spot - spot) * 100
            put_pl = (max(strike - expiry_spot, Decimal(0)) - ask) * 100
            combined = stock_pl + put_pl
            scenarios.extend([stock_pl, put_pl, combined, combined / (spot * 100), put_pl / -stock_pl])

    delta = greeks.delta if greeks else None
    failures = []
    for name, value in (
        ("DTE", dte), ("Delta", delta), ("OI", quote.open_interest), ("Spread", spread),
        ("保費率", premium), ("年化成本", annual), ("最大跌幅", maximum),
    ):
        bounds = limits[name]
        if bounds is None:
            continue
        if value is None:
            quality.append(f"{name} 無法判定" + ("（K > S）" if name == "最大跌幅" and spot and strike and strike > spot else ""))
        elif len(bounds) == 2 and not bounds[0] <= decimal(value) <= bounds[1]:
            failures.append(f"{name} 超出範圍")
        elif len(bounds) == 1 and (decimal(value) < bounds[0] if name == "OI" else decimal(value) > bounds[0]):
            failures.append("OI 不足" if name == "OI" else f"{name} 超標")

    status = FAILED if failures else PENDING
    row = [
        chain.ticker, chain.expiry.isoformat(), dte, strike, maximum,
        ask * 100 if ask and standard and not crossed else None, premium, annual,
        strike / spot if spot and strike else None,
        spot, bid, ask, bid * 100 if bid and standard and not crossed and years > 0 else None,
        delta, greeks.gamma if greeks else None, greeks.theta_per_day if greeks else None,
        greeks.vega_per_pct if greeks else None, quote.implied_volatility, quote.open_interest, quote.volume,
        spread, quote.contract_symbol, status, "；".join(failures + quality),
        "；".join(notes), timestamp(chain.underlying_time, MARKET_ZONE), None,
        timestamp(quote.last_trade_time), timestamp(fetched), rate, chain.dividend_yield, chain.dividend_yield_note,
        *scenarios,
    ]
    return [float(value) if isinstance(value, Decimal) else value for value in row]
