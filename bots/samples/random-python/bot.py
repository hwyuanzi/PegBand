"""Random: the simplest sample bot. Places pegs on random free squares and stretches each
band around two of its own pegs chosen at random, retrying until one is legal.

Useful as a punching bag and for checking that the referee handles odd moves.
"""
import json
import random
import sys


class Bot:
    def start(self, msg):
        self.N = msg['N']
        self.rng = random.Random(12345)      # fixed seed, so a game can be reproduced

    def place_peg(self, msg):
        free = [i for i in range(self.N * self.N)
                if i not in set(msg['your_pegs']) | set(msg['their_pegs'])]
        return self.rng.choice(free)

    def place_band(self, msg):
        mine = list(msg['your_pegs'])
        if len(mine) < 2:
            return mine[:1]
        return self.rng.sample(mine, 2)


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
