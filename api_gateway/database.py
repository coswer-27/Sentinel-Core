import aiosqlite
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "sentinel_logs.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scan_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                url TEXT,
                trust_score INTEGER,
                label TEXT,
                reason TEXT,
                timestamp TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

async def log_scan(content: str, url: str, score: int, label: str, reason: str, ts: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO scan_logs (content, url, trust_score, label, reason, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (content, url, score, label, reason, ts)
        )
        await db.commit()