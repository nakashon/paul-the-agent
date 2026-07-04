"""Export prediction data to docs/data.json for the static GitHub Pages site.

Joins every locked prediction against actual match results, classifies each pick
as exact / correct-outcome / miss, and produces a single JSON payload consumed
by the front-end. Re-run whenever the database changes:

    python scripts/export_site.py
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "data", "wc2026.db")
OUT = os.path.join(BASE, "docs", "data.json")

# Team -> ISO 3166-1 alpha-2 (for regional-indicator flag emoji). England and
# Scotland use their subdivision flags handled separately below.
ISO = {
    "Algeria": "DZ", "Argentina": "AR", "Australia": "AU", "Austria": "AT",
    "Belgium": "BE", "Bosnia and Herzegovina": "BA", "Brazil": "BR",
    "Canada": "CA", "Cape Verde": "CV", "Colombia": "CO", "Croatia": "HR",
    "Curacao": "CW", "Czechia": "CZ", "DR Congo": "CD", "Ecuador": "EC",
    "Egypt": "EG", "France": "FR", "Germany": "DE", "Ghana": "GH",
    "Haiti": "HT", "Iran": "IR", "Iraq": "IQ", "Ivory Coast": "CI",
    "Japan": "JP", "Jordan": "JO", "Mexico": "MX", "Morocco": "MA",
    "Netherlands": "NL", "New Zealand": "NZ", "Norway": "NO", "Panama": "PA",
    "Paraguay": "PY", "Portugal": "PT", "Qatar": "QA", "Saudi Arabia": "SA",
    "Senegal": "SN", "South Africa": "ZA", "South Korea": "KR", "Spain": "ES",
    "Sweden": "SE", "Switzerland": "CH", "Tunisia": "TN", "Turkiye": "TR",
    "USA": "US", "Uruguay": "UY", "Uzbekistan": "UZ",
}
_SUBDIVISION = {
    # England / Scotland: tag-sequence emoji flags
    "England": "\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F",
    "Scotland": "\U0001F3F4\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F",
}


def flag(team):
    if team in _SUBDIVISION:
        return _SUBDIVISION[team]
    iso = ISO.get(team)
    if not iso:
        return "\U0001F3F3"  # white flag fallback
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso)


def direction(hg, ag):
    if hg > ag:
        return "H"
    if hg < ag:
        return "A"
    return "D"


# Elo-based strength tiers (eloratings.net scale). Thresholds tuned to the
# 48-team field so each band is meaningful.
TIERS = [
    (2020, "elite", "Elite"),
    (1920, "contender", "Contender"),
    (1830, "darkhorse", "Dark Horse"),
    (1740, "challenger", "Challenger"),
    (0, "underdog", "Underdog"),
]


def load_elo(con):
    return {t: r for t, r in con.execute("SELECT team, rating FROM elo")}


def tier_for(elo):
    if elo is None:
        return {"key": "unknown", "label": "—", "elo": None}
    for cut, key, label in TIERS:
        if elo >= cut:
            return {"key": key, "label": label, "elo": round(elo)}
    return {"key": "underdog", "label": "Underdog", "elo": round(elo)}


def load_conf(con):
    """Map (home, away) -> model win probability for the picked winner."""
    conf = {}
    for table in ("locked_bets_md2", "locked_bets_md3",
                  "locked_bets_r32", "locked_bets_r16"):
        for home, away, c in con.execute(
                f"SELECT home, away, conf FROM {table}"):
            if c is not None:
                conf[(home, away)] = round(c, 4)
    return conf


def load_scoring(con):
    rows = con.execute("SELECT stage, dir_pts, exact_pts FROM scoring").fetchall()
    return {s: (d, e) for s, d, e in rows}


KNOCKOUT_STAGES = {"r32", "r16", "qf", "sf", "final"}


def load_results(con):
    """Map (home, away) -> (hg, ag, matchday, pen_home, pen_away)."""
    cols = {c[1] for c in con.execute("PRAGMA table_info(match_results)")}
    pen = ", pen_home, pen_away" if {"pen_home", "pen_away"} <= cols else ""
    res = {}
    for row in con.execute(f"SELECT home, away, hg, ag, matchday{pen} FROM match_results"):
        home, away, hg, ag, md = row[:5]
        ph, pa = (row[5], row[6]) if pen else (None, None)
        res[(home, away)] = (hg, ag, md, ph, pa)
    return res


def advance_dir(stage, hg, ag, ph, pa):
    """Directional outcome. For a knockout tie level after 120', the team that
    wins the penalty shootout is treated as the winner (they advance)."""
    if hg != ag:
        return direction(hg, ag)
    if stage in KNOCKOUT_STAGES and ph is not None and pa is not None:
        return "H" if ph > pa else "A"
    return "D"


# Each source: table, columns for predicted (home, away, ph, pa), stage key, round label
SOURCES = [
    ("locked_bets", "home, away, ph, pa", "group", "Group · MD1"),
    ("locked_bets_md2", "home, away, hg, ag", "group", "Group · MD2"),
    ("locked_bets_md3", "home, away, hg, ag", "group", "Group · MD3"),
    ("locked_bets_r32", "home, away, hg, ag", "r32", "Round of 32"),
    ("locked_bets_r16", "home, away, hg, ag", "r16", "Round of 16"),
]


def build_predictions(con, scoring, results, elo, conf):
    out = []
    for table, cols, stage, label in SOURCES:
        dir_pts, exact_pts = scoring.get(stage, (1, 3))
        for home, away, ph, pa in con.execute(f"SELECT {cols} FROM {table}"):
            pred_dir = direction(ph, pa)
            win_prob = conf.get((home, away))
            row = {
                "round": label,
                "stage": stage,
                "home": home,
                "away": away,
                "home_flag": flag(home),
                "away_flag": flag(away),
                "home_tier": tier_for(elo.get(home)),
                "away_tier": tier_for(elo.get(away)),
                "pred_home": ph,
                "pred_away": pa,
                "pred_dir": pred_dir,
                "confidence": win_prob,
            }
            actual = results.get((home, away))
            if actual is None:
                # try reversed fixture orientation
                rev = results.get((away, home))
                if rev is not None:
                    ag, hg, md, pa, ph_pen = rev
                    actual = (hg, ag, md, ph_pen, pa)
            if actual is None:
                row.update({"status": "pending",
                            "actual_home": None, "actual_away": None, "hit": None})
            else:
                hg, ag, _md, pen_h, pen_a = actual
                exact = (ph == hg and pa == ag)
                actual_dir = advance_dir(stage, hg, ag, pen_h, pen_a)
                dir_ok = pred_dir == actual_dir
                shootout = (hg == ag and pen_h is not None and pen_a is not None
                            and stage in KNOCKOUT_STAGES)
                row.update({
                    "status": "played",
                    "actual_home": hg,
                    "actual_away": ag,
                    "actual_dir": actual_dir,
                    "pen_home": pen_h if shootout else None,
                    "pen_away": pen_a if shootout else None,
                    "pen_winner": (home if pen_h > pen_a else away) if shootout else None,
                    "hit": "exact" if exact else ("dir" if dir_ok else "miss"),
                })
            out.append(row)
    return out


def build_futures(con, gb_pick=None):
    out = []
    picks = dict(con.execute("SELECT bet, pick FROM locked_futures"))
    labels = {"champion": "Champion", "golden_boot": "Golden Boot"}

    # Current model-favourite for each market.
    champ_row = con.execute(
        "SELECT team FROM sim_results ORDER BY title DESC LIMIT 1").fetchone()
    current = {
        "champion": champ_row[0] if champ_row else None,
        "golden_boot": gb_pick,
    }

    for kind, pick in picks.items():
        cur = current.get(kind)
        is_player = kind == "golden_boot"
        out.append({
            "kind": kind,
            "label": labels.get(kind, kind.title()),
            "pick": pick,
            "flag": flag_for_player(con, pick) if is_player else flag(pick.split(" ")[-1]),
            "current": cur,
            "current_flag": (flag_for_player(con, cur) if is_player else flag(cur.split(" ")[-1])) if cur else "",
            "holding": (cur == pick),
            "status": "pending",
        })
    return out


def load_alive(con):
    """Teams still in the tournament = the 16 Round-of-16 participants."""
    return {t for (t,) in con.execute(
        "SELECT home FROM locked_bets_r16 UNION SELECT away FROM locked_bets_r16")}


def build_golden_boot(con, alive):
    """Live golden-boot standings: real current goal tallies (sourced from
    public tournament data) plus Paul's re-projected pick, which weighs each
    contender's current goals against how deep his team is expected to run."""
    # Current goals through the Round of 32 (public data, see GB_AS_OF).
    # (player, country, goals, penalty_taker)
    standings = [
        ("Lionel Messi", "Argentina", 7, False),
        ("Kylian Mbappe", "France", 6, True),
        ("Erling Haaland", "Norway", 5, True),
        ("Harry Kane", "England", 5, True),
        ("Ousmane Dembele", "France", 4, False),
        ("Vinicius Junior", "Brazil", 4, False),
        ("Mikel Oyarzabal", "Spain", 4, True),
        ("Ismaila Sarr", "Senegal", 4, False),
    ]

    # Expected remaining matches per team from the tournament simulation:
    # they play the R16 tie for sure, then each later match with the modeled
    # probability of reaching it.
    depth = {}
    for team, title, final, semi, adv in con.execute(
            "SELECT team, title, final, semi, adv FROM sim_results"):
        depth[team] = 1.0 + (adv or 0) + (semi or 0) + (final or 0)

    games_played = 4  # MD1-3 + Round of 32
    # Knockout scoring regresses (tougher defenses, fewer blowouts), so damp
    # the extrapolated rate rather than projecting group-stage pace forward.
    KO_DAMP = 0.7
    rows = []
    for player, country, goals, pen in standings:
        is_alive = country in alive
        rate = goals / games_played
        e_rem = depth.get(country, 1.0) if is_alive else 0.0
        extra = rate * e_rem * KO_DAMP
        projection = goals + extra
        rows.append({
            "player": player, "country": country, "flag": flag(country),
            "goals": goals, "penalty_taker": pen, "alive": is_alive,
            "projection": round(projection, 1),
            "extra": round(extra, 1),
        })

    # Paul's current pick = best projected finish among players still in.
    pick = max((r for r in rows if r["alive"]),
               key=lambda r: r["projection"], default=None)
    for r in rows:
        r["is_pick"] = bool(pick and r["player"] == pick["player"])

    locked = con.execute(
        "SELECT pick FROM locked_futures WHERE bet='golden_boot'").fetchone()
    max_goals = max((r["goals"] for r in rows), default=1) or 1
    return {
        "as_of": GB_AS_OF,
        "source": GB_SOURCE,
        "locked_pick": locked[0] if locked else None,
        "locked_flag": flag_for_player(con, locked[0]) if locked else "",
        "current_pick": pick["player"] if pick else None,
        "leader": rows[0]["player"] if rows else None,
        "max_goals": max_goals,
        "players": rows,
    }


