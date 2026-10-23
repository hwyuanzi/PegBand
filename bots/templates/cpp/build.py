"""Compile bot.cpp to ./bot. The referee runs this before the clock starts."""
import subprocess
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
out = here / ('bot.exe' if sys.platform == 'win32' else 'bot')
cmd = ['c++', '-std=c++17', '-O2', str(here / 'bot.cpp'), '-o', str(out)]
print(' '.join(cmd))
sys.exit(subprocess.call(cmd))
