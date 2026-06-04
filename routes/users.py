"""
Users routes - Creación y gestión de usuarios
"""
from quart import Blueprint, request, jsonify
from db import get_conn
from routes.auth import decode_jwt_token
from passlib.hash import bcrypt
import uuid

users_bp = Blueprint("users", __name__)


def require_admin():
    """Helper function to check if user is admin"""
    token = request.cookies.get("token")
    if not token:
        authz = request.headers.get("Authorization", "")
        if authz.startswith("Bearer "):
            token = authz.split(" ", 1)[1].strip()
    
    if not token:
        return None, jsonify({"error": "No autenticado"}), 401

    try:
        payload = decode_jwt_token(token)
        user_id = payload["user_id"]
    except ValueError as e:
        return None, jsonify({"error": str(e)}), 401

    return user_id, None, None


@users_bp.route("/users", methods=["GET"])
async def get_all_users():
    """Lista usuarios (solo admin). Query: limit, offset, search, role, suspended, premium."""
    user_id, error_response, status_code = require_admin()
    if error_response:
        return error_response, status_code

    raw_limit = request.args.get("limit", default=20, type=int)
    raw_offset = request.args.get("offset", default=0, type=int)
    limit = min(max(raw_limit or 20, 1), 100)
    offset = max(raw_offset or 0, 0)

    search = (request.args.get("search") or request.args.get("q") or "").strip()
    role = (request.args.get("role") or "").strip().lower()
    suspended = request.args.get("suspended")
    premium = request.args.get("premium")

    async with get_conn() as conn:
        admin_row = await conn.fetchrow(
            "SELECT is_admin FROM users WHERE id = $1", user_id
        )
        if not admin_row or not admin_row["is_admin"]:
            return jsonify({"error": "No autorizado"}), 403

        conditions = []
        params = []
        n = 0

        if search:
            p1 = n + 1
            p2 = n + 2
            patt = f"%{search}%"
            conditions.append(
                f"(u.full_name ILIKE ${p1} OR u.email ILIKE ${p2})"
            )
            params.extend([patt, patt])
            n = p2

        if role == "admin":
            n += 1
            conditions.append(f"u.is_admin = ${n}")
            params.append(True)
        elif role == "user":
            n += 1
            conditions.append(f"COALESCE(u.is_admin, FALSE) = ${n}")
            params.append(False)

        if suspended is not None and str(suspended).strip() != "":
            sv = str(suspended).strip().lower()
            if sv in ("true", "1", "yes"):
                n += 1
                conditions.append(f"COALESCE(u.is_suspended, FALSE) = ${n}")
                params.append(True)
            elif sv in ("false", "0", "no"):
                n += 1
                conditions.append(f"COALESCE(u.is_suspended, FALSE) = ${n}")
                params.append(False)

        if premium is not None and str(premium).strip() != "":
            pv = str(premium).strip().lower()
            if pv in ("true", "1", "yes"):
                n += 1
                conditions.append(f"COALESCE(u.is_premium, FALSE) = ${n}")
                params.append(True)
            elif pv in ("false", "0", "no"):
                n += 1
                conditions.append(f"COALESCE(u.is_premium, FALSE) = ${n}")
                params.append(False)

        where_sql = ""
        if conditions:
            where_sql = "WHERE " + " AND ".join(conditions)

        count_query = f"SELECT COUNT(*) FROM users u {where_sql}"
        total = await conn.fetchval(count_query, *params)

        n += 1
        limit_placeholder = n
        n += 1
        offset_placeholder = n
        list_params = list(params) + [limit, offset]

        users = await conn.fetch(
            f"""
            SELECT id, email, full_name, avatar_url, language, is_admin,
                   is_premium, premium_until, email_verified, is_suspended, created_at
            FROM users u
            {where_sql}
            ORDER BY u.created_at DESC
            LIMIT ${limit_placeholder} OFFSET ${offset_placeholder}
            """,
            *list_params,
        )

    users_list = []
    for u in users:
        user_dict = dict(u)
        user_dict["id"] = str(user_dict["id"])
        if user_dict.get("premium_until"):
            user_dict["premium_until"] = user_dict["premium_until"].isoformat()
        users_list.append(user_dict)

    return jsonify({
        "users": users_list,
        "total": int(total or 0),
        "limit": limit,
        "offset": offset,
    })


