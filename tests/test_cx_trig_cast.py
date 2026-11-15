"""Cast-head qualifiers (mtgsim/cx_trig_cast.py, #404): chosen colour/type, keywords, power, zones, targets,
ordinals of one kind of spell, and the "another player" / "enchanted player" subjects."""
import os
import random
import unittest

from mtgsim.carddb import CardDB
from mtgsim.cx_events import compile_head
from mtgsim.engine import Game, Player
from tests.test_combat_triggers import Scripted
from tests.test_templates import BEAR, ISLAND, MOUNTAIN, SHOCK, card

HAVE_DB = os.path.exists("mtgsim/data/cards.sqlite3")
DB = CardDB() if HAVE_DB else None

OPT = card("Test Opt", "{U}", "Instant", "Draw a card.")
BOLT = card("Test Bolt", "{R}", "Instant", "Test Bolt deals 1 damage to any target.")
GOBLIN = card("Test Goblin", "{R}", "Creature — Goblin", "", 1, 1)
ELF = card("Test Elf", "{G}", "Creature — Elf", "", 1, 1)
SECOND = card("Test Second", "{2}{U}", "Enchantment",
              "Whenever you cast your second noncreature spell each turn, draw a card.")


class Heads(unittest.TestCase):
    def test_qualifiers(self):
        cases = {
            "Whenever you cast a spell of the chosen color": [("chosen_color",)],
            "Whenever you cast a creature spell of the chosen type": [("chosen_type",)],
            "Whenever you cast a creature spell that has an Adventure": [("adventure",)],
            "Whenever you cast another spell that has convoke": [("kw", "convoke")],
            "When an opponent casts a creature spell with flying": [("kw", "flying")],
            "Whenever you cast a creature spell with power 5 or greater": [("pow>=", 5)],
            "Whenever you cast a creature spell with mana value 4, 5, or 6": [("mv_in", (4, 5, 6))],
            "Whenever you cast an instant spell during your main phase": [("main",)],
            "Whenever an opponent casts a spell that targets you or a creature you control": [("tg", "me_or_mine")],
        }
        for head, quals in cases.items():
            got = compile_head(head)
            self.assertIsNotNone(got, head)
            self.assertEqual(got[1]["spell"]["q"], quals, head)
        spell = compile_head("Whenever you cast a spell that's white, blue, black, or red")[1]["spell"]
        self.assertEqual(spell["alts"], [("white",), ("blue",), ("black",), ("red",)])
        spell = compile_head("Whenever you cast a spell other than your first spell each turn")[1]["spell"]
        self.assertEqual(spell["nth_not"], 1)
        self.assertEqual(compile_head("Whenever another player casts a spell from anywhere other than their hand")[1]
                         ["player"], "opp")
        self.assertEqual(compile_head("Whenever enchanted player draws a card")[1]["player"], "enchanted")

    def test_refusals(self):
        for head in ("Whenever you cast a spell of the chosen name",
                     "Whenever you cast a spell that has frobnicate",
                     "Whenever you cast a creature spell other than your first instant spell each turn",
                     "Whenever you cast a spell that's white or frobnicated",
                     "Whenever you cast a spell with power 5 or greater and flying",
                     "Whenever you cast a creature spell of the chosen type this turn"):
            self.assertIsNone(compile_head(head), head)


@unittest.skipUnless(HAVE_DB, "card database not built")
class RealCards(unittest.TestCase):
    def test_full(self):
        for n in ("Diamond Knight", "Curse of Wizardry", "Reflections of Littjara", "Vanquisher's Banner",
                  "Wandermare", "Hidden Spider", "Gwenna, Eyes of Gaea", "Aurora Phoenix", "Arcbound Tracker",
                  "Dovin's Acuity", "Hand of the Praetors", "Ichneumon Druid", "Kasla, the Broken Halo",
                  "Slitherwisp", "Quirion Dryad", "Reparations", "Sarkhan's Unsealing", "Kozilek's Unsealing",
                  "The Fantasticar", "Aerial Extortionist", "Ghostly Pilferer", "Danitha, Spear of Agony",
                  "Legolas, Master Archer", "Curse of Fool's Wisdom"):
            self.assertEqual(DB.get(n).unsupported, [], n)


class Base(unittest.TestCase):
    def setUp(self):
        self.a, self.b = Player("a", [], Scripted()), Player("b", [], Scripted())
        self.game = Game(self.a, self.b, random.Random(0), log=True)
        self.game.turn, self.game.step = 2, "main1"
        self.game.active_idx = 0
        for p in (self.a, self.b):
            p.library = [ISLAND] * 20

    def put(self, who, c):
        perm = self.game.enter_battlefield(who, c)
        perm.sick = False
        self.game.settle()
        return perm

    def cast(self, who, c, targets=(), lands=(ISLAND,)):
        for land in lands:
            self.game.enter_battlefield(who, land).tapped = False
        who.hand.append(c)
        self.assertTrue(self.game.cast(who, c, list(targets)), c.name)
        self.game.settle()


class Ordinals(Base):
    def test_second_noncreature_counts_only_noncreature_spells(self):
        self.put(self.a, SECOND)
        hand = len(self.a.hand)
        self.cast(self.a, GOBLIN, lands=(MOUNTAIN,))
        self.cast(self.a, OPT)                      # second spell, first noncreature: no trigger
        self.assertEqual(len(self.a.hand), hand + 1)            # Opt's own draw
        self.cast(self.a, OPT)                      # second noncreature
        self.assertEqual(len(self.a.hand), hand + 3)


