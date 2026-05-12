import os
import sqlite3
from datetime import datetime

from .. import MODULE_NAME


class DataManager:
    def __init__(self):
        self.data_dir = os.path.join("data", MODULE_NAME)
        os.makedirs(self.data_dir, exist_ok=True)
        self.db_path = os.path.join(self.data_dir, f"{MODULE_NAME}.db")
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._init_tables()

    def _init_tables(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_state (
                group_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                allow_assist INTEGER NOT NULL DEFAULT 1,
                banned_until INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (group_id, user_id)
            )
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sign_record (
                group_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                year_month TEXT NOT NULL,
                day INTEGER NOT NULL,
                count INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (group_id, user_id, year_month, day)
            )
            """
        )
        self.conn.commit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is not None:
                self.conn.rollback()
            else:
                self.conn.commit()
        finally:
            self.conn.close()
        return False

    @staticmethod
    def _now_text() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def get_user_state(self, group_id: str, user_id: str) -> dict:
        self.cursor.execute(
            """
            SELECT allow_assist, banned_until FROM user_state
            WHERE group_id = ? AND user_id = ?
            """,
            (group_id, user_id),
        )
        row = self.cursor.fetchone()
        if row:
            return {
                "allow_assist": bool(row["allow_assist"]),
                "banned_until": int(row["banned_until"] or 0),
            }
        return {"allow_assist": True, "banned_until": 0}

    def set_allow_assist(self, group_id: str, user_id: str, allow: bool):
        state = self.get_user_state(group_id, user_id)
        self.cursor.execute(
            """
            INSERT OR REPLACE INTO user_state
            (group_id, user_id, allow_assist, banned_until, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (group_id, user_id, 1 if allow else 0, state["banned_until"], self._now_text()),
        )

    def set_banned_until(self, group_id: str, user_id: str, banned_until: int):
        state = self.get_user_state(group_id, user_id)
        self.cursor.execute(
            """
            INSERT OR REPLACE INTO user_state
            (group_id, user_id, allow_assist, banned_until, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (group_id, user_id, 1 if state["allow_assist"] else 0, banned_until, self._now_text()),
        )

    def add_sign(self, group_id: str, user_id: str, year_month: str, day: int, increment: bool = True) -> int:
        now_text = self._now_text()
        if not increment:
            self.cursor.execute(
                """
                INSERT INTO sign_record (group_id, user_id, year_month, day, count, updated_at)
                VALUES (?, ?, ?, ?, 1, ?)
                ON CONFLICT(group_id, user_id, year_month, day) DO NOTHING
                """,
                (group_id, user_id, year_month, day, now_text),
            )
            return self._get_sign_count(group_id, user_id, year_month, day)

        self.cursor.execute(
            """
            INSERT INTO sign_record (group_id, user_id, year_month, day, count, updated_at)
            VALUES (?, ?, ?, ?, 1, ?)
            ON CONFLICT(group_id, user_id, year_month, day)
            DO UPDATE SET count = count + 1, updated_at = excluded.updated_at
            """,
            (group_id, user_id, year_month, day, now_text),
        )
        return self._get_sign_count(group_id, user_id, year_month, day)

    def _get_sign_count(self, group_id: str, user_id: str, year_month: str, day: int) -> int:
        self.cursor.execute(
            """
            SELECT count FROM sign_record
            WHERE group_id = ? AND user_id = ? AND year_month = ? AND day = ?
            """,
            (group_id, user_id, year_month, day),
        )
        row = self.cursor.fetchone()
        return int(row["count"]) if row else 0

    def has_sign(self, group_id: str, user_id: str, year_month: str, day: int) -> bool:
        self.cursor.execute(
            """
            SELECT 1 FROM sign_record
            WHERE group_id = ? AND user_id = ? AND year_month = ? AND day = ?
            """,
            (group_id, user_id, year_month, day),
        )
        return self.cursor.fetchone() is not None

    def get_month_records(self, group_id: str, user_id: str, year_month: str) -> dict[int, int]:
        self.cursor.execute(
            """
            SELECT day, count FROM sign_record
            WHERE group_id = ? AND user_id = ? AND year_month = ?
            ORDER BY day ASC
            """,
            (group_id, user_id, year_month),
        )
        return {int(row["day"]): int(row["count"]) for row in self.cursor.fetchall()}

    def get_rankings(self, group_id: str, year_month: str, limit: int = 10) -> list[dict]:
        self.cursor.execute(
            """
            SELECT user_id, SUM(count) AS total, COUNT(day) AS days
            FROM sign_record
            WHERE group_id = ? AND year_month = ?
            GROUP BY user_id
            ORDER BY total DESC, days DESC, user_id ASC
            LIMIT ?
            """,
            (group_id, year_month, limit),
        )
        return [dict(row) for row in self.cursor.fetchall()]
