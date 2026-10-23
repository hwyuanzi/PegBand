"""A PegBand bot in Python. Copy this folder to bots/<your-name>/ and write your strategy.

Run by the referee as a subprocess: one JSON message per line arrives on standard input,
one JSON object per line goes back on standard output. Print anything you like to standard
error for debugging. The referee ignores it.

Squares are numbered 0 .. N*N-1, left to right and top to bottom: square i is in row i // N
and column i % N. You may answer with the number or with a [row, column] pair.

Messages you receive:
  {"type": "start", "color": "green", "N": 10, "pegs": 5, "bands": 5, "clock": 120}
      -> reply {"ready": true}.  This one is not on your clock.
  {"type": "peg", "board": [...], "your_pegs": [...], "their_pegs": [...], ...}
      -> reply {"peg": 34}
  {"type": "band", "board": [...], "your_pegs": [...], "their_pegs": [...], ...}
      -> reply {"band": [12, 34, 56]}   the pegs to stretch the band around

Both of those carry the whole position, so a bot never has to remember anything:

  N, pegs_each, bands_each   the parameters of this game
  color, you                 "green" or "blue", and 1 or 2
  phase, round               "pegs" or "bands", and which round of it
  board                      N*N numbers: 0 empty, 1 green peg, 2 blue peg
  your_pegs, their_pegs      the squares each player's pegs are on
  your_bands, their_bands    the pegs each band so far was stretched around
  scores                     [green, blue] as they stand

You have "clock" seconds of thinking time for the whole game, counted only while the referee
waits for your answer. Run out and you forfeit the rest of the game.
"""
import json
import sys


# ----------------------------------------------------------------------------
# EDIT ONLY THIS SECTION
# ----------------------------------------------------------------------------

class Bot:
    def start(self, msg):
        """Called once, before the game. Keep whatever you need from msg."""
        self.N = msg['N']
        self.pegs = msg['pegs']
        self.bands = msg['bands']
        self.color = msg['color']

    def place_peg(self, msg):
        """Return the square to put your next peg on."""
        taken = set(msg['your_pegs']) | set(msg['their_pegs'])
        for i in range(self.N * self.N):
            if i not in taken:
                return i
        return 0

    def place_band(self, msg):
        """Return the list of your own pegs to stretch this rubberband around.

        The band is the convex hull of the pegs you name, so the order does not matter and
        naming a peg inside the hull changes nothing. The band must not contain or touch any
        peg of the other colour, or it is refused and scores nothing.
        """
        return msg['your_pegs'][:1]


# ----------------------------------------------------------------------------
# Below here is the plumbing. You should not need to change it.
# ----------------------------------------------------------------------------

def main():
    bot = Bot()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        kind = msg.get('type')
        if kind == 'start':
            bot.start(msg)
            reply = {'ready': True}
        elif kind == 'peg':
            reply = {'peg': bot.place_peg(msg)}
        elif kind == 'band':
            reply = {'band': bot.place_band(msg)}
        else:
            reply = {}
        sys.stdout.write(json.dumps(reply) + '\n')
        sys.stdout.flush()


if __name__ == '__main__':
    main()
