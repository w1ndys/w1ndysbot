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
            CREATE TABLE IF NOT EXISTS iscc_account (
                user_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                session TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
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

    def get_account(self, user_id: str) -> dict | None:
        self.cursor.execute(
            """
            SELECT user_id, username, password, session FROM iscc_account
            WHERE user_id = ?
            """,
            (user_id,),
        )
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def get_all_accounts(self) -> list[dict]:
        self.cursor.execute(
            """
            SELECT user_id, username, password, session FROM iscc_account
            ORDER BY user_id ASC
            """
        )
        return [dict(row) for row in self.cursor.fetchall()]

    def save_account(self, user_id: str, username: str, password: str, session: str):
        self.cursor.execute(
            """
            INSERT INTO iscc_account (user_id, username, password, session, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET username = excluded.username,
                          password = excluded.password,
                          session = excluded.session,
                          updated_at = excluded.updated_at
            """,
            (user_id, username, password, session, self._now_text()),
        )

    def save_session(self, user_id: str, session: str):
        self.cursor.execute(
            """
            UPDATE iscc_account SET session = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (session, self._now_text(), user_id),
        )
