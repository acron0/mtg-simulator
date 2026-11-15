"""#321: an "instead" sentence tied to the instruction it replaces, run as exactly one of the two branches.

- the whole sentence before ("create a 1/1 Insect token. If ..., create a token that's a copy of ~ instead");
- its object by an anaphor ("destroy target creature. If that permanent is black, exile it instead");
- the replaced group pump with other numbers ("those creatures get +2/+2 until end of turn instead");
- the kicked version ("If this spell was kicked, create twelve of those tokens instead");
- conditions on the replaced effect's object ("is white or blue", "has toxic", "has a +1/+1 counter on it").
"""
import unittest

from mtgsim.cards.parse import _parse_effects
from mtgsim.engine import StackItem
from tests.test_cx_grammar import Base, DB_FILE
from tests.test_templates import BEAR, card

WHITE = card("Test Knight", "{W}", "Creature — Human Knight", "", 2, 2)
BLACK = card("Test Zombie", "{B}", "Creature — Zombie", "", 2, 2)
RED = card("Test Ogre", "{R}", "Creature — Ogre", "", 3, 3)
VAMPIRE = card("Test Vampire", "{B}", "Creature — Vampire", "", 2, 2)


class Parsing(unittest.TestCase):
    def test_anaphor_takes_the_replaced_object(self):
        effects, bad = _parse_effects("Destroy target creature. If that creature is black, exile it instead.")
        self.assertEqual(bad, [])
        self.assertEqual([(e.kind, e.target) for e in effects], [("destroy", "creature"), ("exile_permanent", "prev")])
        self.assertTrue(effects[0].cond.startswith('lib:["not"'))
        self.assertTrue(effects[1].data["instead_branch"])
        self.assertNotIn("cx_anaphor", effects[1].data)

    def test_anaphor_without_a_chosen_object_stays_unmatched(self):
        for text in ("Draw a card. If you control a Wizard, exile it instead.",        # nothing is "it"
                     "Create a 1/1 white Soldier creature token. If you control a Wizard, exile it instead."):
            effects, bad = _parse_effects(text)
            self.assertTrue(bad, text)
            self.assertFalse(any(e.data.get("instead_gate") for e in effects), text)

    def test_group_pump_numbers(self):
        effects, bad = _parse_effects("Creatures you control get +1/+1 until end of turn. If you control a Wizard, "
                                      "those creatures get +2/+2 until end of turn instead.")
        self.assertEqual(bad, [])
        self.assertEqual([(e.kind, e.amount, e.amount2) for e in effects], [("pump_all", 1, 1), ("pump_all", 2, 2)])

    def test_group_pump_refusals(self):
        for text in (
                # a single target is "that creature", not "those creatures"
                "Target creature gets +1/+1 until end of turn. If you control a Wizard, those creatures get +2/+2 "
                "until end of turn instead.",
                # a -N/-N kind can't turn into a pump
                "Creatures your opponents control get -1/-1 until end of turn. If you control a Wizard, those "
                "creatures get +2/+2 until end of turn instead.",
                # a pump that also grants a keyword: the numbers alone would drop it
                "Creatures you control get +1/+1 and gain trample until end of turn. If you control a Wizard, "
                "those creatures get +2/+2 until end of turn instead."):
            effects, bad = _parse_effects(text)
            self.assertTrue(bad, text)
            self.assertFalse(any(e.data.get("instead_gate") for e in effects), text)

    def test_unparsed_sentence_before_is_not_skipped(self):
        # the sentence before gave no effects: the one before that is not what "instead" replaces
        effects, bad = _parse_effects("Draw a card. Frobnicate the widget. If you control a Wizard, you gain 3 life "
                                      "instead.")
        self.assertEqual(len(bad), 2)
        self.assertEqual([(e.kind, e.cond) for e in effects], [("draw", "")])

    def test_color_or_keyword_and_counter_conditions(self):
        from mtgsim.cards.clauses import _if_cond
        self.assertIn('"any_color":["W","U"]', _if_cond("that creature is white or blue"))
        self.assertIn('"kw":"flying"', _if_cond("that creature has flying"))
        self.assertIn('"toxic":true', _if_cond("that creature has toxic"))
        self.assertIn('"counters":["+1/+1",">=",2]', _if_cond("that creature has two or more +1/+1 counters on it"))
        self.assertIn('"counters":["+1/+1",">=",1]', _if_cond("that creature has a +1/+1 counter on it"))
        self.assertEqual(_if_cond("that creature has flying or reach"), "")


