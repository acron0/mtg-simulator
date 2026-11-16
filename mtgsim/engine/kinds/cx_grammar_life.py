"""Kinds for the grammar's life-total verbs (see mtgsim.cx_grammar_life)."""
from ..state import Player
from . import kind


@kind("set_life")
def set_life(game, p, eff, target, cause=None, **_):
    """The player's life total becomes a number: they gain or lose the difference (CR 119.5)."""
    if not isinstance(target, Player):
        return
    from ...cx_grammar_life import new_total
    delta = new_total(game, eff, target) - target.life
    if delta:
        game.change_life(target, delta, cause or "set_life")
