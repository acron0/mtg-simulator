"""Kinds for the grammar's life-total verbs (see mtgsim.cx_grammar_life)."""
from ..state import Player
from . import kind


@kind("set_life")
def set_life(game, p, eff, target, cause=None, **_):
    """The player's life total becomes a number: they gain or lose the difference (CR 119.5)."""
    if not isinstance(target, Player):
        return
    if eff.data["op"] == "exchange":
        _exchange(game, p, eff, target, cause)
        return
    from ...cx_grammar_life import new_total
    delta = new_total(game, eff, target) - target.life
    if delta:
        game.change_life(target, delta, cause or "set_life")


def _exchange(game, p, eff, target, cause):
    """Exchange life totals (CR 701.12): each player gains or loses the difference, at the same time. With "two target
    players" the controller is the other target, so a controller that can't be targeted (shroud) stops it."""
    if target is p:
        return
    from ...batch1_templates import player_targetable
    if eff.data.get("both") and not player_targetable(game, p, p):
        return
    mine, theirs = p.life, target.life
    if eff.data.get("may") and theirs <= mine:
        return                  # "you may": the controller only exchanges up
    gainer = p if theirs > mine else target
    from ...batch1_templates import lifegain_blocked
    if gainer in game.no_lifegain_turn or lifegain_blocked(game, gainer):
        return                  # the gain can't happen, so the exchange doesn't (Platinum Emperion ruling)
    if mine != theirs:
        game.change_life(target, mine - theirs, cause or "exchange_life")
        game.change_life(p, theirs - mine, cause or "exchange_life")


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
