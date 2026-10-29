"""Contest bot checks against the official integer-geometry referee.

Run: python3 -m unittest tests.test_haowen_bot -v
The geometry probe is compiled into a temporary directory, never into the bot.
"""
import itertools
import json
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from referee.engine import Game, GREEN, BLUE, make_config
from referee.geometry import convex_hull, covered_squares, point_in_hull
from referee.runner import BotSession, build, load_bots, play_game

ROOT = Path(__file__).resolve().parent.parent
BOT_DIR = ROOT / "bots" / "haowen"

PROBE = r"""
#include <cstdint>
#include <iostream>
#include <vector>
#include "BANDS_HEADER"
#include "PEGS_HEADER"
int main() {
    char mode;
    int n, m, e;
    while (std::cin >> mode >> n >> m) {
        std::vector<int> mine(m);
        for (int& x : mine) std::cin >> x;
        std::cin >> e;
        std::vector<int> enemy(e);
        for (int& x : enemy) std::cin >> x;
        if (mode == 'g' || mode == 'r') {
            auto bits = pegband::coverage(n, mine, enemy);
            if (mode == 'r') {
                std::sort(mine.begin(), mine.end());
                mine.erase(std::unique(mine.begin(), mine.end()), mine.end());
                if (mine.size() == 3 && placement::cross(placement::point(mine[0], n),
                    placement::point(mine[1], n), placement::point(mine[2], n)) == 0)
                    mine.erase(mine.begin()+1);
                std::array<placement::P, 3> hull{};
                for (size_t i=0; i<mine.size(); ++i) hull[i]=placement::point(mine[i],n);
                if (mine.size()==3 && placement::cross(hull[0],hull[1],hull[2])<0)
                    std::swap(hull[1],hull[2]);
                auto raster = placement::raster(hull, static_cast<int>(mine.size()), n);
                for (int e : enemy) raster.a[e/64] &= ~(uint64_t(1) << (e%64));
                bits.assign(raster.a.begin(), raster.a.begin()+(n*n+63)/64);
            }
            std::cout << "{\"legal\":" << (pegband::legal(n, mine, enemy) ? "true" : "false")
                      << ",\"cover\":[";
            bool first = true;
            for (int i = 0; i < n*n; ++i) {
                if (i/64 < static_cast<int>(bits.size()) && ((bits[i/64] >> (i%64)) & 1)) {
                    if (!first) std::cout << ',';
                    first = false;
                    std::cout << i;
                }
            }
            std::cout << "]}\n";
        } else {
            int bands;
            double seconds;
            std::cin >> bands >> seconds;
            auto plan = pegband::solve_bands(n, mine, enemy, bands, seconds);
            std::cout << "{\"score\":" << plan.score << ",\"bands\":[";
            for (size_t i = 0; i < plan.bands.size(); ++i) {
                if (i) std::cout << ',';
                std::cout << '[';
                for (size_t j = 0; j < plan.bands[i].size(); ++j) {
                    if (j) std::cout << ',';
                    std::cout << plan.bands[i][j];
                }
                std::cout << ']';
            }
            std::cout << "]}\n";
        }
        std::cout.flush();
    }
}
"""


