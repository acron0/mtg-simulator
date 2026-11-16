"""Playing cards from the top of your library.

    You may play lands from the top of your library.                       (Courser of Kruphix)
    You may cast creature spells from the top of your library.              (Ranger Class's third level)
    You may play lands and cast spells from the top of your library.        (Future Sight)
    You may cast Angel spells and Human spells from the top of your library. (Sigarda, Font of Blessings)
    You may play cards from the top of your library.

``parse_line`` records ``advanced_rules["cx_top"] = (lands: bool or descriptions, spell descriptions or None)``.
"Play with the top card of your library revealed." is information only here. Engine: ``options``
offers the library's top card as a ``cx_top`` spell_options variant while a permanent with the rule allows it,
and ``land_ok`` lets ``Game.play_land`` and the AI play the top card when it is a land. "Once each turn"
permissions and extra costs ("by sacrificing a nonland permanent") stay unparsed.
"""
from __future__ import annotations

import re

_TYPES = {"artifact", "creature", "enchantment", "instant", "sorcery", "planeswalker", "battle", "kindred",
          "historic", "colorless", "snow", "legendary", "multicolored", "noncreature", "nonartifact", "permanent",
          "white", "blue", "black", "red", "green"}


def _words(text: str):
    """'instant and sorcery' / 'Angel spells and Human' / 'artifact spells and colorless' -> word groups."""
    out = []
    for part in re.split(r",? and |,? or |, ", text.replace(" spells", "")):
        words = part.split()
        if not words or not all(w in _TYPES or re.fullmatch(r"[A-Z][a-z'-]+", w) for w in words):
            return None
        out.append(" ".join(words))
    return out


def parse_line(line: str, st) -> bool:
    if line == "Play with the top card of your library revealed.":
        return True     # information only: the AI players don't model hidden library cards
    m = re.fullmatch(r"(?:You may look at the top card of your library any time,? and )?[Yy]ou may (.+?) from the top "
                     r"of your library\.( If you cast a spell this way, pay life equal to its mana value rather than pay "
                     r"its mana cost\.)?", line)
    if not m:
        return False
    what = m[1]
    if what == "play cards":
        lands, spells = True, []
    else:
        mm = re.fullmatch(r"(?:play (?:(\w+) )?lands)?(?: and )?(?:cast (.+?) spells|cast spells)?", what)
        if not mm or not what:
            return False
        lands = what.startswith("play ")
        if lands and mm[1]:
            if mm[1] not in _TYPES:
                return False
            lands = [mm[1]]
        spells = None
        if "cast" in what:
            spells = _words(mm[2]) if mm[2] else []
            if spells is None:
                return False
    if m[2] and spells is None:
        return False
    st.extra.setdefault("advanced_rules", {})["cx_top"] = (lands, spells)
    if m[2]:        # Bolas's Citadel (#313): those spells cost life equal to their mana value instead of mana
        st.extra["advanced_rules"]["cx_top_life"] = True
    return True


# ---------------------------------------------------------------- engine side

def _rules(p, life=False):
    return [x.card.advanced_rules["cx_top"] for x in p.battlefield
            if not x.abilities_suppressed and "cx_top" in x.card.advanced_rules
            and (not life or x.card.advanced_rules.get("cx_top_life"))]


def _fits(card, spells) -> bool:
    if not spells:
        return True
    from .engine.state import card_matches
    return any(card_matches(card, f"a {w} card") for w in spells)


def top(p):
    return p.library[-1] if len(p.library) else None


def spell_ok(p, card, life=False) -> bool:
    """card (the top of p's library) may be cast; life: by a permission that has it cost life (Bolas's Citadel)."""
    if card is None or card.is_land or top(p) is not card:
        return False
    return any(spells is not None and _fits(card, spells) for _, spells in _rules(p, life))


def land_ok(p, card) -> bool:
    return card is not None and card.is_land and top(p) is card and \
        any(lands is True or lands and _fits(card, lands) for lands, _ in _rules(p))


def options(game, p) -> list:
    """The top card as a spell option; with a Citadel, also paid with life equal to its mana value (rule 118.9: an
    alternative cost; additional costs and X still apply, and X is 0 when no mana pays it)."""
    from .cards import AltCost
    card = top(p)
    out = [game._variant(card, "cx_top")] if spell_ok(p, card) else []
    if spell_ok(p, card, life=True):
        out.append(game._variant(card, "cx_top_life", AltCost("cx_top_life", {}, zone="library", life=card.cmc)))
    return out
