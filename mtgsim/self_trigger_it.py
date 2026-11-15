""""It" in a trigger of the permanent itself (#319, #320): "When ~ enters, it deals 4 damage to any target and 2 damage
to you", "Whenever ~ attacks, you may have it deal 1 damage to each creature defending player controls".

``_parse_trigger_line`` asks ``rewrite(events, line, rest)`` for the effect text of a trigger. For the permanent's own
enters / attacks / blocks / dies / combat-damage triggers a leading "it" is that permanent, so it is read as "~" where
the "it" wording has no path of its own:

* "it deals N damage to X and M damage to Y" (several recipients);
* "you may have it deal ... / fight ...", except "you may have it deal N damage to target X", which already reads as
  an optional, hostile-only damage effect: the "~" wording of that shape is made mandatory by an older substitution
  (cards/clauses.py), so it is only used when the target is the opponent's anyway.

With the engine's two players, "defending player" in an attack trigger and "that player" in "Whenever ~ deals combat
damage to a player" are the opponent, so "each creature defending player controls" and "target creature that player
controls" read as "... an opponent controls" (as cx_next_turn and cx_counters already do for other wordings).

``backlog_templates.parse_line`` re-parses "Whenever another creature enters, ..." as "When ~ enters, ...": there
"it" is the entering creature, so it excludes these wordings before the rewrite can see them.
"""
from __future__ import annotations

import re

_SELF_EVENTS = {("etb",), ("attacks",), ("blocks",), ("dies",), ("combat_damage_player",)}
_HOSTILE = re.compile(r"(?:an opponent controls|you don't control)\.?$", re.I)


def rewrite(events, line: str, rest: str) -> str:
    if events not in _SELF_EVENTS or not re.match(r"When(?:ever)? ~ ", line):
        return rest
    if events == ("attacks",) and line.startswith("Whenever ~ attacks, ") and " damage to each " in rest:
        rest = re.sub(r"\b(each [\w ]+?) defending player controls\b", r"\1 an opponent controls", rest)
    if events == ("combat_damage_player",) and line.startswith("Whenever ~ deals combat damage to a player, "):
        rest = re.sub(r"\bdamage to target creature that player controls\b",
                      "damage to target creature an opponent controls", rest)
    if events != ("combat_damage_player",) and events != ("dies",) and re.match(r"it deals \w+ damage to [^.]* and ",
                                                                                rest):
        return "~" + rest[2:]
    if re.match(r"you may have it (?:deal|fight)\b", rest):
        plain = re.fullmatch(r"you may have it deal \d+ damage to (?:any target|target [a-z' -]+)\.?", rest, re.I)
        if not plain or _HOSTILE.search(rest):
            return "you may have ~" + rest[len("you may have it"):]
    return rest
