"""The geometry of PegBand: convex hulls, the squares a band covers, and the rules a band must obey.

Everything here is integer arithmetic, so every test is exact and needs no epsilon. A peg sits
at the centre of its square, and the centre of the square in row r, column c is the point
(c, r). A rubberband stretched around a set of pegs is the convex hull of those points: a
single point, a line segment, or a convex polygon.
"""


def cross(o, a, b):
    """Twice the signed area of the triangle o, a, b. Positive means a->b turns left around o."""
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def convex_hull(points):
    """The convex hull of a set of points, counter-clockwise, without repeated points.

    Returns 1 point if they all coincide, 2 if they are collinear (the two extremes), and
    otherwise the corners of the polygon. Interior and collinear points are dropped: a real
    rubberband only touches the pegs on the outside. Andrew's monotone chain.
    """
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts
    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    if len(hull) == 2 and hull[0] == hull[1]:
        return hull[:1]
    return hull


def on_segment(p, a, b):
    """Is point p exactly on the closed segment a-b?"""
    if cross(a, b, p) != 0:
        return False
    return (min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and
            min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))


def point_in_hull(p, hull):
    """Where is p relative to a convex hull given counter-clockwise?

    Returns 'inside', 'boundary' or 'outside'. Works for a hull of 1 point (a peg),
    2 points (a segment) or more (a polygon).
    """
    if len(hull) == 1:
        return 'boundary' if p == hull[0] else 'outside'
    if len(hull) == 2:
        return 'boundary' if on_segment(p, hull[0], hull[1]) else 'outside'
    sign = 0
    for i in range(len(hull)):
        c = cross(hull[i], hull[(i + 1) % len(hull)], p)
        if c == 0 and on_segment(p, hull[i], hull[(i + 1) % len(hull)]):
            return 'boundary'
        if c < 0:
            sign = -1
        elif c > 0:
            sign = sign or 1
    return 'outside' if sign < 0 else 'inside'


# ---------------------------------------------------------------------------
# Which squares does a band cover?
#
# The square in row r, column c covers the area [c - 1/2, c + 1/2] x [r - 1/2, r + 1/2].
# A player scores a square if the band's interior meets it or the band's boundary crosses
# it (the puzzle says "fully or partially contained"). To keep the arithmetic
# exact we work in doubled coordinates, where the square becomes [2c-1, 2c+1] x [2r-1, 2r+1]
# and every corner is an integer point.
# ---------------------------------------------------------------------------

def _seg_hits_box(a, b, lo_x, lo_y, hi_x, hi_y):
    """Does the segment a-b cross the axis-aligned closed box? All coordinates are integers.

    Liang-Barsky, done in rationals as pairs of integers so nothing is rounded. A segment
    that only touches the box at a single point, at a corner or at the end of a side, does
    not count: the part of the segment inside the box must have positive length. This is
    why a diagonal band through the exact corner of a square does not score it.
    """
    dx, dy = b[0] - a[0], b[1] - a[1]
    # The segment is the points a + t*(dx, dy) for t in [0, 1]. Each side of the box gives
    # an inequality p*t <= q; clip the interval of t that satisfies all four.
    t0_n, t0_d = 0, 1          # lower end of the surviving interval, as a fraction
    t1_n, t1_d = 1, 1          # upper end
    for p, q in ((-dx, a[0] - lo_x), (dx, hi_x - a[0]),
                 (-dy, a[1] - lo_y), (dy, hi_y - a[1])):
        if p == 0:
            if q < 0:
                return False           # parallel to this side and outside it
            continue
        if p < 0:                      # t >= q/p : raises the lower end
            n, d = q, p
            if d < 0:
                n, d = -n, -d
            if n * t0_d > t0_n * d:
                t0_n, t0_d = n, d
        else:                          # t <= q/p : lowers the upper end
            n, d = q, p
            if n * t1_d < t1_n * d:
                t1_n, t1_d = n, d
        if t0_n * t1_d > t1_n * t0_d:
            return False
    # The surviving interval of t must have positive length, so that the overlap is a real
    # piece of the segment and not a single grazing point.
    return t0_n * t1_d < t1_n * t0_d


def covered_squares(hull, n):
    """Every square of an n x n board that the band (a convex hull) covers.

    Returns a set of (row, column). A square counts when any part of it meets the band:
    its interior or its boundary, or for a point or segment band the band itself.
    """
    if not hull:
        return set()
    xs = [p[0] for p in hull]
    ys = [p[1] for p in hull]
    # Only squares in the band's bounding box can be touched.
    lo_c, hi_c = max(0, min(xs) - 1), min(n - 1, max(xs) + 1)
    lo_r, hi_r = max(0, min(ys) - 1), min(n - 1, max(ys) + 1)
    edges = [(hull[i], hull[(i + 1) % len(hull)]) for i in range(len(hull))] if len(hull) > 2 \
        else ([(hull[0], hull[1])] if len(hull) == 2 else [])
    out = set()
    for r in range(lo_r, hi_r + 1):
        for c in range(lo_c, hi_c + 1):
            if len(hull) == 1:
                if (c, r) == hull[0]:
                    out.add((r, c))
                continue
            # The square, in doubled coordinates, is this box with integer corners.
            box = (2 * c - 1, 2 * r - 1, 2 * c + 1, 2 * r + 1)
            hit = False
            for a, b in edges:                       # does an edge of the band cross the square?
                if _seg_hits_box((2 * a[0], 2 * a[1]), (2 * b[0], 2 * b[1]), *box):
                    hit = True
                    break
            if not hit and len(hull) > 2:
                # No edge crosses it, so the square is either wholly inside the band or
                # wholly outside: its centre decides which.
                hit = point_in_hull((c, r), hull) == 'inside'
            if hit:
                out.add((r, c))
    return out
