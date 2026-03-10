"""
Users routes - Creación y gestión de usuarios
"""
from quart import Blueprint, jsonify
from db import get_conn

users_bp = Blueprint("users", __name__)

@users_bp.route("/users", methods=["GET"])
async def get_all_users():
    """Get all users"""
    async with get_conn() as conn:
        users = await conn.fetch("SELECT * FROM users")
    users_list = []
    for u in users:
        user_dict = dict(u)
        user_dict["id"] = str(user_dict["id"])
        users_list.append(user_dict)
    return jsonify({"users": users_list})