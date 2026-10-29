# Haowen Aegis — PegBand entry

Bot name: **Haowen Aegis**. The official dashboard discovers this folder as `haowen`.

Language: **C++17**, standard library only. Build helper: **Python 3.8+**.
Tested locally with Apple Clang 21 on macOS ARM64. The compiler does not need
architecture-specific flags, external headers, package downloads, or network access.

## Run with the official architecture

Copy this entire `haowen` folder into the architect's `bots/` folder. In the
dashboard, press **Rescan**, select `haowen`, and start a pairing. The referee
automatically runs `python3 build.py` before the thinking clock starts.

Manual build, from this folder:

```sh
python3 build.py
./bot
```

Or compile directly:

```sh
c++ -std=c++17 -O2 bot.cpp -o bot
```

The executable reads one JSON object per line from stdin and flushes one JSON
reply per line to stdout. It requires the normal official `start`, `peg`, and
`band` messages. It does not open files or communicate with other processes
during play. Windows uses `bot.exe`; `CXX` can select a different C++ compiler.

## Strategy

Peg placement evaluates both new legal coverage and the opponent's coverage
lost to a blocking peg. It searches adversarial replies with iterative
deepening, alpha-beta pruning, spatially varied candidate moves, and an
explicit wall-clock deadline. Completed search iterations determine the move;
an unfinished deeper iteration is discarded. Small final-move positions compare
every empty square using actual terminal band scores.

At the band phase, the bot enumerates every maximal legal subset of its pegs.
Blocked pairs and triples give exact legality certificates for larger subsets.
It calculates exact cell coverage and optimizes the union of at most `r` bands.
One-band selection is exact; larger selections use exhaustive comparisons,
bounded branch-and-bound, multiple starts, and coverage exchanges as appropriate.
All candidate bands are legal. Search-budget limits can prevent proving global
optimality; peg placement is heuristic.

Default peg search is capped at 4 seconds per move, with the remaining game
budget also checked. At the maximum 20 pegs, this reserves substantial margin
inside the official 120-second clock. Band planning runs once, for at most
5 seconds of optimization; later band replies use the saved plan. There are
no background thinking threads. `PEGBAND_SECONDS` can lower the per-peg limit
for local experiments; leave it unset for submission.

## Files to submit

Keep `bot.cpp`, `pegs.h`, `bands.h`, `build.py`, and this README together.
Submit source rather than a compiled executable, so the architect can build
on their M2 Mac. No setup step beyond an available C++17 compiler is needed.

The reference rules and protocol are in the
[official PegBand architecture](https://github.com/KeeferW/pegband).
The implementation follows the supplied referee's scoring, including
enemy pegs on an edge and single-corner cell contacts.

No claim is made that this bot is mathematically unbeatable. Other entrants'
private bots are not available for testing.
