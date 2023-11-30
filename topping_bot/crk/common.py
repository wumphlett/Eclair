from decimal import Decimal
from typing import Union


def linear(start: Union[str, int], end: Union[str, int], lvls: int):
    step = (Decimal(end) - Decimal(start)) / (lvls - 1)
    return lambda x: start + step * (x - 1)