@unittest.skipUnless(DB_FILE.exists(), "card database not built")
class OracleCards(Base):
    def setUp(self):
        super().setUp()
        from mtgsim.carddb import CardDB
        self.db = CardDB(offline=True)

    def get(self, name):
        c = self.db.get(name)
        self.assertEqual(c.unsupported, [], name)
        return c

    def resolve(self, effects, targets=None, card=None, source=None, kicks=0, by=None):
        item = StackItem(by or self.a, list(effects), targets or [None] * len(effects), card=card, source=source,
                         name=getattr(card, "name", "") or "ability", kind="" if card else "trigger")
        item.kicks = kicks
        self.game.stack.append(item)
        self.game.resolve_top()
        return item

    def kicked(self, c):
        return next(a for a in c.alt_costs if a.kind == "kicker").effects

    def test_now_full(self):
        for name in ("Scute Swarm", "Lightning Dart", "Divine Smite", "Ether Well", "Pride of Conquerors",
                     "Marsh Casualties", "Conqueror's Pledge", "Rona's Vortex", "Tezzeret's Simulacrum",
                     "Blade of the Bloodchief", "Bring Low", "Hexgold Slash", "Withering Curse", "Court of Grace",
                     "Composer of Spring", "Desolation Angel", "Dauntless Unity", "Guul Draz Overseer"):
            with self.subTest(name):
                self.get(name)

    def test_lightning_dart_color_upgrade(self):
        c = self.get("Lightning Dart")
        for color, damage in (("R", 1), ("W", 4), ("U", 4)):
            with self.subTest(color=color):
                victim = self.perm(card("Test Wall", "{%s}" % color, "Creature — Wall", "", 0, 9), self.b)
                self.resolve(c.spell_effects, [victim] + [None] * (len(c.spell_effects) - 1), card=c)
                self.assertEqual(victim.damage, damage)

    def test_divine_smite_phases_out_or_exiles(self):
        c = self.get("Divine Smite")
        for victim_card, exiled in ((WHITE, False), (BLACK, True)):
            with self.subTest(victim_card.name):
                victim = self.perm(victim_card, self.b)
                self.resolve(c.spell_effects, [victim] + [None] * (len(c.spell_effects) - 1), card=c)
                self.assertNotIn(victim, self.b.battlefield)
                self.assertEqual(bool(getattr(victim, "phased_out", False)), not exiled)
                self.assertEqual([x.name for x in self.b.exile], [victim_card.name] if exiled else [])

    def test_ether_well_top_or_bottom(self):
        c = self.get("Ether Well")
        for victim_card, index in ((WHITE, -1), (RED, 0)):
            with self.subTest(victim_card.name):
                self.b.library = [BEAR] * 5
                victim = self.perm(victim_card, self.b)
                self.resolve(c.spell_effects, [victim] + [None] * (len(c.spell_effects) - 1), card=c)
                self.assertNotIn(victim, self.b.battlefield)
                self.assertEqual(len(self.b.library), 6)
                self.assertEqual(self.b.library[index].name, victim_card.name)

    def test_pride_of_conquerors_blessing(self):
        c = self.get("Pride of Conquerors")
        for blessed, size in ((False, 3), (True, 4)):
            with self.subTest(blessed=blessed):
                self.a.blessing = blessed
                bear = self.perm(BEAR, self.a)
                self.resolve(c.spell_effects, card=c)
                self.assertEqual((bear.power, bear.toughness), (size, size))
                self.a.battlefield.remove(bear)

    def test_marsh_casualties_kicked(self):
        c = self.get("Marsh Casualties")
        for kicked, effects, size in ((False, c.spell_effects, 2), (True, self.kicked(c), 1)):
            with self.subTest(kicked=kicked):
                ogre = self.perm(RED, self.b)
                self.resolve(effects, [self.b] + [None] * (len(effects) - 1), card=c, kicks=int(kicked))
                self.game.state_based_actions()
                self.assertEqual(ogre.power, size)
                self.b.battlefield.remove(ogre)

    def test_conquerors_pledge_kicked_makes_twelve(self):
        c = self.get("Conqueror's Pledge")
        for kicked, effects, n in ((False, c.spell_effects, 6), (True, self.kicked(c), 12)):
            with self.subTest(kicked=kicked):
                self.a.battlefield.clear()
                self.resolve(effects, card=c, kicks=int(kicked))
                self.assertEqual(sum(x.card.name.startswith("Kor Soldier") for x in self.a.battlefield), n)
                self.assertEqual(len(self.a.battlefield), n)

    def test_ronas_vortex_kicked_to_the_bottom(self):
        c = self.get("Rona's Vortex")
        for kicked, effects in ((False, c.spell_effects), (True, self.kicked(c))):
            with self.subTest(kicked=kicked):
                self.b.library = [BEAR] * 5
                self.b.hand = []
                ogre = self.perm(RED, self.b)
                self.resolve(effects, [ogre] + [None] * (len(effects) - 1), card=c, kicks=int(kicked))
                self.assertNotIn(ogre, self.b.battlefield)
                self.assertEqual([x.name for x in self.b.hand], [] if kicked else ["Test Ogre"])
                self.assertEqual(self.b.library[0].name, "Test Ogre" if kicked else BEAR.name)

    def test_tezzerets_simulacrum_loses_one_or_three(self):
        c = self.get("Tezzeret's Simulacrum")
        effects = c.activated[0].effects
        for tezzeret, loss in ((False, 1), (True, 3)):
            with self.subTest(tezzeret=tezzeret):
                if tezzeret:
                    self.perm(card("Tezzeret, Test", "{3}", "Legendary Planeswalker — Tezzeret", "+1: Draw a card."),
                              self.a)
                life_a, life_b = self.a.life, self.b.life
                self.resolve(effects, [self.b] + [None] * (len(effects) - 1),
                             source=self.perm(c, self.a))
                self.assertEqual(life_b - self.b.life, loss)
                self.assertEqual(self.a.life, life_a)

    def test_blade_of_the_bloodchief_vampire_gets_two(self):
        c = self.get("Blade of the Bloodchief")
        trig = next(t for t in c.triggers if t.event == "creature_dies")
        for host_card, n in ((BEAR, 1), (VAMPIRE, 2)):
            with self.subTest(host_card.name):
                host = self.perm(host_card, self.a)
                blade = self.perm(c, self.a)
                blade.attached_to = host
                self.resolve(trig.effects, source=blade)
                self.assertEqual(host.counters.get("+1/+1", 0), n)

    def test_bring_low_counter_upgrade(self):
        c = self.get("Bring Low")
        for counters, damage in ((0, 3), (1, 5)):
            with self.subTest(counters=counters):
                victim = self.perm(card("Test Wall", "{4}", "Creature — Wall", "", 0, 9), self.b)
                victim.counters["+1/+1"] = counters
                self.resolve(c.spell_effects, [victim] + [None] * (len(c.spell_effects) - 1), card=c)
                self.assertEqual(victim.damage, damage)

    def test_hexgold_slash_toxic_upgrade(self):
        c = self.get("Hexgold Slash")
        for text, damage in (("", 2), ("Toxic 1", 4)):
            with self.subTest(text=text):
                victim = self.perm(card("Test Mite", "{4}", "Creature — Phyrexian Mite", text, 0, 9), self.b)
                targets = [victim if e.target in ("creature", "any", "permanent") else None
                           for e in c.spell_effects]
                self.resolve(c.spell_effects, targets, card=c)
                self.assertEqual(victim.damage, damage)

    def test_withering_curse_wrath_after_life_gain(self):
        c = self.get("Withering Curse")
        for gained, survives in ((False, True), (True, False)):
            with self.subTest(gained=gained):
                wall = self.perm(card("Test Wall", "{4}", "Creature — Wall", "", 0, 9), self.b)
                if gained:
                    self.game.change_life(self.a, 1, "test")
                self.resolve(c.spell_effects, card=c)
                self.game.state_based_actions()
                self.assertEqual(wall in self.b.battlefield, survives)
                self.assertEqual(wall.toughness, 7 if survives else wall.toughness)

    def test_scute_swarm_copies_itself_with_six_lands(self):
        c = self.get("Scute Swarm")
        trig = next(t for t in c.triggers if t.event == "land_enters")
        from tests.test_templates import ISLAND
        for lands, name in ((5, "Insect"), (6, "Scute Swarm")):
            with self.subTest(lands=lands):
                self.a.battlefield.clear()
                swarm = self.perm(c, self.a)
                for _ in range(lands):
                    self.perm(ISLAND, self.a)
                self.resolve(trig.effects, source=swarm)
                new = [x for x in self.a.battlefield if x is not swarm and x.is_creature]
                self.assertEqual(len(new), 1)
                self.assertIn(name, new[0].card.name)


if __name__ == "__main__":
    unittest.main()
