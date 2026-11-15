"""#314: names in noun phrases ("creatures named Paper Tiger", "each other creature you control named ~") and the
deck-construction lines that do nothing in a game."""
import random
import unittest
from pathlib import Path

from mtgsim.ai import HeuristicAI
from mtgsim.engine import Game, Player
from mtgsim.permanent_templates import selector
from tests.test_templates import ISLAND, card

DB_FILE = Path(__file__).resolve().parents[1] / "mtgsim" / "data" / "cards.sqlite3"


class Selector(unittest.TestCase):
    def test_reads_names(self):
        self.assertEqual(selector("creatures named Paper Tiger", plural=True),
                         {"name": "Paper Tiger", "types_all": ["creature"]})
        self.assertEqual(selector("other creature you control named ~"),
                         {"other": True, "name": "~", "controller": "mine", "types_all": ["creature"]})
        self.assertEqual(selector("other creature on the battlefield named ~")["name"], "~")
        self.assertIsNone(selector("creature named Kobolds of ~"))     # a name built on ~: not read

    def test_deck_rules_do_nothing(self):
        for text in ("A deck can have any number of cards named ~.", "A deck can have up to seven cards named ~."):
            c = card("Test Rats", "{1}{B}", "Creature — Rat", text, 1, 1)
            self.assertEqual((c.unsupported, c.triggers, c.activated), ([], [], []), text)


@unittest.skipUnless(DB_FILE.exists(), "card database not built")
class RealCards(unittest.TestCase):
    def setUp(self):
        from mtgsim.carddb import CardDB
        self.db = CardDB(offline=True)
        self.addCleanup(self.db._all.close)
        self.a, self.b = Player("a", [], HeuristicAI()), Player("b", [], HeuristicAI())
        self.g = Game(self.a, self.b, random.Random(0), log=True)
        self.g.turn, self.g.step = 3, "main1"
        self.a.library = self.b.library = [ISLAND] * 10

    def put(self, owner, name):
        x = self.g.enter_battlefield(owner, self.db.get(name))
        x.sick = False
        return x

    def test_full(self):
        from mtgsim.coverage import card_coverage
        for name in ("Rock Lobster", "Scissors Lizard", "Paper Tiger", "Relentless Rats", "Shadowborn Apostle",
                     "Seven Dwarves", "Baloth Packhunter", "Charmed Stray", "Genasi Enforcers", "Pack Mastiff",
                     "Timberpack Wolf", "Cleric of the Forward Order", "Hare Apparent", "Walker of the Wastes",
                     "Ivory Guardians", "Gladewalker Ritualist"):
            self.assertEqual(card_coverage(self.db.get(name)).status, "full", name)

    def test_named_creatures_cant_attack_or_block(self):
        self.put(self.a, "Rock Lobster")
        lizard = self.put(self.b, "Scissors Lizard")
        bears = self.put(self.b, "Grizzly Bears")
        self.assertFalse(lizard.can_attack())
        self.assertTrue(bears.can_attack())
        tiger = self.put(self.b, "Paper Tiger")         # the Lizard's own line names Paper Tiger
        self.assertFalse(tiger.can_attack())

    def test_count_other_creatures_with_the_same_name(self):
        wolves = [self.put(self.a, "Timberpack Wolf") for _ in range(3)]
        self.put(self.a, "Relentless Rats")
        self.assertEqual([w.power for w in wolves], [4, 4, 4])         # 2/2 +1/+1 for each other one
        rats = [self.put(self.b, "Relentless Rats")]
        self.assertEqual(rats[0].power, 3)          # the other Rats on the battlefield count, whoever controls them

    def test_named_land_count(self):
        walker = self.put(self.a, "Walker of the Wastes")
        base = walker.power
        self.put(self.a, "Wastes")
        self.put(self.b, "Wastes")
        self.g.enter_battlefield(self.a, ISLAND)
        self.assertEqual(walker.power, base + 1)

    def test_hare_apparent_makes_one_rabbit_per_other_hare(self):
        for _ in range(2):
            self.put(self.a, "Hare Apparent")
        self.g.settle()
        before = sum(1 for x in self.a.battlefield if x.card.is_token)
        self.put(self.a, "Hare Apparent")
        self.g.settle()
        self.assertEqual(sum(1 for x in self.a.battlefield if x.card.is_token) - before, 2)

    def test_genasi_enforcers_pump_only_the_named_creatures(self):
        enforcer = self.put(self.a, "Genasi Enforcers")
        other = self.put(self.a, "Grizzly Bears")
        base = enforcer.power
        effects = enforcer.card.activated[0].effects
        from mtgsim.engine import StackItem
        self.g.stack.append(StackItem(self.a, list(effects), [None] * len(effects), source=enforcer, name="x"))
        self.g.resolve_top()
        self.assertEqual((enforcer.power, other.power), (base + 1, 2))

    def test_ivory_guardians_ignore_red_tokens(self):
        guardian = self.put(self.a, "Ivory Guardians")
        base = guardian.power
        import dataclasses
        token = dataclasses.replace(card("Red Token", "{R}", "Creature — Elemental", "", 1, 1), is_token=True)
        self.g.enter_battlefield(self.b, token)
        self.assertEqual(guardian.power, base)
        self.put(self.b, "Goblin Piker")                # a nontoken red permanent
        self.assertEqual(guardian.power, base + 1)


if __name__ == "__main__":
    unittest.main()
