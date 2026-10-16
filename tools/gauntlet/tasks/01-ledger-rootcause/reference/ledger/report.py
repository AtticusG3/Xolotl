"""Monthly statement summary."""
from decimal import Decimal

from .parse import parse_amount


def summarize(rows):
    """rows: [{'desc': str, 'amount': str}, ...] -> {'total', 'count', 'skipped'}."""
    total, count, skipped = Decimal("0.00"), 0, []
    for r in rows:
        try:
            a = parse_amount(r["amount"])
        except ValueError:
            skipped.append(r["desc"])
            continue
        total += a
        count += 1
    return {"total": total, "count": count, "skipped": skipped}
