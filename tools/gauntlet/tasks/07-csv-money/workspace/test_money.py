from decimal import Decimal

from money import account_totals


def test_bank_a_has_all_accounts():
    t = account_totals("data/bank_a.csv")
    assert set(t) <= {"CHK-001", "SAV-002", "CRD-003", "BIZ-004"} and len(t) >= 3
    assert all(isinstance(v, Decimal) for v in t.values())
