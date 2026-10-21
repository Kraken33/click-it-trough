import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "sessions.db")


class SessionDatabase:
    """
    SQLite persistence layer for TikTok automation sessions and itemized video interactions.
    Thread-safe and uses WAL (Write-Ahead Logging) mode.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration_seconds INTEGER DEFAULT 0,
                    state TEXT NOT NULL,
                    videos_watched INTEGER DEFAULT 0,
                    likes_count INTEGER DEFAULT 0,
                    favorites_count INTEGER DEFAULT 0,
                    comments_viewed INTEGER DEFAULT 0,
                    follows_count INTEGER DEFAULT 0,
                    session_follow_target INTEGER DEFAULT 0,
                    ads_skipped INTEGER DEFAULT 0,
                    lives_skipped INTEGER DEFAULT 0,
                    niche_matched_count INTEGER DEFAULT 0,
                    niche_match_rate REAL DEFAULT 0.0,
                    target_keywords TEXT DEFAULT '[]',
                    exit_reason TEXT DEFAULT ''
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS video_interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    caption TEXT DEFAULT '',
                    matched_keywords TEXT DEFAULT '[]',
                    is_niche INTEGER DEFAULT 0,
                    is_ad INTEGER DEFAULT 0,
                    is_live INTEGER DEFAULT 0,
                    dwell_time_seconds REAL DEFAULT 0.0,
                    action_liked INTEGER DEFAULT 0,
                    action_favorited INTEGER DEFAULT 0,
                    action_comment_viewed INTEGER DEFAULT 0,
                    action_followed INTEGER DEFAULT 0,
                    action_skipped_early INTEGER DEFAULT 0,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                );
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_video_session_id ON video_interactions(session_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON sessions(start_time DESC);")
            conn.commit()

    def create_session(
        self,
        session_id: str,
        start_time: Optional[str] = None,
        target_keywords: Optional[List[str]] = None,
        session_follow_target: int = 0,
    ) -> bool:
        start_time = start_time or datetime.now().isoformat()
        keywords_json = json.dumps(target_keywords or [])
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO sessions (
                        session_id, start_time, state, target_keywords, session_follow_target
                    ) VALUES (?, ?, 'RUNNING', ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        state = 'RUNNING',
                        start_time = excluded.start_time,
                        target_keywords = excluded.target_keywords,
                        session_follow_target = excluded.session_follow_target
                    """,
                    (session_id, start_time, keywords_json, session_follow_target),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error creating session {session_id} in SQLite: {e}")
            return False

    def update_session_progress(
        self,
        session_id: str,
        duration_seconds: int,
        videos_watched: int,
        likes_count: int,
        favorites_count: int,
        comments_viewed: int,
        follows_count: int,
        ads_skipped: int,
        lives_skipped: int,
        niche_matched_count: int,
        state: str = "RUNNING",
    ) -> bool:
        niche_match_rate = round(niche_matched_count / max(videos_watched, 1), 4)
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE sessions SET
                        duration_seconds = ?,
                        videos_watched = ?,
                        likes_count = ?,
                        favorites_count = ?,
                        comments_viewed = ?,
                        follows_count = ?,
                        ads_skipped = ?,
                        lives_skipped = ?,
                        niche_matched_count = ?,
                        niche_match_rate = ?,
                        state = ?
                    WHERE session_id = ?
                    """,
                    (
                        duration_seconds,
                        videos_watched,
                        likes_count,
                        favorites_count,
                        comments_viewed,
                        follows_count,
                        ads_skipped,
                        lives_skipped,
                        niche_matched_count,
                        niche_match_rate,
                        state,
                        session_id,
                    ),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating session progress {session_id}: {e}")
            return False

    def log_video_interaction(
        self,
        session_id: str,
        caption: str = "",
        matched_keywords: Optional[List[str]] = None,
        is_niche: bool = False,
        is_ad: bool = False,
        is_live: bool = False,
        dwell_time_seconds: float = 0.0,
        action_liked: bool = False,
        action_favorited: bool = False,
        action_comment_viewed: bool = False,
        action_followed: bool = False,
        action_skipped_early: bool = False,
        timestamp: Optional[str] = None,
    ) -> bool:
        timestamp = timestamp or datetime.now().isoformat()
        kws_json = json.dumps(matched_keywords or [])
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO video_interactions (
                        session_id, timestamp, caption, matched_keywords,
                        is_niche, is_ad, is_live, dwell_time_seconds,
                        action_liked, action_favorited, action_comment_viewed,
                        action_followed, action_skipped_early
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        timestamp,
                        caption[:1000],
                        kws_json,
                        1 if is_niche else 0,
                        1 if is_ad else 0,
                        1 if is_live else 0,
                        round(dwell_time_seconds, 2),
                        1 if action_liked else 0,
                        1 if action_favorited else 0,
                        1 if action_comment_viewed else 0,
                        1 if action_followed else 0,
                        1 if action_skipped_early else 0,
                    ),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error logging video interaction for session {session_id}: {e}")
            return False

    def finalize_session(
        self,
        session_id: str,
        duration_seconds: int,
        videos_watched: int,
        likes_count: int,
        favorites_count: int,
        comments_viewed: int,
        follows_count: int,
        ads_skipped: int,
        lives_skipped: int,
        niche_matched_count: int,
        state: str = "COMPLETED",
        exit_reason: str = "",
        end_time: Optional[str] = None,
    ) -> bool:
        end_time = end_time or datetime.now().isoformat()
        niche_match_rate = round(niche_matched_count / max(videos_watched, 1), 4)
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE sessions SET
                        end_time = ?,
                        duration_seconds = ?,
                        videos_watched = ?,
                        likes_count = ?,
                        favorites_count = ?,
                        comments_viewed = ?,
                        follows_count = ?,
                        ads_skipped = ?,
                        lives_skipped = ?,
                        niche_matched_count = ?,
                        niche_match_rate = ?,
                        state = ?,
                        exit_reason = ?
                    WHERE session_id = ?
                    """,
                    (
                        end_time,
                        duration_seconds,
                        videos_watched,
                        likes_count,
                        favorites_count,
                        comments_viewed,
                        follows_count,
                        ads_skipped,
                        lives_skipped,
                        niche_matched_count,
                        niche_match_rate,
                        state,
                        exit_reason,
                        session_id,
                    ),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error finalizing session {session_id}: {e}")
            return False

    def get_sessions(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM sessions
                ORDER BY start_time DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            rows = cursor.fetchall()
            results = []
            for row in rows:
                item = dict(row)
                try:
                    item["target_keywords"] = json.loads(item["target_keywords"] or "[]")
                except Exception:
                    item["target_keywords"] = []
                results.append(item)
            return results

    def get_session_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if not row:
                return None
            session_data = dict(row)
            try:
                session_data["target_keywords"] = json.loads(session_data["target_keywords"] or "[]")
            except Exception:
                session_data["target_keywords"] = []

            # Get video interactions
            cursor.execute(
                """
                SELECT * FROM video_interactions
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            )
            video_rows = cursor.fetchall()
            videos = []
            for vr in video_rows:
                v = dict(vr)
                try:
                    v["matched_keywords"] = json.loads(v["matched_keywords"] or "[]")
                except Exception:
                    v["matched_keywords"] = []
                v["is_niche"] = bool(v["is_niche"])
                v["is_ad"] = bool(v["is_ad"])
                v["is_live"] = bool(v["is_live"])
                v["action_liked"] = bool(v["action_liked"])
                v["action_favorited"] = bool(v["action_favorited"])
                v["action_comment_viewed"] = bool(v["action_comment_viewed"])
                v["action_followed"] = bool(v["action_followed"])
                v["action_skipped_early"] = bool(v["action_skipped_early"])
                videos.append(v)

            session_data["videos"] = videos
            return session_data

    def delete_session(self, session_id: str) -> bool:
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM video_interactions WHERE session_id = ?", (session_id,))
                conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            return False

    def clear_all_sessions(self) -> bool:
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM video_interactions")
                conn.execute("DELETE FROM sessions")
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error clearing sessions: {e}")
            return False
