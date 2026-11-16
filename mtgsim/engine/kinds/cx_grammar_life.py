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


@kind("cx_lose_game")
def lose_game(game, p, eff, target, **_):
    """The named player loses the game (CR 104.3e), unless they can't lose (Platinum Angel)."""
    if not isinstance(target, Player) or target.lost:
        return
    from ...cx_night_aura import cant_lose
    if cant_lose(game, target):
        return
    game.audit("loss", seat=game.players.index(target), cause="a card's effect")
    target.lost = True


@kind("player_counter")
def player_counter(game, p, eff, target, **_):
    """The named player gets N experience / poison counters (player counters, p.counters)."""
    if not isinstance(target, Player):
        return
    name = eff.data["counter"]
    target.counters[name] = target.counters.get(name, 0) + eff.amount
    game.log(f"gets {eff.amount} {name} counter(s)", target)
