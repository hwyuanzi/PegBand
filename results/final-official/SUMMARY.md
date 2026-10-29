# Final official-referee benchmark

All entries use the final source fingerprint, the normal bot settings and a 120-second game clock. Each pairing swaps colors. Timed search can vary with machine load.

| N / k / r | Opponent | Green score | Blue score | Pairing total |
|---|---|---:|---:|---:|
| 2 / 1 / 1 | Spread (Python) | 1–1 | 1–1 | 2–2 |
| 2 / 1 / 1 | Greedy (Python) | 1–1 | 1–1 | 2–2 |
| 2 / 1 / 1 | Random (Python) | 1–1 | 1–1 | 2–2 |
| 10 / 2 / 1 | Spread (Python) | 18–10 | 17–9 | 35–19 |
| 10 / 2 / 1 | Greedy (Python) | 18–18 | 18–18 | 36–36 |
| 10 / 2 / 1 | Random (Python) | 18–7 | 12–0 | 30–7 |
| 10 / 5 / 5 | Spread (Python) | 78–28 | 72–38 | 150–66 |
| 10 / 5 / 5 | Greedy (Python) | 80–25 | 85–56 | 165–81 |
| 10 / 5 / 5 | Random (Python) | 73–16 | 76–15 | 149–31 |
| 20 / 8 / 6 | Spread (Python) | 302–59 | 330–120 | 632–179 |
| 20 / 8 / 6 | Greedy (Python) | 357–119 | 376–112 | 733–231 |
| 20 / 8 / 6 | Random (Python) | 325–81 | 325–63 | 650–144 |
| 20 / 8 / 1 | Spread (Python) | 134–66 | 177–52 | 311–118 |
| 20 / 8 / 1 | Greedy (Python) | 213–67 | 167–50 | 380–117 |
| 20 / 8 / 1 | Random (Python) | 165–11 | 162–12 | 327–23 |
| 50 / 20 / 20 | Random (Python) | 2417–458 | 2373–485 | 4790–943 |

Across 32 games: 24 higher scores, 8 equal scores, 0 lower scores. The eight equal scores are the k=1 games and the k=2 Greedy games. Green wins a single-game tie by rule; the color-swapped pairings tie on total points.

Own protocol errors, timeouts and refused moves: 0. No opponent forfeited. Maximum measured own thinking time: 51.4473 seconds.

Validation: all 48 unit tests passed, including 2,105 geometry oracle cases, 29 exact small band-plan cases and 20 exact final-peg tactical positions.

Full game data, source hashes, clocks and replay paths: [report.json](report.json).
