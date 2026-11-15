"""#321: "{T}: Add {C}. If C, add {C}{C} instead." makes more of the same mana while C holds (Urza's lands, the
Worker cycle); a named-permanent and a written-out subtype condition ("Urza's Power-Plant")."""
import unittest

from mtgsim.engine.mana import payable
from tests.test_cx_grammar import Base, DB_FILE
from tests.test_templates import card


class Parsing(unittest.TestCase):
    def test_conditional_amount(self):
        from mtgsim.mana_count import parse_conditional
        colour, base, dyn = parse_conditional("{T}: Add {C}. If you control an Urza's Mine and an Urza's Tower, "
                                              "add {C}{C} instead.")
        self.assertEqual((colour, base, dyn[0], dyn[2], dyn[3]), ("C", 1, "cond", 1, 2))

    def test_refusals(self):
        from mtgsim.mana_count import parse_conditional
        for line in ("{T}: Add {U}. If you played a land this turn, add {B} instead.",      # another colour
                     "{T}: Add {C}{C}. If you control an Urza's Mine, add {C} instead.",     # less, not more
                     "{T}: Add {C}. If you frobnicate, add {C}{C} instead."):                # unknown condition
            self.assertIsNone(parse_conditional(line), line)
        c = card("Test River", "", "Land", "{T}: Add {U}. If you played a land this turn, add {B} instead.")
        self.assertTrue(c.unsupported)

    def test_named_and_subtype_conditions(self):
        from mtgsim.cx_condlib import parse
        self.assertIn('Tower Worker', parse("you control creatures named Mine Worker and Tower Worker"))
        self.assertIn('Power-Plant', parse("you control an Urza's Mine and an Urza's Power-Plant"))


@unittest.skipUnless(DB_FILE.exists(), "card database not built")
class Tron(Base):
    def setUp(self):
        super().setUp()
        from mtgsim.carddb import CardDB
        self.db = CardDB(offline=True)
        self.a.battlefield.clear()

    def lands(self, *names):
        return [self.perm(self.db.get(n), self.a) for n in names]

    def test_full_tron_makes_seven(self):
        lands = self.lands("Urza's Tower", "Urza's Mine", "Urza's Power Plant")
        for land in lands:
            self.assertEqual(self.db.get(land.card.name).unsupported, [])
        self.assertTrue(payable(lands, {"generic": 7}))
        self.assertFalse(payable(lands, {"generic": 8}))

    def test_without_the_set_each_makes_one(self):
        lands = self.lands("Urza's Tower", "Urza's Mine", "Urza's Mine")
        self.assertTrue(payable(lands, {"generic": 3}))       # Tower lacks a Power-Plant; the Mines lack it too
        self.assertFalse(payable(lands, {"generic": 4}))
        self.lands("Urza's Power Plant")
        self.assertTrue(payable(self.a.battlefield, {"generic": 9}))     # Mines 2 + 2, Plant 2, Tower 3
        self.assertFalse(payable(self.a.battlefield, {"generic": 10}))

    def test_other_condition_families(self):
        # conditions outside cx_condlib (the initiative, "power 4 or greater") are checked the engine's usual way
        tome = self.perm(self.db.get("Sarevok's Tome"), self.a)
        self.assertFalse(payable([tome], {"generic": 2}))
        self.game.initiative = self.a
        self.assertTrue(payable([tome], {"generic": 2}))
        self.assertFalse(payable([tome], {"generic": 3}))
        druid = self.perm(self.db.get("Raucous Audience"), self.a)
        self.assertFalse(payable([druid], {"G": 2}))
        self.perm(card("Test Giant", "{4}", "Creature — Giant", "", 4, 4), self.a)
        self.assertTrue(payable([druid], {"G": 2}))

    def test_worker_cycle(self):
        mine, plant, tower = (self.perm(self.db.get(n), self.a) for n in ("Mine Worker", "Power Plant Worker",
                                                                          "Tower Worker"))
        self.assertTrue(payable([tower], {"generic": 3}))
        self.a.battlefield.remove(plant)
        self.assertFalse(payable([tower], {"generic": 2}))
        effects = self.db.get("Mine Worker").activated[0].effects
        from mtgsim.engine import StackItem
        for have_plant, gain in ((False, 1), (True, 3)):
            if have_plant:
                self.a.battlefield.append(plant)
            before = self.a.life
            self.game.stack.append(StackItem(self.a, list(effects), [None] * len(effects), source=mine,
                                             kind="trigger"))
            self.game.resolve_top()
            self.assertEqual(self.a.life - before, gain)


if __name__ == "__main__":
    unittest.main()
