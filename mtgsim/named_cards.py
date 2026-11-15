"""Named-card references (#314): lines about cards with a given name.

    A deck can have any number of cards named ~.          (Relentless Rats, Shadowborn Apostle, Hare Apparent)
    A deck can have up to seven cards named ~.            (Seven Dwarves)

Deck-construction rules: they change which decklists are legal, not how a game plays, so in a game they do nothing
(the simulator plays whatever decklist it is given). Names inside noun phrases ("creatures named Paper Tiger",
"each other creature you control named ~") are read by ``permanent_templates.selector`` (``name``).
"""
from __future__ import annotations

import re

_DECK_RULE = re.compile(r"A deck can have (?:any number of|up to (?:\w+)) cards named ~\.")


def parse_line(st, line: str):
    """Face-line handler: None once the line is handled, else the line."""
    if _DECK_RULE.fullmatch(line):
        return None
    return line
