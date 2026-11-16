"""#629: life totals set to a number: "double <player>'s life total", "<player>'s life total becomes N", "... the
lowest / highest life total among all players" (mtgsim.cx_grammar_life, kind set_life)."""
import random
import unittest
from pathlib import Path

from mtgsim.ai import HeuristicAI
from mtgsim.engine import Game, Player, StackItem
from tests.test_templates import ISLAND, card

DB_FILE = Path(__file__).resolve().parents[1] / "mtgsim" / "data" / "cards.sqlite3"

FULL = ("Arbiter of Knollridge", "Beacon of Immortality", "Blessed Wind", "Celestial Mantle", "Form of the Dinosaur",
        "Live Long and Prosper", "Magister Sphinx", "Repay in Kind", "Revival // Revenge", "Vraska, Relic Seeker")
DOUBLE = card("Test Beacon", "{3}{W}", "Instant", "Double target player's life total.")
SET10 = card("Test Sphinx", "{3}{U}", "Sorcery", "Target player's life total becomes 10.")
SET20 = card("Test Wind", "{7}{W}", "Sorcery", "Target player's life total becomes 20.")
LOWEST = card("Test Repay", "{5}{B}{B}", "Sorcery", "Each player's life total becomes the lowest life total among "
                                                    "all players.")
LIFELINK_FAN = card("Test Fan", "{1}", "Creature — Human", "Whenever you gain life, put a +1/+1 counter on ~.", 1, 1)


def game(mine=20, theirs=20):
    a, b = Player("a", [], HeuristicAI()), Player("b", [], HeuristicAI())
    g = Game(a, b, random.Random(0), log=True)
    g.turn, g.step = 3, "main1"
    a.library = b.library = [ISLAND] * 10
    a.life, b.life = mine, theirs
    return g, a, b


def cast(g, p, c, targets=None):
    effects = list(c.spell_effects)
    targets = g.auto_targets(p, effects, None) if targets is None else targets
    g.stack.append(StackItem(p, effects, targets, card=c, name=c.name))
    g.resolve_top()
    g.settle()
    return targets


class Parse(unittest.TestCase):
    def test_shapes(self):
        for c in (DOUBLE, SET10, SET20, LOWEST):
            self.assertEqual(c.unsupported, [], c.name)
        inner = SET10.spell_effects[0].data["effects"][0]
        self.assertEqual((inner.kind, inner.amount, inner.data["op"]), ("set_life", 10, "set"))
        self.assertEqual(DOUBLE.spell_effects[0].data["side"], "mine")
        self.assertEqual(SET10.spell_effects[0].data["side"], "theirs")
        self.assertEqual(SET20.spell_effects[0].data["side"], "mine")

    def test_refusals(self):
        for text in ("Target player's life total becomes 10 until end of turn.",
                     "Each player's life total becomes the number of creatures they control.",
                     "Triple target player's life total."):
            self.assertTrue(card("Test Odd", "{W}", "Sorcery", text).unsupported, text)


class Resolve(unittest.TestCase):
    def test_double_targets_ourselves(self):
        g, a, b = game(12, 20)
        targets = cast(g, a, DOUBLE)
        self.assertIs(targets[0], a)
        self.assertEqual((a.life, b.life), (24, 20))

    def test_becomes_ten_targets_the_opponent(self):
        g, a, b = game(20, 20)
        targets = cast(g, a, SET10)
        self.assertIs(targets[0], b)
        self.assertEqual((a.life, b.life), (20, 10))

    def test_becomes_twenty_from_seven_targets_ourselves(self):
        g, a, b = game(7, 20)
        targets = cast(g, a, SET20)
        self.assertIs(targets[0], a)
        self.assertEqual(a.life, 20)

    def test_lowest(self):
        g, a, b = game(20, 5)
        cast(g, a, LOWEST, [None])
        self.assertEqual((a.life, b.life), (5, 5))

    def test_setting_life_is_gaining_it(self):
        g, a, b = game(7, 20)
        fan = g.enter_battlefield(a, LIFELINK_FAN)
        g.settle()
        cast(g, a, SET20, [a])
        self.assertEqual(a.life, 20)
        self.assertEqual(fan.p1, 1)                  # "whenever you gain life" saw the gain (CR 119.5)


@unittest.skipUnless(DB_FILE.exists(), "card database not built")
class RealCards(unittest.TestCase):
    def test_full(self):
        from mtgsim.carddb import CardDB
        from mtgsim.coverage import card_coverage
        db = CardDB(offline=True)
        self.addCleanup(db._all.close)
        for name in FULL:
            self.assertEqual(card_coverage(db.get(name)).status, "full", name)

    def test_magister_sphinx_etb(self):
        from mtgsim.carddb import CardDB
        db = CardDB(offline=True)
        self.addCleanup(db._all.close)
        g, a, b = game(20, 20)
        g.enter_battlefield(a, db.get("Magister Sphinx"))
        g.settle()
        self.assertEqual((a.life, b.life), (20, 10))


if __name__ == "__main__":
    unittest.main()
