"""Qualifiers on cast heads ("Whenever you cast <spell>") for the cx_events trigger grammar (#404):

    a spell of the chosen color | a creature spell of the chosen type          (the source's choice as it entered)
    a creature spell that has an Adventure | another spell that has convoke | a creature spell with flying
    a creature spell with power 5 or greater | ... with power 4, 5, or 6 | ... with mana value 4, 5, or 6
    an instant spell during your main phase | ... from your hand | ... from anywhere other than their hand
    a spell that targets you or a creature you control | ... an opponent or a creature an opponent controls
    a spell that targets a creature you don't control
    a spell that's white, blue, black, or red
    a spell other than your first spell each turn | your fourth noncreature spell each turn

``tail`` peels one qualifier off the end of a spell phrase; ``ok`` checks the recorded qualifiers on the cast
spell. Ordinals ("your second noncreature spell each turn") count only the spells of the phrase's kind: the
casts of the turn are logged by ``record`` (cx_events.observe calls it for every cast).
"""
from __future__ import annotations

import re

_KW = ("flying", "infect", "flash", "convoke", "cascade", "deathtouch", "lifelink", "trample", "haste", "vigilance",
       "reach", "menace", "first strike", "double strike", "defender", "indestructible", "hexproof", "storm",
       "delve", "affinity for artifacts")
_N = r"(\d+)"

TAILS = [
    (r" of the chosen colou?r", lambda m: ("chosen_color",)),
    (r" of the chosen (?:creature )?type", lambda m: ("chosen_type",)),
    (r" (?:that has|with) (" + "|".join(_KW) + ")", lambda m: ("kw", m[1])),
    (r" that has an Adventure", lambda m: ("adventure",)),
    (rf" with power {_N} or greater", lambda m: ("pow>=", int(m[1]))),
    (rf" with power {_N} or less", lambda m: ("pow<=", int(m[1]))),
    (rf" with power {_N}, {_N}, or {_N}", lambda m: ("pow_in", (int(m[1]), int(m[2]), int(m[3])))),
    (rf" with mana value {_N}, {_N}, or {_N}", lambda m: ("mv_in", (int(m[1]), int(m[2]), int(m[3])))),
    (r" from your hand", lambda m: ("zone", "hand")),
    (r" from anywhere other than their hand", lambda m: ("zone", "nothand")),
    (r" during your main phase", lambda m: ("main",)),
    (r" that targets you or a creature you control", lambda m: ("tg", "me_or_mine")),
    (r" that targets an opponent or a creature an opponent controls", lambda m: ("tg", "opp_or_theirs")),
    (r" that targets a creature you don't control", lambda m: ("tg", "theirs")),
]
_ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}
_COLORS = r"(?:white|blue|black|red|green)"


def tail(text: str):
    """(qualifier, text without it) for a qualifier at the end of a spell phrase, or None."""
    for pat, mk in TAILS:
        m = re.search("(?:" + pat + ")$", text)
        if m:
            return mk(m), text[:m.start()]
    return None


def head(text: str, spec: dict):
    """Rewrite the leading forms the base reader lacks; returns the plain spell phrase (or None to refuse)."""
    m = re.fullmatch(r"(an?|another) (.*?)spell other than (?:your first (.*?)spell each turn|"
                     r"the first (.*?)spell that player casts each turn)", text)
    if m:
        if m[2] != (m[3] if m[3] is not None else m[4]):
            return None
        spec["nth_not"] = 1
        return f"{m[1]} {m[2]}spell"
    m = re.fullmatch(r"(?:your|their) (fourth|fifth) (.*?)spells? each turn", text)
    if m:
        spec["nth"] = _ORD[m[1]]
        return "a " + (m[2] or "") + "spell"
    m = re.fullmatch(rf"an? spell that's ({_COLORS}(?:, {_COLORS})*,? or {_COLORS})", text)
    if m:
        spec["alts_override"] = [(c,) for c in re.split(r",? or |, ", m[1])]
        return "a spell"
    m = re.fullmatch(r"another (.+)", text)
    if m and "spell" in m[1]:
        spec["other"] = True
        return "a " + m[1]
    return text


def record(game, item) -> None:
    """Log a cast spell for ordinal heads that count a kind of spell ("your second noncreature spell")."""
    log = getattr(game, "cx_cast_log", None)
    if log is None or log[0] != game.turn:
        log = game.cx_cast_log = (game.turn, [])
    if all(x is not item for x in log[1]):
        log[1].append(item)


def nth_of_kind(game, caster, alts, word_ok) -> int:
    """How many spells of this kind the caster has cast this turn, the current one included."""
    log = getattr(game, "cx_cast_log", None)
    if log is None or log[0] != game.turn:
        return 0
    return sum(1 for it in log[1] if it.controller is caster and any(all(word_ok(it, w) for w in ws) for ws in alts))


def ok(game, quals, item, caster, me, perm) -> bool:
    from .engine.state import Permanent
    card = item.card
    for q in quals:
        k = q[0]
        if k == "chosen_color":
            col = getattr(perm, "chosen_color", None)
            if not col or col not in card.colors:
                return False
        elif k == "chosen_type":
            typ = getattr(perm, "chosen_type", "")
            if not typ or not (typ in card.subtypes or card.changeling):
                return False
        elif k == "kw":
            if q[1] == "convoke":
                if not card.convoke:
                    return False
            elif q[1] == "cascade":
                if not (card.cascade or "cascade" in card.keywords):
                    return False
            elif q[1] not in card.keywords:
                return False
        elif k == "adventure":
            if card.adventure is None:
                return False
        elif k in ("pow>=", "pow<=", "pow_in"):
            if not card.is_creature:
                return False
            pw = card.power
            if k == "pow>=" and pw < q[1] or k == "pow<=" and pw > q[1] or k == "pow_in" and pw not in q[1]:
                return False
        elif k == "mv_in":
            if card.cmc not in q[1]:
                return False
        elif k == "zone":
            zone = getattr(item, "cast_zone", "hand" if getattr(item, "cast_from_hand", False) else "other")
            if (zone != "hand") if q[1] == "hand" else zone == "hand":
                return False
        elif k == "main":
            if game.active is not me or game.step not in ("main1", "main2"):
                return False
        elif k == "tg":
            tg = [t for t in item.targets if t is not None]
            if q[1] == "me_or_mine":
                hit = any(t is me or isinstance(t, Permanent) and t.is_creature and t.controller is me for t in tg)
            elif q[1] == "opp_or_theirs":
                hit = any(t in game.players and t is not me or
                          isinstance(t, Permanent) and t.is_creature and t.controller is not me for t in tg)
            else:
                hit = any(isinstance(t, Permanent) and t.is_creature and t.controller is not me for t in tg)
            if not hit:
                return False
    return True


def hostile_choice(card) -> bool:
    """A permanent that punishes the caster of a spell of its chosen colour (Curse of Wizardry: "that player loses
    1 life") picks the opponent's colour; one that rewards you (Paradise Plume, Prism Ring) keeps its own."""
    for t in card.triggers:
        f = t.filter or ""
        if re.match(r"When(?:ever)? (?:a player|an opponent) casts a spell of the chosen color", f) and \
                any(e.target in ("that_player", "that_controller") for e in t.effects):
            return True
    return False
