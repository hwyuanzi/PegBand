# Local adversarial opponent

`defender.cpp` is an independently implemented test opponent, not another
student's submission. It opens in the center when appropriate and emphasizes
blocking the opponent's current legal triangle coverage. Its band phase shares
the entry's exact geometry/coverage planner so that placement is tested against
a competent band phase rather than only the weaker official samples.

Build from the repository root:

```sh
c++ -std=c++17 -O2 tools/opponents/defender.cpp -o /tmp/pegband-defender
```

Run a complete two-color pairing with the provided registry (it builds both
bots automatically):

```sh
python3 tools/benchmark.py --registry tools/opponents/registry.json --opponent Defender --params 20,8,6
```

The opponent stays outside `bots/` so it is not accidentally included in the
competition submission. Fixed seeds are used; a wall-clock-limited search can
choose different moves when hardware speed or concurrent CPU load changes.
