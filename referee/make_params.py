"""Write a parameter file: the board side N, the pegs each, the rubberbands each.

  python3 start.py params --n 20 --pegs 8 --bands 6 --out params/my_game.txt
"""
import argparse

from .engine import make_config
from .runner import ROOT


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--n', type=int, required=True, help='board side, at most 50')
    ap.add_argument('--pegs', type=int, required=True, help='pegs each, at most 20')
    ap.add_argument('--bands', type=int, required=True, help='rubberbands each, at most the pegs')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    cfg = make_config(args.n, args.pegs, args.bands)
    path = ROOT / args.out
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'# N (board side), pegs each, rubberbands each\n'
                    f'{cfg.n}\n{cfg.k}\n{cfg.r}\n', encoding='utf-8')
    if cfg.warning:
        print(f'Note: {cfg.warning}')
    print(f'Wrote {args.out}: {cfg}')


if __name__ == '__main__':
    main()
