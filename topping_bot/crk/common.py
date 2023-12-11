from decimal import Decimal
from typing import Union


def linear(start: Union[str, int], end: Union[str, int], lvls: int):
    start, end = Decimal(start), Decimal(end)
    step = (end - start) / (lvls - 1)
    return lambda x: start + step * (x - 1)