@users_bp.route("/users/<user_id>/suspend", methods=["PUT"])
async def suspend_user(user_id: str):
    """Suspend or unsuspend a user (admin only)"""
    admin_user_id, error_response, status_code = require_admin()
    if error_response:
        return error_response, status_code

    # Check if user is admin
    async with get_conn() as conn:
        admin_user = await conn.fetchrow("SELECT is_admin FROM users WHERE id = $1", admin_user_id)
        if not admin_user or not admin_user["is_admin"]:
            return jsonify({"error": "No autorizado"}), 403

        # Get request data
        data = await request.get_json()
        if not data:
            return jsonify({"error": "Datos requeridos"}), 400

        is_suspended = data.get("is_suspended")
        if is_suspended is None:
            return jsonify({"error": "El campo is_suspended es requerido"}), 400

        # Validate user_id
        try:
            user_uuid = uuid.UUID(user_id)
        except ValueError:
            return jsonify({"error": "ID de usuario inválido"}), 400

        # Check if user exists
        user = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_uuid)
        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        # Update user suspension status
        await conn.execute(
            "UPDATE users SET is_suspended = $1 WHERE id = $2",
            bool(is_suspended),
            user_uuid
        )

        # Get updated user
        updated_user = await conn.fetchrow(
            "SELECT id, email, full_name, avatar_url, language, is_admin, is_premium, email_verified, is_suspended, created_at FROM users WHERE id = $1",
            user_uuid
        )

    # Convert UUID to string for JSON serialization
    user_dict = dict(updated_user)
    user_dict["id"] = str(user_dict["id"])
    
    return jsonify({
        "message": "Usuario suspendido" if is_suspended else "Usuario reactivado",
        "user": user_dict
    })


@users_bp.route("/users/admin", methods=["POST"])
async def create_admin_user():
    """Create a new admin user (admin only)"""
    admin_user_id, error_response, status_code = require_admin()
    if error_response:
        return error_response, status_code

    # Check if user is admin
    async with get_conn() as conn:
        admin_user = await conn.fetchrow("SELECT is_admin FROM users WHERE id = $1", admin_user_id)
        if not admin_user or not admin_user["is_admin"]:
            return jsonify({"error": "No autorizado"}), 403

        # Get request data
        data = await request.get_json()
        if not data:
            return jsonify({"error": "Datos requeridos"}), 400

        email = data.get("email")
        full_name = data.get("full_name")
        password = data.get("password")

        if not email or not full_name or not password:
            return jsonify({"error": "Email, nombre completo y contraseña son obligatorios"}), 400

        if len(password) < 8:
            return jsonify({"error": "La contraseña debe tener al menos 8 caracteres"}), 400

        # Check if user already exists
        existing_user = await conn.fetchrow(
            "SELECT * FROM users WHERE email = $1",
            email.lower()
        )
        if existing_user:
            return jsonify({"error": "El email ya está en uso"}), 400

        # Hash password
        hashed_password = bcrypt.hash(password)
        
        # Create admin user
        await conn.execute(
            """
            INSERT INTO users (email, full_name, password_hash, language, email_verified, is_admin)
            VALUES ($1, $2, $3, $4, TRUE, TRUE)
            """,
            email.lower(), full_name, hashed_password, "es"
        )

        # Get created user
        user = await conn.fetchrow(
            "SELECT id, email, full_name, avatar_url, language, is_admin, is_premium, email_verified, is_suspended, created_at FROM users WHERE email = $1",
            email.lower()
        )

    # Convert UUID to string for JSON serialization
    user_dict = dict(user)
    user_dict["id"] = str(user_dict["id"])
    
    return jsonify({
        "message": "Usuario admin creado exitosamente",
        "user": user_dict
    }), 201
