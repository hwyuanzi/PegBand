"""Checks that the referee handles bots that misbehave: crashes, timeouts and illegal moves.

Each test writes a small bot into a temporary folder and plays a real game against it.
"""
import sys
import tempfile
import unittest
from pathlib import Path

from referee.engine import make_config
from referee.runner import play_game

GOOD = """
import json, sys
for line in sys.stdin:
    m = json.loads(line)
    if m['type'] == 'start':
        print(json.dumps({'ready': True}), flush=True)
    elif m['type'] == 'peg':
        n = m['N']
        taken = set(m['your_pegs']) | set(m['their_pegs'])
        # One row per peg, each player on its own side, so the two colours never interleave.
        side = 0 if m['color'] == 'green' else n - 1
        order = sorted((r * n + c for r in range(n) for c in range(n)),
                       key=lambda i: (abs(i % n - side), i // n))
        print(json.dumps({'peg': next(i for i in order if i not in taken)}), flush=True)
    else:
        print(json.dumps({'band': m['your_pegs'][:2]}), flush=True)
"""


class Misbehaving(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.cfg = make_config(8, 3, 2)

    def tearDown(self):
        self.dir.cleanup()

    def bot(self, name, source):
        folder = Path(self.dir.name) / f'{name}{len(list(Path(self.dir.name).iterdir()))}'
        folder.mkdir()
        (folder / 'bot.py').write_text(source, encoding='utf-8')
        return {'name': name, 'cwd': str(folder), 'command': [sys.executable, 'bot.py']}

    def good(self):
        return self.bot('good', GOOD)

    def test_a_crash_forfeits_and_the_other_player_plays_on(self):
        crash = self.bot('crash', """
import json, sys
seen = 0
for line in sys.stdin:
    m = json.loads(line)
    if m['type'] == 'start':
        print(json.dumps({'ready': True}), flush=True)
        continue
    seen += 1
    if seen > 2:
        raise SystemExit(1)
    print(json.dumps({'peg': seen}), flush=True)
""")
        r = play_game([crash, self.good()], self.cfg, clock=20)
        self.assertEqual(r['errors'][0], 'crashed')
        self.assertIsNone(r['errors'][1])
        self.assertGreater(r['scores'][1], 0)        # the other player finished its game
        self.assertEqual(r['ended'], 'finished')

    def test_running_out_of_time_forfeits(self):
        slow = self.bot('slow', """
import json, sys, time
for line in sys.stdin:
    m = json.loads(line)
    if m['type'] == 'start':
        print(json.dumps({'ready': True}), flush=True)
        continue
    time.sleep(5)
    print(json.dumps({'peg': 0}), flush=True)
""")
        r = play_game([slow, self.good()], self.cfg, clock=1.5)
        self.assertEqual(r['errors'][0], 'time')
        self.assertEqual(r['clocks'][0], 0.0)
        self.assertEqual(r['scores'][0], 0)
        self.assertGreater(r['scores'][1], 0)

    def test_illegal_moves_are_refused_but_the_game_goes_on(self):
        cheat = self.bot('cheat', """
import json, sys
for line in sys.stdin:
    m = json.loads(line)
    if m['type'] == 'start':
        print(json.dumps({'ready': True}), flush=True)
    elif m['type'] == 'peg':
        print(json.dumps({'peg': m['their_pegs'][0] if m['their_pegs'] else 9999}), flush=True)
    else:
        print(json.dumps({'band': m['their_pegs'][:2] or [0]}), flush=True)
""")
        r = play_game([cheat, self.good()], self.cfg, clock=20)
        self.assertIsNone(r['errors'][0])            # breaking a rule is not a forfeit
        self.assertEqual(r['scores'][0], 0)          # but nothing it asked for was allowed
        self.assertTrue(any('off the board' in n for n in r['notes']))
        self.assertTrue(any('already holds' in n for n in r['notes']))

    def test_bad_json_forfeits(self):
        noise = self.bot('noise', """
import sys
for line in sys.stdin:
    print('not json at all', flush=True)
""")
        r = play_game([noise, self.good()], self.cfg, clock=20)
        self.assertIn('startup', r['errors'][0])

    def test_numbers_written_the_way_other_languages_write_them(self):
        """34.0 and "34" name square 34: a bot is not punished for its JSON encoder."""
        loose = self.bot('loose', """
import json, sys
n = 0
for line in sys.stdin:
    m = json.loads(line)
    if m['type'] == 'start':
        print(json.dumps({'ready': True}), flush=True)
    elif m['type'] == 'peg':
        n += 1
        print(json.dumps({'peg': float(n * 9)}), flush=True)     # 9.0, 18.0, ...
    else:
        print(json.dumps({'band': [str(x) for x in m['your_pegs'][:2]]}), flush=True)
""")
        r = play_game([loose, self.good()], self.cfg, clock=20)
        self.assertIsNone(r['errors'][0])
        self.assertEqual([n for n in r['notes'] if n.startswith('green')], [])
        self.assertGreater(r['scores'][0], 0)

    def test_a_square_with_a_real_fraction_is_still_refused(self):
        half = self.bot('half', """
import json, sys
for line in sys.stdin:
    m = json.loads(line)
    if m['type'] == 'start':
        print(json.dumps({'ready': True}), flush=True)
    elif m['type'] == 'peg':
        print(json.dumps({'peg': 12.5}), flush=True)
    else:
        print(json.dumps({'band': [0]}), flush=True)
""")
        r = play_game([half, self.good()], self.cfg, clock=20)
        self.assertIsNone(r['errors'][0])
        self.assertTrue(any('not a square' in n for n in r['notes']))

    def test_debug_output_on_standard_error_is_fine(self):
        chatty = self.bot('chatty', """
import json, sys
for line in sys.stdin:
    m = json.loads(line)
    print('thinking hard', file=sys.stderr)
    if m['type'] == 'start':
        print(json.dumps({'ready': True}), flush=True)
    elif m['type'] == 'peg':
        taken = set(m['your_pegs']) | set(m['their_pegs'])
        print(json.dumps({'peg': next(i for i in range(m['N'] * m['N']) if i not in taken)}), flush=True)
    else:
        print(json.dumps({'band': m['your_pegs'][:2]}), flush=True)
""")
        r = play_game([chatty, self.good()], self.cfg, clock=20)
        self.assertEqual(r['errors'], [None, None])

    def test_a_flood_of_output_is_stopped(self):
        flood = self.bot('flood', """
import json, sys
for line in sys.stdin:
    m = json.loads(line)
    if m['type'] == 'start':
        print(json.dumps({'ready': True}), flush=True)
        continue
    sys.stderr.write('x' * 3_000_000)      # no newline: must still be counted
    print(json.dumps({'peg': 0}), flush=True)
""")
        r = play_game([flood, self.good()], self.cfg, clock=20)
        self.assertEqual(r['errors'][0], 'too much output')

    def test_debug_text_on_standard_output_is_caught(self):
        noisy = self.bot('noisy', """
import json, sys
for line in sys.stdin:
    m = json.loads(line)
    print('about to move')                 # on stdout, where the protocol lives
    print(json.dumps({'ready': True} if m['type'] == 'start' else {'peg': 0}), flush=True)
""")
        r = play_game([noisy, self.good()], self.cfg, clock=20)
        self.assertIn('invalid JSON', r['errors'][0])

    def test_a_reply_of_the_wrong_shape_is_caught(self):
        wrong = self.bot('wrong', """
import json, sys
for line in sys.stdin:
    m = json.loads(line)
    print(json.dumps({'ready': 'yes'} if m['type'] == 'start' else {'move': {'peg': 5}}), flush=True)
""")
        r = play_game([wrong, self.good()], self.cfg, clock=20)
        self.assertIn('ready', r['errors'][0])

    def test_extra_fields_in_a_reply_are_ignored(self):
        extra = self.bot('extra', """
import json, sys
for line in sys.stdin:
    m = json.loads(line)
    if m['type'] == 'start':
        print(json.dumps({'ready': True, 'name': 'me'}), flush=True)
    elif m['type'] == 'peg':
        taken = set(m['your_pegs']) | set(m['their_pegs'])
        i = next(j for j in range(m['N'] * m['N']) if j not in taken)
        print(json.dumps({'peg': i, 'why': 'because', 'guess': 9}), flush=True)
    else:
        print(json.dumps({'band': m['your_pegs'][:2], 'note': 'hull'}), flush=True)
""")
        r = play_game([extra, self.good()], self.cfg, clock=20)
        self.assertEqual(r['errors'], [None, None])

    def test_a_missing_interpreter_is_reported_clearly(self):
        bot = {'name': 'nolang', 'cwd': self.dir.name,
               'command': ['definitely-not-a-real-interpreter', 'bot.xyz']}
        r = play_game([bot, self.good()], self.cfg, clock=20)
        self.assertIn('could not start', r['errors'][0])
        self.assertGreater(r['scores'][1], 0)        # the opponent still plays a full game

    def test_a_normal_game_finishes_with_both_clocks_intact(self):
        r = play_game([self.good(), self.good()], self.cfg, clock=20)
        self.assertEqual(r['errors'], [None, None])
        self.assertEqual(r['ended'], 'finished')
        # Three pegs each then two bands each: ten moves in all.
        self.assertEqual(len(r['moves']), 2 * (self.cfg.k + self.cfg.r))
        self.assertTrue(all(c > 0 for c in r['clocks']))


if __name__ == '__main__':
    unittest.main()
