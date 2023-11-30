import operator
from abc import ABC, abstractmethod
from decimal import Decimal
from heapq import nlargest, nsmallest

from pyparsing import (
    CaselessLiteral,
    Literal,
    MatchFirst,
    Opt,
    StringStart as Start,
    StringEnd as End,
    Word,
    nums,
    printables,
)

from topping_bot.crk.toppings import INFO, Type


SUBSTATS = MatchFirst(
    [CaselessLiteral(substat.value) for substat in sorted(list(INFO.keys()), key=lambda x: x.value, reverse=True)]
)
TARGET = Word(nums) + Opt("." + Word(nums))


class Operator:
    OPERATORS = {
        ">": operator.gt,
        "<": operator.lt,
        ">=": operator.ge,
        "<=": operator.le,
    }

    INVERSES = {">": "<", ">=": "<=", "<": ">", "<=": ">="}

    def __init__(self, op: str):
        self.str = op
        self.compare = self.OPERATORS[self.str]

    def __str__(self):
        return self.str

    def invert(self):
        return Operator(self.INVERSES[self.str])


class Validity(ABC):
    pass

    @abstractmethod
    def __str__(self):
        pass

    @classmethod
    @abstractmethod
    def parse(cls, req_str: str):
        pass

    @abstractmethod
    def convert(self, **kwargs):
        pass


class Normal(Validity):
    """
    DMG Resist >= 30
    """

    INEQUALITIES = MatchFirst([Literal(op) for op in (">=", "<=", ">", "<")])

    def __init__(self, substat: Type, op: Operator, target: Decimal):
        self.substat = substat
        self.op = op
        self.target = target

    def __str__(self):
        return f"{self.substat.value} {self.op} {self.target}"

    def __hash__(self):
        return hash((self.substat, self.op.str))

    @classmethod
    def parse(cls, req_str: str):
        if r := (Start() + SUBSTATS("substat") + cls.INEQUALITIES("op") + TARGET("target") + End()).search_string(
            req_str
        ):
            r = r[0].as_dict()
            return cls(Type(r["substat"]), Operator(r["op"]), Decimal("".join(r["target"])))
        elif r := (Start() + TARGET("target") + cls.INEQUALITIES("op") + SUBSTATS("substat") + End()).search_string(
            req_str
        ):
            r = r[0].as_dict()
            return cls(Type(r["substat"]), Operator(r["op"]).invert(), Decimal("".join(r["target"])))

    def convert(self, **kwargs):
        return [self]

    def fuzz(self):
        if self.op.str == ">":
            self.op = Operator(">=")
            self.target += Decimal("0.1")
        elif self.op.str == "<":
            self.op = Operator("<=")
            self.target -= Decimal("0.1")

        if self.target == Decimal("-0.1"):
            self.target = Decimal(0)


class Range(Validity):
    """
    27 <= Cooldown <= 29
    """

    LESS = MatchFirst([Literal(op) for op in ("<=", "<")])
    MORE = MatchFirst([Literal(op) for op in (">=", ">")])

    def __init__(self, l_target: Decimal, l_op: Operator, substat: Type, h_op: Operator, h_target: Decimal):
        self.substat = substat
        self.low_target = l_target
        self.low_op = l_op
        self.high_target = h_target
        self.high_op = h_op

    def __str__(self):
        return f"{self.low_target} {self.low_op} {self.substat.value} {self.high_op} {self.high_target}"

    @classmethod
    def parse(cls, req_str: str):
        if r := (
            Start()
            + TARGET("l_target")
            + cls.LESS("l_op")
            + SUBSTATS("substat")
            + cls.LESS("h_op")
            + TARGET("h_target")
            + End()
        ).search_string(req_str):
            r = r[0].as_dict()
            return cls(
                Decimal("".join(r["l_target"])),
                Operator(r["l_op"]),
                Type(r["substat"]),
                Operator(r["h_op"]),
                Decimal("".join(r["h_target"])),
            )
        elif r := (
            Start()
            + TARGET("l_target")
            + cls.MORE("l_op")
            + SUBSTATS("substat")
            + cls.MORE("h_op")
            + TARGET("h_target")
            + End()
        ).search_string(req_str):
            r = r[0].as_dict()
            return cls(
                Decimal("".join(r["h_target"])),
                Operator(r["h_op"]).invert(),
                Type(r["substat"]),
                Operator(r["l_op"]).invert(),
                Decimal("".join(r["l_target"])),
            )

    def convert(self, **kwargs):
        return [
            Normal(self.substat, self.low_op.invert(), self.low_target),
            Normal(self.substat, self.high_op, self.high_target),
        ]


class Equality(Validity):
    """
    Cooldown == 28.5
    """

    EQUALITY = MatchFirst([Literal(op) for op in ("==", "=")])

    def __init__(self, substat: Type, target: Decimal):
        self.substat = substat
        self.target = target

    def __str__(self):
        return f"{self.substat.value} == {self.target}"

    @classmethod
    def parse(cls, req_str: str):
        if r := (Start() + SUBSTATS("substat") + cls.EQUALITY + TARGET("target") + End()).search_string(req_str):
            r = r[0].as_dict()
            return cls(Type(r["substat"]), Decimal("".join(r["target"])))
        elif r := (Start() + TARGET("target") + cls.EQUALITY + SUBSTATS("substat") + End()).search_string(req_str):
            r = r[0].as_dict()
            return cls(Type(r["substat"]), Decimal("".join(r["target"])))

    def convert(self, **kwargs):
        if self.target == Decimal(0):
            return [
                Normal(self.substat, Operator("<="), self.target),
            ]
        else:
            return [
                Normal(self.substat, Operator(">="), self.target),
                Normal(self.substat, Operator("<="), self.target),
            ]


class Relative(Validity):
    """
    ATK SPD below Squid
    """

    RELATIVE = MatchFirst([CaselessLiteral(op) for op in ("above", "below")])

    def __init__(self, substat: Type, direction: str, cookie: str):
        self.substat = substat
        self.direction = direction
        self.cookie = cookie

    def __str__(self):
        return f"{self.substat.value} {self.direction} {self.cookie}"

    @classmethod
    def parse(cls, req_str: str):
        if r := (
            Start() + SUBSTATS("substat") + cls.RELATIVE("direction") + Word(printables + " ")("cookie") + End()
        ).search_string(req_str):
            r = r[0].as_dict()
            return cls(Type(r["substat"]), r["direction"], r["cookie"])

    def convert(self, cookies: dict, **kwargs):
        target = cookies[self.cookie].value(self.substat)
        if self.direction == "above":
            return [
                Normal(self.substat, Operator(">"), target),
            ]
        elif self.direction == "below":
            return [
                Normal(self.substat, Operator("<"), target),
            ]


if __name__ == "__main__":
    test = Normal.parse("Cooldown>28")
    print(test)
