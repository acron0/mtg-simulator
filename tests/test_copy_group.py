"""'Choose target creature. Each other creature [you control] becomes a copy of that creature until end of turn,
except it isn't legendary.' (#340, copies._become_group)."""
import os
import random
import unittest

from mtgsim import copies
from mtgsim.ai import HeuristicAI
from mtgsim.carddb import ALL_CARDS, CardDB
from mtgsim.engine import Game, Player
from tests.test_combat_triggers import Scripted
from tests.test_templates import ISLAND, card

LEGEND = card("Test Legend", "{3}{G}", "Legendary Creature — Elf Warrior", "Trample", 5, 4)
BEAR = card("Test Bear", "{1}{G}", "Creature — Bear", "", 2, 2)
CUB = card("Test Cub", "{G}", "Creature — Bear", "", 1, 1)
ROCK = card("Test Rock", "{2}", "Artifact", "", cmc=2)


class Parse(unittest.TestCase):
    def test_shapes(self):
        c = card("Group Test", "{2}{U}", "Sorcery", "Choose target creature you control. Each other creature you "
                 "control becomes a copy of that creature until end of turn, except it isn't legendary.")
        self.assertEqual(c.unsupported, [])
        eff = c.spell_effects[-1]
        self.assertEqual((eff.kind, eff.target, eff.data["group"], eff.data["who"], eff.data["mods"]),
                         ("become_copy", "prev", "creature", "mine", {"legendary": False}))

    def test_refusals(self):
        for text in ("Choose target creature you control. Each creature you control becomes a copy of that creature "
                     "until end of turn.",                                     # includes the target itself
                     "Choose target creature you control. Each other creature you control becomes a copy of that "
                     "creature.",                                              # no duration
                     "Choose target creature you control. Each other creature you control becomes a copy of that "
                     "creature until end of turn, except it flurbles."):
            c = card("Group Test", "{2}{U}", "Sorcery", text)
            self.assertTrue(c.unsupported, text)


@unittest.skipUnless(os.path.exists(ALL_CARDS), "card database not built")
class Games(unittest.TestCase):
    def setUp(self):
        self.db = CardDB(offline=True)
        self.a, self.b = Player("a", [], Scripted()), Player("b", [], Scripted())
        self.g = Game(self.a, self.b, random.Random(0), log=True)
        self.g.turn, self.g.step = 2, "main1"
        for p in self.g.players:
            p.library = [ISLAND] * 20
            p.ai.attack, p.ai.block = (), {}
            p.ai.respond = p.ai.respond_extras = lambda *args: None

    def islands(self, n):
        for _ in range(n):
            self.g.enter_battlefield(self.a, ISLAND).sick = False

    def test_nanogene_conversion_copies_every_other_creature_until_end_of_turn(self):
        self.assertEqual(self.db.get("Nanogene Conversion").unsupported, [])
        legend = self.g.enter_battlefield(self.a, LEGEND)
        bear = self.g.enter_battlefield(self.a, BEAR)
        theirs = self.g.enter_battlefield(self.b, CUB)
        rock = self.g.enter_battlefield(self.a, ROCK)
        self.islands(4)
        spell = self.db.get("Nanogene Conversion")
        self.a.hand = [spell]
        self.assertTrue(self.g.cast(self.a, spell, [legend]))
        self.g.settle()
        for perm in (bear, theirs):           # "each other creature": both players' creatures
            self.assertEqual((perm.card.name, perm.power, perm.toughness), ("Test Legend", 5, 4))
            self.assertFalse(perm.card.legendary)
        self.assertTrue(legend.card.legendary)
        self.assertIn(legend, self.a.battlefield)          # no legend-rule loss: the copies aren't legendary
        self.assertEqual(rock.card.name, "Test Rock")
        self.g.cleanup(self.a) if hasattr(self.g, "cleanup") else None
        for perm in (bear, theirs):
            copies.revert(perm)
        self.assertEqual((bear.card.name, theirs.card.name), ("Test Bear", "Test Cub"))

    def test_echoing_equation_only_your_creatures(self):
        equation = self.db.get("Augmenter Pugilist // Echoing Equation")
        self.assertEqual(equation.back.unsupported if equation.back else equation.unsupported, [])
        eff = next(e for face in (equation, equation.back) if face is not None for e in face.spell_effects
                   if e.kind == "become_copy")
        self.assertEqual(eff.data["who"], "mine")
        legend = self.g.enter_battlefield(self.a, LEGEND)
        bear = self.g.enter_battlefield(self.a, BEAR)
        theirs = self.g.enter_battlefield(self.b, CUB)
        from mtgsim.engine.state import StackItem
        from mtgsim.cards.model import Effect
        effects = [Effect("die_roll", target="creature_mine", data={"sides": 0}), eff]
        self.g.stack.append(StackItem(self.a, effects, [legend, None], card=equation.back, kind="spell"))
        self.g.settle()
        self.assertEqual(bear.card.name, "Test Legend")
        self.assertEqual(theirs.card.name, "Test Cub")

    def test_target_gone_does_nothing(self):
        legend = self.g.enter_battlefield(self.a, LEGEND)
        bear = self.g.enter_battlefield(self.a, BEAR)
        eff = self.db.get("Nanogene Conversion").spell_effects[-1]
        copies.resolve(self.g, self.a, eff, None)
        self.g.leave_battlefield(legend, "graveyard")
        copies.resolve(self.g, self.a, eff, legend)
        self.assertEqual(bear.card.name, "Test Bear")

    def test_ai_value_and_cast(self):
        eff = self.db.get("Nanogene Conversion").spell_effects[-1]
        self.g.enter_battlefield(self.a, CUB)
        self.assertLess(copies.value(self.g, self.a, eff), 0)       # nothing else to copy onto
        legend = self.g.enter_battlefield(self.a, LEGEND)
        self.g.enter_battlefield(self.a, BEAR)
        self.assertGreater(copies.value(self.g, self.a, eff), 0)
        self.a.ai = HeuristicAI()
        self.islands(4)
        self.a.hand = [self.db.get("Nanogene Conversion")]
        self.a.ai.main_phase(self.g, self.a)
        self.g.settle()
        names = sorted(x.card.name for x in self.a.battlefield if x.is_creature)
        self.assertEqual(names, ["Test Legend"] * 3)
        self.assertIn(legend, self.a.battlefield)

    def test_ai_activates_loki_naming_its_best_creature(self):
        from mtgsim.engine.policy import choose_ability
        self.a.ai = HeuristicAI()
        loki = self.g.enter_battlefield(self.a, self.db.get("Loki, Lord of Misrule"))
        loki.sick = False
        self.assertEqual(loki.card.unsupported, [])
        self.g.enter_battlefield(self.a, CUB)
        titan = self.g.enter_battlefield(self.a, card("Test Titan", "{6}", "Creature — Giant", "", 7, 7))
        self.g.enter_battlefield(self.b, BEAR)
        self.islands(1)
        action = choose_ability(self.g, self.a, instant=False)
        self.assertIsNotNone(action)
        self.assertTrue(self.g.do_action(self.a, action))
        self.g.settle()
        self.assertEqual(sorted(x.card.name for x in self.a.battlefield if x.is_creature), ["Test Titan"] * 3)
        self.assertEqual(titan.card.name, "Test Titan")
        self.assertEqual([x.card.name for x in self.b.battlefield], ["Test Bear"])      # "you control"


if __name__ == "__main__":
    unittest.main()
