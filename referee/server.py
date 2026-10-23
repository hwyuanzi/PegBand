"""Tournament dashboard: pick bots, pairings and parameter files in the browser.

  python3 start.py            # then open http://127.0.0.1:8092

Bots come from bots.json (and any folder dropped into bots/). Parameter files come from
params/: drop in as many as you like and press "Rescan folder". Standard library only.
"""
import argparse
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .engine import load_config, make_config
from .runner import ROOT, load_bots, play_match
from .tournament import build_all, list_params, pairing_result

SAVED = ROOT / 'results' / 'all_results.json'   # every finished pairing, kept across restarts


class Tournament:
    """One tournament at a time, run on a background thread."""

    def __init__(self, registry, params):
        self.registry = registry
        self.params_dirs = params.split(',')
        self.lock = threading.Lock()
        self.stop_flag = threading.Event()
        self.thread = None
        try:
            self.done = json.loads(SAVED.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.done = []
        self.state = {'status': 'idle', 'message': 'Choose bots and pairings, then start.',
                      'pairings': list(self.done), 'current': None, 'run_from': len(self.done)}
        self.match = None            # state dict of the match being played
        self.game = None             # the engine.Game being played (for /state)
        self.clock = {}              # live clocks of that game, ticking while a bot thinks
        self.pace = 0.3              # seconds to linger per move, so people can watch

    def save(self):
        SAVED.parent.mkdir(parents=True, exist_ok=True)
        SAVED.write_text(json.dumps(self.done, indent=1), encoding='utf-8')

    def clear(self):
        if self.thread and self.thread.is_alive():
            raise ValueError('Stop the tournament before clearing the results.')
        if SAVED.exists():
            SAVED.rename(SAVED.with_name(f'all_results-cleared-{time.strftime("%Y%m%d-%H%M%S")}.json'))
        with self.lock:
            self.done = []
            self.state.update(pairings=[], current=None, run_from=0, status='idle',
                              message='Results cleared.')

    def add_params(self, req):
        """Save a parameter file typed into the page. Returns its path, e.g. params/my_game.txt."""
        name = re.sub(r'[^A-Za-z0-9_-]+', '_', str(req.get('name') or '').strip()).strip('_')
        if not name:
            raise ValueError('Give the parameter file a name.')
        folder = ROOT / self.params_dirs[0]
        path = folder / f'{name}.txt'
        if path.exists():
            raise ValueError(f'{path.name} already exists. Pick another name.')
        cfg = make_config(req.get('N'), req.get('pegs'), req.get('bands'))
        folder.mkdir(parents=True, exist_ok=True)
        path.write_text(f'# N (board side), pegs each, rubberbands each\n'
                        f'{cfg.n}\n{cfg.k}\n{cfg.r}\n', encoding='utf-8')
        return path.relative_to(ROOT).as_posix()

    def setup(self):
        bots = load_bots(self.registry)
        return {'bots': [{'key': b['name'], 'name': b['name']} for b in bots],
                'params': list_params(self.params_dirs),
                'params_dir': ' and '.join(d + '/' for d in self.params_dirs)}

    def snapshot(self):
        with self.lock:
            snap = json.loads(json.dumps(self.state))
        # A replay file can disappear after its result was saved (someone cleans out results/).
        # Say so on the page instead of offering a link that opens "not found".
        for pairing in snap.get('pairings', []):
            link = pairing.get('replay')
            if link and not (ROOT / link.lstrip('/')).is_file():
                pairing['replay'] = None
                pairing['replay_missing'] = True
        return snap

    def live(self):
        """What the live view needs right now: the board, the bands, the clocks and the score."""
        m, g = self.match, self.game
        if not m:
            return {'status': 'No match yet. Start a tournament.', 'names': []}
        out = {'status': m.get('status', ''), 'names': m['names'], 'params': m.get('params'),
               'time_budget': m.get('time_budget'), 'pace': self.pace,
               'games': [{k: gs.get(k) for k in ('game', 'green', 'blue', 'green_team',
                                                 'status', 'scores', 'phase', 'errors')}
                         for gs in m.get('games', [])]}
        if g is not None:
            out['now'] = {'N': g.n, 'phase': g.phase, 'round': g.round, 'turn': g.turn,
                          'board': g.board(), 'cover': g.cover_lists(),
                          'scores': g.scores(),
                          'bands': [[b['hull'] for b in g.bands[p]] for p in (0, 1)],
                          'notes': g.notes[-6:]}
            cur = m['games'][-1] if m.get('games') else None
            if cur:
                out['notes'] = list(cur.get('notes') or [])[-8:]
        c = self.clock
        if 'clocks' in c and m.get('status') != 'Finished':
            now = time.monotonic()
            left, thinking = [], []
            for player in (0, 1):
                since = c['since'][player]
                left.append(round(max(0.0, c['clocks'][player] - (now - since if since else 0)), 2))
                thinking.append(since is not None)
            out['live_clocks'], out['thinking'] = left, thinking
        return out

    def start(self, req):
        if self.thread and self.thread.is_alive():
            raise ValueError('A tournament is already running. Stop it first.')
        roster = {b['name']: b for b in load_bots(self.registry)}
        valid = {p['file'] for p in list_params(self.params_dirs) if 'error' not in p}
        plan = []
        for p in req.get('pairings', []):
            a, b, cfg = p.get('a'), p.get('b'), p.get('config')
            if a not in roster or b not in roster or a == b:
                raise ValueError('Each pairing needs two different bots from bots.json.')
            if cfg:
                if cfg not in valid:
                    raise ValueError(f'Unknown or invalid parameter file: {cfg}')
            else:
                cfg = make_config(p.get('N'), p.get('pegs'), p.get('bands'))
            plan.append((a, b, cfg))
        if not plan:
            raise ValueError('Add at least one pairing.')
        self.set_pace(req.get('pace', 300))
        budget = float(req.get('clock') or 120.0)
        out = ROOT / 'results' / 'tournament' / time.strftime('%Y%m%d-%H%M%S')
        self.stop_flag.clear()
        with self.lock:
            first = len(self.done)
            pairings = list(self.done) + [
                {'bots': [a, b],
                 'config': cfg if isinstance(cfg, str) else None,
                 'params': cfg.as_dict() if not isinstance(cfg, str) else None,
                 'dir': f'{i + 1:02d}'}
                for i, (a, b, cfg) in enumerate(plan)]
            self.state = {'status': 'running',
                          'message': 'Preparing bots (compiling C++ if needed)...',
                          'time_budget': budget, 'output': str(out.relative_to(ROOT)),
                          'pairings': pairings, 'run_from': first, 'current': None}
            self.match = None
            self.game = None
        self.thread = threading.Thread(target=self.run, args=(roster, plan, first, budget, out),
                                       daemon=True)
        self.thread.start()

    def set_pace(self, ms):
        try:
            self.pace = min(3.0, max(0.0, float(ms) / 1000.0))
        except (TypeError, ValueError):
            raise ValueError('pace must be a number of milliseconds per move')

    def run(self, roster, plan, first, budget, out):
        out.mkdir(parents=True, exist_ok=True)
        build_all([roster[n] for n in sorted({n for a, b, _ in plan for n in (a, b)})])
        for i, (a, b, cfg) in enumerate(plan):
            if self.stop_flag.is_set():
                break
            with self.lock:
                entry = self.state['pairings'][first + i]
                self.state['current'] = first + i
                self.state['message'] = f'Pairing {i + 1} of {len(plan)}: {a} vs {b}'
                self.match = {'status': f'Starting {a} vs {b}...', 'names': [a, b],
                              'games': [], 'time_budget': budget}
                self.game = None
                self.clock = {}

            def progress(st, g=None):
                self.match = st
                self.game = g

            try:
                st = play_match(roster[a], roster[b], cfg, budget, out / entry['dir'],
                                on_progress=progress, delay=lambda: self.pace,
                                stop=self.stop_flag, live=self.clock)
                self.match = st
                result = pairing_result(st)
                result['replay'] = '/' + (out / entry['dir'] / 'replay.html').relative_to(ROOT).as_posix()
                if self.stop_flag.is_set():
                    result = {'error': 'stopped'}
            except Exception as exc:
                result = {'error': str(exc)}
            with self.lock:
                entry.update(result)
                if 'totals' in entry:
                    self.done.append(dict(entry))
                    self.save()
                (out / 'results.json').write_text(
                    json.dumps(self.state['pairings'][first:], indent=2), encoding='utf-8')
        with self.lock:
            self.state['current'] = None
            self.state['status'] = 'stopped' if self.stop_flag.is_set() else 'finished'
            self.state['message'] = ('Stopped. Finished pairings are kept.' if self.stop_flag.is_set()
                                     else f'Finished. Results saved in {self.state["output"]}/')

    def stop(self):
        self.stop_flag.set()


def make_handler(t):
    page = ROOT / 'dashboard' / 'index.html'
    replay_page = ROOT / 'dashboard' / 'replay.html'

    class Handler(BaseHTTPRequestHandler):
        def send(self, code, body, mime='application/json'):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header('Content-Type', mime)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split('?')[0]
            try:
                if path in ('/', '/index.html'):
                    return self.send(200, page.read_bytes(), 'text/html; charset=utf-8')
                if path == '/api/setup':
                    return self.send(200, t.setup())
                if path == '/api/state':
                    return self.send(200, t.snapshot())
                if path == '/live':
                    return self.send(200, replay_page.read_bytes(), 'text/html; charset=utf-8')
                if path == '/state':
                    return self.send(200, t.live())
            except (OSError, ValueError) as exc:
                return self.send(400, {'error': str(exc)})
            if path.startswith('/results/') and path.endswith(('.html', '.json')):
                target = (ROOT / path.lstrip('/')).resolve()
                if (ROOT / 'results').resolve() in target.parents and target.is_file():
                    mime = ('text/html; charset=utf-8' if path.endswith('.html')
                            else 'application/json')
                    return self.send(200, target.read_bytes(), mime)
            self.send(404, {'error': 'not found'})

        def do_POST(self):
            try:
                n = int(self.headers.get('Content-Length') or 0)
                req = json.loads(self.rfile.read(n) or b'{}')
                if self.path == '/api/start':
                    t.start(req)
                elif self.path == '/api/stop':
                    t.stop()
                elif self.path == '/api/clear':
                    t.clear()
                elif self.path == '/api/pace':
                    t.set_pace(req.get('pace', 0))
                elif self.path == '/api/params':
                    return self.send(200, {'ok': True, 'file': t.add_params(req)})
                else:
                    return self.send(404, {'error': 'not found'})
                self.send(200, {'ok': True})
            except (ValueError, OSError) as exc:
                self.send(400, {'error': str(exc)})

        def log_message(self, *unused):
            pass

    return Handler


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--port', type=int, default=8092)
    ap.add_argument('--registry', default='bots.json')
    ap.add_argument('--params', default='params', help='folder(s) of parameter files, comma-separated')
    args = ap.parse_args()
    (ROOT / 'params').mkdir(exist_ok=True)
    t = Tournament(args.registry, args.params)
    t.setup()                                       # fail early if bots.json is broken
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(t))
    print(f'PegBand dashboard: http://127.0.0.1:{server.server_port}  (Ctrl+C to stop)', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        t.stop()
        print('\nStopped.')


if __name__ == '__main__':
    main()
