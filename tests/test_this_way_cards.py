"""#642: "for each card discarded / milled / exiled this way" reads what the previous effect of the resolution did."""
import random
import unittest

from mtgsim.ai import HeuristicAI
from mtgsim.engine import Game, Player
from tests.test_templates import ISLAND, card

def bears(n):
    return [card(f"Bear{i}", "{1}", "Creature — Bear", "", 2, 2) for i in range(n)]


def game():
    a, b = Player("a", [], HeuristicAI()), Player("b", [], HeuristicAI())
    g = Game(a, b, random.Random(0), log=True)
    g.turn, g.step = 1, "main1"
    a.library = b.library = [ISLAND] * 10
    return g, a, b


def spell(text):
    return card("Test Spell", "{1}", "Sorcery", text)


class ThisWayCards(unittest.TestCase):
    def test_parse(self):
        for text in ("Discard a card. Draw a card for each card discarded this way.",
                     "Mill four cards. Draw a card for each card milled this way.",
                     "Each player discards their hand. You gain 1 life for each card discarded this way.",
                     "Exile all cards from all graveyards. You gain 1 life for each card exiled this way."):
            self.assertEqual(spell(text).unsupported, [], text)

    def test_refuses_other_verbs_and_filters(self):
        for text in ("Discard a card. Draw a card for each creature card discarded this way.",
                     "Discard a card. Draw a card for each card revealed this way."):
            self.assertTrue(spell(text).unsupported, text)

    def run_spell(self, text, setup):
        g, a, b = game()
        s = spell(text)
        setup(a, b)
        a.hand.append(s)
        g.enter_battlefield(a, ISLAND)
        self.assertTrue(g.cast(a, s, [None]))
        g.settle()
        return g, a, b

    def test_discard_then_draw(self):
        g, a, b = self.run_spell("Discard two cards. Draw a card for each card discarded this way.",
                                 lambda a, b: setattr(a, "hand", bears(3)))
        self.assertEqual(len(a.hand), 3)       # one left, two drawn

    def test_mill_then_draw(self):
        g, a, b = self.run_spell("Mill three cards. Draw a card for each card milled this way.", lambda a, b: None)
        self.assertEqual(len(a.hand), 3)
        self.assertEqual(len(a.library), 4)

    def test_each_player_hand_then_life(self):
        def setup(a, b):
            a.hand, b.hand = bears(2), bears(3)
        g, a, b = self.run_spell("Each player discards their hand. You gain 1 life for each card discarded this way.", setup)
        self.assertEqual(a.life, 20 + 5)

    def test_exile_graveyards_then_life(self):
        def setup(a, b):
            a.graveyard, b.graveyard = bears(1), bears(2)
        g, a, b = self.run_spell("Exile all cards from all graveyards. You gain 1 life for each card exiled this way.", setup)
        self.assertEqual(a.life, 20 + 3)

    def test_exile_target_players_graveyard_then_life(self):
        def setup(a, b):
            a.graveyard, b.graveyard = bears(1), bears(2)
        g, a, b = self.run_spell("Exile target player's graveyard. You gain 1 life for each card exiled this way.", setup)
        self.assertEqual(a.life, 20 + 2)       # the targeted (opposing) graveyard: Titania's Command, Mind Extraction


if __name__ == "__main__":
    unittest.main()
