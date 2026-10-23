"""The rules of PegBand: the board, peg placement, rubberbands and the score.

Coordinates. Squares are numbered 0 .. N*N-1 reading left to right, top to bottom, exactly as
in the game description: square i is row i // N, column i % N. A bot may use either the number
or a [row, column] pair; the referee accepts both and always speaks numbers back.

A game has two phases:

  1. Peg placement. The players take turns placing one peg each, k times. Green places first in
     game 1. A peg may not go on a square that already holds a peg of either colour.
  2. Rubberband placement. The players take turns placing one band each, r times. A band is a
     set of the player's own pegs, and the band is the convex hull of those pegs.

A band of colour C is legal when every peg named belongs to C and no peg of the other colour
lies inside the hull or on its boundary. The puzzle says a band "may touch only pegs of that
player's colour", so an enemy peg exactly on an edge counts as a touch. An illegal band is
not placed and the turn is used up.

The score of a player is the number of distinct squares its bands cover, not counting squares
holding a peg of the other colour. Bands may overlap, and a square under two of a player's
own bands counts once. Both players can score the same square.
"""
import json

from .geometry import convex_hull, covered_squares, point_in_hull

GREEN, BLUE = 0, 1
COLORS = ('green', 'blue')
MAX_N = 50
MAX_PEGS = 20
MAX_BANDS = 20


class Config:
    """The parameters the architecture supplies: board size N, pegs k, rubberbands r."""

    warning = None          # set when the parameters are legal but outside the tournament limits

    def __init__(self, n, k, r):
        self.n, self.k, self.r = n, k, r

    def as_dict(self):
        return {'N': self.n, 'pegs': self.k, 'bands': self.r}

    def __str__(self):
        return f'N={self.n} pegs={self.k} bands={self.r}'


def make_config(n, k, r):
    """Check the parameters against the limits in the spec and return a Config."""
    try:
        n, k, r = int(n), int(k), int(r)
    except (TypeError, ValueError):
        raise ValueError('N, the number of pegs and the number of rubberbands must be whole numbers.')
    if not 2 <= n <= MAX_N:
        raise ValueError(f'N must be between 2 and {MAX_N}.')
    if k < 1 or k > MAX_PEGS:
        raise ValueError(f'The number of pegs must be between 1 and {MAX_PEGS}.')
    if r < 1 or r > MAX_BANDS:
        raise ValueError(f'The number of rubberbands must be between 1 and {MAX_BANDS}.')
    if r > k:
        raise ValueError('The number of rubberbands may not be more than the number of pegs.')
    if 2 * k > n:
        # The tournament spec says k is at most N/2, but the puzzle's own 5 x 5 examples use
        # four pegs, so the referee allows it and the dashboard shows a warning.
        cfg = Config(n, k, r)
        cfg.warning = (f'{k} pegs on a {n} x {n} board is more than the N/2 the tournament '
                       f'spec allows (at most {n // 2}).')
        return cfg
    return Config(n, k, r)


def load_config(path):
    """Read a parameter file: three whole numbers (N, pegs, rubberbands), # comments allowed."""
    nums = []
    for line in open(path, encoding='utf-8'):
        line = line.split('#', 1)[0].strip()
        if line:
            nums += line.split()
    if len(nums) != 3:
        raise ValueError(f'{path}: expected three numbers (N, pegs, rubberbands), found {len(nums)}.')
    return make_config(*nums)


