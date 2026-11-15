"""Library searches for "up to that many" cards (#339): the count sacrificed just before (Scapeshift, Genesis
Device) or the amount of the triggering event (Hexhaven Invigorator); any other antecedent is refused."""
import random
import unittest
from pathlib import Path

from mtgsim.ai import HeuristicAI
from mtgsim.cards.parse import _parse_effects
from mtgsim.carddb import CardDB
from mtgsim.engine import Game, Permanent, Player, StackItem
from mtgsim.search_counted import parse

from tests.test_templates import BEAR, ISLAND, card

DB_FILE = Path(__file__).resolve().parents[1] / "mtgsim" / "data" / "cards.sqlite3"
FOREST = card("Forest", types="Basic Land — Forest", text="({T}: Add {G}.)")
SHIFT = card("Test Shift", "{2}{G}{G}", "Sorcery", "Sacrifice any number of lands. Search your library for up to "
             "that many land cards, put them onto the battlefield tapped, then shuffle.")
DEVICE = card("Test Device", "{3}", "Artifact", "{T}: Sacrifice any number of lands you control, then search your "
              "library for up to that many land cards, put them onto the battlefield tapped, then shuffle.")
HEXHAVEN = card("Test Hexhaven", "{3}{G}", "Creature — Horror", "Whenever this creature is dealt damage, you may "
                "search your library for up to that many land cards, put them onto the battlefield tapped, then "
                "shuffle.", 2, 6)


class Parsing(unittest.TestCase):
    def test_cards(self):
        for c in (SHIFT, DEVICE, HEXHAVEN):
            with self.subTest(card=c.name):
                self.assertEqual(c.unsupported, [])
        search = SHIFT.spell_effects[-1]
        self.assertEqual((search.kind, search.amount, search.data["upto"], search.data["that_much"]),
                         ("search_plan", 0, True, True))

    def test_refusals(self):
        # no antecedent: "that many" outside a trigger with an event amount and not after a sacrifice
        self.assertIsNone(parse("Search your library for up to that many land cards, put them onto the battlefield "
                                "tapped, then shuffle."))
        for text in ("Exile all attacking creatures. Search your library for that many basic land cards, put those "
                     "cards onto the battlefield tapped, then shuffle.",
                     "Sacrifice any number of lands. Draw a card. Search your library for up to that many land "
                     "cards, put them onto the battlefield tapped, then shuffle."):
            with self.subTest(text=text):
                self.assertTrue(_parse_effects(text)[1])

    @unittest.skipUnless(DB_FILE.exists(), "card database not built")
    def test_real_cards(self):
        db = CardDB(offline=True)
        for name in ("Scapeshift", "Genesis Device", "Hexhaven Invigorator"):
            with self.subTest(name=name):
                self.assertEqual(db.get(name).unsupported, [])
        for name in ("Settle the Wreckage", "The Earth King"):      # other antecedents stay visible
            self.assertTrue(db.get(name).unsupported, name)


class Resolving(unittest.TestCase):
    def setUp(self):
        self.a = Player("a", [], HeuristicAI())
        self.b = Player("b", [BEAR] * 10, HeuristicAI())
        self.game = Game(self.a, self.b, random.Random(0))
        self.game.turn, self.game.step = 1, "main1"
        self.a.library = [BEAR] * 5 + [FOREST] * 6

    def perm(self, c, owner):
        p = Permanent(c, owner)
        p.sick = p.tapped = False
        owner.battlefield.append(p)
        return p

    def lands(self):
        return [x for x in self.a.battlefield if x.card.is_land]

    def test_scapeshift_finds_as_many_as_it_sacrificed(self):
        for _ in range(9):
            self.perm(ISLAND, self.a)
        self.a.ai.choose_sac_any = lambda game, me, cands: [x for x in cands][:4]
        self.game.stack.append(StackItem(self.a, list(SHIFT.spell_effects), [None] * 2, card=SHIFT, name=SHIFT.name))
        self.game.resolve_top()
        names = sorted(x.card.name for x in self.lands())
        self.assertEqual(names, ["Forest"] * 4 + ["Island"] * 5)
        self.assertTrue(all(x.tapped for x in self.lands() if x.card.name == "Forest"))
        self.assertEqual(len(self.a.library), 7)
        self.assertEqual(sum(c.name == "Island" for c in self.a.graveyard), 4)

    def test_scapeshift_sacrificing_nothing_finds_nothing(self):
        self.perm(ISLAND, self.a)
        self.a.ai.choose_sac_any = lambda game, me, cands: []
        self.game.stack.append(StackItem(self.a, list(SHIFT.spell_effects), [None] * 2, card=SHIFT, name=SHIFT.name))
        self.game.resolve_top()
        self.assertEqual(len(self.lands()), 1)
        self.assertEqual(len(self.a.library), 11)

    def test_short_library_finds_what_is_there(self):
        for _ in range(9):
            self.perm(ISLAND, self.a)
        self.a.library = [FOREST, BEAR]
        self.a.ai.choose_sac_any = lambda game, me, cands: [x for x in cands][:4]
        self.game.stack.append(StackItem(self.a, list(SHIFT.spell_effects), [None] * 2, card=SHIFT, name=SHIFT.name))
        self.game.resolve_top()
        self.assertEqual(sorted(x.card.name for x in self.lands()), ["Forest"] + ["Island"] * 5)
        self.assertEqual([c.name for c in self.a.library], [BEAR.name])

    def test_device_ability(self):
        device = self.perm(DEVICE, self.a)
        for _ in range(8):
            self.perm(ISLAND, self.a)
        self.a.ai.choose_sac_any = lambda game, me, cands: [x for x in cands][:2]
        self.assertTrue(self.game.activate(self.a, device, "ability:0"))
        self.game.settle()
        self.assertEqual(sum(x.card.name == "Forest" for x in self.lands()), 2)
        self.assertEqual(sum(x.card.name == "Island" for x in self.lands()), 6)

    def test_hexhaven_finds_as_many_as_the_damage(self):
        hexhaven = self.perm(HEXHAVEN, self.a)
        self.game.deal_damage(hexhaven, 3, by=self.b, cause="test", source=None)
        self.game.settle()
        self.assertEqual(sum(x.card.name == "Forest" for x in self.lands()), 3)
        self.assertEqual(len(self.a.library), 8)


if __name__ == "__main__":
    unittest.main()
