import operator as op
from typing import List, Tuple

import pyparsing as pp

from topping_bot.optimize.reader import read_toppings
from topping_bot.optimize.toppings import INFO, Resonance, Topping, Type
from topping_bot.util.image import toppings_to_images


OPERATORS = {
    "eq": op.eq,
    "ne": op.ne,
    "in": op.contains,
    "ni": lambda a, b: not op.contains(a, b),
}


class Grammar:
    def __init__(self):
        eq = pp.one_of("is ==", caseless=True)
        ne = pp.CaselessLiteral("is not") | pp.CaselessLiteral("!=")
        comp = ne("ne") | eq("eq")
        pres = pp.CaselessLiteral("not in")("ni") | pp.CaselessLiteral("in")("in")

        resonances = pp.MatchFirst([pp.CaselessLiteral(res.value) for res in Resonance])("resonance")
        substats = pp.MatchFirst(
            [
                pp.CaselessLiteral(substat.value)
                for substat in sorted(list(INFO.keys()), key=lambda x: x.value, reverse=True)
            ]
        )("substat")
        ids = pp.Word(pp.nums)("id")

        # res is Moonkissed | resonance in (Trio, Tropical Rock)
        resonance = pp.Group(
            pp.one_of("resonance res", caseless=True)("topping.resonance")
            + (comp + resonances | pres + self.tuple(resonances))
        )("specifier.resonance")
        # flav == ATK | flavor in (DMG Resist, CRIT%)
        flavor = pp.Group(
            pp.one_of("flavor flav", caseless=True)("topping.flavor") + (comp + substats | pres + self.tuple(substats))
        )("specifier.flavor")
        # ATK in subs | (ATK SPD, Cooldown) in substats
        substat = pp.Group(
            (substats | self.tuple(substats)) + pres + pp.one_of("substats subs sub", caseless=True)("topping.substats")
        )("specifier.substat")
        # id is 15 | id in (34, 38) | (45, 46, 47, 48) | 65, 66, 67, 68, 69
        tid = pp.Group(
            pp.CaselessLiteral("id")("topping.id") + (comp + ids | pres + self.tuple(ids))
            | self.tuple(ids)
            | pp.delimited_list(ids, delim=" ", allow_trailing_delim=True).leave_whitespace()
        )("specifier.id")
        # duplicates
        duplicate = pp.Group(pp.one_of("duplicates duplicate dups dup", caseless=True)("topping.duplicate"))(
            "specifier.duplicate"
        )

        identifiers = resonance | flavor | substat | tid | duplicate
        query = pp.infix_notation(
            identifiers,
            [
                (pp.CaselessLiteral("not")("not"), 1, pp.opAssoc.RIGHT),
                (pp.CaselessLiteral("and")("and"), 2, pp.opAssoc.LEFT),
                (pp.CaselessLiteral("or")("or"), 2, pp.opAssoc.LEFT),
            ],
            lpar="(",
            rpar=")",
        )
        self.grammar = pp.StringStart() + query + pp.StringEnd()

    @staticmethod
    def tuple(expr):
        lpar = pp.Literal("(").suppress()
        rpar = pp.Literal(")").suppress()

        return pp.Group(lpar + pp.delimited_list(expr, allow_trailing_delim=True) + rpar)("Tuple")

    def parse(self, query: str):
        return self.grammar.parse_string(query)

    def filter_topping(self, parsed: pp.ParseResults, idx: int, topping: Topping, toppings: List[Topping]):
        if len(parsed) == 1:
            return self.one_atom(parsed, idx, topping, toppings)
        elif len(parsed) == 2:
            return self.two_atoms(parsed, idx, topping, toppings)
        elif len(parsed) == 3:
            return self.three_atoms(parsed, idx, topping, toppings)
        raise ValueError

    def one_atom(self, parsed: pp.ParseResults, idx: int, topping: Topping, toppings: List[Topping]):
        """Simple atom wrapper"""
        if parsed.get_name() == "specifier.id":
            return self.eval_id_spec(parsed, idx, topping)
        elif parsed.get_name() == "specifier.duplicate":
            return self.eval_duplicate_spec(parsed, idx, topping, toppings)
        return self.filter_topping(parsed[0], idx, topping, toppings)

    def two_atoms(self, parsed: pp.ParseResults, idx: int, topping: Topping, toppings: List[Topping]):
        """Unary operator"""
        if parsed[0] == "not":
            return not self.filter_topping(parsed[1], idx, topping, toppings)
        raise ValueError

    def three_atoms(self, parsed: pp.ParseResults, idx: int, topping: Topping, toppings: List[Topping]):
        """Binary operator or specifier"""
        if parsed[1] == "and":
            return self.filter_topping(parsed[0], idx, topping, toppings) and self.filter_topping(
                parsed[2], idx, topping, toppings
            )
        elif parsed[1] == "or":
            return self.filter_topping(parsed[0], idx, topping, toppings) or self.filter_topping(
                parsed[2], idx, topping, toppings
            )
        else:
            return self.eval_specifier(parsed, idx, topping)

    def eval_specifier(self, parsed: pp.ParseResults, idx: int, topping: Topping):
        """Eval topping filter"""
        if parsed.get_name() == "specifier.resonance":
            return self.eval_resonance_spec(parsed, topping)
        elif parsed.get_name() == "specifier.flavor":
            return self.eval_flavor_spec(parsed, topping)
        elif parsed.get_name() == "specifier.substat":
            return self.eval_substat_spec(parsed, topping)
        elif parsed.get_name() == "specifier.id":
            return self.eval_id_spec(parsed, idx, topping)

    @staticmethod
    def eval_resonance_spec(parsed: pp.ParseResults, topping: Topping):
        """Eval topping resonance filter"""
        operator, operand = list(parsed.as_dict())[1], parsed[-1]
        operand = (
            tuple(Resonance(r) for r in operand)
            if any(o in parsed.as_dict() for o in ("in", "ni"))
            else Resonance(operand)
        )
        return OPERATORS[operator](operand, topping.resonance)

    @staticmethod
    def eval_flavor_spec(parsed: pp.ParseResults, topping: Topping):
        """Eval topping flavor filter"""
        operator, operand = list(parsed.as_dict())[1], parsed[-1]
        operand = tuple(Type(t) for t in operand) if any(o in parsed.as_dict() for o in ("in", "ni")) else Type(operand)
        return OPERATORS[operator](operand, topping.flavor)

    @staticmethod
    def eval_substat_spec(parsed: pp.ParseResults, topping: Topping):
        """Eval topping substat filter"""
        operand, operator = parsed[0], list(parsed.as_dict())[1]
        if type(operand) == str:
            operand = [operand]
        operand = tuple(Type(s) for s in operand)
        substats = list(s for s, v in topping.substats[1:])
        return all(OPERATORS[operator](substats, s) for s in operand)

    def eval_id_spec(self, parsed: pp.ParseResults, idx: int, topping: Topping):
        """Eval topping id filter"""
        if type(parsed[0]) != str:
            return self.eval_id_spec(parsed[0], idx, topping)

        operand = parsed[-1] if type(parsed[-1]) == list else parsed
        operand = tuple(int(i) for i in operand)
        return idx in operand

    def eval_duplicate_spec(self, parsed: pp.ParseResults, idx: int, topping: Topping, toppings: List[Topping]):
        """Eval topping duplicate filter"""
        return topping in toppings[:idx]


GRAMMAR = Grammar()


class Inventory:
    def __init__(self, toppings: List[Tuple[int, Topping]]):
        self.toppings: List[Tuple[int, Topping]] = toppings

    @classmethod
    def from_file(cls, fp):
        return cls(list(enumerate(read_toppings(fp))))

    def to_images(self, tmp_prefix):
        return toppings_to_images(self.toppings, tmp_prefix, show_index=True)

    def filter(self, query):
        parsed = GRAMMAR.parse(query)
        toppings = list(t for i, t in self.toppings)
        return Inventory(list((i, t) for i, t in self.toppings if GRAMMAR.filter_topping(parsed, i, t, toppings)))
