"""
Warstwa bazy danych — SQLite, przechowuje historię sygnałów cenowych
i wysłanych alertów.
"""

import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "prices.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS price_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material TEXT NOT NULL,
    material_detail TEXT,
    change_type TEXT,
    amount REAL,
    unit TEXT,
    currency TEXT,
    region TEXT,
    effective_date TEXT,
    announcement_date TEXT,
    source_company TEXT,
    source_url TEXT,
    confidence TEXT,
    summary_pl TEXT,
    extracted_on TEXT NOT NULL,
    UNIQUE(material, source_company, effective_date, amount)
);

CREATE TABLE IF NOT EXISTS alerts_sent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER,
    alert_message TEXT,
    sent_on TEXT NOT NULL,
    channel TEXT,
    FOREIGN KEY (signal_id) REFERENCES price_signals(id)
);
"""


@contextmanager
def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)


def insert_signal(signal, source_url: str | None = None) -> int | None:
    """Zapisuje sygnał cenowy. Zwraca id nowego wiersza albo None jeśli duplikat."""
    d = asdict(signal)
    d["source_url"] = source_url
    with get_connection() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO price_signals
                (material, material_detail, change_type, amount, unit, currency,
                 region, effective_date, announcement_date, source_company,
                 source_url, confidence, summary_pl, extracted_on)
                VALUES (:material, :material_detail, :change_type, :amount, :unit,
                        :currency, :region, :effective_date, :announcement_date,
                        :source_company, :source_url, :confidence, :summary_pl,
                        :extracted_on)""",
                d,
            )
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None  # ten sygnał już istnieje w bazie


def get_all_signals(material: str | None = None) -> list[dict]:
    with get_connection() as conn:
        if material:
            rows = conn.execute(
                "SELECT * FROM price_signals WHERE material = ? ORDER BY announcement_date DESC",
                (material,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM price_signals ORDER BY announcement_date DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def log_alert(signal_id: int, message: str, channel: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO alerts_sent (signal_id, alert_message, sent_on, channel) "
            "VALUES (?, ?, date('now'), ?)",
            (signal_id, message, channel),
        )


if __name__ == "__main__":
    init_db()
    print(f"Baza zainicjalizowana: {DB_PATH}")
