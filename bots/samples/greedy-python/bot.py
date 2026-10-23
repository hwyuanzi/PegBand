"""Greedy: a sample bot that counts squares before it moves.

Pegs: it puts each peg on the square that most increases the area of the hull of its own
pegs, while keeping that hull clear of enemy pegs. Bands: it tries every subset of its pegs
up to a small size and keeps the legal one covering the most squares it has not scored yet.

It is still only a sample: slow, and easy to trap.
"""
import itertools
import json
import sys


def cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


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
    h = half(pts)[:-1] + half(pts[::-1])[:-1]
    return h[:1] if len(h) == 2 and h[0] == h[1] else h


def on_seg(p, a, b):
    return (cross(a, b, p) == 0 and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))


def where(p, h):
    if len(h) == 1:
        return 'boundary' if p == h[0] else 'outside'
    if len(h) == 2:
        return 'boundary' if on_seg(p, h[0], h[1]) else 'outside'
    sign = 0
    for i in range(len(h)):
        a, b = h[i], h[(i + 1) % len(h)]
        c = cross(a, b, p)
        if c == 0 and on_seg(p, a, b):
            return 'boundary'
        if c < 0:
            sign = -1
    return 'outside' if sign < 0 else 'inside'


def seg_hits_box(a, b, lo_x, lo_y, hi_x, hi_y):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t0n, t0d, t1n, t1d = 0, 1, 1, 1
    for p, q in ((-dx, a[0] - lo_x), (dx, hi_x - a[0]), (-dy, a[1] - lo_y), (dy, hi_y - a[1])):
        if p == 0:
            if q < 0:
                return False
            continue
        n, d = q, p
        if p < 0:
            if d < 0:
                n, d = -n, -d
            if n * t0d > t0n * d:
                t0n, t0d = n, d
        else:
            if n * t1d < t1n * d:
                t1n, t1d = n, d
        if t0n * t1d > t1n * t0d:
            return False
    return t0n * t1d < t1n * t0d


def covered(h, n):
    """The squares a band covers. Same rule as the referee uses."""
    if not h:
        return set()
    xs = [p[0] for p in h]
    ys = [p[1] for p in h]
    out = set()
    edges = ([(h[i], h[(i + 1) % len(h)]) for i in range(len(h))] if len(h) > 2
             else ([(h[0], h[1])] if len(h) == 2 else []))
    for r in range(max(0, min(ys) - 1), min(n - 1, max(ys) + 1) + 1):
        for c in range(max(0, min(xs) - 1), min(n - 1, max(xs) + 1) + 1):
            if len(h) == 1:
                if (c, r) == h[0]:
                    out.add(r * n + c)
                continue
            box = (2 * c - 1, 2 * r - 1, 2 * c + 1, 2 * r + 1)
            hit = any(seg_hits_box((2 * a[0], 2 * a[1]), (2 * b[0], 2 * b[1]), *box) for a, b in edges)
            if not hit and len(h) > 2:
                hit = where((c, r), h) == 'inside'
            if hit:
                out.add(r * n + c)
    return out


class Bot:
    def start(self, msg):
        self.N = msg['N']
        self.scored = set()

    def pt(self, i):
        return (i % self.N, i // self.N)

    def band_squares(self, band, enemy):
        """The squares a band would score, or None if the band is illegal."""
        h = hull([self.pt(i) for i in band])
        for e in enemy:
            if where(self.pt(e), h) != 'outside':
                return None
        return covered(h, self.N) - set(enemy)

    def place_peg(self, msg):
        n = self.N
        mine, theirs = list(msg['your_pegs']), list(msg['their_pegs'])
        taken = set(mine) | set(theirs)
        best, best_key = None, None
        for i in range(n * n):
            if i in taken:
                continue
            got = self.band_squares(mine + [i], theirs)
            # How much does this peg open up, and how far is it from the enemy's pegs?
            size = len(got) if got is not None else 0
            r, c = divmod(i, n)
            away = min((abs(r - e // n) + abs(c - e % n) for e in theirs), default=n)
            key = (size, away)
            if best_key is None or key > best_key:
                best, best_key = i, key
        return best

    def place_band(self, msg):
        mine, theirs = list(msg['your_pegs']), list(msg['their_pegs'])
        best, best_gain = mine[:1], -1
        # All of my pegs first, then every small subset. Enough for the peg counts we play with.
        sizes = range(len(mine), 0, -1) if len(mine) <= 8 else [len(mine), 4, 3, 2, 1]
        for size in sizes:
            for band in itertools.combinations(mine, size):
                got = self.band_squares(list(band), theirs)
                if got is None:
                    continue
                gain = len(got - self.scored)
                if gain > best_gain:
                    best, best_gain = list(band), gain
            if best_gain > 0 and size <= 3:
                break
        got = self.band_squares(best, theirs)
        if got:
            self.scored |= got
        return best


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
