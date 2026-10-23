# PegBand

The architecture for the Heuristic Problem Solving game **PegBand** (Dennis Shasha's Upstart
Puzzle, [CACM](https://cacm.acm.org/upstart-puzzles/pegband/)): a referee that runs the bots,
a live dashboard in the browser, saved replays, and starter bots in **Python, C++ and Julia**.
It is set up the same way as the Evasion and Kelly architectures.

| | |
|---|---|
| **Runs on** | Mac, Linux (including crunchy5) and Windows |
| **Needs** | Python 3.8+, standard library only (nothing to `pip install`) |
| **Clock** | 120 seconds of thinking time per bot per game; bots think one at a time |
| **Board** | N × N, N up to 50, with a peg hole at the centre of every square |
| **Pegs** | k each, at most 20 and no more than N/2 |
| **Rubberbands** | r each, at most 20 and never more than k |
| **A pairing** | 2 games: each bot plays Green (first) once. A team's score is its points over both games |

**Contents:** [Quick start](#quick-start) · [The rules](#the-rules-the-referee-enforces) ·
[The dashboard](#the-dashboard) · [Making a bot](#making-a-bot) ·
[The messages between referee and bot](#the-messages-between-referee-and-bot) ·
[Other ways to run](#other-ways-to-run)

---

## Quick start

```sh
cd pegband
python3 start.py
```

Open **http://127.0.0.1:8092** in your browser. Stop the server with **Ctrl+C**.
(On Windows, type `python` instead of `python3`.)

Press **Every pair**, then **Start tournament**, and the sample bots play each other
while you watch.

---

## The rules the referee enforces

A game has two phases. The players move one at a time, Green first.

**1. Pegs.** Each player places one peg per turn, k times. A peg may not go where either
player already has one. A peg sent off the board or onto a taken square is not placed, the
referee notes it, and the game goes on.

**2. Rubberbands.** Each player places one band per turn, r times. A band is given as a set
of your own pegs, and the band is the convex hull of those pegs, the shape a real rubberband
takes when stretched around them. The order you list them in does not matter, and naming a peg
that falls inside the hull changes nothing.

A band is refused when it names a peg that is not yours (or no peg at all), or when a peg of
the other colour lies inside the hull or exactly on its boundary. The puzzle says a band "may
touch only pegs of that player's colour", so an enemy peg on an edge counts as a touch. A
refused band is not placed and scores nothing. It still uses up that turn, but it is not a
forfeit.

**Scoring.** A player scores a square when one of its bands covers it, "fully or partially":
the square is inside the band, or the band's boundary crosses it. A square holding a peg of
the *other* colour never scores. Bands may overlap, and a player never scores the same square
twice, but both players can score the same square. The player with more points wins; on a
tie the player who went first (Green) wins.

A band that touches a square at a single point does not cross it. In the column's warm-up,
Blue's triangle scores 6 and not 7 because one edge passes exactly through the corner of a
neighbouring square. `tests/test_game.py` replays every worked example from the column and
checks the final score of 8 to 8.

**Clocks and failure.** Each bot has 120 seconds of thinking time for a whole game, counted
only while the referee waits for its answer. A bot that runs out of time, crashes or breaks
the protocol forfeits: it places nothing more and keeps the points it had. The other player
plays on to the end, and the pairing is marked forfeit in the results so a win that way is
never mistaken for a win on play.

A bot whose build fails (a C++ file that no longer compiles, say) forfeits with the compiler's
message. The referee deletes the binary left by the last good build, so nobody is scored on
code that no longer compiles.

The geometry uses only integer arithmetic, so two runs of the same game always score the
same.

---

## The dashboard

The page has three steps, then the live view and the results.

1. **Bots** are read from `bots.json`, plus any folder dropped into `bots/` that holds a
   `bot.py`, `bot.cpp` or `bot.jl`. Press **Rescan** after adding one.
2. **Parameters** are read from `params/`: each file holds N, the pegs each and the
   rubberbands each. Type new ones into the page, or drop a file in and press **Rescan**.
3. **Pairings:** press **Add pairing** (or **Every pair** for a round robin), choose two bots
   and a parameter file. Then **Start tournament**.

While a tournament runs, **Playing now** shows the board live: pegs, every rubberband as the
polygon it really is, each player's covered squares shaded (purple where both players score
the same square), the running points and both clocks. The **watching pace** lingers a few
hundred milliseconds per move so the game is watchable; it never counts against the bots'
clocks and you can change it while a game runs.

Each side of the board view names the team, its colour, whether it moves first or second,
and its clock. While a game runs, the side that is ahead and the side to play are marked, and
when it ends the winner is marked WON.

Finished pairings go into the results table with each game's score tagged by the colour that
team played (`165 G – 179 B`), the total, the winner and the margin, and a replay link.
Replays are self-contained HTML files under `results/`. Step through one with the arrow keys,
or press space to play. Results survive a restart, and **Clear results** keeps a backup.

---

## Making a bot

Copy a template out of `bots/templates/` into `bots/<your-name>/`:

```sh
cp -r bots/templates/python bots/my-bot
```

Edit the part marked `EDIT ONLY THIS SECTION`. You write two functions: `place_peg` returns
the square for your next peg, and `place_band` returns the list of your own pegs to stretch
this rubberband around. The referee finds the folder by itself; press **Rescan** on the page. Working examples are in
`bots/samples/`:

| Bot | What it does |
|---|---|
| **Spread** | Puts pegs far from every other peg, then stretches the biggest legal band it can |
| **Greedy** | Counts squares: each peg is the one that opens the most area, each band the legal one gaining the most new squares |
| **Random** | Random free squares, random pairs of pegs. A punching bag |

A bot in another language just needs to read a line of JSON and write a line of JSON; list it
in `bots.json` with the command that runs it.

Flush after every reply. C++ (`std::flush`), Julia (`flush(stdout)`) and buffered Python
will otherwise hold the answer until the buffer fills, and the referee times you out. Note
also that `your_bands` and `their_bands` are lists of lists. The C++ and Julia templates read
the flat lists with `list_field` and those two with `list_of_lists`.

---

## The messages between referee and bot

One JSON object per line, on standard input and standard output. Anything on standard error
is ignored, so debug there. A stray `print` on standard output lands in the middle of the
protocol and ends your game.

Squares are numbered `0 .. N*N-1`, left to right and top to bottom: square `i` is in row
`i // N`, column `i % N`. You may answer with a number or a `[row, column]` pair.

Not every language's JSON encoder keeps integers looking like integers, so `34`, `34.0` and
`"34"` all name square 34, and `[2, 3]`, `[2.0, 3.0]` and `["2", "3"]` all name row 2, column 3.
A real fraction such as `34.5` names no square and is refused.

**Start** (not on your clock, 30 seconds to reply):

```json
{"type":"start","protocol_version":1,"color":"green","you":1,"N":10,"pegs":5,"bands":5,"clock":120}
```
reply `{"ready": true}`

**A peg:** reply `{"peg": 34}`. **A band:** reply `{"band": [12, 34, 56]}`.
Both messages carry the whole position, so a bot never has to remember anything:

| field | meaning |
|---|---|
| `N`, `pegs_each`, `bands_each` | the parameters of this game |
| `color`, `you` | `"green"` or `"blue"`, and `1` or `2` |
| `phase`, `round` | `"pegs"` or `"bands"`, and which round of it |
| `board` | N*N numbers: 0 empty, 1 green peg, 2 blue peg |
| `your_pegs`, `their_pegs` | the squares each player's pegs are on |
| `your_bands`, `their_bands` | the pegs each band so far was stretched around |
| `scores` | `[green, blue]` as they stand |

---

## Other ways to run

```sh
python3 start.py match "Greedy (Python)" "Spread (Python)"     # one match, opens the replay
python3 start.py match "A" "B" --config params/n20_k8_r6.txt
python3 start.py tournament                                     # every pair, no browser
python3 start.py params --n 20 --pegs 8 --bands 6 --out params/my_game.txt
python3 -m unittest discover -s tests -t .                      # the rules and the referee
```

`--help` after any command lists its options.

## What is where

```
start.py              every command
referee/geometry.py   convex hulls and which squares a band covers (exact integer arithmetic)
referee/engine.py     the rules: pegs, bands, refusals and the score
referee/runner.py     runs the bot processes, the clocks, one game and one match
referee/server.py     the dashboard
referee/tournament.py round robin from the command line
dashboard/            the two pages: the dashboard and the board view (also used for replays)
bots/templates/       starter bots in Python, C++ and Julia
bots/samples/         working bots to play against
params/               parameter files
tests/                the worked examples from the column, and misbehaving bots
```
