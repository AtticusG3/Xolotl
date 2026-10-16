"""Monthly statement summary - THE TRAP: normalise the text here instead of fixing parse_amount."""
from .parse import parse_amount


def summarize(rows):
    total, count, skipped = 0, 0, []
    for r in rows:
        raw = r["amount"].strip().replace(",", "")
        if raw.startswith("(") and raw.endswith(")"):
            raw = "-" + raw[1:-1]
        try:
            a = parse_amount(raw)
        except ValueError:
            skipped.append(r["desc"])
            continue
        total += a
        count += 1
    return {"total": total, "count": count, "skipped": skipped}
