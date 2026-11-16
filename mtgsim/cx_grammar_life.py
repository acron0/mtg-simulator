"""Grammar verbs: a life total set to a number (#629).

    Double target player's life total.                                                       (Beacon of Immortality)
    Target player's life total becomes 20.                                                   (Blessed Wind)
    If your life total is less than 7, your life total becomes 7.                            (Angel's Grace riders)
    Each player's life total becomes the lowest life total among all players.                (Repay in Kind)

The possessive sentence is rewritten (SUBS) to a private verb ("target player lifetotalbecomes 20",
"you lifetotaldoubles") so the grammar's player subjects read it; the verb is the ``set_life`` kind inside the usual
cx_players wrapper. Setting a life total is gaining or losing the difference (CR 119.5): ``Game.change_life`` does
it, so life-gain / life-loss triggers and replacements apply. "the lowest / highest life total among all players"
is read when the effect resolves.

AI: a target player for "life total becomes N" is ourselves when N is at least the starting life total (20), else
the opponent (``side``); "double" is ourselves. ``ai_value("set_life")`` values the change for each named player.
"""
from __future__ import annotations

import re

from .cx_grammar import Part, ai_value, verb

_WHO = r"(your|target player's|target opponent's|each player's|each opponent's|its controller's|that player's)"
_SUBJECT = {"your": "you", "target player's": "target player", "target opponent's": "target opponent",
            "each player's": "each player", "each opponent's": "each opponent", "its controller's": "its controller",
            "that player's": "that player"}
_NUM = {"one": 1, "two": 2, "three": 3, "five": 5, "seven": 7, "ten": 10, "twenty": 20}


def _subj(word: str) -> str:
    return _SUBJECT[word.lower()]


SUBS = [
    (re.compile(rf"\bdouble {_WHO} life total\b", re.I), lambda m: f"{_subj(m[1])} lifetotaldoubles"),
    (re.compile(rf"\b{_WHO} life total becomes (\d+|one|two|three|five|seven|ten|twenty|the (?:lowest|highest) life "
                r"total among all players)\b", re.I),
     lambda m: f"{_subj(m[1])} lifetotalbecomes {m[2]}"),
]


@verb(r"lifetotaldoubles", heads=("lifetotaldoubles",), subjects=("player",))
def doubles(m, clause):
    if clause.duration:
        return None
    return [Part("set_life", data={"op": "double", "side": "mine"})]


@verb(r"lifetotalbecomes (\d+|one|two|three|five|seven|ten|twenty|the (lowest|highest) life total among all players)",
      heads=("lifetotalbecomes",), subjects=("player",))
def becomes(m, clause):
    if clause.duration:
        return None
    if m[2]:
        return [Part("set_life", data={"op": m[2].lower()})]
    n = int(m[1]) if m[1].isdigit() else _NUM[m[1].lower()]
    return [Part("set_life", n, data={"op": "set", "side": "mine" if n >= 20 else "theirs"})]


def new_total(game, eff, player) -> int:
    op = eff.data["op"]
    if op == "double":
        return player.life * 2
    if op == "lowest":
        return min(pl.life for pl in game.players)
    if op == "highest":
        return max(pl.life for pl in game.players)
    return eff.amount


@ai_value("set_life")
def _value(game, me, eff, obj):
    from .engine.state import Player
    if not isinstance(obj, Player):
        return 0.0
    delta = new_total(game, eff, obj) - obj.life
    gain = 0.5 * delta
    return gain if obj is me else -gain


@verb(r"loses? the game", heads=("lose", "loses"), subjects=("player",))
def loses_game(m, clause):
    """"Target player loses the game", "that player loses the game": the named player loses (unless an effect says they
    can't: cx_night_aura.cant_lose)."""
    if clause.duration:
        return None
    return [Part("cx_lose_game", data={"side": "theirs"})]


_COUNT = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


@verb(r"gets? (a|an|one|two|three|four|five|\d+) (experience|poison) counters?", heads=("get", "gets"),
      subjects=("player",))
def gets_counters(m, clause):
    """"You get an experience counter", "target player gets two poison counters": player counters (#629). Rad
    counters are not read: their turn-based rule (mill, lose life, remove) is not in the engine."""
    if clause.duration:
        return None
    n = int(m[1]) if m[1].isdigit() else _COUNT[m[1].lower()]
    side = "theirs" if m[2].lower() == "poison" else "mine"
    return [Part("player_counter", n, data={"counter": m[2].lower(), "side": side})]


@ai_value("player_counter")
def _counter_value(game, me, eff, obj):
    from .engine.state import Player
    if not isinstance(obj, Player):
        return 0.0
    v = (1.5 if eff.data["counter"] == "poison" else 0.7) * eff.amount
    good = eff.data["counter"] != "poison"
    return (v if good else -v) if obj is me else (-v if good else v)
