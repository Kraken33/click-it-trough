import json
import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from .session_db import SessionDatabase

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """
    Computes lifetime statistics, engagement ratios, trend timelines,
    and the 4-Factor TikTok Account Warming Health Score.
    """

    def __init__(self, db: SessionDatabase):
        self.db = db

    def get_summary_metrics(self) -> Dict[str, Any]:
        """
        Calculates lifetime metrics and today's activity usage.
        """
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Lifetime aggregation
            cursor.execute("""
                SELECT
                    COUNT(*) as total_sessions,
                    COALESCE(SUM(duration_seconds), 0) as total_duration_seconds,
                    COALESCE(SUM(videos_watched), 0) as total_videos_watched,
                    COALESCE(SUM(likes_count), 0) as total_likes,
                    COALESCE(SUM(favorites_count), 0) as total_favorites,
                    COALESCE(SUM(comments_viewed), 0) as total_comments,
                    COALESCE(SUM(follows_count), 0) as total_follows,
                    COALESCE(SUM(ads_skipped), 0) as total_ads_skipped,
                    COALESCE(SUM(lives_skipped), 0) as total_lives_skipped,
                    COALESCE(SUM(niche_matched_count), 0) as total_niche_matched
                FROM sessions
            """)
            lifetime_row = dict(cursor.fetchone())

            # Today's activity
            today_str = datetime.now().strftime("%Y-%m-%d")
            cursor.execute(
                """
                SELECT
                    COUNT(*) as today_sessions,
                    COALESCE(SUM(duration_seconds), 0) as today_duration_seconds,
                    COALESCE(SUM(videos_watched), 0) as today_videos_watched,
                    COALESCE(SUM(likes_count), 0) as today_likes,
                    COALESCE(SUM(favorites_count), 0) as today_favorites,
                    COALESCE(SUM(follows_count), 0) as today_follows
                FROM sessions
                WHERE start_time LIKE ?
                """,
                (f"{today_str}%",),
            )
            today_row = dict(cursor.fetchone())

            # Dwell time comparison (niche vs non-niche)
            cursor.execute("""
                SELECT
                    COALESCE(AVG(CASE WHEN is_niche = 1 THEN dwell_time_seconds END), 0.0) as avg_niche_dwell,
                    COALESCE(AVG(CASE WHEN is_niche = 0 AND is_ad = 0 AND is_live = 0 THEN dwell_time_seconds END), 0.0) as avg_generic_dwell
                FROM video_interactions
            """)
            dwell_row = dict(cursor.fetchone())

        total_videos = lifetime_row["total_videos_watched"]
        like_rate = round((lifetime_row["total_likes"] / max(total_videos, 1)) * 100, 2)
        fav_rate = round((lifetime_row["total_favorites"] / max(total_videos, 1)) * 100, 2)
        follow_rate = round((lifetime_row["total_follows"] / max(total_videos, 1)) * 100, 2)
        niche_rate = round((lifetime_row["total_niche_matched"] / max(total_videos, 1)) * 100, 2)

        health_score_data = self.calculate_warming_health_score()

        return {
            "lifetime": {
                **lifetime_row,
                "like_rate_percent": like_rate,
                "favorite_rate_percent": fav_rate,
                "follow_rate_percent": follow_rate,
                "niche_match_rate_percent": niche_rate,
                "avg_niche_dwell_seconds": round(dwell_row["avg_niche_dwell"], 1),
                "avg_generic_dwell_seconds": round(dwell_row["avg_generic_dwell"], 1),
            },
            "today": today_row,
            "warming_health_score": health_score_data,
        }

    def calculate_warming_health_score(self) -> Dict[str, Any]:
        """
        Computes the weighted 4-factor Account Warming Health Score (0 - 100):
        1. Niche Alignment (40%): Rolling niche match % over recent sessions.
        2. Engagement Balance (25%): Organic like rate target (8% - 18%).
        3. Dwell Differentiation (20%): Niche dwell vs generic dwell ratio (target 1.8x - 3.0x).
        4. Session Stability (15%): Completed clean sessions vs halted/crashed over last 7 days.
        """
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Recent sessions (last 10) for Niche Alignment & Engagement
            cursor.execute("""
                SELECT videos_watched, likes_count, niche_matched_count, state
                FROM sessions
                ORDER BY start_time DESC
                LIMIT 10
            """)
            recent_sessions = cursor.fetchall()

            # 2. Dwell times
            cursor.execute("""
                SELECT
                    COALESCE(AVG(CASE WHEN is_niche = 1 THEN dwell_time_seconds END), 0.0) as niche_dwell,
                    COALESCE(AVG(CASE WHEN is_niche = 0 AND is_ad = 0 AND is_live = 0 THEN dwell_time_seconds END), 0.0) as generic_dwell
                FROM video_interactions
                WHERE session_id IN (
                    SELECT session_id FROM sessions ORDER BY start_time DESC LIMIT 10
                )
            """)
            dwell_data = dict(cursor.fetchone())

            # 3. 7-day stability
            seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total_count,
                    COALESCE(SUM(CASE WHEN state IN ('COMPLETED', 'STOPPED') THEN 1 ELSE 0 END), 0) as clean_count,
                    COALESCE(SUM(CASE WHEN state = 'CAPTCHA_HALTED' THEN 1 ELSE 0 END), 0) as captcha_count
                FROM sessions
                WHERE start_time >= ?
                """,
                (seven_days_ago,),
            )
            stability_data = dict(cursor.fetchone())

        if not recent_sessions:
            return {
                "score": 0,
                "rating": "No Data Yet",
                "factors": {
                    "niche_alignment": {"score": 0, "weight": 40, "details": "No sessions recorded"},
                    "engagement_balance": {"score": 0, "weight": 25, "details": "No sessions recorded"},
                    "dwell_differentiation": {"score": 0, "weight": 20, "details": "No sessions recorded"},
                    "session_stability": {"score": 0, "weight": 15, "details": "No sessions recorded"},
                },
            }

        # Factor 1: Niche Alignment (40%)
        total_recent_videos = sum(r["videos_watched"] for r in recent_sessions)
        total_recent_niche = sum(r["niche_matched_count"] for r in recent_sessions)
        recent_niche_pct = (total_recent_niche / max(total_recent_videos, 1)) * 100
        # Benchmark: >= 60% niche is 100 points, 30% is 50 points, <10% is 10 points
        s_niche = min(100.0, max(0.0, (recent_niche_pct / 60.0) * 100.0))

        # Factor 2: Engagement Balance (25%)
        total_recent_likes = sum(r["likes_count"] for r in recent_sessions)
        recent_like_pct = (total_recent_likes / max(total_recent_videos, 1)) * 100
        # Organic target is 8% to 18%
        if 8.0 <= recent_like_pct <= 18.0:
            s_engagement = 100.0
        elif 4.0 <= recent_like_pct < 8.0:
            s_engagement = (recent_like_pct / 8.0) * 100.0
        elif 18.0 < recent_like_pct <= 30.0:
            # Over-aggressive penalty
            s_engagement = max(40.0, 100.0 - (recent_like_pct - 18.0) * 5.0)
        elif recent_like_pct > 30.0:
            s_engagement = max(10.0, 40.0 - (recent_like_pct - 30.0) * 3.0)
        else:
            s_engagement = max(10.0, recent_like_pct * 10.0)

        # Factor 3: Dwell Differentiation (20%)
        n_dwell = dwell_data["niche_dwell"]
        g_dwell = dwell_data["generic_dwell"]
        if g_dwell > 0.5:
            dwell_ratio = n_dwell / g_dwell
            # Target ratio: 1.8x - 3.0x
            if dwell_ratio >= 1.8:
                s_dwell = min(100.0, 70.0 + (dwell_ratio - 1.8) * 25.0)
            else:
                s_dwell = max(20.0, (dwell_ratio / 1.8) * 70.0)
        else:
            s_dwell = 50.0
            dwell_ratio = 1.0

        # Factor 4: Session Stability (15%)
        st_total = stability_data["total_count"]
        st_clean = stability_data["clean_count"]
        if st_total > 0:
            s_stability = (st_clean / st_total) * 100.0
            if stability_data["captcha_count"] > 0:
                s_stability = max(10.0, s_stability - (stability_data["captcha_count"] * 25.0))
        else:
            s_stability = 80.0

        total_score = round(
            (0.40 * s_niche)
            + (0.25 * s_engagement)
            + (0.20 * s_dwell)
            + (0.15 * s_stability)
        )
        total_score = max(0, min(100, total_score))

        if total_score >= 85:
            rating = "Optimized & Mature"
        elif total_score >= 70:
            rating = "Healthy Warming"
        elif total_score >= 50:
            rating = "Developing Algorithm"
        else:
            rating = "Initial / Needs Seeding"

        return {
            "score": total_score,
            "rating": rating,
            "factors": {
                "niche_alignment": {
                    "score": round(s_niche, 1),
                    "weight": 40,
                    "value_percent": round(recent_niche_pct, 1),
                    "details": f"{round(recent_niche_pct, 1)}% FYP niche alignment over last {len(recent_sessions)} sessions",
                },
                "engagement_balance": {
                    "score": round(s_engagement, 1),
                    "weight": 25,
                    "value_percent": round(recent_like_pct, 1),
                    "details": f"{round(recent_like_pct, 1)}% like rate (Target: 8%-18% organic human window)",
                },
                "dwell_differentiation": {
                    "score": round(s_dwell, 1),
                    "weight": 20,
                    "ratio": round(dwell_ratio, 2),
                    "details": f"{round(dwell_ratio, 2)}x dwell time on niche ({round(n_dwell, 1)}s) vs generic ({round(g_dwell, 1)}s)",
                },
                "session_stability": {
                    "score": round(s_stability, 1),
                    "weight": 15,
                    "clean_rate_percent": round(s_stability, 1),
                    "details": f"{stability_data['clean_count']}/{max(stability_data['total_count'], 1)} clean sessions without safety halts (past 7 days)",
                },
            },
        }

    def get_trends(self, limit: int = 20) -> Dict[str, Any]:
        """
        Returns time series progression of sessions (niche match rate, like rate, duration)
        and frequency of top 10 discovered keywords.
        """
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Timeline of recent sessions
            cursor.execute(
                """
                SELECT
                    session_id,
                    start_time,
                    duration_seconds,
                    videos_watched,
                    likes_count,
                    favorites_count,
                    follows_count,
                    niche_matched_count,
                    niche_match_rate,
                    state
                FROM sessions
                ORDER BY start_time DESC
                LIMIT ?
                """,
                (limit,),
            )
            sessions = [dict(r) for r in cursor.fetchall()]
            sessions.reverse()  # Chronological order for plotting

            # Keywords frequency from video_interactions
            cursor.execute("""
                SELECT matched_keywords FROM video_interactions
                WHERE is_niche = 1 AND matched_keywords != '[]'
                ORDER BY id DESC
                LIMIT 500
            """)
            rows = cursor.fetchall()

        keyword_counter = Counter()
        for r in rows:
            try:
                kws = json.loads(r["matched_keywords"] or "[]")
                for kw in kws:
                    clean_kw = kw.strip().lower()
                    if clean_kw:
                        keyword_counter[clean_kw] += 1
            except Exception:
                pass

        top_keywords = [
            {"keyword": kw, "count": count}
            for kw, count in keyword_counter.most_common(12)
        ]

        return {
            "session_progression": sessions,
            "top_keywords": top_keywords,
        }
