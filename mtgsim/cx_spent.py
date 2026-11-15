"""Mana-spent conditions written after their effect (#324).

"<Effect> if {G} was spent to cast ~." and the paired form "<A> if {R} was spent to cast ~ and <B> if {G} was
spent to cast ~." (Firespout, Repel Intruders, Torrent of Souls) are rewritten to the leading form "If <cond>,
<effect>." that the condition library (cx_condlib) already reads, one sentence per clause, so each half is
checked on resolution against the colours the spell's payment recorded. A clause is only moved when the
condition library knows its condition; otherwise the Oracle text stays as it was and stays unmatched.
"""
from __future__ import annotations

import re

# a mana-spent condition, ending at "spent to cast ~"
_SPENT = (r"(?:(?:\{[WUBRG]\})+|at least \w+ (?:white |blue |black |red |green |colorless )?mana(?: of the same color)?"
          r"|no (?:colored )?mana|\w+ or more (?:colors of )?mana) (?:was|were) spent to cast (?:~|it|this spell)")


def _lead(effect: str, cond: str):
    from .cards import _parse_effects
    from .cx_condlib import parse
    if not parse(cond):
        return None
    sentence = f"If {cond}, {effect}."
    effects, bad = _parse_effects(sentence)
    # only when the moved clause really parses: otherwise another template may read the whole sentence
    return sentence if effects and not bad else None


def _move(m):
    first = _lead(m[1], m[2])
    if first is None:
        return m[0]
    if not m[3]:
        return first
    second = m[3]
    elided = re.match(r"(?:\d+|x|an?|one|two|three|four|five) ", second, re.I)
    if elided:      # "~ deals 3 damage to A if ... and 3 damage to B if ...": the verb is the first clause's
        verb = re.match(r"(.+?)\b(?:\d+|X|an?|one|two|three|four|five) ", m[1])
        if verb is None:
            return m[0]
        second = verb[1] + second
    second = _lead(second, m[4])
    return m[0] if second is None else f"{first} {second}"


SUBS = [
    (re.compile(r"(?:^|(?<=\. ))([A-Z~](?:(?! if )[^.])*?) if (" + _SPENT + r")(?:,? and ((?:(?! if )[^.])+?) if (" + _SPENT + r"))?\.",
                re.I), _move),
]
