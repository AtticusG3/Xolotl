"""Monthly statement summary."""
from .parse import parse_amount


def summarize(rows):
    """rows: [{'desc': str, 'amount': str}, ...] -> {'total', 'count', 'skipped'}.

    A row whose amount cannot be parsed is skipped (its desc listed in 'skipped'), never guessed.
    """
    total, count, skipped = 0, 0, []
    for r in rows:
        try:
            a = parse_amount(r["amount"])
        except ValueError:
            skipped.append(r["desc"])
            continue
        total += a
        count += 1
    return {"total": total, "count": count, "skipped": skipped}
