from decimal import Decimal, ROUND_HALF_UP
CENTS = Decimal("0.01")
def decimal(value): return value if isinstance(value, Decimal) else Decimal(str(value))
def money(value): return decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)
def effective_hourly_rate(base_hourly, multiplier): return money(decimal(base_hourly) * decimal(multiplier))
def line_amount(hours, rate): return money(decimal(hours) * decimal(rate))
