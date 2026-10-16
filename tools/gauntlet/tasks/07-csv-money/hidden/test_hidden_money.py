"""Hidden grading: the documented contract of money.build_report (task 07)."""
import os
import shutil

import pytest

from money import build_report

HERE = os.path.dirname(os.path.abspath(__file__))
RATES = "base: USD\nUSD: 1.0000\nEUR: 1.0855\nGBP: 1.2700\nCHF: 1.4000\nJPY: 0.0067\nCAD: 0.7400\n"


def build(tmp_path, files):
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "rates.yaml").write_text(RATES)
    for name, text in files.items():
        (inp / name).write_text(text)
    out = tmp_path / "report.txt"
    build_report(str(inp), str(out))
    return out.read_text()


def section(text, name):
    body = text.split(f"[{name}]\n", 1)[1].split("\n[", 1)[0]
    return body.splitlines()[1:]  # drop the header row


def total_of(text):
    return text.split("[total]\n", 1)[1].split("\n", 1)[0]


def test_full_report_matches_expected(tmp_path):
    inp = tmp_path / "in"
    inp.mkdir()
    for name in os.listdir("data"):  # the workspace exports + rates.yaml
        shutil.copy(os.path.join("data", name), inp)
    for name in os.listdir(HERE):  # the extra exports the model never saw
        if name.startswith("extra_"):
            shutil.copy(os.path.join(HERE, name), inp)
    out = tmp_path / "report.txt"
    build_report(str(inp), str(out))
    assert out.read_text() == open(os.path.join(HERE, "expected_report.txt"), encoding="utf-8").read()


def test_dialect_a_parses_us_number(tmp_path):
    text = build(tmp_path, {"a.csv": 'date,account,description,amount\n2026-07-02,X,coffee,"1,234.56 USD"\n2026-07-02,X,fee,-12.34 USD\n'})
    assert section(text, "account-month") == ["X,2026-07,1222.22,2"]


def test_dialect_b_parses_german_number_and_bom(tmp_path):
    text = build(tmp_path, {"b.csv": "\ufeffDatum;Konto;Beschreibung;Betrag\r\n2026-08-09;Y;kauf;1.234,56 USD\r\n"})
    assert section(text, "account-month") == ["Y,2026-08,1234.56,1"]


def test_dialect_c_trailing_minus_and_total_row_skipped(tmp_path):
    text = build(tmp_path, {"c.tsv": "posted\taccount\tmemo\tamount\n2026-09-01\tZ\ta\t12.50- USD\n2026-09-01\tZ\tb\t2.50 USD\n\n\tTOTAL\t\t10.00- USD\n"})
    assert section(text, "account-month") == ["Z,2026-09,-10.00,2"]
    assert "TOTAL" not in text


def test_dialect_decided_by_header_not_delimiter(tmp_path):
    text = build(tmp_path, {"m.csv": "date;account;description;amount\n2026-07-04;M;x;9.99 USD\n"})
    assert section(text, "account-month") == ["M,2026-07,9.99,1"]


def test_rounding_is_per_row_not_at_the_total(tmp_path):
    text = build(tmp_path, {"r.csv": "date,account,description,amount\n2026-09-05,F,a,0.01 CHF\n2026-09-06,F,a,0.01 CHF\n"})
    assert section(text, "account-month") == ["F,2026-09,0.02,2"]  # 0.01+0.01, not quantize(0.028)=0.03
    assert total_of(text) == "USD,0.02"


def test_duplicates_dropped_and_listed_in_order(tmp_path):
    text = build(tmp_path, {"d.csv": "date,account,description,amount\n2026-07-01,D,a,5.00 USD\n2026-07-02,D,b,5.00 USD\n2026-07-03,D,c,5.00 USD\n2026-07-01,D,dup,5.00 USD\n"})
    assert section(text, "account-month") == ["D,2026-07,15.00,3"]
    assert section(text, "duplicates") == ["d.csv,2026-07-01,D,5.00"]


def test_currency_is_normalised_to_base(tmp_path):
    text = build(tmp_path, {"n.csv": "date,account,description,amount\n2026-07-01,H,a,1.23 USD\n2026-07-02,I,a,4.56 EUR\n"})
    assert total_of(text) == "USD,6.18"  # 1.23 + (4.56 * 1.0855 -> 4.95)


def test_account_and_month_ordering(tmp_path):
    text = build(tmp_path, {"o.csv": "date,account,description,amount\n2026-09-01,B,a,1.00 USD\n2026-08-01,B,a,1.00 USD\n2026-09-01,A,a,1.00 USD\n2026-08-01,A,a,1.00 USD\n"})
    assert section(text, "account-month") == ["A,2026-08,1.00,1", "A,2026-09,1.00,1", "B,2026-08,1.00,1", "B,2026-09,1.00,1"]
    assert section(text, "account") == ["A,2.00,2", "B,2.00,2"]


def test_amounts_are_two_decimals(tmp_path):
    text = build(tmp_path, {"f.csv": "date,account,description,amount\n2026-07-01,G,a,5 USD\n"})
    assert section(text, "account-month") == ["G,2026-07,5.00,1"]


def test_unknown_header_raises(tmp_path):
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "rates.yaml").write_text(RATES)
    (inp / "x.csv").write_text("when,who,what,how much\n2026-01-01,a,b,1 USD\n")
    with pytest.raises(ValueError):
        build_report(str(inp), str(tmp_path / "o.txt"))


def test_unknown_currency_raises(tmp_path):
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "rates.yaml").write_text(RATES)
    (inp / "x.csv").write_text("date,account,description,amount\n2026-01-01,a,b,1.00 XXX\n")
    with pytest.raises(ValueError):
        build_report(str(inp), str(tmp_path / "o.txt"))
