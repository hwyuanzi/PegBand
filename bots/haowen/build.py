"""Portable build, run by the official referee before the game clock starts."""
import os
from pathlib import Path
import shlex
import subprocess
import sys

here = Path(__file__).resolve().parent
compiler = shlex.split(os.environ.get("CXX", "c++"))
target = here / ("bot.exe" if sys.platform == "win32" else "bot")
subprocess.run(compiler + ["-std=c++17", "-O2", "-Wall", "-Wextra",
                         str(here / "bot.cpp"), "-o", str(target)], check=True)
