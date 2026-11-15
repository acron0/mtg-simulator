"""#315: "that much" damage and life aimed back at the creature a damage trigger names, or its controller."""
import random
import unittest
from pathlib import Path

from mtgsim.ai import HeuristicAI
from mtgsim.engine import Game, Player
from tests.test_templates import ISLAND, card

DB_FILE = Path(__file__).resolve().parents[1] / "mtgsim" / "data" / "cards.sqlite3"


class Refs(unittest.TestCase):
    def setUp(self):
        self.a, self.b = Player("a", [], HeuristicAI()), Player("b", [], HeuristicAI())
        self.g = Game(self.a, self.b, random.Random(0), log=True)
        self.g.turn, self.g.step = 3, "main1"
        self.a.library = self.b.library = [ISLAND] * 10

    def put(self, owner, name, text, p=None, t=None, types=None):
        c = card(name, "{2}", types or ("Creature — Sliver" if p is not None else "Enchantment"), text, p, t)
        self.assertEqual(c.unsupported, [], text)
        return self.g.enter_battlefield(owner, c)

    def aura(self, owner, text, host):
        x = self.put(owner, "Test Aura", "Enchant creature\n" + text, types="Enchantment — Aura")
        x.aura_host = host
        host.auras.append(x)
        return x

    def test_its_controller_gains_even_when_the_subject_is_the_trigger_itself(self):
        sliver = self.put(self.a, "Essence", "Whenever a Sliver deals damage, its controller gains that much life.", 2, 2)
        other = self.put(self.b, "Other Sliver", "", 3, 3)
        self.g.deal_damage(self.b, 2, by=self.a, source=sliver)
        self.g.settle()
        self.assertEqual((self.a.life, self.b.life), (22, 18))
        self.g.deal_damage(self.a, 3, by=self.b, source=other)       # their Sliver: they gain
        self.g.settle()
        self.assertEqual((self.a.life, self.b.life), (19, 21))

    def test_aura_deals_that_much_to_the_enchanted_creature(self):
        bear = self.put(self.b, "Bear", "", 2, 4, "Creature — Bear")
        self.aura(self.a, "Whenever enchanted creature deals damage, ~ deals that much damage to that creature.", bear)
        self.g.deal_damage(self.a, 2, by=self.b, source=bear)
        self.g.settle()
        self.assertEqual(bear.damage, 2)

    def test_enchanted_creature_dealt_damage_hurts_its_controller(self):
        bear = self.put(self.b, "Bear", "", 2, 4, "Creature — Bear")
        self.aura(self.a, "Whenever enchanted creature is dealt damage, it deals that much damage to its controller.",
                  bear)
        mine = self.put(self.a, "Mine", "", 3, 3, "Creature — Bear")
        self.g.deal_damage(bear, 3, by=self.a, source=mine)
        self.g.settle()
        self.assertEqual((self.a.life, self.b.life), (20, 17))

    def test_each_opponent_is_untargeted(self):
        bear = self.put(self.a, "Bear", "", 2, 4, "Creature — Bear")
        self.aura(self.a, "Whenever enchanted creature is dealt damage, it deals that much damage to each opponent.",
                  bear)
        self.put(self.b, "Leyline", "You have hexproof.")
        self.g.deal_damage(bear, 2, by=self.b)
        self.g.settle()
        self.assertEqual(self.b.life, 18)          # #484: hexproof doesn't stop an untargeted "each opponent"

    def test_creature_dealt_damage_its_controller_is_hit(self):
        self.put(self.a, "Repercussion", "Whenever a creature is dealt damage, ~ deals that much damage to that "
                                         "creature's controller.")
        bear = self.put(self.b, "Bear", "", 2, 4, "Creature — Bear")
        self.g.deal_damage(bear, 3, by=self.a)
        self.g.settle()
        self.assertEqual(self.b.life, 17)

    def test_enchanted_creature_dealing_damage_to_you(self):
        ogre = self.put(self.b, "Ogre", "", 3, 3, "Creature — Ogre")
        self.aura(self.a, "Whenever enchanted creature deals damage to you, ~ deals that much damage to that "
                          "creature's controller.", ogre)
        self.g.deal_damage(self.a, 3, by=self.b, source=ogre)
        self.g.settle()
        self.assertEqual((self.a.life, self.b.life), (17, 17))

    def test_each_other_opponent_is_nobody_in_two_player(self):
        self.put(self.a, "Hydra", "Whenever ~ deals combat damage to an opponent, it deals that much damage to each "
                                  "other opponent.", 3, 3)
        hydra = self.a.battlefield[-1]
        self.g.deal_damage(self.b, 3, by=self.a, source=hydra, combat=True)
        self.g.settle()
        self.assertEqual((self.a.life, self.b.life), (20, 17))


@unittest.skipUnless(DB_FILE.exists(), "card database not built")
class RealCards(unittest.TestCase):
    def test_full(self):
        from mtgsim.carddb import CardDB
        from mtgsim.coverage import card_coverage
        db = CardDB(offline=True)
        self.addCleanup(db._all.close)
        for name in ("Backfire", "Essence Sliver", "Visions of Brutality", "Guilty Conscience", "Repercussion",
                     "Spiteful Shadows", "Flayed Nim", "Hydra Omnivore", "Grenzo's Ruffians", "Amarant Coral"):
            self.assertEqual(card_coverage(db.get(name)).status, "full", name)


if __name__ == "__main__":
    unittest.main()
