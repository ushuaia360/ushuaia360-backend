from quart import Blueprint, jsonify, request
from db import get_conn
from routes.trails import require_admin

legal_bp = Blueprint("legal", __name__)

VALID_TYPES = {"terms", "privacy"}


@legal_bp.route("/legal/<doc_type>", methods=["GET"])
async def get_legal(doc_type: str):
    """Devuelve el contenido de un documento legal (terms / privacy). Público."""
    if doc_type not in VALID_TYPES:
        return jsonify({"error": "Tipo inválido"}), 404

    async with get_conn() as conn:
        row = await conn.fetchrow(
            "SELECT type, content, updated_at FROM legal_documents WHERE type = $1",
            doc_type,
        )

    if not row:
        return jsonify({"type": doc_type, "content": "", "updated_at": None}), 200

    return jsonify({
        "type": row["type"],
        "content": row["content"],
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }), 200


@legal_bp.route("/legal/<doc_type>", methods=["PUT"])
@require_admin
async def update_legal(doc_type: str, user_id: str):
    """Actualiza el contenido de un documento legal. Solo admin."""
    if doc_type not in VALID_TYPES:
        return jsonify({"error": "Tipo inválido"}), 404

    data = await request.get_json()
    if not data or "content" not in data:
        return jsonify({"error": "El campo 'content' es requerido"}), 400

    content = str(data["content"])

    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO legal_documents (type, content, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (type) DO UPDATE
                SET content = EXCLUDED.content, updated_at = NOW()
            RETURNING type, content, updated_at
            """,
            doc_type,
            content,
        )

    return jsonify({
        "message": "Documento actualizado",
        "document": {
            "type": row["type"],
            "content": row["content"],
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        },
    }), 200
