"""#642: event results "this way" as a condition and as a quantity (mtgsim.this_way)."""
import random
import unittest

from mtgsim.ai import HeuristicAI
from mtgsim.cards.parse import _parse_effects
from mtgsim.engine import Game, Player, StackItem

from tests.test_cx_grammar import DB_FILE
from tests.test_templates import BEAR, ISLAND, card

ROCK = card("Test Rock", "{2}", "Artifact", "")
CHARM = card("Test Charm", "{2}", "Enchantment", "")
WOLF = card("Test Werewolf", "{2}{G}", "Creature — Human Werewolf", "", 2, 2)
GIANT = card("Test Giant", "{4}{G}", "Creature — Giant", "", 5, 5)

REAL = ("Acolyte Hybrid", "Bonehoard Dracosaur", "Burn from Within", "Coerced Confession", "Deathgorge Scavenger",
        "Fanatic of the Harrowing", "Feral Appetite", "Fumigate", "Gerrard's Verdict", "Gorging Vulture",
        "Liliana's Indignation", "Malfegor", "Noxious Gearhulk", "Patient Rebuilding", "Psychic Miasma",
        "Raven Eagle", "Renegade Reaper", "Silver Bolt", "Smashing Success", "Soul-Shackled Zombie",
        "The Black Arrow", "Titania's Command", "Phyrexian Rebirth", "Rain of Daggers")


class Base(unittest.TestCase):
    def setUp(self):
        self.a = Player("a", [], HeuristicAI())
        self.b = Player("b", [], HeuristicAI())
        self.game = Game(self.a, self.b, random.Random(0), log=True)
        self.game.turn, self.game.step = 1, "main1"
        for p in (self.a, self.b):
            p.library = [ISLAND] * 10

    def cast(self, text, targets=None, types="Sorcery"):
        c = card("Test Spell", "{1}", types, text)
        self.assertEqual(c.unsupported, [], text)
        effs = list(c.spell_effects)
        self.game.stack.append(StackItem(self.a, effs, (targets or []) + [None] * (len(effs) - len(targets or [])),
                                         card=c, name=c.name))
        self.game.resolve_top()
        return c


class Parse(unittest.TestCase):
    @unittest.skipUnless(DB_FILE.exists(), "card database not built")
    def test_real_cards_full(self):
        from mtgsim.carddb import CardDB
        db = CardDB()
        for name in REAL:
            with self.subTest(name=name):
                c = db.get(name)
                self.assertEqual((c.unsupported, c.approximations), ([], []))

    def test_refusals(self):
        for s in ("If a creature card is revealed this way, draw a card.",              # "revealed": not journaled
                  "If you sacrificed a creature this way, draw a card.",                # a cost: not journaled
                  "If a Foo card is exiled this way, draw a card.",
                  "You gain 1 life for each card returned this way.",
                  "You gain 1 life for each creature you controlled that was destroyed this way."):
            with self.subTest(s=s):
                self.assertTrue(_parse_effects(s)[1], s)


class Conditions(Base):
    def test_exiled_creature_card_vs_noncreature(self):
        text = ("Exile target card from a graveyard. If a creature card is exiled this way, you gain 2 life. "
                "If a noncreature card is exiled this way, draw a card.")
        self.b.graveyard.append(BEAR)
        self.b.graveyard.append(ROCK)
        self.cast(text, [self.b.graveyard[0]])
        self.assertEqual((self.a.life, len(self.a.hand)), (22, 0))
        self.cast(text, [self.b.graveyard[0]])
        self.assertEqual((self.a.life, len(self.a.hand)), (22, 1))

    def test_destroyed_artifact_only(self):
        text = "Destroy target artifact or enchantment. If an artifact is destroyed this way, you gain 3 life."
        charm = self.game.enter_battlefield(self.b, CHARM)
        self.cast(text, [charm])
        self.assertEqual(self.a.life, 20)
        rock = self.game.enter_battlefield(self.b, ROCK)
        self.cast(text, [rock])
        self.assertNotIn(rock, self.b.battlefield)
        self.assertEqual(self.a.life, 23)

    def test_both_effects_of_one_condition_read_the_same_result(self):
        """"If ..., A and B": B is checked after A resolved, and still reads the exile, not A's own result."""
        self.b.graveyard.append(BEAR)
        self.cast("Exile target card from a graveyard. If a creature card is exiled this way, each opponent loses 2 "
                  "life and you gain 2 life.", [self.b.graveyard[0]])
        self.assertEqual((self.a.life, self.b.life), (22, 18))

    def test_dealt_damage_this_way(self):
        text = "~ deals 3 damage to target creature. If a Werewolf is dealt damage this way, you gain 5 life."
        giant = self.game.enter_battlefield(self.b, GIANT)
        self.cast(text, [giant])
        self.assertEqual(self.a.life, 20)
        wolf = self.game.enter_battlefield(self.b, WOLF)
        self.cast(text, [wolf])
        self.assertEqual(self.a.life, 25)


class Quantities(Base):
    def test_milled_creature_cards(self):
        self.a.library = [ISLAND, BEAR, ISLAND, BEAR, BEAR]        # the top is the end
        self.cast("Mill four cards. You gain 1 life for each creature card milled this way.")
        self.assertEqual(self.a.life, 23)

    def test_put_into_their_graveyard(self):
        self.b.library = [BEAR, BEAR, ISLAND, BEAR, ISLAND]
        self.cast("Target player mills four cards. You draw a card for each creature card put into their graveyard "
                  "this way.", [self.b])
        self.assertEqual(len(self.a.hand), 2)

    def test_creatures_destroyed_this_way(self):
        for _ in range(3):
            self.game.enter_battlefield(self.b, BEAR)
        self.game.enter_battlefield(self.a, BEAR)
        self.cast("Destroy all creatures. You gain 1 life for each creature destroyed this way.")
        self.assertEqual(self.a.life, 24)

    def test_discarded_this_way(self):
        self.a.hand = [ISLAND, BEAR, ISLAND]
        self.cast("Discard your hand, then draw cards equal to the number of cards discarded this way.")
        self.assertEqual(len(self.a.hand), 3)
        self.assertEqual(len(self.a.graveyard), 4)          # the three cards and the spell

    def test_mana_for_each_card_discarded(self):
        self.a.hand = [ISLAND, BEAR]
        self.cast("Discard two cards. Add {R} for each card discarded this way.")
        self.assertEqual(len(self.a.pool), 2)

    def test_noncreature_milled_condition(self):
        self.a.library = [BEAR, ISLAND]
        self.cast("Mill a card. If a noncreature card was milled this way, you gain 2 life.")
        self.assertEqual(self.a.life, 22)
        self.cast("Mill a card. If a noncreature card was milled this way, you gain 2 life.")
        self.assertEqual(self.a.life, 22)

    def test_nothing_before_counts_nothing(self):
        self.cast("You gain 1 life for each creature card milled this way.")
        self.assertEqual(self.a.life, 20)


if __name__ == "__main__":
    unittest.main()
