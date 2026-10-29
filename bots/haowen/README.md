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
explicit wall-clock deadline. Position and move caches reuse completed work.
Small boards (N <= 12, k <= 6) search the final four placements over every empty
square, with a preliminary beam search supplying a fallback. On other boards,
final placement candidates are expanded, including all cells for N <= 30,
k <= 10. Scores come from the actual terminal band planner. At a terminal
search deadline the bot retains improvements from fully evaluated root moves.
The deadline can prevent completing the entire endgame tree.

For large boards with many bands (N > 30 or k > 10, and 2*r >= k), the validated
v1 placement policy is retained through the Green final placement. Blue's last
placement uses the enhanced terminal search. This preserves the successful
large-board policy after testing found regressions from using the new search
throughout that configuration.

At the band phase, the bot enumerates every maximal legal subset of its pegs.
Blocked pairs and triples give exact legality certificates for larger subsets.
It calculates exact cell coverage and optimizes the union of at most `r` bands.
One-band selection is exact; larger selections use exhaustive comparisons,
bounded branch-and-bound, multiple starts, and coverage exchanges as appropriate.
All candidate bands are legal. Search-budget limits can prevent proving global
optimality; peg placement is heuristic.

Default peg search is capped at 4 seconds per move. The enhanced final
placement may use 18 seconds, and small-board penultimate placements may use
12 seconds. The remaining game budget is also checked. At 20 pegs the placement
caps plus band planning total at most 99 seconds, leaving margin inside the
official 120-second clock. Band planning runs once, for at most
5 seconds of optimization; later band replies use the saved plan. There are
no background thinking threads. `PEGBAND_SECONDS` can lower the per-peg limit
for local experiments; leave it unset for submission.

## Files to submit

The preferred submission is the generated, standalone `submission/bot.cpp`
from the repository root. It embeds both placement policies and the band
planner; only that one C++ file is required. Compile it with
`c++ -std=c++17 -O2 bot.cpp -o bot` on the architect's M2 Mac.

For the modular development version in this folder, keep `bot.cpp`, `pegs.h`,
`pegs_classic.h`, `bands.h`, and `build.py` together. Regenerate the standalone
file with `python3 tools/package_bot.py` from the repository root.

The reference rules and protocol are in the
[official PegBand architecture](https://github.com/KeeferW/pegband).
The implementation follows the supplied referee's scoring, including
enemy pegs on an edge and single-corner cell contacts.

No claim is made that this bot is mathematically unbeatable. Other entrants'
private bots are not available for testing.
