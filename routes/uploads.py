"""
Subida de archivos para la app móvil (p. ej. fotos de reseñas → bucket `reviews`).
Requiere SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en el entorno del servidor.
"""
from __future__ import annotations

import os
import uuid

import httpx
from quart import Blueprint, jsonify, request

from routes.trails import require_auth

uploads_bp = Blueprint("uploads", __name__)

REVIEWS_BUCKET = "reviews"
MAX_BYTES = 6 * 1024 * 1024
ALLOWED_TYPES = frozenset(
    {
        "image/webp",
        "image/jpeg",
        "image/jpg",
        "image/png",
    }
)


def _review_upload_prefix() -> tuple[str | None, str | None]:
    base = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    return base, key


@uploads_bp.route("/uploads/review-image", methods=["POST"])
@require_auth
async def upload_review_image(user_id: str):
    files = await request.files
    f = files.get("file") if files else None
    if f is None or not getattr(f, "filename", None):
        return jsonify({"error": "Campo multipart file requerido"}), 400

    content_type = (f.content_type or "").split(";")[0].strip().lower()
    if content_type == "image/jpg":
        content_type = "image/jpeg"
    if content_type not in ALLOWED_TYPES:
        return jsonify({"error": "Tipo de archivo no permitido"}), 400

    data = f.read()
    if not data:
        return jsonify({"error": "Archivo vacío"}), 400
    if len(data) > MAX_BYTES:
        return jsonify({"error": "Archivo demasiado grande (máx. 6 MB)"}), 400

    base, service_key = _review_upload_prefix()
    if not base or not service_key:
        return jsonify(
            {
                "error": "Almacenamiento no configurado",
                "detail": "Definí SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en el servidor",
            }
        ), 503

    ext = ".webp"
    if content_type == "image/jpeg":
        ext = ".jpg"
    elif content_type == "image/png":
        ext = ".png"

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return jsonify({"error": "Usuario inválido"}), 400

    object_path = f"{uid}/{uuid.uuid4().hex}{ext}"
    upload_url = f"{base}/storage/v1/object/{REVIEWS_BUCKET}/{object_path}"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(
                upload_url,
                content=data,
                headers={
                    "Authorization": f"Bearer {service_key}",
                    "apikey": service_key,
                    "Content-Type": content_type,
                    "x-upsert": "true",
                },
            )
    except httpx.RequestError as e:
        return jsonify({"error": "Error al contactar almacenamiento", "detail": str(e)}), 502

    if res.status_code not in (200, 201):
        detail = res.text[:500] if res.text else ""
        return (
            jsonify(
                {
                    "error": "No se pudo subir la imagen",
                    "status": res.status_code,
                    "detail": detail,
                }
            ),
            502,
        )

    public_url = f"{base}/storage/v1/object/public/{REVIEWS_BUCKET}/{object_path}"
    return jsonify({"url": public_url}), 201
