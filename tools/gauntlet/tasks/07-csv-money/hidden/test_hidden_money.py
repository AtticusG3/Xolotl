import json
import os
from decimal import Decimal

import pytest

from money import account_totals

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = json.load(open(os.path.join(HERE, "expected.json")))


@pytest.mark.parametrize("name", ["bank_a.csv", "bank_b.csv", "bank_c.tsv", "extra_a.csv", "extra_b.csv", "extra_c.tsv"])
def test_exact_totals(name):
    path = os.path.join("data", name) if name.startswith("bank") else os.path.join(HERE, name)
    got = account_totals(path)
    assert {k: str(v) for k, v in got.items()} == EXP[name]
    assert all(isinstance(v, Decimal) and v == v.quantize(Decimal("0.01")) for v in got.values())


def test_unknown_header(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("when,who,what,how much\n2026-01-01,a,b,1\n")
    with pytest.raises(ValueError):
        account_totals(str(p))
