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
    """Get all users (admin only)"""
    user_id, error_response, status_code = require_admin()
    if error_response:
        return error_response, status_code

    # Check if user is admin
    async with get_conn() as conn:
        user = await conn.fetchrow("SELECT is_admin FROM users WHERE id = $1", user_id)
        if not user or not user["is_admin"]:
            return jsonify({"error": "No autorizado"}), 403

        # Get all users
        users = await conn.fetch(
            "SELECT id, email, full_name, avatar_url, language, is_admin, is_premium, email_verified, is_suspended, created_at FROM users ORDER BY created_at DESC"
        )

    # Convert UUIDs to strings for JSON serialization
    users_list = []
    for u in users:
        user_dict = dict(u)
        user_dict["id"] = str(user_dict["id"])
        users_list.append(user_dict)
    
    return jsonify({"users": users_list})


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
