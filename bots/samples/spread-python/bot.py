"""Spread: a simple sample bot.

Pegs: take squares far from every peg already on the board, so its own pegs end up spread
out and the bands it can stretch later are large. Bands: one band around all of its pegs,
then smaller ones if that is refused.

It is only a sample and never thinks about the other player.
"""
import itertools
import json
import sys


class Bot:
    def start(self, msg):
        self.N = msg['N']

    def place_peg(self, msg):
        n = self.N
        taken = set(msg['your_pegs']) | set(msg['their_pegs'])
        best, best_key = None, None
        for i in range(n * n):
            if i in taken:
                continue
            r, c = divmod(i, n)
            # Prefer a square far from every peg, and away from the edges as a tie-break.
            far = min((abs(r - p // n) + abs(c - p % n) for p in taken), default=n)
            edge = min(r, c, n - 1 - r, n - 1 - c)
            key = (far, edge)
            if best_key is None or key > best_key:
                best, best_key = i, key
        return best

    def place_band(self, msg):
        """The largest legal band I can make out of my pegs.

        Taking all of them is usually illegal because an enemy peg ends up inside, so try
        every subset from the largest down and keep the first that is allowed.
        """
        mine = list(msg['your_pegs'])
        for size in range(len(mine), 1, -1):
            for band in itertools.combinations(mine, size):
                if legal(list(band), msg['their_pegs'], self.N):
                    return list(band)
        return mine[:1]


# -- enough geometry to tell whether a band would be refused ------------------

def hull(points):
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts
    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2 and cross(out[-2], out[-1], p) <= 0:
                out.pop()
            out.append(p)
        return out
    return half(pts)[:-1] + half(pts[::-1])[:-1]


def cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def legal(band, enemy, n):
    """Would this band avoid every enemy peg, inside and on the boundary?"""
    h = hull([(i % n, i // n) for i in band])
    for e in enemy:
        p = (e % n, e // n)
        if where(p, h) != 'outside':
            return False
    return True


def where(p, h):
    if len(h) == 1:
        return 'boundary' if p == h[0] else 'outside'
    if len(h) == 2:
        if cross(h[0], h[1], p) != 0:
            return 'outside'
        return 'boundary' if (min(h[0][0], h[1][0]) <= p[0] <= max(h[0][0], h[1][0]) and
                              min(h[0][1], h[1][1]) <= p[1] <= max(h[0][1], h[1][1])) else 'outside'
    sign = 0
    for i in range(len(h)):
        a, b = h[i], h[(i + 1) % len(h)]
        c = cross(a, b, p)
        if c == 0 and (min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and
                       min(a[1], b[1]) <= p[1] <= max(a[1], b[1])):
            return 'boundary'
        if c < 0:
            sign = -1
    return 'outside' if sign < 0 else 'inside'


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
