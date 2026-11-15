"""One-shot creature-type and card-type changes through the animation verb (#406 slice 1):
"becomes a Dragon with base power and toughness 4/4", "becomes a Pirate in addition to its other types",
"becomes an artifact in addition to its other types"."""
import unittest

from mtgsim.cx_grammar import parse_sentence

from tests.test_cx_grammar import DB_FILE, Base
from tests.test_templates import BEAR, card

RELIC = card("Test Relic", "{2}", "Artifact", "")
SMITH = card("Test Smith", "{1}", "Artifact Creature — Human Artificer", "", 1, 1)


def data(s):
    effs = parse_sentence(s)
    return None if effs is None else effs[0].data


class Parsing(unittest.TestCase):
    def test_subtype_only(self):
        d = data("Until end of turn, target creature becomes a Dragon with base power and toughness 4/4 and gains "
                 "flying.")
        self.assertEqual((d["subtypes"], d["types"], d["pt"], d["subtypes_only"]), (("Dragon",), (), (4, 4), True))
        d = data("Until end of turn, target creature becomes a blue and red Dragon Illusion with base power and "
                 "toughness 4/4.")
        self.assertEqual((d["subtypes"], d["colors"]), (("Dragon", "Illusion"), "RU"))
        d = data("Until end of turn, creatures you control become Dragons with base power and toughness 4/4.")
        self.assertEqual(d["effects"][0].data["subtypes"], ("Dragon",))
        d = data("Until end of turn, ~ becomes a Dragon with base power and toughness 4/4, flying, and haste.")
        self.assertEqual(d["keywords"], ("flying", "haste"))
        d = data("Until end of turn, target creature becomes a Pirate in addition to its other types.")
        self.assertTrue(d["addition"] and d["subtypes_only"] and "pt" not in d)

    def test_card_type_addition(self):
        d = data("Target nonland permanent becomes an artifact in addition to its other types until end of turn.")
        self.assertEqual((d["types"], d["types_only"]), (("Artifact",), True))
        d = data("Until end of turn, target creature you control becomes a blue artifact in addition to its other "
                 "colors and types.")
        self.assertEqual((d["types"], d["colors"]), (("Artifact",), "U"))

    def test_shrinking_is_aimed_at_their_creature(self):
        self.assertEqual(data("Until end of turn, target creature becomes a white Rabbit with base power and "
                              "toughness 0/1.")["side"], "theirs")
        self.assertEqual(data("Until end of turn, target creature becomes a Dragon with base power and toughness "
                              "4/4.")["side"], "mine")

    def test_rejects(self):
        for s in ("Until end of turn, target creature becomes a Dragons with base power and toughness 4/4.",
                  "Until end of turn, target creature becomes a Forest with base power and toughness 4/4.",
                  "Until end of turn, creatures you control become Dragon with base power and toughness 4/4.",
                  "Until end of turn, target creature becomes a Dragon with base power and toughness 4/4 and banding.",
                  "Target creature becomes a 3/3 Golem until end of turn.",          # no "base": not read
                  "Until end of turn, target creature becomes a blue Dragon in addition to its other colors and "
                  "types and Wizard.",
                  "Target permanent becomes a black artifact in addition to its other types until end of turn.",
                  "Target permanent becomes an artifact until end of turn."):       # replacing card types
            self.assertIsNone(parse_sentence(s), s)


