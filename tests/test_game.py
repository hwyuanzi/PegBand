"""Checks on the rules and the geometry. Run with: python3 -m unittest discover tests

The first group replays the worked examples from Dennis Shasha's PegBand column, which is
the clearest statement of what the scoring rules mean.
"""
import unittest

from referee.engine import GREEN, BLUE, Game, make_config, parse_square
from referee.geometry import convex_hull, covered_squares, point_in_hull


def sq(r, c, n=5):
    return r * n + c


def cells(pegs, n=5):
    """The squares a band around these (row, col) pegs covers."""
    return covered_squares(convex_hull([(c, r) for (r, c) in pegs]), n)


class WarmUp(unittest.TestCase):
    """The 5 x 5 board from the column:   *G***  /  **B*G  /  *B**B  /  *G**G  /  **B**"""

    GREEN_PEGS = [(0, 1), (1, 4), (3, 1), (3, 4)]
    BLUE_PEGS = [(1, 2), (2, 1), (2, 4), (4, 2)]

    def test_green_band_over_two_pegs_scores_four(self):
        # The band between the two green pegs on row 3 is a segment crossing four squares.
        self.assertEqual(len(cells([(3, 1), (3, 4)])), 4)

    def test_blue_triangle_scores_six(self):
        # Blue's triangle over rows 1 and 2. The column counts six squares, not seven: the
        # edge grazes the corner of square (1, 1) at a single point, which does not count.
        got = cells([(1, 2), (2, 1), (2, 4)])
        self.assertEqual(sorted(got), [(1, 2), (1, 3), (2, 1), (2, 2), (2, 3), (2, 4)])

    def test_a_single_peg_covers_its_own_square(self):
        self.assertEqual(cells([(2, 2)]), {(2, 2)})


class WorkedGame(unittest.TestCase):
    """Questions 1 to 3 of the column, played out: the final score is 8 to 8."""

    def setUp(self):
        self.g = Game(make_config(5, 4, 2))
        self.g.pegs[GREEN] = [(0, 1), (0, 4), (1, 4), (2, 2)]
        self.g.pegs[BLUE] = [(1, 2), (2, 1), (2, 4), (4, 2)]
        self.g.phase = 'bands'

    def test_the_column_scores_eight_all(self):
        plays = [(BLUE, [sq(2, 1), sq(4, 2)], 4),        # question 2, blue
                 (GREEN, [sq(0, 1), sq(0, 4), sq(1, 4)], 6),   # question 2, green
                 (BLUE, [sq(1, 2), sq(2, 4)], 4),        # question 3, blue
                 (GREEN, [sq(1, 4), sq(2, 2)], 2)]       # question 3, green: two are already scored
        for player, band, gained in plays:
            placed, why = self.g.place_band(player, band)
            self.assertIsNone(why)
            self.assertEqual(len(placed['new']), gained)
        self.assertEqual(self.g.scores(), [8, 8])


class BandRules(unittest.TestCase):
    def setUp(self):
        self.g = Game(make_config(7, 4, 4))
        self.g.pegs[GREEN] = [(1, 1), (1, 5), (5, 1), (5, 5)]
        self.g.pegs[BLUE] = [(3, 3), (0, 0)]
        self.g.phase = 'bands'

    def test_enemy_peg_inside_refuses_the_band(self):
        band, why = self.g.place_band(GREEN, [sq(1, 1, 7), sq(1, 5, 7), sq(5, 5, 7), sq(5, 1, 7)])
        self.assertIsNone(band)
        self.assertIn('inside', why)

    def test_enemy_peg_on_an_edge_refuses_the_band(self):
        # A blue peg at (3, 3) sits exactly halfway along the green segment (1, 1)-(5, 5).
        band, why = self.g.place_band(GREEN, [sq(1, 1, 7), sq(5, 5, 7)])
        self.assertIsNone(band)
        self.assertIn('touching', why)

    def test_cannot_use_a_peg_that_is_not_yours(self):
        band, why = self.g.place_band(GREEN, [sq(1, 1, 7), sq(3, 3, 7)])
        self.assertIsNone(band)
        self.assertIn('only be stretched around your own pegs', why)

    def test_a_refused_band_scores_nothing(self):
        self.g.place_band(GREEN, [sq(1, 1, 7), sq(5, 5, 7)])
        self.assertEqual(self.g.scores(), [0, 0])
        self.assertEqual(self.g.bands[GREEN], [])

    def test_a_square_is_never_scored_twice_by_one_player(self):
        self.g.place_band(GREEN, [sq(1, 1, 7), sq(1, 5, 7)])
        first = self.g.scores()[GREEN]
        again, _ = self.g.place_band(GREEN, [sq(1, 1, 7), sq(1, 5, 7)])
        self.assertEqual(again['new'], [])
        self.assertEqual(self.g.scores()[GREEN], first)

    def test_no_point_for_a_square_holding_an_enemy_peg(self):
        g = Game(make_config(5, 3, 1))
        g.pegs[GREEN] = [(0, 0), (0, 4)]
        g.pegs[BLUE] = [(0, 2)]                    # sits on the green segment's own row
        g.phase = 'bands'
        band, why = g.place_band(GREEN, [sq(0, 0), sq(0, 4)])
        self.assertIsNone(band)                    # it is on the band: refused outright
        g.pegs[BLUE] = [(1, 2)]
        band, why = g.place_band(GREEN, [sq(0, 0), sq(0, 4)])
        self.assertIsNone(why)
        self.assertEqual(len(band['cover']), 5)


