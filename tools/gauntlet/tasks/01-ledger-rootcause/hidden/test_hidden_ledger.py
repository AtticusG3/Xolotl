from decimal import Decimal

import pytest

from ledger.parse import parse_amount
from ledger.report import summarize


@pytest.mark.parametrize("text,want", [("$1,234.50", "1234.50"), ("(12.50)", "-12.50"), ("-$3.10", "-3.10"),
                                       (" 0.10 ", "0.10"), ("($1,000.00)", "-1000.00"), ("$1,000,000.01", "1000000.01"),
                                       ("7", "7")])
def test_parse_exact(text, want):
    got = parse_amount(text)
    assert isinstance(got, Decimal) and got == Decimal(want)


@pytest.mark.parametrize("bad", ["abc", "1,23.00", "12,3456.00", "1.2.3", "", "$", "()", "--5"])
def test_parse_rejects(bad):
    with pytest.raises(ValueError):
        parse_amount(bad)


def test_total_is_exact_cents():
    rows = [{"desc": "a", "amount": "0.10"}, {"desc": "b", "amount": "0.20"}, {"desc": "c", "amount": "(0.30)"},
            {"desc": "d", "amount": "$0.10"}]
    s = summarize(rows)
    assert isinstance(s["total"], Decimal) and s["total"] == Decimal("0.10") and str(s["total"]) == "0.10"


def test_skips_malformed_not_guessed():
    rows = [{"desc": "ok", "amount": "$5.00"}, {"desc": "typo", "amount": "1,23.00"}, {"desc": "junk", "amount": "n/a"}]
    s = summarize(rows)
    assert s["skipped"] == ["typo", "junk"] and s["count"] == 1 and s["total"] == Decimal("5.00")