class Resolving(Base):
    def resolve(self, text, target):
        effs = parse_sentence(text)
        for e in effs:
            self.game.resolve(self.a, e, target)

    def test_becomes_a_dragon_until_end_of_turn(self):
        bear = self.perm(BEAR, self.b)
        self.resolve("Until end of turn, target creature becomes a Dragon with base power and toughness 4/4 and "
                     "gains flying.", bear)
        self.assertEqual((bear.power, bear.toughness), (4, 4))
        self.assertEqual(set(bear.card.subtypes), {"Dragon"})         # no longer a Bear
        self.assertEqual(set(bear.card.types), {"Creature"})
        self.assertTrue(bear.has("flying"))
        bear.counters["+1/+1"] = 1
        self.assertEqual(bear.power, 5)                               # counters apply after base P/T
        bear.counters.clear()
        self.end_turn()
        bear.animated = None                       # the turn's cleanup ends an until-end-of-turn animation
        self.assertEqual(set(bear.card.subtypes), {"Bear"})
        self.assertEqual((bear.power, bear.toughness), (2, 2))

    def test_card_types_and_other_subtypes_stay(self):
        smith = self.perm(SMITH, self.a)
        self.resolve("Until end of turn, target creature becomes a Frog with base power and toughness 1/1.", smith)
        self.assertEqual(set(smith.card.types), {"Artifact", "Creature"})
        self.assertEqual(set(smith.card.subtypes), {"Frog"})

    def test_in_addition_keeps_its_types(self):
        bear = self.perm(BEAR, self.a)
        self.resolve("Until end of turn, target creature becomes a blue Crab in addition to its other types.", bear)
        self.assertEqual(set(bear.card.subtypes), {"Bear", "Crab"})
        self.assertEqual(set(bear.card.colors), {"U"})                 # "blue" without "other colors": set
        self.assertEqual((bear.power, bear.toughness), (2, 2))

    def test_card_type_addition(self):
        bear = self.perm(BEAR, self.a)
        self.resolve("Until end of turn, target creature becomes an artifact in addition to its other types.", bear)
        self.assertEqual(set(bear.card.types), {"Artifact", "Creature"})
        self.assertEqual(set(bear.card.subtypes), {"Bear"})
        self.end_turn()
        self.assertEqual(set(bear.card.types), {"Creature"})

    def test_noncreature_gets_no_creature_type(self):
        relic = self.perm(RELIC, self.a)
        self.resolve("Until end of turn, target permanent becomes a Dragon with base power and toughness 4/4.", relic)
        self.assertFalse(relic.is_creature)
        self.assertEqual(set(relic.card.subtypes), set())

    def test_figure_of_destiny_levels_up(self):
        fig = card("Test Figure", "{R/W}", "Creature — Kithkin", "{R/W}: ~ becomes a Kithkin Spirit with base power "
                   "and toughness 4/4.\n{R/W}{R/W}{R/W}: If ~ is a Spirit, it becomes a Kithkin Spirit Warrior with "
                   "base power and toughness 8/8.", 1, 1)
        self.assertEqual(fig.unsupported, [])
        f = self.perm(fig, self.a)
        level2 = fig.activated[1].effects[0]
        self.assertFalse(f.condition(level2.cond))                     # not a Spirit yet
        self.game.resolve(self.a, fig.activated[0].effects[0], f)
        self.assertEqual((f.power, f.toughness), (4, 4))
        self.assertIn("Spirit", f.card.subtypes)
        self.assertTrue(f.condition(level2.cond))
        self.end_turn()
        self.assertIn("Spirit", f.card.subtypes)                       # no duration: for good
        self.assertEqual((f.power, f.toughness), (4, 4))


class AIUse(Base):
    def test_ai_shrinks_the_opponents_creature(self):
        mine = self.perm(BEAR, self.a)
        big = card("Test Giant", "{4}", "Creature — Giant", "", 5, 5)
        theirs = self.perm(big, self.b)
        spell = self.spell("Until end of turn, target creature becomes a white Rabbit with base power and toughness "
                           "0/1.")
        plan = self.a.ai.plan_spell(self.game, self.a, spell, precombat=True)
        self.assertIsNotNone(plan)
        self.assertIs(plan[1][0], theirs)
        self.assertIsNot(plan[1][0], mine)

    def test_ai_grows_its_own_creature(self):
        mine = self.perm(BEAR, self.a)
        mine.sick = False
        theirs = self.perm(card("Test Giant", "{4}", "Creature — Giant", "", 5, 5), self.b)
        spell = self.spell("Until end of turn, target creature becomes a Dragon with base power and toughness 6/6 and "
                           "gains flying.")
        plan = self.a.ai.plan_spell(self.game, self.a, spell, precombat=True)
        self.assertIsNotNone(plan)
        self.assertIs(plan[1][0], mine)
        self.assertIsNot(plan[1][0], theirs)


@unittest.skipUnless(DB_FILE.exists(), "card database not built")
class RealCards(unittest.TestCase):
    def test_cards_parse_fully(self):
        from mtgsim.carddb import CardDB
        from mtgsim.coverage import FULL, card_coverage
        db = CardDB()
        for name in ("Nogi, Draco-Zealot", "Mordenkainen's Polymorph", "Metamorphic Blast", "Scale Up", "Skinshifter",
                     "Figure of Destiny", "Bogardan Dragonheart", "Coercive Recruiter", "Scuttling Sentinel",
                     "Thran Forge", "Liquimetal Torque", "Unctus, Grand Metatect", "Eccentric Apprentice"):
            row = card_coverage(db.get(name))
            self.assertEqual(row.status, FULL, (name, row.ignored))


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(DB_FILE.exists(), "card database not built")
class RestrictedType(Base):
    def test_boldwyr_cowards_the_opponents_creature_and_warriors_its_own(self):
        from mtgsim.carddb import CardDB
        from mtgsim.engine.policy import default_choose_target
        boldwyr = CardDB().get("Boldwyr Intimidator")
        src = self.perm(boldwyr, self.a)
        mine = self.perm(BEAR, self.a)
        theirs = self.perm(card("Test Giant", "{4}", "Creature — Giant", "", 5, 5), self.b)
        coward, warrior = (a.effects[0] for a in boldwyr.activated)
        self.game.target_source = src
        target = default_choose_target(self.game, self.a, coward)
        self.assertIs(target, theirs)
        self.assertIsNot(target, mine)
        self.assertIn(default_choose_target(self.game, self.a, warrior), (mine, src))

    def test_unrestricted_type_change_is_mine(self):
        from mtgsim.engine.policy import default_choose_target
        mine = self.perm(BEAR, self.a)
        self.perm(card("Test Giant", "{4}", "Creature — Giant", "", 5, 5), self.b)
        eff = parse_sentence("Until end of turn, target creature becomes a Pirate in addition to its other types.")[0]
        self.game.target_source = None
        self.assertIs(default_choose_target(self.game, self.a, eff), mine)
