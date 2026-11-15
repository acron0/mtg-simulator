""""~ deals damage equal to <Q> to <recipient>" read as "~ deals damage to <recipient> equal to <Q>" (#319): the same
sentence, in the word order the counted-damage templates read (Goblin Razerunners: "you may have this creature deal
damage equal to the number of +1/+1 counters on it to target player or planeswalker").

With "~" as the source, "counters on it" in that amount is ~'s own counters (the sentence names nothing else).
Only "the number of ..." amounts and the "target player or planeswalker" recipient (the one the forward order
misses) are moved, so sentences that already parse keep their reading; anything the reordered sentence doesn't parse
stays unsupported.
"""
from __future__ import annotations

import re

SUBS = [
    (re.compile(r"(?<!\w)((?:you may have )?~ deals? damage) equal to (the number of [^.]+?) to "
                r"(target player or planeswalker)"
                r"(?=\.|$)", re.I),
     lambda m: f"{m[1]} to {m[3]} equal to {re.sub(r' counters on it$', ' counters on ~', m[2])}"),
]
