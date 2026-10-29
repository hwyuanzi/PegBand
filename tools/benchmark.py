#!/usr/bin/env python3
"""Benchmark color-swapped matches with the official referee.

Examples:
  python3 tools/benchmark.py --params 10,5,5
  python3 tools/benchmark.py --params 20,8,6 --opponent 'Spread (Python)'
  python3 tools/benchmark.py --params 50,20,20 --opponent haowen

Full results and a replay are saved for every pairing. The report distinguishes
wins on play from matches involving a crash or timeout.
"""
import argparse
import datetime
import hashlib
import json
import os
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from referee.engine import make_config
from referee.runner import build, load_bots, play_match


def parameters(value):
    try:
        n, k, r = [int(x) for x in value.replace(":", ",").split(",")]
        return make_config(n, k, r)
    except (ValueError, TypeError) as exc:
        raise argparse.ArgumentTypeError("use N,pegs,bands: %s" % exc)


def compact_result(state, bot_name, opponent_name):
    rows = []
    for game in state["games"]:
        index = 0 if game["green_team"] == 0 else 1
        opponent_index = 1 - index
        errors = game.get("errors", [None, None])
        scores = game["scores"]
        tied = scores[index] == scores[opponent_index]
        win = scores[index] > scores[opponent_index] or (tied and index == 0)
        own_moves = [m for m in game["moves"] if m["player"] == index]
        rows.append({
            "color": "green" if index == 0 else "blue",
            "score": scores[index],
            "opponent_score": scores[opponent_index],
            "winner_on_score": bot_name if win else opponent_name,
            "thinking_seconds": round(state["time_budget"] - game["clocks"][index], 4),
            "opponent_thinking_seconds": round(state["time_budget"] - game["clocks"][opponent_index], 4),
            "error": errors[index],
            "opponent_error": errors[opponent_index],
            "refused_moves": sum(bool(m.get("refused")) for m in own_moves),
            "opponent_refused_moves": sum(bool(m.get("refused")) for m in game["moves"]
                                          if m["player"] == opponent_index),
            "finished": game["ended"] == "finished",
        })
    # Compute team totals from the color-swapped rows.
    total_score = sum(g["score"] for g in rows)
    opponent_total = sum(g["opponent_score"] for g in rows)
    return {
        "bot": bot_name, "opponent": opponent_name,
        "params": state["params"], "games": rows,
        "total_score": total_score, "opponent_total": opponent_total,
        "margin": total_score - opponent_total,
        "winner": bot_name if total_score > opponent_total else
                  opponent_name if total_score < opponent_total else None,
        "all_moves_legal": all(g["refused_moves"] == 0 for g in rows),
        "clean_match": all(not g["error"] and not g["opponent_error"] for g in rows),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bot", default="haowen", help="bot name from the referee roster")
    parser.add_argument("--opponent", action="append", help="repeat to select opponents")
    parser.add_argument("--params", type=parameters, action="append", help="N,pegs,bands; repeat for a matrix")
    parser.add_argument("--clock", type=float, default=120.0)
    parser.add_argument("--output", type=Path, help="directory for report.json and replays")
    parser.add_argument("--registry", default="bots.json")
    args = parser.parse_args()
    if args.clock <= 0:
        parser.error("--clock must be positive")
    roster = {bot["name"]: bot for bot in load_bots(args.registry)}
    opponents = args.opponent or ["Spread (Python)", "Greedy (Python)", "Random (Python)"]
    configs = args.params or [make_config(10, 5, 5)]
    for name in [args.bot] + opponents:
        if name not in roster:
            parser.error("unknown bot %r; available: %s" % (name, ", ".join(roster)))
        build(roster[name])
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or ROOT / "results" / ("benchmark-" + stamp)
    output.mkdir(parents=True, exist_ok=True)
    fingerprints = {}
    for name in [args.bot] + opponents:
        folder = Path(roster[name]["cwd"])
        fingerprints[name] = {
            str(path.relative_to(folder)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(folder.rglob("*"))
            if path.is_file() and path.suffix in (".cpp", ".h", ".hpp", ".py", ".jl")
        }
    report = {"created_utc": stamp, "clock_seconds": args.clock,
              "platform": platform.platform(), "python_version": platform.python_version(),
              "bot_environment": {key: os.environ[key] for key in ("PEGBAND_SECONDS", "PEGBAND_SEARCH") if key in os.environ},
              "sources_sha256": fingerprints, "matches": []}
    for config in configs:
        for opponent in opponents:
            number = len(report["matches"]) + 1
            directory = output / ("%02d-n%d-k%d-r%d" % (number, config.n, config.k, config.r))
            # Separate names preserve team totals even when comparing a bot to itself.
            other = dict(roster[opponent])
            if opponent == args.bot:
                other["name"] += " (mirror)"
            print("Playing %s vs %s, %s ..." % (args.bot, other["name"], config), flush=True)
            finished_games = set()
            def progress(current, *_):
                for game in current["games"]:
                    if game.get("status") == "finished" and game["game"] not in finished_games:
                        finished_games.add(game["game"])
                        print("  Game %d: %s %d - %d %s; thinking %.3f/%.3fs; errors=%s" % (
                            game["game"], game["green"], game["scores"][0], game["scores"][1],
                            game["blue"], args.clock-game["clocks"][0], args.clock-game["clocks"][1],
                            game["errors"]), flush=True)
            state = play_match(roster[args.bot], other, config, clock=args.clock,
                               out_dir=directory, on_progress=progress)
            result = compact_result(state, args.bot, other["name"])
            result["replay"] = str((directory / "replay.html").resolve())
            result["results"] = str((directory / "results.json").resolve())
            report["matches"].append(result)
            (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(result, ensure_ascii=False), flush=True)
    print("Report: %s" % (output / "report.json"))
    return 1 if any(not m["all_moves_legal"] or any(g["error"] for g in m["games"])
                    for m in report["matches"]) else 0


if __name__ == "__main__":
    sys.exit(main())
