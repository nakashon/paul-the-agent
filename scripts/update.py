"""Paul the Agent — one-command matchday sync.

Run this after logging new results and goals to refresh everything, in order:
  1. calibrate.py        — re-tune goal calibration from all stored results
  2. model.py            — refresh every still-pending locked bet (with calibration)
  3. qf.py               — lock in any quarter-final ties that just became knowable
                           (never touches a QF tie once it's already locked)
  4. simulate_bracket.py — re-run the bracket-aware Monte Carlo for live title odds
                           (plays the actual set draw, not a bracket-blind reseed)
  5. export_site.py      — regenerate docs/data.json for the website

Usage:
    # 1) log whatever came in first:
    python3 scripts/result.py "Home" 2 1 "Away"      # match score (add --pens for shootouts)
    python3 scripts/goals.py "Player" +1              # golden boot goal tally
    # 2) then run the sync:
    python3 scripts/update.py
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
    for s in ("calibrate.py", "model.py", "qf.py", "simulate_bracket.py", "export_site.py"):
        run(s)
    print("\n🐙 Paul the Agent — fully synced: model, title odds, and site data are all up to date.")


if __name__ == "__main__":
    main()
