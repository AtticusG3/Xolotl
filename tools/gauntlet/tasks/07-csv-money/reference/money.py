"""Totals per account from bank exports (reference)."""
import csv
from decimal import Decimal, InvalidOperation

HEADERS = {("date", "account", "description", "amount"): ",", ("datum", "konto", "beschreibung", "betrag"): ";",
           ("posted", "account", "memo", "amount"): "\t"}


def _amount(fmt, s):
    s = s.strip()
    try:
        if fmt == ",":
            neg = s.startswith("-")
            s = s.lstrip("-").lstrip("$").replace(",", "")
            d = Decimal(s)
            return -d if neg else d
        if fmt == ";":
            neg = s.startswith("-")
            d = Decimal(s.lstrip("-").replace(".", "").replace(",", "."))
            return -d if neg else d
        neg = s.endswith("-")
        d = Decimal(s.rstrip("-"))
        return -d if neg else d
    except InvalidOperation:
        raise ValueError(f"bad amount {s!r}") from None


def account_totals(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        first = f.readline()
        for head, sep in HEADERS.items():
            cells = next(csv.reader([first], delimiter=sep))
            if tuple(c.strip().lower() for c in cells) == head:
                break
        else:
            raise ValueError("unknown export format")
        totals = {}
        for row in csv.reader(f, delimiter=sep):
            if not row or all(not c.strip() for c in row):
                continue
            acct = row[1].strip()
            if sep == "\t" and acct == "TOTAL":
                continue
            totals[acct] = totals.get(acct, Decimal("0")) + _amount(sep, row[3])
    return {k: v.quantize(Decimal("0.01")) for k, v in totals.items()}