class Overlap(unittest.TestCase):
    def test_both_players_may_score_the_same_square(self):
        g = Game(make_config(9, 3, 1))
        g.pegs[GREEN] = [(0, 0), (0, 8)]
        g.pegs[BLUE] = [(8, 0), (8, 8)]
        g.phase = 'bands'
        # Two long segments that cross in the middle of the board.
        g.pegs[GREEN] = [(0, 0), (8, 8)]
        g.pegs[BLUE] = [(0, 8), (8, 0)]
        a, _ = g.place_band(GREEN, [sq(0, 0, 9), sq(8, 8, 9)])
        b, _ = g.place_band(BLUE, [sq(0, 8, 9), sq(8, 0, 9)])
        self.assertTrue(set(a['cover']) & set(b['cover']))


class PegPhase(unittest.TestCase):
    def setUp(self):
        self.g = Game(make_config(6, 3, 3))

    def test_cannot_place_on_the_other_players_peg(self):
        self.g.place_peg(GREEN, 7)
        peg, why = self.g.place_peg(BLUE, 7)
        self.assertIsNone(peg)
        self.assertIn('already holds', why)

    def test_cannot_place_on_your_own_peg(self):
        self.g.place_peg(GREEN, 7)
        peg, why = self.g.place_peg(GREEN, 7)
        self.assertIsNone(peg)

    def test_off_board_peg_is_refused(self):
        peg, why = self.g.place_peg(GREEN, 999)
        self.assertIsNone(peg)
        self.assertIn('off the board', why)

    def test_row_column_pairs_are_accepted(self):
        peg, why = self.g.place_peg(GREEN, [2, 3])
        self.assertEqual(peg, (2, 3))

    def test_turns_alternate_and_phases_follow(self):
        g = Game(make_config(6, 2, 2))
        order = []
        while not g.done():
            order.append((g.phase, g.turn))
            if g.phase == 'pegs':
                g.place_peg(g.turn, len(order))
            else:
                g.place_band(g.turn, [g.pegs[g.turn][0][0] * 6 + g.pegs[g.turn][0][1]])
            g.advance()
        self.assertEqual(order, [('pegs', 0), ('pegs', 1), ('pegs', 0), ('pegs', 1),
                                 ('bands', 0), ('bands', 1), ('bands', 0), ('bands', 1)])


class Geometry(unittest.TestCase):
    def test_hull_drops_interior_and_collinear_points(self):
        h = convex_hull([(0, 0), (4, 0), (4, 4), (0, 4), (2, 2), (2, 0)])
        self.assertEqual(sorted(h), [(0, 0), (0, 4), (4, 0), (4, 4)])

    def test_collinear_pegs_make_a_segment(self):
        self.assertEqual(sorted(convex_hull([(1, 1), (2, 2), (3, 3)])), [(1, 1), (3, 3)])

    def test_repeated_peg_makes_a_point(self):
        self.assertEqual(convex_hull([(2, 2), (2, 2)]), [(2, 2)])

    def test_point_in_hull(self):
        h = convex_hull([(0, 0), (4, 0), (4, 4), (0, 4)])
        self.assertEqual(point_in_hull((2, 2), h), 'inside')
        self.assertEqual(point_in_hull((0, 2), h), 'boundary')
        self.assertEqual(point_in_hull((5, 2), h), 'outside')

    def test_a_grazed_corner_does_not_count(self):
        # The diagonal from (1, 2) to (2, 1) in (x, y) passes through the corner shared by
        # four squares; only the two squares it really crosses are covered.
        got = covered_squares(convex_hull([(2, 1), (1, 2)]), 5)
        self.assertEqual(sorted(got), [(1, 2), (2, 1)])

    def test_a_filled_square_is_covered(self):
        got = covered_squares(convex_hull([(1, 1), (3, 1), (3, 3), (1, 3)]), 6)
        self.assertEqual(len(got), 9)             # the 3 x 3 block from (1, 1) to (3, 3)

    def test_parse_square_rejects_rubbish(self):
        for bad in (True, 'x', [1], [1, 2, 3], None, 1.5):
            with self.assertRaises(ValueError):
                parse_square(bad, 5)


class Parameters(unittest.TestCase):
    def test_limits_from_the_spec(self):
        with self.assertRaises(ValueError):
            make_config(51, 5, 5)                  # N over 50
        with self.assertRaises(ValueError):
            make_config(10, 21, 5)                 # more than 20 pegs
        with self.assertRaises(ValueError):
            make_config(10, 4, 5)                  # more bands than pegs

    def test_more_pegs_than_half_of_n_is_allowed_but_flagged(self):
        cfg = make_config(5, 4, 2)                 # the column's own board
        self.assertIsNotNone(cfg.warning)
        self.assertIsNone(make_config(10, 5, 5).warning)


if __name__ == '__main__':
    unittest.main()
