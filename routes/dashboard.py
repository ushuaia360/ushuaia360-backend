"""
Dashboard stats (admin): KPIs para el home del panel.
Zona horaria: America/Argentina/Ushuaia.

La "variación vs el mes anterior" es la cantidad de altas registradas en el
mes calendario en curso. Si el mes actual no tuvo altas, el delta es 0 (nunca
negativo) y el frontend muestra "0 vs mes anterior".
"""
from quart import Blueprint, jsonify
from db import get_conn
from routes.users import require_admin

dashboard_bp = Blueprint("dashboard", __name__)

# Inicio del mes calendario actual en Ushuaia, como timestamptz.
_CUR_MONTH_START = (
    "(date_trunc('month', now() AT TIME ZONE 'America/Argentina/Ushuaia')) "
    "AT TIME ZONE 'America/Argentina/Ushuaia'"
)


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

        users_total = await conn.fetchval("SELECT COUNT(*) FROM users")
        active_trails = await conn.fetchval(
            "SELECT COUNT(*) FROM trails WHERE status_id = $1", 1
        )
        trails_in_review = await conn.fetchval(
            "SELECT COUNT(*) FROM trails WHERE status_id = $1", 2
        )

        trail_reviews_total = await conn.fetchval(
            "SELECT COUNT(*) FROM trail_reviews"
        )
        place_reviews_total = await conn.fetchval(
            "SELECT COUNT(*) FROM place_reviews"
        )
        comments_total = (trail_reviews_total or 0) + (place_reviews_total or 0)

        users_new_current = await conn.fetchval(
            f"""
            SELECT COUNT(*) FROM users
            WHERE created_at >= {_CUR_MONTH_START}
            """
        )
        tr_curr = await conn.fetchval(
            f"""
            SELECT COUNT(*) FROM trail_reviews
            WHERE created_at >= {_CUR_MONTH_START}
            """
        )
        pr_curr = await conn.fetchval(
            f"""
            SELECT COUNT(*) FROM place_reviews
            WHERE created_at >= {_CUR_MONTH_START}
            """
        )
        comments_new_current = (tr_curr or 0) + (pr_curr or 0)

        users_delta = max(0, int(users_new_current or 0))
        comments_delta = max(0, int(comments_new_current or 0))

        recent_trails_rows = await conn.fetch(
            """
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
            LIMIT 4
            """
        )
        recent_trails = [
            {
                "id": str(r["id"]),
                "slug": r["slug"],
                "name": r["name"],
                "difficulty": r["difficulty"],
                "walks_count": int(r["walks_count"] or 0),
            }
            for r in recent_trails_rows
        ]

        trail_comments_rows = await conn.fetch(
            """
            SELECT t.id, t.slug, t.name, t.difficulty,
                   c.cnt AS comments_count
            FROM trails t
            JOIN (
              SELECT trail_id, COUNT(*) AS cnt
              FROM trail_reviews
              GROUP BY trail_id
            ) c ON c.trail_id = t.id
            ORDER BY c.cnt DESC, t.created_at DESC
            """
        )
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
            "trails_in_review": int(trails_in_review or 0),
            "users_total": int(users_total or 0),
            "users_new_current_month": int(users_new_current or 0),
            "users_new_delta_vs_previous_month": users_delta,
            "comments_total": int(comments_total or 0),
            "comments_new_current_month": int(comments_new_current or 0),
            "comments_new_delta_vs_previous_month": comments_delta,
            "recent_trails": recent_trails,
            "trail_comments": trail_comments,
        }
    )
