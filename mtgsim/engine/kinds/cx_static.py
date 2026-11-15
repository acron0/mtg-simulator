"""Small effect kinds for the static lane (sim-static)."""
from . import kind


@kind("exile_own_gy_n")
def exile_own_gy_n(game, p, eff, **_):
    """"Exile two cards from your graveyard." (Bloodcurdler's end step): exile N cards of your own graveyard, all of
    them when there are fewer; the AI keeps the creature cards and the expensive ones."""
    picks = sorted(p.graveyard, key=lambda c: (c.is_creature, c.cmc))[:eff.amount]
    for card in picks:
        game.move_card(card, p.graveyard, p.exile, reason="exile_graveyard")
    if picks:
        game.log(f"exiles {len(picks)} card(s) from their graveyard", p)