def oracle(n, mine, enemy):
    hull = convex_hull([(i % n, i // n) for i in mine])
    legal = bool(hull) and all(point_in_hull((i % n, i // n), hull) == "outside" for i in enemy)
    cover = {r * n + c for r, c in covered_squares(hull, n)} - set(enemy)
    return legal, cover


def encoded(mode, n, mine, enemy, suffix=""):
    return " ".join(str(x) for x in [mode, n, len(mine)] + list(mine) + [len(enemy)] + list(enemy)) + suffix


@unittest.skipUnless(shutil.which("c++"), "requires a C++17 compiler")
class BandGeometry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        header = BOT_DIR / "bands.h"
        if not header.exists():
            raise unittest.SkipTest("contest bot not present")
        cls.temp = tempfile.TemporaryDirectory()
        source = Path(cls.temp.name) / "probe.cpp"
        source.write_text(PROBE.replace("BANDS_HEADER", str(header)).replace("PEGS_HEADER", str(BOT_DIR / "pegs.h")), encoding="utf-8")
        cls.probe = str(Path(cls.temp.name) / "probe")
        result = subprocess.run(["c++", "-std=c++17", "-O2", str(source), "-o", cls.probe],
                                capture_output=True, text=True)
        if result.returncode:
            cls.temp.cleanup()
            raise AssertionError(result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def ask(self, requests, timeout=40):
        result = subprocess.run([self.probe], input="\n".join(requests) + "\n",
                                capture_output=True, text=True, timeout=timeout, check=True)
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(rows), len(requests))
        return rows

    def test_every_small_segment_and_random_hulls_match_referee(self):
        cases = [(5, list(pair), []) for pair in itertools.combinations(range(25), 2)]
        rng = random.Random(2965)
        for _ in range(500):
            n = rng.choice([2, 3, 5, 10, 20, 50])
            count = rng.randrange(1, min(20, n*n) + 1)
            enemy_count = rng.randrange(min(20, n*n-count) + 1)
            squares = rng.sample(range(n*n), count + enemy_count)
            cases.append((n, squares[:count], squares[count:]))
        cases += [(5, [7, 11, 14], []), (7, [8, 12, 40, 36], [24]),
                  (7, [8, 40], [24]), (6, [7, 9, 21, 19, 14], []), (5, [], [0])]
        rows = self.ask([encoded("g", *case) for case in cases])
        for case, row in zip(cases, rows):
            with self.subTest(case=case):
                legal, cover = oracle(*case)
                self.assertEqual(row["legal"], legal)
                self.assertEqual(set(row["cover"]), cover)

    def test_placement_scanline_raster_matches_exact_referee(self):
        cases = [(5, list(pair), []) for pair in itertools.combinations(range(25), 2)]
        rng = random.Random(20261029)
        for _ in range(1000):
            n = rng.choice([2, 3, 5, 10, 20, 50])
            count = rng.randrange(1, 4)
            enemy_count = rng.randrange(min(20, n*n-count)+1)
            squares = rng.sample(range(n*n), count+enemy_count)
            cases.append((n, squares[:count], squares[count:]))
        rows = self.ask([encoded("r", *case) for case in cases])
        for case, row in zip(cases, rows):
            with self.subTest(case=case):
                self.assertEqual(set(row["cover"]), oracle(*case)[1])

    def test_small_band_plans_are_optimal_against_exhaustive_oracle(self):
        rng = random.Random(8773)
        cases = []
        for _ in range(12):
            n = rng.choice([5, 7, 10])
            count = rng.choice([4, 5, 6])
            squares = rng.sample(range(n*n), 2*count)
            for bands in [1, 2]:
                cases.append((n, squares[:count], squares[count:], bands))
        cases.extend((n, mine, enemy, 3) for n, mine, enemy, _ in cases[::2][:5])
        rows = self.ask([encoded("p", n, mine, enemy, " %d 0.15" % bands)
                         for n, mine, enemy, bands in cases])
        for (n, mine, enemy, bands), row in zip(cases, rows):
            with self.subTest(n=n, mine=mine, enemy=enemy, bands=bands):
                covers = []
                for count in range(1, len(mine) + 1):
                    for subset in itertools.combinations(mine, count):
                        legal, cover = oracle(n, subset, enemy)
                        if legal:
                            covers.append(cover)
                optimal = max(map(len, covers), default=0)
                if bands >= 2:
                    optimal = max([optimal] + [len(a | b) for a, b in itertools.combinations(covers, 2)])
                if bands == 3:
                    optimal = max([optimal] + [len(a | b | c) for a, b, c in itertools.combinations(covers, 3)])
                actual = self.check_plan(n, mine, enemy, bands, row)
                self.assertEqual(actual, optimal)

    def check_plan(self, n, mine, enemy, bands, row):
        self.assertLessEqual(len(row["bands"]), bands)
        union = set()
        for band in row["bands"]:
            self.assertTrue(band)
            self.assertTrue(set(band) <= set(mine))
            legal, cover = oracle(n, band, enemy)
            self.assertTrue(legal, (mine, enemy, band))
            union |= cover
        self.assertEqual(row["score"], len(union))
        return len(union)

    def test_maximum_size_plans_remain_legal_and_report_exact_score(self):
        rng = random.Random(20)
        cases = []
        for n, bands in [(50, 20), (50, 1), (40, 6)]:
            squares = rng.sample(range(n*n), 40)
            cases.append((n, squares[:20], squares[20:], bands))
        # All collinear points and opponent pegs on some segments.
        cases.append((50, list(range(0, 40, 2)), list(range(1, 40, 2)), 20))
        rows = self.ask([encoded("p", n, mine, enemy, " %d 0.3" % bands)
                         for n, mine, enemy, bands in cases])
        for case, row in zip(cases, rows):
            with self.subTest(case=case):
                self.check_plan(*case, row)


@unittest.skipUnless(shutil.which("c++"), "requires a C++17 compiler")
class BotProtocol(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (BOT_DIR / "bot.cpp").exists():
            raise unittest.SkipTest("contest bot not present")
        cls.bot = next((b for b in load_bots() if Path(b["cwd"]) == BOT_DIR), None)
        if cls.bot is None:
            raise AssertionError("contest bot was not discovered")
        build(cls.bot)
        cls.other = {"name": "random", "cwd": str(ROOT / "bots/samples/random-python"),
                     "command": [sys.executable, "bot.py"]}

    def test_one_peg_one_band_game_both_colors(self):
        for bot_index in [0, 1]:
            players = [self.other, self.other]
            players[bot_index] = self.bot
            result = play_game(players, make_config(2, 1, 1), clock=120)
            self.assertIsNone(result["errors"][bot_index])
            self.assertTrue(all(not m["refused"] for m in result["moves"] if m["player"] == bot_index))
            self.assertEqual(result["scores"][bot_index], 1)
            self.assertEqual(result["ended"], "finished")

    def test_final_blue_peg_maximizes_exact_terminal_score_difference(self):
        n, k, bands = 6, 3, 1
        rng = random.Random(331)
        def best_band(pegs, enemy):
            best = 0
            for count in range(1, len(pegs)+1):
                for subset in itertools.combinations(pegs, count):
                    legal, cover = oracle(n, subset, enemy)
                    if legal:
                        best = max(best, len(cover))
            return best
        session = BotSession(self.bot)
        try:
            session.start()
            ready, _ = session.ask({"type": "start", "protocol_version": 1, "color": "blue",
                                    "you": 2, "N": n, "pegs": k, "bands": bands, "clock": 120}, 30)
            self.assertIs(ready.get("ready"), True)
            for _ in range(20):
                squares = rng.sample(range(n*n), 5)
                mine, enemy = squares[:2], squares[2:]
                values = {}
                for q in range(n*n):
                    if q not in squares:
                        values[q] = best_band(mine+[q], enemy) - best_band(enemy, mine+[q])
                game = Game(make_config(n, k, bands))
                game.pegs = [[divmod(i, n) for i in enemy], [divmod(i, n) for i in mine]]
                game.turn, game.round = BLUE, k-1
                reply, _ = session.ask(dict(game.state(), type="peg"), 10)
                chosen = reply.get("peg")
                with self.subTest(mine=mine, enemy=enemy, chosen=chosen):
                    self.assertIn(chosen, values)
                    self.assertEqual(values[chosen], max(values.values()),
                                     "best cells: %s" % [q for q, v in values.items() if v == max(values.values())])
        finally:
            session.close()

    def test_maximum_board_band_protocol_all_twenty_rounds(self):
        n, k, count = 50, 20, 20
        rng = random.Random(1483)
        squares = rng.sample(range(n*n), 2*k)
        game = Game(make_config(n, k, count))
        game.pegs = [[divmod(i, n) for i in squares[:k]], [divmod(i, n) for i in squares[k:]]]
        game.phase = "bands"
        game.turn = GREEN
        session = BotSession(self.bot)
        elapsed = 0.0
        try:
            session.start()
            ready, _ = session.ask({"type": "start", "protocol_version": 1, "color": "green",
                                    "you": 1, "N": n, "pegs": k, "bands": count, "clock": 120}, 30)
            self.assertIs(ready.get("ready"), True)
            for round_number in range(count):
                game.round = round_number
                msg = dict(game.state(), type="band")
                reply, used = session.ask(msg, max(0.1, 120-elapsed))
                elapsed += used
                placed, why = game.place_band(GREEN, reply.get("band"))
                self.assertIsNone(why, why)
                self.assertIsNotNone(placed)
            self.assertLess(elapsed, 120)
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