GB_AS_OF = "Through the Round of 32"
GB_SOURCE = "Public tournament scoring data"


def flag_for_player(con, player):
    row = con.execute(
        "SELECT country FROM gb_candidates WHERE player = ?", (player,)
    ).fetchone()
    return flag(row[0]) if row else "\U0001F3F3"


# Knockout bracket wiring (from scripts/r32.py and scripts/r16.py). R32 games
# are ordered so each adjacent pair feeds one R16 tie, top to bottom.
R32_ORDER = [
    ("South Africa", "Canada"), ("Netherlands", "Morocco"),
    ("Germany", "Paraguay"), ("France", "Sweden"),
    ("Brazil", "Japan"), ("Ivory Coast", "Norway"),
    ("Mexico", "Ecuador"), ("England", "DR Congo"),
    ("USA", "Bosnia and Herzegovina"), ("Belgium", "Senegal"),
    ("Portugal", "Croatia"), ("Spain", "Austria"),
    ("Switzerland", "Algeria"), ("Colombia", "Ghana"),
    ("Argentina", "Cape Verde"), ("Australia", "Egypt"),
]
R16_ORDER = [
    ("Canada", "Morocco"), ("Paraguay", "France"),
    ("Brazil", "Norway"), ("Mexico", "England"),
    ("USA", "Belgium"), ("Portugal", "Spain"),
    ("Switzerland", "Colombia"), ("Argentina", "Egypt"),
]