def _whole(value):
    """A whole number written any of the ways a JSON encoder might write one, or None.

    A bot whose arithmetic produced a float may send 34.0, and one that builds its reply by
    hand may send "34". Both are read as 34. A real fraction such as 34.5 names no square
    and is refused.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        try:
            return _whole(json.loads(value.strip()))
        except (ValueError, AttributeError):
            return None
    return None


def parse_square(value, n):
    """A square from a bot: either the number i, or the pair [row, column]. Returns (row, col)."""
    i = _whole(value)
    if i is not None:
        if not 0 <= i < n * n:
            raise ValueError(f'square {i} is off the board')
        return divmod(i, n)
    if isinstance(value, (list, tuple)) and len(value) == 2:
        pair = [_whole(v) for v in value]
        if all(v is not None for v in pair):
            r, c = pair
            if not (0 <= r < n and 0 <= c < n):
                raise ValueError(f'square [{r}, {c}] is off the board')
            return r, c
    raise ValueError(f'{value!r} is not a square')


class Game:
    """One game of PegBand between Green and Blue."""

    def __init__(self, config):
        self.cfg = config
        self.n = config.n
        self.pegs = [[], []]                 # pegs[player] = list of (row, col), in the order placed
        self.bands = [[], []]                # bands[player] = list of placed bands (dicts)
        self.covered = [set(), set()]        # squares each player's bands cover, after the enemy-peg rule
        self.turn = GREEN                    # who places next
        self.phase = 'pegs'
        self.round = 0                       # how many full rounds of this phase are done
        self.notes = []                      # refusals and other remarks, for the log and the page

    # -- the board ---------------------------------------------------------

    def peg_at(self, square):
        """Which player has a peg on this (row, col), or None."""
        for p in (GREEN, BLUE):
            if square in self.pegs[p]:
                return p
        return None

    def board(self):
        """The board as a flat list of N*N codes, the way the bots and the page read it.

        0 empty, 1 green peg, 2 blue peg. A separate list per player gives the band cover.
        """
        cells = [0] * (self.n * self.n)
        for p in (GREEN, BLUE):
            for (r, c) in self.pegs[p]:
                cells[r * self.n + c] = p + 1
        return cells

    def state(self):
        """What a bot is told before each of its moves."""
        return {'N': self.n, 'pegs_each': self.cfg.k, 'bands_each': self.cfg.r,
                'color': COLORS[self.turn], 'you': self.turn + 1,
                'phase': self.phase, 'round': self.round,
                'board': self.board(),
                'your_pegs': sorted(r * self.n + c for (r, c) in self.pegs[self.turn]),
                'their_pegs': sorted(r * self.n + c for (r, c) in self.pegs[1 - self.turn]),
                'your_bands': [b['pegs'] for b in self.bands[self.turn]],
                'their_bands': [b['pegs'] for b in self.bands[1 - self.turn]],
                'scores': self.scores()}

    # -- phase 1: pegs -----------------------------------------------------

    def place_peg(self, player, value):
        """Place one peg. Returns (square_or_None, note). A refused peg is not placed."""
        try:
            square = parse_square(value, self.n)
        except ValueError as exc:
            return None, f'{COLORS[player]}: {exc}; no peg placed'
        owner = self.peg_at(square)
        if owner is not None:
            whose = 'its own' if owner == player else "the other player's"
            return None, (f'{COLORS[player]}: square {square[0] * self.n + square[1]} already holds '
                          f'{whose} peg; no peg placed')
        self.pegs[player].append(square)
        return square, None

    # -- phase 2: rubberbands ---------------------------------------------

    def check_band(self, player, value):
        """Work out the band a player asked for.

        Returns (band, note). band is None when the request is refused, and note says why.
        A band is a dict with the pegs named, the hull, the squares it covers and the squares
        it newly scores.
        """
        if not isinstance(value, (list, tuple)) or not value:
            return None, f'{COLORS[player]}: a rubberband must be a non-empty list of your own pegs'
        if len(value) > self.cfg.k:
            return None, f'{COLORS[player]}: a rubberband may name at most {self.cfg.k} pegs'
        squares = []
        for v in value:
            try:
                squares.append(parse_square(v, self.n))
            except ValueError as exc:
                return None, f'{COLORS[player]}: {exc}; no rubberband placed'
        mine = set(self.pegs[player])
        for sq in squares:
            if sq not in mine:
                owner = self.peg_at(sq)
                what = ("the other player's peg" if owner is not None else 'no peg of yours')
                return None, (f'{COLORS[player]}: square {sq[0] * self.n + sq[1]} holds {what}; '
                              f'a rubberband may only be stretched around your own pegs')
        hull = convex_hull([(c, r) for (r, c) in squares])          # geometry works in (x, y)
        for (r, c) in self.pegs[1 - player]:
            where = point_in_hull((c, r), hull)
            if where != 'outside':
                how = 'inside' if where == 'inside' else 'touching'
                return None, (f'{COLORS[player]}: the band would be {how} '
                              f"the other player's peg at {r * self.n + c}; no rubberband placed")
        cover = covered_squares(hull, self.n)
        enemy = set(self.pegs[1 - player])
        scoring = {sq for sq in cover if sq not in enemy}           # no point for an enemy peg's square
        band = {'pegs': sorted(r * self.n + c for (r, c) in squares),
                'hull': [[y, x] for (x, y) in hull],                 # as [row, col]
                'cover': sorted(r * self.n + c for (r, c) in cover),
                'new': sorted(r * self.n + c for (r, c) in scoring - self.covered[player])}
        return band, None

    def place_band(self, player, value):
        """Place one rubberband. Returns (band_or_None, note)."""
        band, note = self.check_band(player, value)
        if band is None:
            return None, note
        self.bands[player].append(band)
        self.covered[player] |= {divmod(i, self.n) for i in band['cover']} - set(self.pegs[1 - player])
        return band, None

    # -- score -------------------------------------------------------------

    def scores(self):
        return [len(self.covered[GREEN]), len(self.covered[BLUE])]

    def cover_lists(self):
        """Each player's covered squares, as numbers, for the page."""
        return [sorted(r * self.n + c for (r, c) in self.covered[p]) for p in (GREEN, BLUE)]

    def done(self):
        return self.phase == 'done'

    def advance(self):
        """Hand the turn to the other player, moving on to the next phase when a round ends."""
        if self.turn == GREEN:
            self.turn = BLUE
            return
        self.turn = GREEN
        self.round += 1
        if self.phase == 'pegs' and self.round >= self.cfg.k:
            self.phase, self.round = 'bands', 0
        elif self.phase == 'bands' and self.round >= self.cfg.r:
            self.phase = 'done'
