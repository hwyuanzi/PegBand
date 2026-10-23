"""Round-robin tournament from the command line (the dashboard uses the same code).

  python3 start.py tournament                                # every pair, rotating parameter files
  python3 start.py tournament --config params/n20_k8_r6.txt  # one parameter file for every pairing
  python3 start.py tournament --bots "Greedy (Python)" "Spread (Python)"

Each pairing is one match: two games with the same parameters, each bot playing Green once.
A team's score for the pairing is its points over the two games added together.
"""
import argparse
import itertools
import json
import sys
import time
from pathlib import Path

from .engine import load_config
from .runner import ROOT, build, load_bots, play_match

PARAM_FOLDERS = ('params',)


def list_params(folders=PARAM_FOLDERS):
    """Every .txt parameter file in the given folders, with its N, pegs and rubberbands."""
    if isinstance(folders, (str, Path)):
        folders = [folders]
    out = []
    paths = [p for f in folders for p in sorted((ROOT / f).glob('*.txt'))]
    for path in paths:
        rel = path.resolve().relative_to(ROOT).as_posix()
        entry = {'file': rel, 'name': rel[:-4]}
        try:
            cfg = load_config(path)
            entry.update(cfg.as_dict())
            if cfg.warning:
                entry['warning'] = cfg.warning
        except (OSError, ValueError) as exc:
            entry['error'] = str(exc)
        out.append(entry)
    return out


def pairing_result(state):
    """The fields the results table needs from one finished match."""
    s = state['summary']
    return {'totals': s['totals'], 'winner': s['winner'], 'games': s['games'],
            'params': state['params']}


def build_all(bots):
    """Compile bots that need it, before any clock runs. Returns {name: error or None}."""
    problems = {}
    for b in bots:
        try:
            build(b)
            problems[b['name']] = None
        except Exception as exc:
            problems[b['name']] = str(exc)
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--bots', nargs='+', help='bot names from bots.json (default: all)')
    ap.add_argument('--registry', default='bots.json')
    ap.add_argument('--config', help='use this one parameter file for every pairing')
    ap.add_argument('--clock', type=float, default=120, help='seconds per bot per game')
    ap.add_argument('--output', default='results/tournament')
    args = ap.parse_args()

    roster = {b['name']: b for b in load_bots(args.registry)}
    names = args.bots or list(roster)
    missing = [n for n in names if n not in roster]
    if len(names) < 2 or missing:
        raise ValueError(f'Pick at least two bots from: {", ".join(roster)}')
    files = [args.config] if args.config else [p['file'] for p in list_params() if 'error' not in p]
    if not files:
        raise ValueError('No valid parameter files in params/')
    out = ROOT / args.output / time.strftime('%Y%m%d-%H%M%S')

    for name, err in build_all([roster[n] for n in names]).items():
        if err:
            print(f'! {name}: {err}')
    pairs = list(itertools.combinations(names, 2))
    print(f'{len(names)} bots, {len(pairs)} pairings\n')
    pairings = []
    table = {n: 0 for n in names}
    for i, (a, b) in enumerate(pairs):
        config = files[i % len(files)]
        entry = {'bots': [a, b], 'config': config}
        print(f'[{i + 1}/{len(pairs)}] {a} vs {b} ({Path(config).name}) ... ', end='', flush=True)
        state = play_match(roster[a], roster[b], config, args.clock, out / f'{i + 1:02d}')
        entry.update(pairing_result(state))
        tot = entry['totals']
        print(f"{a} {tot.get(a, '?')} - {tot.get(b, '?')} {b}  ->  {entry['winner'] or 'tie'}")
        table[a] += tot.get(a, 0)
        table[b] += tot.get(b, 0)
        pairings.append(entry)
        (out / 'results.json').write_text(json.dumps(pairings, indent=2), encoding='utf-8')

    print('\nPoints over the whole tournament:')
    for name, pts in sorted(table.items(), key=lambda kv: -kv[1]):
        print(f'  {pts:6}  {name}')
    print(f'\nResults: {out.relative_to(ROOT)}/')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nStopped. Finished pairings are saved.')
    except (OSError, ValueError) as exc:
        sys.exit(f'Error: {exc}')
