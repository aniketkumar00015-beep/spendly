import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'expense_tracker.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT    NOT NULL UNIQUE,
                email      TEXT    NOT NULL UNIQUE,
                password   TEXT    NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL REFERENCES users(id),
                title      TEXT    NOT NULL,
                amount     REAL    NOT NULL,
                category   TEXT    NOT NULL,
                date       TEXT    NOT NULL,
                note       TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
    conn.close()


def seed_db():
    conn = get_db()
    with conn:
        conn.execute("""
            INSERT OR IGNORE INTO users (username, email, password)
            VALUES ('demo', 'demo@example.com', 'hashed_placeholder')
        """)
        user = conn.execute("SELECT id FROM users WHERE username = 'demo'").fetchone()
        conn.executemany("""
            INSERT OR IGNORE INTO expenses (user_id, title, amount, category, date, note)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            (user['id'], 'Groceries', 45.50,  'Food',          '2026-04-01', 'Weekly shop'),
            (user['id'], 'Netflix',   15.99,  'Entertainment', '2026-04-02', None),
            (user['id'], 'Bus pass',  30.00,  'Transport',     '2026-04-03', 'Monthly'),
        ])
    conn.close()
