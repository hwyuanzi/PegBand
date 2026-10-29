#!/usr/bin/env python3
"""Play an existing bot through a board symmetry, for adversarial regression.

Usage: python3 symmetry.py SYMMETRY EXECUTABLE [ARG ...]
SYMMETRY is 0..7: four rotations, then four reflected rotations.
This is a testing adapter, not part of the submitted entry.
"""
import json
import subprocess
import sys


def square(p, n, symmetry):
    x, y = p % n, p // n
    if symmetry >= 4:
        x = n-1-x
    for _ in range(symmetry % 4):
        x, y = n-1-y, x
    return y*n+x


def main():
    symmetry = int(sys.argv[1])
    if symmetry not in range(8):
        raise ValueError("symmetry must be 0..7")
    child = subprocess.Popen(sys.argv[2:], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, text=True, bufsize=1)
    n, inverse = 0, []
    try:
        for line in sys.stdin:
            message = json.loads(line)
            if message.get("type") == "start":
                n = message["N"]
                inverse = [0]*(n*n)
                for p in range(n*n):
                    inverse[square(p, n, symmetry)] = p
            for field in ("your_pegs", "their_pegs"):
                if field in message:
                    message[field] = sorted(square(p, n, symmetry) for p in message[field])
            for field in ("your_bands", "their_bands"):
                if field in message:
                    message[field] = [[square(p, n, symmetry) for p in band]
                                      for band in message[field]]
            if "board" in message:
                board = [0]*(n*n)
                for p, value in enumerate(message["board"]):
                    board[square(p, n, symmetry)] = value
                message["board"] = board
            child.stdin.write(json.dumps(message)+"\n")
            child.stdin.flush()
            reply = json.loads(child.stdout.readline())
            if "peg" in reply:
                reply["peg"] = inverse[reply["peg"]]
            if "band" in reply:
                reply["band"] = [inverse[p] for p in reply["band"]]
            print(json.dumps(reply), flush=True)
    finally:
        child.stdin.close()
        child.terminate()
        child.wait()


if __name__ == "__main__":
    main()
