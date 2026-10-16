"""Totals per account from bank exports.  Implement account_totals(path) -> {account: Decimal}.

Three export formats, told apart by their header line (a UTF-8 byte-order mark may precede it):
  A  `date,account,description,amount`        comma-separated; amounts like "$1,234.56", "-$12.00"
  B  `Datum;Konto;Beschreibung;Betrag`        semicolon-separated, UTF-8 with BOM, CRLF line ends; German numbers:
                                              "1.234,56" (dot = thousands, comma = decimal), "-12,00"
  C  `posted<TAB>account<TAB>memo<TAB>amount` tab-separated; negatives have a TRAILING minus ("12.50-"); the file ends
                                              with a blank line and a summary row whose account is "TOTAL" - that row
                                              is not an account and must not be counted
In every format text fields may be quoted and may contain the separator, quotes ("" escaped) or newlines.
Totals must be exact to the cent: return Decimal values quantized to 0.01 (e.g. Decimal('12.30'), never 12.299999).
Any other header -> ValueError.
"""


def account_totals(path):
    raise NotImplementedError
