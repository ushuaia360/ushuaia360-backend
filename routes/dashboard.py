"""
Dashboard stats (admin): KPIs para el home del panel.
"""
import asyncio

from quart import Blueprint, jsonify

from db import get_conn
from routes.users import require_admin

dashboard_bp = Blueprint("dashboard", __name__)

_AGG_STATS_SQL = """
SELECT
    (SELECT COUNT(*)::bigint FROM users) AS users_total,
    (SELECT COUNT(*)::bigint FROM trails WHERE status_id = 1) AS active_trails,
    (SELECT COUNT(*)::bigint FROM trail_reviews) AS trail_reviews_total,
    (SELECT COUNT(*)::bigint FROM place_reviews) AS place_reviews_total,
    (SELECT COUNT(*)::bigint FROM user_trail_history WHERE completed = TRUE) AS trail_completions_total
"""

_RECENT_TRAILS_SQL = """
SELECT t.id, t.slug, t.name, t.difficulty,
       c.cnt AS walks_count
FROM trails t
JOIN (
  SELECT trail_id, COUNT(*) AS cnt
  FROM user_trail_history
  WHERE completed = TRUE
  GROUP BY trail_id
) c ON c.trail_id = t.id
ORDER BY c.cnt DESC, t.created_at DESC
LIMIT 3
"""

_TRAIL_COMMENTS_SQL = """
SELECT t.id, t.slug, t.name, t.difficulty,
       c.cnt AS comments_count
FROM trails t
JOIN (
  SELECT trail_id, COUNT(*) AS cnt
  FROM trail_reviews
  GROUP BY trail_id
) c ON c.trail_id = t.id
ORDER BY c.cnt DESC, t.created_at DESC
LIMIT $1::int
"""


async def _fetch_recent_trails():
    async with get_conn() as conn:
        return await conn.fetch(_RECENT_TRAILS_SQL)


async def _fetch_trail_comments_leaderboard(limit: int):
    async with get_conn() as conn:
        return await conn.fetch(_TRAIL_COMMENTS_SQL, limit)


TRAIL_COMMENT_LEADERBOARD_LIMIT = 3


@dashboard_bp.route("/admin/dashboard-stats", methods=["GET"])
async def dashboard_stats():
    user_id, error_response, status_code = require_admin()
    if error_response:
        return error_response, status_code

    async with get_conn() as conn:
        admin = await conn.fetchrow(
            "SELECT is_admin FROM users WHERE id = $1", user_id
        )
        if not admin or not admin["is_admin"]:
            return jsonify({"error": "No autorizado"}), 403

        agg = await conn.fetchrow(_AGG_STATS_SQL)

    users_total = agg["users_total"]
    active_trails = agg["active_trails"]
    trail_reviews_total = agg["trail_reviews_total"]
    place_reviews_total = agg["place_reviews_total"]
    comments_total = (trail_reviews_total or 0) + (place_reviews_total or 0)
    trail_completions_total = agg["trail_completions_total"]

    recent_rows, trail_comments_rows = await asyncio.gather(
        _fetch_recent_trails(),
        _fetch_trail_comments_leaderboard(TRAIL_COMMENT_LEADERBOARD_LIMIT),
    )

    recent_trails = [
        {
            "id": str(r["id"]),
            "slug": r["slug"],
            "name": r["name"],
            "difficulty": r["difficulty"],
            "walks_count": int(r["walks_count"] or 0),
        }
        for r in recent_rows
    ]

    trail_comments = [
        {
            "id": str(r["id"]),
            "slug": r["slug"],
            "name": r["name"],
            "difficulty": r["difficulty"],
            "comments_count": int(r["comments_count"] or 0),
        }
        for r in trail_comments_rows
    ]

    return jsonify(
        {
            "active_trails": int(active_trails or 0),
            "users_total": int(users_total or 0),
            "comments_total": int(comments_total or 0),
            "trail_completions_total": int(trail_completions_total or 0),
            "recent_trails": recent_trails,
            "trail_comments": trail_comments,
        }
    )