@unittest.skipUnless(HAVE_DB, "card database not built")
class Games(Base):
    def test_chosen_color(self):
        knight = self.put(self.a, DB.get("Diamond Knight"))
        knight.chosen_color = "U"
        self.cast(self.a, BOLT, [self.b], lands=(MOUNTAIN,))
        self.assertEqual(knight.counters.get("+1/+1", 0), 0)
        self.cast(self.a, OPT)
        self.assertEqual(knight.counters.get("+1/+1", 0), 1)

    def test_curse_of_wizardry_picks_the_opponents_color(self):
        self.put(self.b, ISLAND)
        blue = card("Test Blue Bear", "{1}{U}", "Creature — Bear", "", 2, 2)
        self.put(self.b, blue)
        curse = self.put(self.a, DB.get("Curse of Wizardry"))
        self.assertEqual(curse.chosen_color, "U")
        self.game.active_idx = 1
        self.cast(self.b, OPT)
        self.assertEqual(self.b.life, 19)

    def test_chosen_type(self):
        banner = self.put(self.a, DB.get("Vanquisher's Banner"))
        banner.chosen_type = "Goblin"
        hand = len(self.a.hand)
        self.cast(self.a, ELF, lands=(card("Test Forest", "", "Basic Land — Forest", "{T}: Add {G}."),))
        self.assertEqual(len(self.a.hand), hand)
        self.cast(self.a, GOBLIN, lands=(MOUNTAIN,))
        self.assertEqual(len(self.a.hand), hand + 1)

    def test_other_than_first_spell(self):
        tracker = self.put(self.a, DB.get("Arcbound Tracker"))
        base = tracker.counters.get("+1/+1", 0)
        self.cast(self.a, OPT)
        self.assertEqual(tracker.counters.get("+1/+1", 0), base)
        self.cast(self.a, OPT)
        self.assertEqual(tracker.counters.get("+1/+1", 0), base + 1)

    def test_targets_you_or_your_creature(self):
        self.put(self.a, DB.get("Reparations"))
        bear = self.put(self.a, BEAR)
        self.game.active_idx = 1
        hand = len(self.a.hand)
        self.cast(self.b, SHOCK, [self.b], lands=(MOUNTAIN,))       # targets its own controller: no trigger
        self.assertEqual(len(self.a.hand), hand)
        self.cast(self.b, SHOCK, [bear], lands=(MOUNTAIN,))
        self.assertEqual(len(self.a.hand), hand + 1)

    def test_enchanted_player_draws(self):
        curse = self.put(self.a, DB.get("Curse of Fool's Wisdom"))
        curse.curse_target = self.b
        self.game.draw(self.a, 1)
        self.game.settle()
        self.assertEqual((self.a.life, self.b.life), (20, 20))
        self.game.draw(self.b, 1)
        self.game.settle()
        self.assertEqual((self.a.life, self.b.life), (22, 18))

    def test_graveyard_cast_trigger(self):
        phoenix = DB.get("Aurora Phoenix")
        self.a.graveyard.append(phoenix)
        self.cast(self.a, OPT)                                  # no cascade: stays
        self.assertIn(phoenix, self.a.graveyard)
        cascader = card("Test Cascader", "{U}", "Sorcery", "Cascade\nDraw a card.")
        self.assertTrue(cascader.cascade or "cascade" in cascader.keywords)
        self.cast(self.a, cascader)
        self.assertNotIn(phoenix, self.a.graveyard)
        self.assertIn(phoenix, self.a.hand)

    def test_opponents_graveyard_card_does_not_see_your_cast(self):
        phoenix = DB.get("Aurora Phoenix")
        self.b.graveyard.append(phoenix)
        self.cast(self.a, card("Test Cascader", "{U}", "Sorcery", "Cascade\nDraw a card."))
        self.assertIn(phoenix, self.b.graveyard)

    def test_target_player_poison_hits_only_the_opponent(self):
        from mtgsim.ai import HeuristicAI
        self.a.ai = HeuristicAI()
        self.put(self.a, DB.get("Hand of the Praetors"))
        infect = card("Test Infector", "{G}", "Creature — Phyrexian", "Infect", 1, 1)
        self.cast(self.a, infect, lands=(card("Test Forest", "", "Basic Land — Forest", "{T}: Add {G}."),))
        self.assertEqual((self.a.counters.get("poison", 0), self.b.counters.get("poison", 0)), (0, 1))

    def test_heuristic_ai_curses_the_opponent(self):
        from mtgsim.ai import HeuristicAI
        a = Player("a", [], HeuristicAI())
        b = Player("b", [], HeuristicAI())
        game = Game(a, b, random.Random(0))
        game.turn, game.step, game.active_idx = 3, "main1", 0
        swamp = card("Test Swamp", "", "Basic Land — Swamp", "{T}: Add {B}.")
        for _ in range(6):                          # {4}{B}{B}
            game.enter_battlefield(a, swamp)
        a.library, b.library = [ISLAND] * 10, [ISLAND] * 10
        a.hand = [DB.get("Curse of Fool's Wisdom")]
        a.ai.main_phase(game, a)
        game.settle()
        curse = next(x for x in a.battlefield if x.card.name == "Curse of Fool's Wisdom")
        self.assertIs(curse.curse_target, b)


if __name__ == "__main__":
    unittest.main()
