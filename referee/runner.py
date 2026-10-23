"""Runs PegBand matches between bots. The referee starts each bot itself.

Bots are run the same way as in the Evasion and Kelly architectures. Every game starts a
fresh process for each bot, from its folder in bots.json. The bot gets a "start" message and
must reply {"ready": true} within STARTUP_LIMIT seconds, which is not on its clock. The
players then move one at a time, and each is timed from the referee's message to its answer.

A bot that runs out of time, crashes or breaks the protocol forfeits: it places nothing for
the rest of the game and keeps the score it had, and the other player plays on. A move that
breaks a rule is not made (no peg is placed, or no band is stretched) and the reason goes in
the notes.

Messages are one JSON object per line. See the README, "The messages between referee and bot".
"""
import json
import os
import queue
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .engine import COLORS, GREEN, BLUE, Game, load_config, make_config

ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_VERSION = 1
STARTUP_LIMIT = 30.0        # seconds a bot may take to start (not on its clock)
OUTPUT_LIMIT = 1 << 20      # bytes a bot may print per reply (stdout or stderr)
NOTE_LIMIT = 400            # referee notes kept per game


class BotError(Exception):
    """A bot broke the protocol: crash, bad JSON, too much output, or timeout."""


def _resolve(arg, cwd):
    """{python} -> this Python; ./prog -> full path to prog in the bot folder (prog.exe on Windows)."""
    if arg == '{python}':
        return sys.executable
    if arg.startswith(('./', '.\\')):
        p = Path(cwd) / arg[2:]
        if os.name == 'nt' and not p.suffix:
            p = p.with_suffix('.exe')
        return str(p)
    return arg


def load_bots(path='bots.json'):
    """Read the roster. Each entry: name, cwd, command, optional build.

    bots.local.json next to it, if present, is read too and its entries added: it is ignored
    by git, so the players' bots can be listed there without ever being pushed.
    """
    path = (ROOT / path).resolve()
    entries = json.loads(path.read_text(encoding='utf-8'))
    local = path.with_name(path.stem + '.local.json')
    if local.exists():
        extra = json.loads(local.read_text(encoding='utf-8'))
        if not isinstance(extra, list):
            raise ValueError(f'{local.name} must be a list of bots')
        entries = list(entries) + extra
    if not isinstance(entries, list) or not entries:
        raise ValueError('bots.json must be a list of bots')
    entries = list(entries) + discover_bots(path.parent, entries)
    names = set()
    for bot in entries:
        name = bot.get('name')
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError('Every bot needs a unique, non-empty "name"')
        names.add(name)
        cwd = (path.parent / bot.get('cwd', '.')).resolve()
        if not cwd.is_dir():
            raise ValueError(f'{name}: folder not found: {cwd}')
        for key in ('command', 'build'):
            cmd = bot.get(key)
            if key == 'build' and cmd is None:
                continue
            if not isinstance(cmd, list) or not cmd or not all(isinstance(x, str) for x in cmd):
                raise ValueError(f'{name}: "{key}" must be a non-empty list of strings')
            bot[key] = [_resolve(x, cwd) for x in cmd]
        bot['cwd'] = str(cwd)
    return entries


def discover_bots(root, listed):
    """Bots dropped into bots/ without a roster entry: any folder (other than templates/ and
    samples/) holding a bot.py, bot.jl or bot.cpp is registered under the folder's name.
    """
    root = Path(root)
    bots_dir = root / 'bots'
    if not bots_dir.is_dir():
        return []
    taken_dirs = {str((root / b.get('cwd', '.')).resolve()) for b in listed if isinstance(b, dict)}
    taken_names = {b.get('name') for b in listed if isinstance(b, dict)}
    found = []
    for folder in sorted(p for p in bots_dir.rglob('*') if p.is_dir()):
        if folder.name in ('templates',) or folder.name.startswith(('.', '_')):
            continue
        if 'templates' in folder.relative_to(bots_dir).parts:
            continue
        if str(folder.resolve()) in taken_dirs:
            continue
        rel = folder.relative_to(root).as_posix()
        if (folder / 'bot.py').is_file():
            entry = {'name': folder.name, 'cwd': rel, 'command': ['{python}', 'bot.py']}
        elif (folder / 'bot.jl').is_file():
            entry = {'name': folder.name, 'cwd': rel,
                     'command': ['julia', '-t', 'auto', '--startup-file=no', 'bot.jl']}
        elif (folder / 'bot.cpp').is_file():
            entry = {'name': folder.name, 'cwd': rel, 'command': ['./bot'],
                     'build': ['{python}', 'build.py'] if (folder / 'build.py').is_file()
                     else ['c++', '-std=c++17', '-O2', 'bot.cpp', '-o', 'bot']}
        else:
            continue
        if entry['name'] in taken_names:
            entry['name'] = f"{entry['name']} ({rel})"
        found.append(entry)
        taken_names.add(entry['name'])
    return found


