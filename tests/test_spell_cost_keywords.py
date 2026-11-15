"""#513 slice: additional spell costs "blight N", "forage" and "sacrifice half the lands you control, rounded up"."""
import random
import unittest

from mtgsim.ai import HeuristicAI
from mtgsim.cx_spell_costs import choose, parse_cost
from mtgsim.engine import Game, Player
from mtgsim.cards import make_token
from tests.test_cx_grammar import DB_FILE


@unittest.skipUnless(DB_FILE.exists(), "needs mtgsim/data/cards.sqlite3")
class KeywordCosts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from mtgsim.carddb import CardDB
        cls.db = CardDB(offline=True)

    def game(self, lands, mine=(), theirs=()):
        a, b = Player("a", [], HeuristicAI()), Player("b", [], HeuristicAI())
        g = Game(a, b, random.Random(0), log=True)
        g.turn, g.step = 3, "main1"
        a.library = b.library = [self.db.get("Island")] * 10
        for name in lands:
            g.enter_battlefield(a, self.db.get(name)).sick = False
        perms = [g.enter_battlefield(a, self.db.get(n) if isinstance(n, str) else n) for n in mine]
        foes = [g.enter_battlefield(b, self.db.get(n)) for n in theirs]
        g.settle()
        return g, a, b, perms, foes

    def test_parse(self):
        self.assertEqual(parse_cost("blight 1 or pay {3}"), ((("blight", 1, {}),), (("mana", 0, {"generic": 3}),)))
        self.assertEqual(parse_cost("forage or pay {B}")[0], (("forage", 1, {}),))
        for name in ("Bogslither's Embrace", "Wild Unraveling", "Feed the Cycle", "Tectonic Split"):
            self.assertEqual(self.db.get(name).unsupported, [], name)
        for text in ("blight X", "blight X or pay {1}", "sacrifice half the creatures you control, rounded up",
                     "forage twice"):
            self.assertIsNone(parse_cost(text), text)
        self.assertTrue(self.db.get("Soul Immolation").unsupported)          # blight X: X needs #502's X counts

    def test_blight_puts_counters_on_a_creature_that_survives(self):
        g, a, b, (courser,), (bear,) = self.game(["Swamp"] * 2, ["Centaur Courser"], ["Grizzly Bears"])
        embrace = self.db.get("Bogslither's Embrace")
        a.hand.append(embrace)
        self.assertTrue(g.cast(a, embrace, [bear]))
        g.settle()
        self.assertNotIn(bear, b.battlefield)
        self.assertEqual(courser.counters.get("-1/-1"), 1)                   # the 3/3 is now 2/2

    def test_blight_needs_a_creature_else_mana(self):
        g, a, b, _, (bear,) = self.game(["Swamp"] * 2, (), ["Grizzly Bears"])
        embrace = self.db.get("Bogslither's Embrace")
        a.hand.append(embrace)
        self.assertFalse(g.can_cast_now(a, embrace))                         # {1}{B} + {3}: not with two lands
        g, a, b, _, (bear,) = self.game(["Swamp"] * 5, (), ["Grizzly Bears"])
        a.hand.append(embrace)
        self.assertTrue(g.cast(a, embrace, [bear]))
        self.assertEqual(sum(x.tapped for x in a.battlefield), 5)

    def test_ai_pays_mana_rather_than_blight_a_good_creature_to_death(self):
        g, a, b, (elf,), _ = self.game(["Swamp"] * 5, ["Llanowar Elves"])
        chosen = choose(g, a, self.db.get("Bogslither's Embrace"))
        self.assertEqual(chosen[1][0][0], "mana")
        token = make_token("Soldier", 1, 1)
        g, a, b, (tok,), _ = self.game(["Swamp"] * 5, [token])
        chosen = choose(g, a, self.db.get("Bogslither's Embrace"))
        self.assertEqual(chosen[1][0][0], "blight")                         # a 1/1 token is fine to lose

    def test_forage_exiles_three_or_sacrifices_a_food(self):
        g, a, b, _, (bear,) = self.game(["Swamp"] * 2, (), ["Grizzly Bears"])
        a.graveyard = [self.db.get(n) for n in ("Forest", "Giant Growth", "Hill Giant", "Island")]
        feed = self.db.get("Feed the Cycle")
        a.hand.append(feed)
        self.assertTrue(g.cast(a, feed, [bear]))
        g.settle()
        self.assertNotIn(bear, b.battlefield)
        self.assertEqual(len(a.graveyard), 2)                               # three exiled, then the spell itself
        self.assertEqual(len(a.exile), 3)
        g, a, b, (food,), (bear,) = self.game(["Swamp"] * 2, [make_token("Food", 0, 0, kind="food")], ["Grizzly Bears"])
        a.graveyard = [self.db.get("Forest")]                               # too few cards: the Food goes
        a.hand.append(feed)
        self.assertTrue(g.cast(a, feed, [bear]))
        self.assertNotIn(food, a.battlefield)
        g, a, b, _, (bear,) = self.game(["Swamp"] * 2, (), ["Grizzly Bears"])
        a.hand.append(feed)
        self.assertFalse(g.can_cast_now(a, feed))                           # no forage, no {B} to spare

    def test_tectonic_split_sacrifices_half_rounded_up(self):
        g, a, b, _, _ = self.game(["Forest"] * 7)
        split = self.db.get("Tectonic Split")
        a.hand.append(split)
        self.assertTrue(g.cast(a, split))
        g.settle()
        self.assertEqual(sum(x.card.is_land for x in a.battlefield), 3)       # 7 lands: 4 sacrificed (after paying)
        self.assertIn("Tectonic Split", [x.card.name for x in a.battlefield])

    def test_ai_casts_bogslithers_embrace(self):
        g, a, b, (courser,), (angel,) = self.game(["Swamp"] * 2, ["Centaur Courser"], ["Serra Angel"])
        a.hand = [self.db.get("Bogslither's Embrace")]
        a.ai.main_phase(g, a)
        g.settle()
        self.assertNotIn(angel, b.battlefield)                               # exiled the opponent's creature
        self.assertEqual(courser.counters.get("-1/-1"), 1)


if __name__ == "__main__":
    unittest.main()
