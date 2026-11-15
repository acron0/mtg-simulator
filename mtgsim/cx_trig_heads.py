"""Attack, damage, targeting and counter heads for the cx_events trigger grammar (#404 slice 3):

    Whenever equipped creature attacks alone | a Rogue you control attacks and isn't blocked
    Whenever a creature attacks enchanted player | deals combat damage to enchanted player     (Curses)
    Whenever ~ becomes the target of a spell [you control]
    Whenever ~ deals damage to a Dinosaur | to one or more creatures | deals 6 or more damage to an opponent
    Whenever a source an opponent controls deals damage to you
    Whenever one or more +1/+1 counters are put on another creature you control
    Whenever you put one or more +1/+1 counters on a creature you control

cx_events keeps the verb table; this module reads the verbs' own arguments (``verb_arg``), checks their flags
(``flag_ok``) and parses the counter heads (``counter_head``), whose subject is the permanent the counters go on.
"""
from __future__ import annotations

import re

from . import cx_events

FLAGS = {"alone", "atk_cursed", "dmg_cursed", "tg_spell", "tg_spell_mine", "dmg_n", "dmgd", "you_put"}


def verb_arg(flag: str, text: str, subject: dict):
    """Read the argument of a verb into the subject spec; None refuses the head."""
    if flag == "dmg_n":
        m = re.search(r"(\d+) or more damage", text)
        subject["dmg_n"] = int(m[1])
        return True
    m = re.search(r"damage to (an?|one or more) (.+)$", text)
    if not m or m[2] in ("player", "opponent", "creature", "player or planeswalker"):
        return None             # the fixed verbs read those
    alts = cx_events._desc_alts(m[2], plural=m[1] == "one or more")
    if alts is None:
        return None
    subject["dmgd"] = alts
    if m[1] == "one or more":
        subject["batch"] = True     # once per damage step / resolution, however many it hit
    return True


def flag_ok(game, flag, spec, perm, obj, context) -> bool:
    from .engine.state import Permanent
    if flag == "alone":
        return len(game.attackers) == 1
    if flag == "atk_cursed":
        cursed = getattr(perm, "curse_target", None)
        return cursed is not None and game.attack_targets.get(obj) is cursed
    if flag == "dmg_cursed":
        cursed = getattr(perm, "curse_target", None)
        return cursed is not None and context is cursed
    if flag in ("tg_spell", "tg_spell_mine"):
        item = getattr(game, "event_targeter", None)
        if item is None or not item.is_spell:
            return False
        return flag == "tg_spell" or item.controller is perm.controller
    if flag == "dmg_n":
        return context is not perm.controller and (getattr(game, "event_amount", None) or 0) >= spec["dmg_n"]
    if flag == "dmgd":
        return isinstance(context, Permanent) and cx_events._perm_fits(game, context, spec["dmgd"])
    if flag == "you_put":
        item = getattr(game, "resolving_item", None)
        return (item.controller if item is not None else obj.controller) is perm.controller
    return True


_COUNTER = re.compile(r"(?:one or more \+1/\+1 counters are put on|(?P<you>you put one or more \+1/\+1 counters on)) "
                      r"(?P<s>.+)")


def counter_head(body: str):
    """"one or more +1/+1 counters are put on <subject>" -> (raws, spec), or None."""
    m = _COUNTER.fullmatch(body)
    if not m:
        return None
    if m["s"] in ("~", "it", "this creature"):
        return None             # the base table's "p1_added" self head
    subject = cx_events._object_subject(m["s"], head=True)
    if subject is None or subject["batch"] or subject["host"]:
        return None
    subject["flags"] = {"p1_added": "you_put" if m["you"] else ""}
    subject["by"] = None
    return ("p1_added",), subject


# "a source an opponent controls deals damage to you": the damaged player is you, the damage came from them
cx_events._PLAYER_SUBJ["a source an opponent controls"] = "src_opp"
cx_events._PLAYER_VERBS[0:0] = [(r"deals? damage to you", "src_dmg_me")]
cx_events._PLAYER_RAW["src_dmg_me"] = ("player_damaged",)
cx_events._OBSERVED.update({"p1_added", "unblocked"})


def subject_takes(who: str, kind: str) -> bool:
    """The source subjects take only their damage verbs ("a source you control draws a card" is no head)."""
    if who == "src_opp":
        return kind == "src_dmg_me"
    if who == "src_you":
        return kind == "src_noncombat"
    return True


def player_ok(game, spec, actor, me) -> bool:
    if spec["kind"] == "src_dmg_me":
        by = getattr(game, "event_dmg_by", None)
        return spec["player"] == "src_opp" and actor is me and by is not None and by is not me
    if spec["player"] == "src_opp":
        return False            # no other verb takes this subject
    return True
