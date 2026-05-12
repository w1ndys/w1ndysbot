"""ISCC 擂台赛监控模块数据管理。

持久化以下信息：
- iscc_monitor_target: 被监控的 team id 列表及备注
- iscc_monitor_submit: 每个 team id 已知的通过题目记录，用于判断"本次轮询新出现了哪些题目"
- iscc_monitor_meta: 模块级 k/v 配置（例如 session）
"""

import os
import sqlite3
from datetime import datetime
from typing import Optional

from .. import MODULE_NAME


SESSION_META_KEY = "monitor_session"


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
        # 监控目标
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS iscc_monitor_target (
                team_id TEXT PRIMARY KEY,
                remark TEXT NOT NULL DEFAULT '',
                team_name TEXT NOT NULL DEFAULT '',
                total_score TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        # 已知通过记录，以 (team_id, track, challenge_name) 作为唯一键
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS iscc_monitor_submit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id TEXT NOT NULL,
                track TEXT NOT NULL,
                challenge_name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                score TEXT NOT NULL DEFAULT '',
                solved_at TEXT NOT NULL DEFAULT '',
                recorded_at TEXT NOT NULL,
                UNIQUE(team_id, track, challenge_name)
            )
            """
        )
        # 通用 k/v 元数据
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS iscc_monitor_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT '',
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

    # ==================== 监控目标 ====================

    def add_target(self, team_id: str, remark: str = "") -> bool:
        """添加监控目标，返回是否为新插入。"""
        exists = self.get_target(team_id)
        now = self._now_text()
        if exists:
            self.cursor.execute(
                """
                UPDATE iscc_monitor_target
                SET remark = ?, updated_at = ?
                WHERE team_id = ?
                """,
                (remark, now, team_id),
            )
            return False
        self.cursor.execute(
            """
            INSERT INTO iscc_monitor_target (team_id, remark, team_name, total_score, created_at, updated_at)
            VALUES (?, ?, '', '', ?, ?)
            """,
            (team_id, remark, now, now),
        )
        return True

    def remove_target(self, team_id: str) -> bool:
        self.cursor.execute(
            "DELETE FROM iscc_monitor_target WHERE team_id = ?",
            (team_id,),
        )
        removed = self.cursor.rowcount > 0
        if removed:
            self.cursor.execute(
                "DELETE FROM iscc_monitor_submit WHERE team_id = ?",
                (team_id,),
            )
        return removed

    def get_target(self, team_id: str) -> Optional[dict]:
        self.cursor.execute(
            """
            SELECT team_id, remark, team_name, total_score, created_at, updated_at
            FROM iscc_monitor_target
            WHERE team_id = ?
            """,
            (team_id,),
        )
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def list_targets(self) -> list[dict]:
        self.cursor.execute(
            """
            SELECT team_id, remark, team_name, total_score, created_at, updated_at
            FROM iscc_monitor_target
            ORDER BY created_at ASC
            """
        )
        return [dict(row) for row in self.cursor.fetchall()]

    def update_target_profile(self, team_id: str, team_name: str, total_score: str):
        """更新监控目标的最新队名和总分（用于展示）。"""
        self.cursor.execute(
            """
            UPDATE iscc_monitor_target
            SET team_name = ?, total_score = ?, updated_at = ?
            WHERE team_id = ?
            """,
            (team_name, total_score, self._now_text(), team_id),
        )

    # ==================== 已知提交 ====================

    def get_known_submits(self, team_id: str, track: str) -> dict[str, dict]:
        """返回某 team id 在某赛道的全部已知通过题目，key 为题目名称。"""
        self.cursor.execute(
            """
            SELECT challenge_name, category, score, solved_at, recorded_at
            FROM iscc_monitor_submit
            WHERE team_id = ? AND track = ?
            """,
            (team_id, track),
        )
        result: dict[str, dict] = {}
        for row in self.cursor.fetchall():
            result[row["challenge_name"]] = dict(row)
        return result

    def record_submit(
        self,
        team_id: str,
        track: str,
        challenge_name: str,
        category: str,
        score: str,
        solved_at: str,
    ):
        self.cursor.execute(
            """
            INSERT INTO iscc_monitor_submit
                (team_id, track, challenge_name, category, score, solved_at, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(team_id, track, challenge_name)
            DO UPDATE SET category = excluded.category,
                          score = excluded.score,
                          solved_at = excluded.solved_at
            """,
            (
                team_id,
                track,
                challenge_name,
                category,
                score,
                solved_at,
                self._now_text(),
            ),
        )

    # ==================== 元数据 ====================

    def get_meta(self, key: str) -> str:
        self.cursor.execute(
            "SELECT value FROM iscc_monitor_meta WHERE key = ?",
            (key,),
        )
        row = self.cursor.fetchone()
        return row["value"] if row else ""

    def set_meta(self, key: str, value: str):
        self.cursor.execute(
            """
            INSERT INTO iscc_monitor_meta (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key)
            DO UPDATE SET value = excluded.value,
                          updated_at = excluded.updated_at
            """,
            (key, value, self._now_text()),
        )

    def get_session(self) -> str:
        return self.get_meta(SESSION_META_KEY)

    def set_session(self, session: str):
        self.set_meta(SESSION_META_KEY, session)
