"""
Configuración de estado de la app: mantenimiento y actualización requerida.

GET /api/v1/app/config?platform=ios&build=3
→ responde qué carteles debe mostrar la app según la configuración de la tabla app_config.
"""
from quart import Blueprint, jsonify, request
from db import get_conn

app_config_bp = Blueprint("app_config", __name__)


def _build_is_outdated(current_build: int | None, min_build: int | None) -> bool:
    """True si el build actual existe y es menor al mínimo requerido."""
    if current_build is None or min_build is None:
        return False
    return current_build < min_build


@app_config_bp.route("/app/config", methods=["GET"])
async def get_app_config():
    """
    Devuelve el estado de mantenimiento y actualización requerida.

    Query params:
      platform  – "ios" | "android"   (obligatorio para required_update)
      build     – número entero del build instalado
    """
    platform = (request.args.get("platform") or "").lower().strip()
    build_raw = request.args.get("build")
    try:
        current_build = int(build_raw) if build_raw else None
    except (ValueError, TypeError):
        current_build = None

    async with get_conn() as conn:
        rows = await conn.fetch(
            """
            SELECT type, is_active, title, message,
                   ios_min_build, android_min_build
            FROM app_config
            """
        )

    configs = {r["type"]: r for r in rows}

    # ── Mantenimiento ─────────────────────────────────────────────────────────
    maint_row = configs.get("maintenance")
    maintenance = {
        "active": bool(maint_row["is_active"]) if maint_row else False,
        "title": maint_row["title"] if maint_row else "",
        "message": maint_row["message"] if maint_row else "",
    }

    # ── Actualización requerida ───────────────────────────────────────────────
    upd_row = configs.get("required_update")
    if upd_row and upd_row["is_active"]:
        if platform == "ios":
            min_build = upd_row["ios_min_build"]
        elif platform == "android":
            min_build = upd_row["android_min_build"]
        else:
            min_build = None

        update_active = _build_is_outdated(current_build, min_build)
    else:
        update_active = False

    required_update = {
        "active": update_active,
        "title": upd_row["title"] if upd_row else "",
        "message": upd_row["message"] if upd_row else "",
    }

    return jsonify({
        "maintenance": maintenance,
        "required_update": required_update,
    })
