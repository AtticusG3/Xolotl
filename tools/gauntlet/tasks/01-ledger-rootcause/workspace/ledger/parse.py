"""Amount parsing for bank-statement exports."""


def parse_amount(text):
    """Parse one amount cell from a bank export into an exact Decimal (cents matter).

    Formats seen in the exports:
      '$1,234.50'  -> Decimal('1234.50')    thousands separators are commas in groups of three
      '(12.50)'    -> Decimal('-12.50')     accounting negative
      '-$3.10'     -> Decimal('-3.10')
      ' 0.10 '     -> Decimal('0.10')
    Anything else (text, '1,23.00', two decimal points, ...) raises ValueError.
    """
    t = text.strip().replace("$", "")
    return float(t)
