"""Paul the Agent — one-command matchday update loop.

Runs the full pipeline after new results are in:
  1. calibrate.py  — re-tune goal calibration from all stored results
  2. model.py      — refresh every pending per-match bet (with calibration)
  3. simulate.py   — re-run the Monte Carlo tournament for live title odds

Usage:
    # 1) log any new results first:
    python add_result.py "Brazil" 2 1 "Morocco" 1
    # 2) then run the loop:
    python update.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(__file__)
PY = sys.executable


def run(script):
    print(f"\n{'='*60}\n  {script}\n{'='*60}")
    subprocess.run([PY, os.path.join(HERE, script)], check=True)


def main():
    for s in ("calibrate.py", "model.py", "simulate.py"):
        run(s)
    print("\n🐙 Paul the Agent — update complete. Bets and title odds refreshed.")


if __name__ == "__main__":
    main()
