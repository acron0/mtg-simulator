"""Counted mana amounts: "{T}: Add {G} for each creature you control", "Add an amount of {G} equal to ~'s power",
"Add {C} for each charge counter on ~". A card carries ``mana_dyn`` and the engine asks ``dynamic_amount`` for
how much mana the permanent makes when it is tapped (or counted toward a payment)."""
import re

_SYM = r"\{[WUBRGC]\}"


def parse_dynamic(text: str) -> tuple:
    """The mana_dyn tuple for the text after "{T}: Add ", or () if the amount isn't a supported count."""
    m = re.fullmatch(_SYM + r" for each ([\w+/-]+) counter on ~", text)
    if m:
        return ("counters", m[1])
    m = re.fullmatch(r"an amount of " + _SYM + r" equal to the number of ([\w+/-]+) counters on ~", text)
    if m:
        return ("counters", m[1])
    if re.fullmatch(r"an amount of " + _SYM + r" equal to ~'s power", text):
        return ("power",)
    m = re.fullmatch(_SYM + r" for each (\w+) (you control|on the battlefield)", text)
    from .counting import known
    if m and known(m[1]):    # one type or subtype word: copies.fits can't test "with defender" or "power 4 or greater"
        return ("count", m[1], "battlefield" if m[2] == "you control" else "all")
    return ()


def parse_conditional(line: str):
    """(colour, base amount, mana_dyn) for "{T}: Add {C}. If C, add {C}{C} instead.", or None: the same colour
    either way, more of it while the condition holds (checked when the mana is made or counted)."""
    m = re.fullmatch(r"\{T\}: Add ((?:\{([WUBRGC])\})+)\. If (.+?), add ((?:\{([WUBRGC])\})+) instead\.", line)
    if not m or m[2] != m[5] or {*re.findall(r"[WUBRGC]", m[1] + m[4])} != {m[2]}:
        return None
    from .cx_condlib import parse
    code = parse(m[3])
    base, more = m[1].count("{"), m[4].count("{")
    return (m[2], base, ("cond", code, base, more)) if code and more > base else None


def dynamic_amount(perm) -> int:
    kind = perm.card.mana_dyn
    if kind[0] == "cond":
        from .cx_condlib import check
        game = perm.controller._game
        return kind[3] if check(game, perm.controller, kind[1], source=perm) else kind[2]
    if kind[0] == "power":
        return max(0, perm.power)
    if kind[0] == "counters":
        return perm.counters.get(kind[1], 0)
    from .counting import count
    return count(perm.controller._game, perm.controller, {"what": kind[1], "zone": kind[2]}, perm)
