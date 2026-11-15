"""Coin flips with one result per player or per creature, and heads/tails outcomes (#568).

    each player flips a coin. Each player whose coin comes up tails sacrifices a creature of their choice.
                                                                                  (Goblin Assassin)
    You and target opponent each flip a coin. ~ deals 1 damage to each player whose coin comes up tails.
        Repeat this process until both players' coins come up heads on the same flip.   (Mana Clash)
    flip a coin for each creature that isn't a Demon, Devil, or Imp. Destroy each creature whose coin comes up
        tails.                                                                    (Rakdos, the Showstopper)
    flip two coins. If both coins come up heads, X. If both coins come up tails, Y.   (Two-Headed Giant)
    flip a coin for each opponent you have. For each flip you win, X. For each flip you lose, ~ deals N damage
        to that player.                           (Mutalith Vortex Beast; two players: the one opponent)

``flip_each`` (engine/kinds/cards.py) tosses one coin per player (active player first) or per matching creature
and runs the tails effects for each coin that came up tails. Nobody calls these coins, so nobody wins or loses
them and "whenever you win a coin flip" doesn't trigger (CR 705.2); the same holds for Two-Headed Giant's
"flip two coins", whose riders read "both heads" / "both tails" (cx_condlib ``flips_all``).
"""
from __future__ import annotations

import re

_STORE: dict = {}


def _keep(effects):
    key = repr(effects)
    if key not in _STORE:
        _STORE[key] = effects
    return f"FLIPEACH {list(_STORE).index(key)}."


def _players(m):
    from .cards import Effect
    tails = {"sacrifices a creature of their choice": [Effect("sac_own", data={"kind": "creature"})],
             "sacrifices a creature": [Effect("sac_own", data={"kind": "creature"})]}.get(m[1].lower())
    if tails is None:
        return m[0]
    return _keep([Effect("flip_each", data={"flip_per": "players", "tails": tails})])


def _clash(m):
    from .cards import Effect
    eff = Effect("flip_each", data={"flip_per": "players", "tails_damage": int(m[1]), "until_all_heads": True})
    return _keep([eff])


def _creatures(m):
    from .cards import Effect
    subs = [s for s in re.split(r", (?:or )?| or ", m[1]) if s]
    if not subs or not all(re.fullmatch(r"[A-Z][a-z]+", s) for s in subs):
        return m[0]
    selector = {"types_all": ["creature"], "not_subtypes": [s.lower() for s in subs]}
    return _keep([Effect("flip_each", data={"flip_per": "creatures", "selector": selector, "tails": "destroy"})])


def _both(m):
    import dataclasses
    from .cards import Effect, _parse_effects
    from .cx_condlib import _code
    from .cx_grammar_cond import _both as both
    if m[1].lower() == m[3].lower():
        return m[0]
    out = [Effect("flip_coin", 2, data={"count": True, "no_call": True})]
    for side, body in ((m[1], m[2]), (m[3], m[4])):
        effects, bad = _parse_effects(body[0].upper() + body[1:] + ".")
        if bad or not effects:
            return m[0]
        cond = _code("flips_all", "won" if side.lower() == "heads" else "lost")
        out += [dataclasses.replace(e, cond=both(e.cond, cond)) for e in effects]
    return _keep(out)


SUBS = [
    (re.compile(r"(?:^|(?<=\. ))each player flips a coin\. each player whose coin comes up tails ([^.]+)\.", re.I),
     _players),
    (re.compile(r"(?:^|(?<=\. ))you and target opponent each flip a coin\. ~ deals (\d+) damage to each player whose "
                r"coin comes up tails\. repeat this process until both players' coins come up heads on the same "
                r"flip\.", re.I), _clash),
    (re.compile(r"(?:^|(?<=\. ))flip a coin for each creature that isn't an? ([A-Za-z, ]+?)\. destroy each creature "
                r"whose coin comes up tails\.", re.I), _creatures),
    (re.compile(r"(?:^|(?<=\. ))flip two coins\. if both coins come up (heads|tails), ([^.]+)\. if both coins come up "
                r"(heads|tails), ([^.]+)\.", re.I), _both),
    # two players: "for each opponent you have" is one flip, and "that player" is that opponent
    (re.compile(r"(?:^|(?<=\. ))flip a coin for each opponent you have\. (for each flip you win, [^.]+\.) "
                r"(for each flip you lose, [^.]+?) to that player\.", re.I),
     lambda m: f"Flip a coin. {m[1]} {m[2]} to each opponent."),
]


def _stored(m):
    return list(list(_STORE.values())[int(m[1])])


EFFECT_PATTERNS = [
    (r"FLIPEACH (\d+)", _stored),
]


def resolve(game, p, eff, item):
    """One coin per player (active player first) or per matching creature; the tails effects for each tails."""
    from .chance_templates import toss
    from .engine.state import Permanent
    data = eff.data
    if data["flip_per"] == "creatures":
        from .permanent_templates import matches
        src = item.source if item is not None and isinstance(item.source, Permanent) else None
        victims = [x for pl in game.players for x in pl.battlefield if x.is_creature
                   and matches(game, x, data["selector"], p, src)]
        tails = [x for x in victims if not toss(game, p)]
        game.log(f"flips {len(victims)} coins: {len(tails)} tails", p)
        for x in tails:
            if x in x.controller.battlefield:
                game.destroy(x)
        return
    order = list(game.players)
    start = order.index(game.active) if game.active in order else 0
    order = order[start:] + order[:start]
    for _ in range(100):            # "repeat until both come up heads": a fair coin ends it long before this
        heads = {pl: toss(game, pl) for pl in order}
        for pl in order:
            game.log(f"flips a coin: {'heads' if heads[pl] else 'tails'}", pl)
        for pl in order:
            if heads[pl] or game.over:
                continue
            if data.get("tails_damage"):
                from .cards import Effect
                game.resolve(p, Effect("damage", data["tails_damage"], target="player"), pl, item)
            for e in data.get("tails", ()):
                game.resolve(pl, e, None, item)
        if not data.get("until_all_heads") or all(heads.values()) or game.over:
            return
