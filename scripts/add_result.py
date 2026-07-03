"""Add or update a played match result, generically.

Usage:
    python add_result.py "Home Team" hg ag "Away Team" [matchday]

Example:
    python add_result.py "Brazil" 2 1 "Morocco" 1

Stored in match_results and consumed by calibrate.py and simulate.py so the
model and tournament odds update automatically. Team names must match those in
the teams table (run with no args to list valid names).
"""
import os
import sqlite3
import sys

DB = os.path.join(os.path.dirname(__file__), "..", "data", "wc2026.db")


def valid_names():
    con = sqlite3.connect(DB)
    names = [r[0] for r in con.execute("SELECT name FROM teams ORDER BY name")]
    con.close()
    return names


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        print("Valid team names:")
        print(", ".join(valid_names()))
        return
    home = sys.argv[1]
    hg = int(sys.argv[2])
    ag = int(sys.argv[3])
    away = sys.argv[4]
    md = int(sys.argv[5]) if len(sys.argv) > 5 else 0

    names = set(valid_names())
    for t in (home, away):
        if t not in names:
            print(f"ERROR: '{t}' is not a valid team name. Run with no args to list names.")
            return

    con = sqlite3.connect(DB)
    con.execute("INSERT OR REPLACE INTO match_results VALUES (?,?,?,?,?)",
                (home, away, hg, ag, md))
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM match_results").fetchone()[0]
    con.close()
    print(f"Recorded: {home} {hg}-{ag} {away} (matchday {md}). Total results stored: {n}")


if __name__ == "__main__":
    main()