def _winner(row):
    """Predicted and actual winner team names (None if draw / not played)."""
    pred_w = None
    if row["pred_home"] > row["pred_away"]:
        pred_w = row["home"]
    elif row["pred_home"] < row["pred_away"]:
        pred_w = row["away"]
    act_w = None
    if row["status"] == "played":
        if row["actual_home"] > row["actual_away"]:
            act_w = row["home"]
        elif row["actual_home"] < row["actual_away"]:
            act_w = row["away"]
    return pred_w, act_w


def build_bracket(preds):
    """Structured knockout bracket: R32 -> R16 -> QF -> SF -> Final. Rounds not
    yet predicted are emitted as empty placeholder slots so the tree is complete."""
    by_key = {(p["home"], p["away"]): p for p in preds}

    def match_from(pair):
        p = by_key.get(pair)
        if not p:
            return None
        pred_w, act_w = _winner(p)
        return {
            "home": p["home"], "away": p["away"],
            "home_flag": p["home_flag"], "away_flag": p["away_flag"],
            "home_tier": p["home_tier"], "away_tier": p["away_tier"],
            "pred_home": p["pred_home"], "pred_away": p["pred_away"],
            "pred_winner": pred_w,
            "confidence": p.get("confidence"),
            "status": p["status"], "hit": p["hit"],
            "actual_home": p["actual_home"], "actual_away": p["actual_away"],
            "actual_winner": act_w,
        }

    def placeholders(n):
        return [None] * n

    return [
        {"key": "r32", "label": "Round of 32",
         "matches": [match_from(x) for x in R32_ORDER]},
        {"key": "r16", "label": "Round of 16",
         "matches": [match_from(x) for x in R16_ORDER]},
        {"key": "qf", "label": "Quarter-finals", "matches": placeholders(4)},
        {"key": "sf", "label": "Semi-finals", "matches": placeholders(2)},
        {"key": "final", "label": "Final", "matches": placeholders(1)},
    ]


