"""Amount parsing for bank-statement exports."""
import re
from decimal import Decimal

_AMOUNT = re.compile(r"^(?P<sign>-)?\$?(?P<int>\d{1,3}(?:,\d{3})*|\d+)(?:\.(?P<frac>\d+))?$")


def parse_amount(text):
    """Parse one amount cell from a bank export into an exact Decimal (see the task for the formats)."""
    t = text.strip()
    neg = False
    if t.startswith("(") and t.endswith(")"):
        t, neg = t[1:-1].strip(), True
    m = _AMOUNT.match(t)
    if not m:
        raise ValueError(f"not an amount: {text!r}")
    if m.group("sign"):
        if neg:
            raise ValueError(f"two signs: {text!r}")
        neg = True
    digits = m.group("int").replace(",", "") + ("." + m.group("frac") if m.group("frac") else "")
    d = Decimal(digits)
    return -d if neg else d
