from decimal import Decimal

from ledger.report import summarize


def test_monthly_total():
    rows = [{"desc": "rent", "amount": "$1,200.00"}, {"desc": "refund", "amount": "(45.50)"},
            {"desc": "coffee", "amount": "$4.25"}, {"desc": "fee", "amount": "-$0.75"}]
    s = summarize(rows)
    assert s["skipped"] == []
    assert s["count"] == 4
    assert s["total"] == Decimal("1158.00")