def build_odds(con, alive=None):
    rows = con.execute(
        "SELECT team, title, final, semi, adv FROM sim_results ORDER BY title DESC"
    ).fetchall()
    if alive:
        rows = [r for r in rows if r[0] in alive]
    rows = rows[:12]
    return [
        {"team": t, "flag": flag(t), "title": ti, "final": f, "semi": s, "advance": a}
        for t, ti, s, f, a in [(r[0], r[1], r[3], r[2], r[4]) for r in rows]
    ]


def summarize(preds, futures):
    played = [p for p in preds if p["status"] == "played"]
    exact = sum(1 for p in played if p["hit"] == "exact")
    dir_only = sum(1 for p in played if p["hit"] == "dir")
    miss = sum(1 for p in played if p["hit"] == "miss")
    correct = exact + dir_only
    n = len(played)
    return {
        "matches_scored": n,
        "exact": exact,
        "direction_only": dir_only,
        "miss": miss,
        "outcome_accuracy": round(correct / n, 4) if n else 0,
        "exact_rate": round(exact / n, 4) if n else 0,
        "pending": sum(1 for p in preds if p["status"] == "pending"),
        "futures_open": len(futures),
    }


def build_timeline(preds):
    """Per-round accuracy in chronological order, plus a running cumulative
    accuracy so the model's improvement over the tournament is visible."""
    order = []
    groups = {}
    for p in preds:
        if p["status"] != "played":
            continue
        r = p["round"]
        if r not in groups:
            groups[r] = []
            order.append(r)
        groups[r].append(p)

    timeline = []
    cum_correct = cum_n = cum_exact = 0
    for r in order:
        rows = groups[r]
        n = len(rows)
        correct = sum(1 for p in rows if p["hit"] in ("exact", "dir"))
        exact = sum(1 for p in rows if p["hit"] == "exact")
        cum_correct += correct
        cum_n += n
        cum_exact += exact
        timeline.append({
            "round": r,
            "matches": n,
            "exact": exact,
            "accuracy": round(correct / n, 4) if n else 0,
            "exact_rate": round(exact / n, 4) if n else 0,
            "cum_accuracy": round(cum_correct / cum_n, 4) if cum_n else 0,
            "cum_exact_rate": round(cum_exact / cum_n, 4) if cum_n else 0,
        })
    return timeline


def build_title_race(con, odds):
    """Champion pick summary for the Title Race banner: the locked pre-tournament
    pick vs Paul's current bracket-aware favourite, plus its title probability."""
    locked = con.execute(
        "SELECT pick FROM locked_futures WHERE bet='champion'").fetchone()
    locked_pick = locked[0] if locked else None
    current = odds[0]["team"] if odds else None
    return {
        "locked_pick": locked_pick,
        "locked_flag": flag(locked_pick) if locked_pick else "",
        "current_pick": current,
        "current_flag": flag(current) if current else "",
        "title_pct": odds[0]["title"] if odds else None,
        "holding": (current == locked_pick),
        "sims": SIM_COUNT,
    }


SIM_COUNT = 20000


def main():
    con = sqlite3.connect(DB)
    scoring = load_scoring(con)
    results = load_results(con)
    elo = load_elo(con)
    conf = load_conf(con)
    preds = build_predictions(con, scoring, results, elo, conf)
    alive = load_alive(con)
    golden_boot = build_golden_boot(con, alive)
    futures = build_futures(con, gb_pick=golden_boot.get("current_pick"))
    odds = build_odds(con, alive)
    title_race = build_title_race(con, odds)
    bracket = build_bracket(preds)
    summary = summarize(preds, futures)
    timeline = build_timeline(preds)
    con.close()

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "timeline": timeline,
        "predictions": preds,
        "bracket": bracket,
        "futures": futures,
        "golden_boot": golden_boot,
        "title_race": title_race,
        "odds": odds,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {OUT}: {summary['matches_scored']} graded, "
          f"{summary['outcome_accuracy']*100:.1f}% outcome accuracy, "
          f"{len(preds)} predictions total.")


if __name__ == "__main__":
    main()
