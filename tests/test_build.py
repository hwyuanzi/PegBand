"""Checks around compiled bots: a build that fails must not let an older binary play on.

Otherwise a student who breaks their C++ without noticing would be scored on the last
version that compiled.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from referee import runner
from referee.engine import make_config
from referee.runner import build, play_game

WORKS = r'''
#include <iostream>
#include <string>
int main() {
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.find("\"type\":\"start\"") != std::string::npos) std::cout << "{\"ready\":true}\n";
        else if (line.find("\"type\":\"peg\"") != std::string::npos) std::cout << "{\"peg\":0}\n";
        else std::cout << "{\"band\":[0]}\n";
        std::cout.flush();
    }
}
'''

GOOD_PY = """
import json, sys
for line in sys.stdin:
    m = json.loads(line)
    if m['type'] == 'start':
        print(json.dumps({'ready': True}), flush=True)
    elif m['type'] == 'peg':
        taken = set(m['your_pegs']) | set(m['their_pegs'])
        print(json.dumps({'peg': next(i for i in range(m['N'] * m['N']) if i not in taken)}), flush=True)
    else:
        print(json.dumps({'band': m['your_pegs'][:2]}), flush=True)
"""


@unittest.skipUnless(shutil.which('c++'), 'no C++ compiler on this machine')
class CompiledBots(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.cfg = make_config(8, 3, 2)
        runner._built.clear()
        runner._build_errors.clear()
        folder = Path(self.dir.name) / 'cpp'
        folder.mkdir()
        self.src = folder / 'bot.cpp'
        self.src.write_text(WORKS, encoding='utf-8')
        self.bot = {'name': 'cpp', 'cwd': str(folder),
                    'command': [str(folder / 'bot')],
                    'build': ['c++', '-std=c++17', '-O2', str(self.src), '-o', str(folder / 'bot')]}
        other = Path(self.dir.name) / 'py'
        other.mkdir()
        (other / 'bot.py').write_text(GOOD_PY, encoding='utf-8')
        self.other = {'name': 'py', 'cwd': str(other), 'command': [sys.executable, 'bot.py']}

    def tearDown(self):
        runner._built.clear()
        runner._build_errors.clear()
        self.dir.cleanup()

    def test_a_compiled_bot_plays(self):
        build(self.bot)
        r = play_game([self.bot, self.other], self.cfg, clock=20)
        self.assertEqual(r['errors'], [None, None])

    def test_a_broken_build_forfeits_instead_of_running_the_old_binary(self):
        build(self.bot)                                   # a good binary now exists
        self.assertTrue(Path(self.bot['command'][0]).is_file())
        self.src.write_text(WORKS + '\nthis is not valid c++\n', encoding='utf-8')
        with self.assertRaises(RuntimeError):
            build(self.bot)
        r = play_game([self.bot, self.other], self.cfg, clock=20)
        self.assertIsNotNone(r['errors'][0])
        self.assertIn('build failed', r['errors'][0])
        self.assertEqual(r['scores'][0], 0)

    def test_fixing_the_source_makes_it_play_again(self):
        build(self.bot)
        self.src.write_text(WORKS + '\nbroken\n', encoding='utf-8')
        with self.assertRaises(RuntimeError):
            build(self.bot)
        self.src.write_text(WORKS, encoding='utf-8')
        build(self.bot)                                   # compiles again
        r = play_game([self.bot, self.other], self.cfg, clock=20)
        self.assertEqual(r['errors'], [None, None])


if __name__ == '__main__':
    unittest.main()