_built = {}          # bot folder -> fingerprint of its files right after the last successful build
_build_errors = {}   # bot folder -> why its last build failed, so starting it says so


def _fingerprint(folder):
    out = []
    for f in sorted(Path(folder).rglob('*')):
        if f.is_file() and '__pycache__' not in f.parts:
            st = f.stat()
            out.append((str(f), st.st_mtime_ns, st.st_size))
    return hash(tuple(out))


def build(bot):
    """Run a bot's build step (e.g. compiling C++) outside any clock.

    A failed build also throws away whatever the last successful build left behind, so a bot
    whose source no longer compiles cannot quietly keep playing with an older binary. The
    error is remembered against the folder, and starting that bot re-raises it, so the
    failure shows up as that bot's forfeit instead of disappearing into the log.
    """
    if not bot.get('build'):
        return
    key = str(Path(bot['cwd']).resolve())
    if _built.get(key) == _fingerprint(key):
        return
    _built.pop(key, None)
    r = subprocess.run(bot['build'], cwd=bot['cwd'], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        why = f"build failed: {(r.stderr or r.stdout).strip()[-300:]}"
        _build_errors[key] = why
        for arg in bot['command']:                 # drop the stale product of an earlier build
            target = Path(arg)
            if target.is_file() and target.parent == Path(bot['cwd']).resolve():
                try:
                    target.unlink()
                except OSError:
                    pass
        raise RuntimeError(why)
    _build_errors.pop(key, None)
    _built[key] = _fingerprint(key)


class BotSession:
    """One running bot process for one game."""

    def __init__(self, bot):
        self.bot = bot
        self.proc = None
        self.lines = queue.Queue()
        self.stderr_tail = []
        self.stderr_bytes = 0
        self.stderr_dropped = 0      # stderr already accounted for by an earlier reply
        self.readers = []

    def start(self):
        failed = _build_errors.get(str(Path(self.bot['cwd']).resolve()))
        if failed:
            raise BotError(failed)
        try:
            self.proc = subprocess.Popen(self.bot['command'], cwd=self.bot['cwd'],
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE, text=True, bufsize=1,
                                         encoding='utf-8', errors='replace')
        except OSError as exc:
            raise BotError(f'could not start: {exc}')
        self.readers = [threading.Thread(target=self._read_out, daemon=True),
                        threading.Thread(target=self._read_err, daemon=True)]
        for r in self.readers:
            r.start()

    def _read_out(self):
        for line in self.proc.stdout:
            self.lines.put(line)
        self.lines.put(None)

    def _read_err(self):
        """Drain the bot's standard error, counting it but keeping only the last few lines.

        Read in fixed-size chunks, not by line, because a bot that prints megabytes without a
        newline would otherwise sit in the reader's buffer uncounted. The tail is what an
        error message quotes.
        """
        while True:
            chunk = self.proc.stderr.read(8192)
            if not chunk:
                break
            self.stderr_bytes += len(chunk)
            if self.stderr_bytes - self.stderr_dropped <= OUTPUT_LIMIT:
                self.stderr_tail = (''.join(self.stderr_tail) + chunk)[-800:]
                self.stderr_tail = [self.stderr_tail]

    def ask(self, msg, timeout):
        """Send one message, wait for one JSON reply. Returns (reply, seconds)."""
        start = time.monotonic()
        before_err = self.stderr_bytes
        try:
            self.proc.stdin.write(json.dumps(msg, separators=(',', ':')) + '\n')
            self.proc.stdin.flush()
        except (OSError, ValueError):
            raise BotError('crashed' + self._err_note())
        try:
            line = self.lines.get(timeout=max(0.001, timeout))
        except queue.Empty:
            raise BotError('time')
        elapsed = time.monotonic() - start
        if line is None:
            raise BotError('crashed' + self._err_note())
        too_much = len(line) > OUTPUT_LIMIT or self.stderr_bytes - before_err > OUTPUT_LIMIT
        self.stderr_dropped = self.stderr_bytes
        if too_much:
            raise BotError('too much output')
        try:
            reply = json.loads(line)
        except ValueError:
            raise BotError(f'invalid JSON: {line.strip()[:60]!r}')
        if not isinstance(reply, dict):
            raise BotError('reply must be a JSON object')
        return reply, elapsed

    def _err_note(self):
        tail = ''.join(self.stderr_tail).strip()
        return f' ({tail[-160:]})' if tail else ''

    def close(self):
        if not self.proc:
            return
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        for r in self.readers:
            r.join(timeout=1)
        for stream in (self.proc.stdout, self.proc.stderr):
            try:
                stream.close()
            except OSError:
                pass


def play_game(bots, config, clock=120.0, game=1, on_move=None, delay=0, stop=None, live=None):
    """Play one game. bots = [bot playing green, bot playing blue]; green moves first.

    Returns a dict with the scores, every move made (for the replay), the referee's notes,
    the errors and the clocks. live (optional dict) is kept up to date for the dashboard.
    """
    g = Game(config)
    clocks = [float(clock), float(clock)]
    if live is not None:
        live['clocks'], live['since'] = clocks, [None, None]
    errors = [None, None]            # once set, that bot is no longer asked anything
    moves = []                       # every move, in order, for the replay
    notes = []
    sessions = [BotSession(b) for b in bots]
    pool = ThreadPoolExecutor(max_workers=2)

    def note(text):
        if len(notes) < NOTE_LIMIT:
            notes.append(text)

    try:
        def start(player):           # untimed: launch + start message + ready reply
            s = sessions[player]
            s.start()
            reply, _ = s.ask({'type': 'start', 'protocol_version': PROTOCOL_VERSION,
                              'color': COLORS[player], 'you': player + 1,
                              'N': g.n, 'pegs': config.k, 'bands': config.r,
                              'clock': clock}, STARTUP_LIMIT)
            if reply.get('ready') is not True:
                raise BotError('did not reply {"ready": true} to the start message')

        for player, fut in enumerate([pool.submit(start, p) for p in (GREEN, BLUE)]):
            try:
                fut.result()
            except BotError as exc:
                errors[player] = f'startup: {exc}'
                note(f'{COLORS[player]} failed to start: {exc}')

        while not g.done():
            if stop is not None and stop.is_set():
                break
            player = g.turn
            if errors[player]:                       # forfeited: skip its turn entirely
                g.advance()
                continue
            msg = {'type': 'peg' if g.phase == 'pegs' else 'band'}
            msg.update(g.state())
            if clocks[player] <= 0:
                errors[player] = 'time'
                note(f'{COLORS[player]} ran out of time')
                g.advance()
                continue
            if live is not None:
                live['since'][player] = time.monotonic()
            try:
                reply, elapsed = sessions[player].ask(msg, clocks[player])
                clocks[player] = max(0.0, clocks[player] - elapsed)
                if clocks[player] == 0.0:
                    raise BotError('time')
            except BotError as exc:
                if str(exc) == 'time':
                    clocks[player] = 0.0
                errors[player] = str(exc)
                note(f'{COLORS[player]} forfeited: {exc}')
                if live is not None:
                    live['since'][player] = None
                g.advance()
                continue
            if live is not None:
                live['since'][player] = None

            if g.phase == 'pegs':
                square, why = g.place_peg(player, reply.get('peg'))
                if why:
                    note(why)
                move = {'phase': 'pegs', 'player': player, 'round': g.round,
                        'peg': None if square is None else square[0] * g.n + square[1],
                        'refused': why}
            else:
                band, why = g.place_band(player, reply.get('band'))
                if why:
                    note(why)
                move = {'phase': 'bands', 'player': player, 'round': g.round,
                        'band': band, 'refused': why}
            move['clocks'] = [round(c, 2) for c in clocks]
            move['scores'] = g.scores()
            moves.append(move)
            g.advance()
            if on_move:
                on_move(g, move, clocks)
            d = delay() if callable(delay) else delay
            if d:
                if stop is not None:
                    stop.wait(d)
                else:
                    time.sleep(d)

        scores = g.scores()
        return {'scores': scores, 'moves': moves, 'notes': notes, 'errors': errors,
                'clocks': clocks, 'board': g.board(), 'cover': g.cover_lists(),
                'pegs': [sorted(r * g.n + c for (r, c) in g.pegs[p]) for p in (GREEN, BLUE)],
                'bands': [list(g.bands[p]) for p in (GREEN, BLUE)],
                'ended': 'finished' if g.done() else 'stopped'}
    finally:
        for s in sessions:
            s.close()
        pool.shutdown(wait=False)


def play_match(bot1, bot2, config, clock=120.0, out_dir=None, on_progress=None,
               delay=0, stop=None, live=None):
    """Two games: bot1 is Green in game 1, bot2 is Green in game 2, same parameters.

    A team's score is the sum of its points over the two games, as the spec says. Writes
    results.json and replay.html to out_dir (if given) and returns the match state.
    """
    if isinstance(config, dict):
        cfg = make_config(config.get('N'), config.get('pegs'), config.get('bands'))
        label = str(cfg)
    elif isinstance(config, (str, Path)):
        label = str(config)
        cfg = load_config(ROOT / config)
    else:
        cfg, label = config, str(config)
    names = [bot1['name'], bot2['name']]
    state = {'status': 'Starting', 'names': names, 'config': label, 'params': cfg.as_dict(),
             'time_budget': clock, 'games': []}
    totals = [0, 0]
    for game in (1, 2):
        green_team = 0 if game == 1 else 1        # which of the two teams plays Green
        players = [(bot1, bot2)[green_team], (bot1, bot2)[1 - green_team]]
        gstate = {'game': game, 'green': players[0]['name'], 'blue': players[1]['name'],
                  'green_team': green_team, 'status': 'starting the bots', 'scores': [0, 0]}
        state['games'].append(gstate)
        state['status'] = f'Game {game} · starting the bots'
        if on_progress:
            on_progress(state)
        if live is not None:
            live.clear()
            live['game'] = game
            live['green_team'] = green_team

        def on_move(g, move, clocks):
            gstate['status'] = 'playing'
            gstate['scores'] = g.scores()
            gstate['phase'] = g.phase
            state['status'] = (f'Game {game} · {g.phase} · '
                               f'{gstate["green"]} {g.scores()[0]} - {g.scores()[1]} {gstate["blue"]}')
            if on_progress:
                on_progress(state, g)

        result = play_game(players, cfg, clock, game, on_move=on_move, delay=delay,
                           stop=stop, live=live)
        gstate.update(result, status='finished')
        totals[green_team] += result['scores'][GREEN]
        totals[1 - green_team] += result['scores'][BLUE]
        state['status'] = (f'Game {game} finished: {gstate["green"]} {result["scores"][0]} - '
                           f'{result["scores"][1]} {gstate["blue"]}')
        if on_progress:
            on_progress(state)
        if stop is not None and stop.is_set():
            break

    finished = [gs for gs in state['games'] if gs.get('status') == 'finished']
    winner = None
    if len(finished) == 2 and totals[0] != totals[1]:
        winner = names[0] if totals[0] > totals[1] else names[1]
    state['status'] = 'Finished'
    state['summary'] = {'type': 'match_over', 'totals': {names[0]: totals[0], names[1]: totals[1]},
                        'winner': winner,
                        'games': [{'game': gs['game'], 'green': gs['green'], 'blue': gs['blue'],
                                   'scores': gs.get('scores'),
                                   'errors': gs.get('errors') if any(gs.get('errors') or []) else None}
                                  for gs in state['games']]}
    if out_dir:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(state, separators=(',', ':'))
        (out / 'results.json').write_text(payload, encoding='utf-8')
        html = (ROOT / 'dashboard' / 'replay.html').read_text(encoding='utf-8')
        (out / 'replay.html').write_text(
            html.replace('/* REPLAY_DATA */ null', payload.replace('<', '\\u003c')), encoding='utf-8')
    return state
