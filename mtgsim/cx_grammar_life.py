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
the opponent (``side``); "double" is ourselves; an exchange names the opponent and is worth their lead in life. ``ai_value("set_life")`` values the change for each named player.
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
    # "Exchange life totals with target opponent" (Mirror Universe); "[you may have] two target players exchange life
    # totals" (Soul Conduit, Axis of Mortality): with two players the two targets are you and the other player.
    # "you may": the controller exchanges only when it gains them life (kept on the verb, read when it resolves).
    (re.compile(r"\b(you may )?exchange life totals with (target (?:opponent|player))\b", re.I),
     lambda m: f"{m[2]} lifetotalsexchange{' may' if m[1] else ''}"),
    (re.compile(r"\b(you may have )?two target players exchange life totals\b", re.I),
     lambda m: f"target player lifetotalsexchange both{' may' if m[1] else ''}"),
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


@verb(r"lifetotalsexchange( both)?( may)?", heads=("lifetotalsexchange",), subjects=("player",))
def exchanges(m, clause):
    """Exchange life totals between the controller and the named player (CR 701.12). "both": the controller is a target
    too, so they must also be a legal target when it resolves."""
    if clause.duration:
        return None
    return [Part("set_life", data={"op": "exchange", "both": bool(m[1]), "may": bool(m[2]), "side": "theirs"})]


def new_total(game, eff, player) -> int:
    op = eff.data["op"]
    if op == "double":
        return player.life * 2
    if op == "lowest":
        return min(pl.life for pl in game.players)
    if op == "highest":
        return max(pl.life for pl in game.players)
    if op == "exchange":
        return game.opponent(player).life
    return eff.amount


@ai_value("set_life")
def _value(game, me, eff, obj):
    from .engine.state import Player
    if not isinstance(obj, Player) or (eff.data["op"] == "exchange" and obj is me):
        return 0.0
    delta = new_total(game, eff, obj) - obj.life
    gain = 0.5 * delta
    if eff.data["op"] == "exchange":
        return -gain - 1.0          # worth it once the opponent leads by more than two life
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


def ability_value(game, me, eff, target):
    """An activated ability's value (engine.policy._mode_value, via residual_templates.effect_value) when it is a
    player wrapper around life-total kinds only: the registered value on the chosen player, else None (the default)."""
    inner = eff.data.get("effects") or ()
    if eff.kind != "cx_players" or not inner or any(e.kind != "set_life" for e in inner):
        return None
    from .cx_grammar import member_value
    from .engine.state import Player
    if not isinstance(target, Player):
        return None
    return sum(member_value(game, me, e, target)[0] for e in inner)
