"""The cx_temp_cost kind (see mtgsim.cx_static_cost, #341 slice 2)."""
from . import kind


@kind("cx_temp_cost")
def temp_cost(game, p, eff, **_):
    """"The next Dragon spell you cast costs {2} less to cast" / "Artifact spells you cast this turn cost {1} less"
    (cx_static_cost, #341): a rule read by cost_of until it's spent or its turn ends."""
    d = eff.data
    rules = game.__dict__.setdefault("temp_cost_rules", [])
    rules.append({"player": p, "turn": game.turn if d["this_turn"] else None, "once": d["once"],
                  "specs": d["specs"], "amount": d["amount"]})
