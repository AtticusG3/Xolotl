"""Writes workspace/data/{bank_a.csv,bank_b.csv,bank_c.tsv}, hidden/extra_{a,b,c}.* and hidden/expected.json."""
import csv
import io
import json
import random
from decimal import Decimal

R = random.Random(77)
ACCTS = ["CHK-001", "SAV-002", "CRD-003", "BIZ-004"]


def rows(n):
    out = []
    for i in range(n):
        cents = R.randint(-250000, 900000) if R.random() < 0.85 else R.randint(-5, 5)
        memo = R.choice(["Coffee", "Rent, October", 'Refund "dup"', "Wire\nref 99", "Salary", "Fee; monthly", "ATM"])
        out.append((f"2026-10-{R.randint(1, 28):02d}", R.choice(ACCTS), memo, Decimal(cents) / 100))
    return out


def fmt_a(d):
    s = f"{abs(d):,.2f}"
    return ("-$" if d < 0 else "$") + s


def fmt_b(d):
    s = f"{abs(d):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if d < 0 else "") + s


def fmt_c(d):
    return f"{abs(d):.2f}" + ("-" if d < 0 else "")


def write(path, kind, data):
    buf = io.StringIO()
    if kind == "a":
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["date", "account", "description", "amount"])
        for r in data:
            w.writerow([r[0], r[1], r[2], fmt_a(r[3])])
        open(path, "w", newline="").write(buf.getvalue())
    elif kind == "b":
        w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
        w.writerow(["Datum", "Konto", "Beschreibung", "Betrag"])
        for r in data:
            w.writerow([r[0], r[1], r[2], fmt_b(r[3])])
        open(path, "w", newline="", encoding="utf-8-sig").write(buf.getvalue())
    else:
        w = csv.writer(buf, delimiter="\t", lineterminator="\n")
        w.writerow(["posted", "account", "memo", "amount"])
        for r in data:
            w.writerow([r[0], r[1], r[2], fmt_c(r[3])])
        total = sum((r[3] for r in data), Decimal(0))
        buf.write("\n")
        w.writerow(["", "TOTAL", "", fmt_c(total)])
        open(path, "w", newline="").write(buf.getvalue())


def totals(data):
    t = {}
    for r in data:
        t[r[1]] = t.get(r[1], Decimal("0.00")) + r[3]
    return {k: str(v.quantize(Decimal("0.01"))) for k, v in t.items()}


exp = {}
for name, kind, n, where in [("bank_a.csv", "a", 40, "workspace/data"), ("bank_b.csv", "b", 40, "workspace/data"),
                             ("bank_c.tsv", "c", 40, "workspace/data"), ("extra_a.csv", "a", 60, "hidden"),
                             ("extra_b.csv", "b", 60, "hidden"), ("extra_c.tsv", "c", 60, "hidden")]:
    d = rows(n)
    write(f"{where}/{name}", kind, d)
    exp[name] = totals(d)
json.dump(exp, open("hidden/expected.json", "w"), indent=1)
