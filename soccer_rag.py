#!/usr/bin/env python3
"""
soccer_rag.py — Search the soccer database and return relevant facts
to inject into the cottage door's soccer persona system prompt.
"""
import sqlite3
import re
from pathlib import Path

DB_PATH = Path(__file__).parent / "workspace" / "soccer_db" / "soccer.db"


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def search_matches(query: str, limit: int = 8) -> list[dict]:
    """Find matches involving teams or players mentioned in the query."""
    conn  = _conn()
    words = [w for w in re.findall(r"[a-zA-Z]{3,}", query) if len(w) > 2]
    if not words:
        return []
    results = []
    seen = set()
    for word in words:
        rows = conn.execute(
            "SELECT league, season, date, home, away, score, goals "
            "FROM matches WHERE home LIKE ? OR away LIKE ? "
            "ORDER BY date DESC LIMIT ?",
            (f"%{word}%", f"%{word}%", limit)
        ).fetchall()
        for r in rows:
            key = (r["home"], r["away"], r["date"])
            if key not in seen:
                seen.add(key)
                results.append(dict(r))
    conn.close()
    return results[:limit]


def search_facts(query: str, limit: int = 5) -> list[str]:
    """Search both seeded facts and user-added facts."""
    conn    = _conn()
    results = []
    try:
        rows = conn.execute(
            "SELECT content FROM facts WHERE topic LIKE ? OR content LIKE ? LIMIT ?",
            (f"%{query}%", f"%{query}%", limit)
        ).fetchall()
        results += [r["content"] for r in rows]
        rows = conn.execute(
            "SELECT content FROM user_facts WHERE topic LIKE ? OR content LIKE ? LIMIT ?",
            (f"%{query}%", f"%{query}%", limit)
        ).fetchall()
        results += [r["content"] for r in rows]
    except Exception:
        pass
    conn.close()
    return results[:limit]


def build_context(query: str) -> str:
    """Build a factual context block to inject into the system prompt."""
    facts   = search_facts(query)
    matches = search_matches(query)

    lines = []
    if facts:
        lines.append("VERIFIED SOCCER FACTS:")
        lines.extend(f"- {f}" for f in facts)

    if matches:
        lines.append("MATCH RESULTS FROM DATABASE:")
        for m in matches:
            score = f" ({m['score']})" if m['score'] else " (result unknown)"
            goals = f" — Goals: {m['goals']}" if m['goals'] else ""
            lines.append(
                f"- {m['league']} {m['season']}, {m['date']}: "
                f"{m['home']} vs {m['away']}{score}{goals}"
            )

    if not lines:
        return ""

    return (
        "\n\nFACTUAL SOCCER KNOWLEDGE BASE (use these facts accurately — "
        "if asked something not covered here, say you are not certain rather than guessing):\n"
        + "\n".join(lines)
    )


def add_user_fact(topic: str, content: str) -> None:
    """Add a user-supplied fact to the database."""
    from datetime import datetime
    conn = _conn()
    conn.execute(
        "INSERT INTO user_facts (topic, content, added) VALUES (?,?,?)",
        (topic, content, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_user_facts() -> list[dict]:
    """Return all user-added facts."""
    conn  = _conn()
    rows  = conn.execute(
        "SELECT id, topic, content, added FROM user_facts ORDER BY added DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_user_fact(fact_id: int) -> None:
    conn = _conn()
    conn.execute("DELETE FROM user_facts WHERE id=?", (fact_id,))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    # quick test
    ctx = build_context("Manchester City Premier League")
    print(ctx[:800])
