"""Conservative documentary numbers; preserve ambiguous spellings as unknown."""
from decimal import Decimal,InvalidOperation
import re


def number(value,*,integer=False):
    if not isinstance(value,str):return None
    value=value.strip()
    if integer:
        # Counts have no decimal fraction. Brazilian thousands groups are
        # explicit; never shrink 1.000 to one or interpret comma fractions.
        if not re.fullmatch(r'(?:[0-9]+|[1-9][0-9]{0,2}(?:\.[0-9]{3})+)',value):return None
        value=value.replace('.','')
    else:
        # Dot with three trailing digits is locale-ambiguous for a weight.
        # Keep its literal source instead of claiming an official magnitude.
        if re.fullmatch(r'[0-9]+\.[0-9]{3}',value):return None
        if re.fullmatch(r'[0-9]{1,3}(?:\.[0-9]{3})+,[0-9]+',value):value=value.replace('.','')
        elif not re.fullmatch(r'[0-9]+(?:[.,][0-9]+)?',value):return None
        value=value.replace(',','.')
    try:
        numeric=Decimal(value)
        if not numeric.is_finite() or numeric<0 or numeric>(10000 if integer else 1000):return None
        return int(numeric) if integer else float(numeric) if numeric>0 else None
    except (InvalidOperation,ValueError):return None
