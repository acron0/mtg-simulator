"""Two-card searches split between two destinations, also when the split is its own sentence (#339):
"Search your library for up to two basic land cards and reveal them. Put one into your hand and the other into your
graveyard. Then shuffle." (Fork in the Road, Jarad's Orders, Final Parting, Flourishing Bloom-Kin)."""
import random
import unittest
from pathlib import Path

from mtgsim.ai import HeuristicAI
from mtgsim.cards.parse import _parse_effects
from mtgsim.carddb import CardDB
from mtgsim.engine import Game, Player, StackItem
from mtgsim.search_counted import parse

from tests.test_templates import BEAR, ISLAND, card

DB_FILE = Path(__file__).resolve().parents[1] / "mtgsim" / "data" / "cards.sqlite3"
FOREST = card("Forest", types="Basic Land — Forest", text="({T}: Add {G}.)")
OGRE = card("Big Ogre", "{4}{R}", "Creature — Ogre", "", 5, 5)
FORK = card("Test Fork", "{G}", "Sorcery", "Search your library for up to two basic land cards and reveal them. Put "
            "one into your hand and the other into your graveyard. Then shuffle.")
PARTING = card("Test Parting", "{3}{B}{B}", "Sorcery", "Search your library for two cards. Put one into your hand "
               "and the other into your graveyard. Then shuffle.")


class Parsing(unittest.TestCase):
    def test_written_cards(self):
        for c in (FORK, PARTING):
            with self.subTest(card=c.name):
                self.assertEqual(c.unsupported, [])
                self.assertEqual([e.kind for e in c.spell_effects], ["search_plan"])
                self.assertEqual(c.spell_effects[0].data["plan"], [["hand", 1, False], ["graveyard", None, False]])
        self.assertTrue(FORK.spell_effects[0].data["upto"])
        self.assertFalse(PARTING.spell_effects[0].data["upto"])

    def test_refusals(self):
        self.assertIsNone(parse("Search your library for up to two cards, put one into your hand and the other into "
                                "your hand, then shuffle."))
        self.assertIsNone(parse("Search your library for a card, put one into your hand and the other into your "
                                "graveyard, then shuffle."))
        for text in ("Search your library for three cards and reveal them. Target opponent chooses one. Put that "
                     "card into your hand and the rest into your graveyard. Then shuffle.",
                     "Search your library for up to two creature cards and reveal them. Put one into your hand and "
                     "the other on top of your library. Then shuffle."):
            with self.subTest(text=text):
                self.assertTrue(_parse_effects(text)[1])

    @unittest.skipUnless(DB_FILE.exists(), "card database not built")
    def test_real_cards(self):
        db = CardDB(offline=True)
        for name in ("Fork in the Road", "Jarad's Orders", "Final Parting", "Flourishing Bloom-Kin"):
            with self.subTest(name=name):
                self.assertEqual(db.get(name).unsupported, [])
        self.assertTrue(db.get("Intuition").unsupported)          # the opponent chooses: not read


class Resolving(unittest.TestCase):
    def setUp(self):
        self.a = Player("a", [], HeuristicAI())
        self.b = Player("b", [BEAR] * 10, HeuristicAI())
        self.game = Game(self.a, self.b, random.Random(0))
        self.game.turn, self.game.step = 1, "main1"

    def cast(self, c):
        self.game.stack.append(StackItem(self.a, list(c.spell_effects), [None], card=c, name=c.name))
        self.game.resolve_top()

    def test_one_to_hand_one_to_graveyard(self):
        self.a.library = [BEAR] * 3 + [FOREST, ISLAND]
        self.cast(FORK)
        self.assertEqual(len(self.a.hand), 1)
        self.assertTrue(self.a.hand[0].is_land)
        lands_in_yard = [c for c in self.a.graveyard if c.is_land]
        self.assertEqual(len(lands_in_yard), 1)
        self.assertEqual(sorted([self.a.hand[0].name, lands_in_yard[0].name]), ["Forest", "Island"])
        self.assertEqual(len(self.a.library), 3)

    def test_one_found_goes_to_hand(self):
        self.a.library = [BEAR, BEAR, FOREST]
        self.cast(FORK)
        self.assertEqual([c.name for c in self.a.hand], ["Forest"])
        self.assertEqual([c for c in self.a.graveyard if c.is_land], [])

    def test_final_parting_bins_the_reanimation_target(self):
        self.a.library = [ISLAND, OGRE, BEAR, ISLAND]
        self.cast(PARTING)
        self.assertEqual(len(self.a.hand), 1)
        self.assertIn(OGRE.name, [c.name for c in self.a.graveyard])
        self.assertEqual(len(self.a.library), 2)


if __name__ == "__main__":
    unittest.main()
