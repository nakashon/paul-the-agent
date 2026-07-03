"""Export prediction data to docs/data.json for the static GitHub Pages site.

Joins every locked prediction against actual match results, applies the
stage-based scoring rules, and produces a single JSON payload consumed by the
front-end. Re-run whenever the database changes:

    python scripts/export_site.py
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "data", "wc2026.db")
OUT = os.path.join(BASE, "docs", "data.json")


def direction(hg, ag):
    if hg > ag:
        return "H"
    if hg < ag:
        return "A"
    return "D"


def load_scoring(con):
    rows = con.execute("SELECT stage, dir_pts, exact_pts FROM scoring").fetchall()
    return {s: (d, e) for s, d, e in rows}


def load_results(con):
    """Map (home, away) -> (hg, ag, matchday)."""
    res = {}
    for home, away, hg, ag, md in con.execute(
        "SELECT home, away, hg, ag, matchday FROM match_results"
    ):
        res[(home, away)] = (hg, ag, md)
    return res


# Each source: table, columns for predicted (home, away, ph, pa), stage key, round label
SOURCES = [
    ("locked_bets", "home, away, ph, pa", "group", "Group · MD1"),
    ("locked_bets_md2", "home, away, hg, ag", "group", "Group · MD2"),
    ("locked_bets_md3", "home, away, hg, ag", "group", "Group · MD3"),
    ("locked_bets_r32", "home, away, hg, ag", "r32", "Round of 32"),
    ("locked_bets_r16", "home, away, hg, ag", "r16", "Round of 16"),
]


def build_predictions(con, scoring, results):
    out = []
    for table, cols, stage, label in SOURCES:
        dir_pts, exact_pts = scoring.get(stage, (1, 3))
        for home, away, ph, pa in con.execute(f"SELECT {cols} FROM {table}"):
            row = {
                "round": label,
                "stage": stage,
                "home": home,
                "away": away,
                "pred_home": ph,
                "pred_away": pa,
                "pred_dir": direction(ph, pa),
            }
            actual = results.get((home, away))
            if actual is None:
                # try reversed fixture orientation
                rev = results.get((away, home))
                if rev is not None:
                    ag, hg, md = rev
                    actual = (hg, ag, md)
            if actual is None:
                row.update({"status": "pending", "points": None,
                            "actual_home": None, "actual_away": None, "hit": None})
            else:
                hg, ag, _md = actual
                exact = (ph == hg and pa == ag)
                dir_ok = direction(ph, pa) == direction(hg, ag)
                pts = exact_pts if exact else (dir_pts if dir_ok else 0)
                row.update({
                    "status": "played",
                    "actual_home": hg,
                    "actual_away": ag,
                    "actual_dir": direction(hg, ag),
                    "hit": "exact" if exact else ("dir" if dir_ok else "miss"),
                    "points": pts,
                    "max_points": exact_pts,
                })
            out.append(row)
    return out


def build_futures(con, scoring_futures):
    out = []
    picks = dict(con.execute("SELECT bet, pick FROM locked_futures"))
    pts = dict(con.execute("SELECT kind, pts FROM futures_pts"))
    labels = {"champion": "Champion", "golden_boot": "Golden Boot"}
    for kind, pick in picks.items():
        out.append({
            "kind": kind,
            "label": labels.get(kind, kind.title()),
            "pick": pick,
            "max_points": pts.get(kind, 0),
            "status": "pending",
            "points": None,
        })
    return out


def build_odds(con):
    rows = con.execute(
        "SELECT team, title, final, semi, adv FROM sim_results ORDER BY title DESC LIMIT 12"
    ).fetchall()
    return [
        {"team": t, "title": ti, "final": f, "semi": s, "advance": a}
        for t, ti, s, f, a in [(r[0], r[1], r[3], r[2], r[4]) for r in rows]
    ]


def summarize(preds, futures):
    played = [p for p in preds if p["status"] == "played"]
    total_pts = sum(p["points"] for p in played)
    max_pts = sum(p["max_points"] for p in played)
    exact = sum(1 for p in played if p["hit"] == "exact")
    dir_only = sum(1 for p in played if p["hit"] == "dir")
    miss = sum(1 for p in played if p["hit"] == "miss")
    correct = exact + dir_only
    n = len(played)
    return {
        "matches_scored": n,
        "total_points": total_pts,
        "max_points": max_pts,
        "efficiency": round(total_pts / max_pts, 4) if max_pts else 0,
        "exact": exact,
        "direction_only": dir_only,
        "miss": miss,
        "outcome_accuracy": round(correct / n, 4) if n else 0,
        "exact_rate": round(exact / n, 4) if n else 0,
        "pending": sum(1 for p in preds if p["status"] == "pending"),
        "futures_open": len(futures),
    }


def main():
    con = sqlite3.connect(DB)
    scoring = load_scoring(con)
    results = load_results(con)
    preds = build_predictions(con, scoring, results)
    futures = build_futures(con, scoring)
    odds = build_odds(con)
    summary = summarize(preds, futures)
    con.close()

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "predictions": preds,
        "futures": futures,
        "odds": odds,
        "scoring": scoring,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {OUT}: {summary['matches_scored']} scored, "
          f"{summary['total_points']}/{summary['max_points']} pts, "
          f"{len(preds)} predictions total.")


if __name__ == "__main__":
    main()
