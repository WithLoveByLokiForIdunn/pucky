#!/usr/bin/env python3
"""
build_soccer_db.py — Build SQLite soccer knowledge base from OpenFootball JSON files.
Run once to create the database, then again to update it.
"""
import json
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent / "workspace" / "soccer_db"
DB_PATH  = Path(__file__).parent / "workspace" / "soccer_db" / "soccer.db"

LEAGUE_NAMES = {
    "en_premier": "English Premier League",
    "es_laliga":  "Spanish La Liga",
    "de_bundesliga": "German Bundesliga",
    "it_seriea":  "Italian Serie A",
    "fr_ligue1":  "French Ligue 1",
}

def build():
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS matches (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            league   TEXT,
            season   TEXT,
            round    TEXT,
            date     TEXT,
            home     TEXT,
            away     TEXT,
            score    TEXT,
            goals    TEXT
        );
        CREATE TABLE IF NOT EXISTS facts (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            topic   TEXT,
            content TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts
            USING fts5(topic, content, content=facts, content_rowid=id);
        CREATE TABLE IF NOT EXISTS user_facts (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            topic   TEXT,
            content TEXT,
            added   TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS user_facts_fts
            USING fts5(topic, content, content=user_facts, content_rowid=id);
    """)

    # load match data
    c.execute("DELETE FROM matches")
    for json_file in sorted(DATA_DIR.glob("*.json")):
        parts  = json_file.stem.split("_")
        league_key = "_".join(parts[:2])
        season     = parts[-1] if len(parts) > 2 else "unknown"
        league     = LEAGUE_NAMES.get(league_key, league_key)
        try:
            data = json.loads(json_file.read_text())
        except Exception:
            continue
        for match in data.get("matches", []):
            home       = match.get("team1", "")
            away       = match.get("team2", "")
            date       = match.get("date", "")
            round_name = match.get("round", "")
            score_data = match.get("score", {})
            if isinstance(score_data, dict):
                ft    = score_data.get("ft", [])
                score = f"{ft[0]}-{ft[1]}" if ft and len(ft) == 2 else ""
            else:
                score = str(score_data)
            goals_list = match.get("goals", [])
            goals = "; ".join(
                f"{g.get('name','')} {g.get('minute','')}' ({g.get('team','')})"
                for g in goals_list
            ) if goals_list else ""
            c.execute(
                "INSERT INTO matches (league,season,round,date,home,away,score,goals) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (league, season, round_name, date, home, away, score, goals)
            )

    # seed facts table with league info
    c.execute("DELETE FROM facts")
    base_facts = [
        ("Premier League", "The English Premier League has 20 teams. Season runs August to May. Each team plays 38 matches."),
        ("La Liga", "La Liga is the top Spanish football league with 20 teams. Real Madrid and Barcelona are the most decorated clubs."),
        ("Bundesliga", "The Bundesliga is the top German football league with 18 teams. Bayern Munich have won the most titles."),
        ("Serie A", "Serie A is the top Italian football league with 20 teams. Juventus have won the most Scudetti."),
        ("Ligue 1", "Ligue 1 is the top French football league with 18 teams. Paris Saint-Germain have dominated recently."),
        ("Offside rule", "A player is offside if they are nearer to the opponent's goal line than both the ball and the second-to-last defender when the ball is played to them. The goalkeeper usually counts as one defender."),
        ("Yellow card", "A yellow card is a caution. Two yellow cards in one match result in a red card and dismissal."),
        ("Red card", "A red card means immediate dismissal. The player's team continues with ten players."),
        ("Penalty kick", "A penalty kick is taken from 12 yards (11 metres) from goal. Only the goalkeeper may defend it."),
        ("VAR", "VAR (Video Assistant Referee) reviews clear and obvious errors in goals, penalties, red cards, and mistaken identity."),
        ("FIFA World Cup", "The FIFA World Cup is held every four years. Brazil have won it the most times (5). Germany and Italy have won it 4 times each."),
        ("Champions League", "The UEFA Champions League is the top European club competition. Real Madrid have won it the most times (14)."),
        ("Ballon d'Or", "The Ballon d'Or is awarded annually to the world's best footballer. Lionel Messi has won it a record 8 times."),
    ]
    c.executemany("INSERT INTO facts (topic, content) VALUES (?,?)", base_facts)
    c.execute("INSERT INTO facts_fts(facts_fts) VALUES ('rebuild')")

    conn.commit()
    conn.close()

    total = sqlite3.connect(DB_PATH).execute("SELECT COUNT(*) FROM matches").fetchone()[0]
    print(f"Built soccer.db — {total} matches loaded + {len(base_facts)} base facts")


if __name__ == "__main__":
    build()
