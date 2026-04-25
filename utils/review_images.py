"""
Validación de URLs de fotos de reseñas (subidas al bucket `reviews` en Supabase Storage).
"""
from __future__ import annotations

import os
from typing import Any, List

MAX_REVIEW_PHOTOS = 5
MAX_URL_LEN = 2048


def _public_reviews_prefix() -> str | None:
    base = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    if not base:
        return None
    return f"{base}/storage/v1/object/public/reviews/"


def parse_and_validate_review_image_urls(raw: Any) -> List[str]:
    """
    Acepta lista opcional de URLs públicas del bucket reviews.
    Devuelve lista (puede estar vacía). Lanza ValueError si el payload es inválido.
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("image_urls debe ser una lista")
    prefix = _public_reviews_prefix()
    if not prefix:
        raise ValueError("Servidor sin SUPABASE_URL: no se pueden validar fotos de reseña")

    out: List[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise ValueError("Cada elemento de image_urls debe ser texto")
        u = item.strip()
        if not u:
            continue
        if len(u) > MAX_URL_LEN:
            raise ValueError("URL de imagen demasiado larga")
        if not u.startswith(prefix):
            raise ValueError("Las fotos deben provenir del almacenamiento de reseñas")
        out.append(u)
        if len(out) > MAX_REVIEW_PHOTOS:
            raise ValueError(f"Máximo {MAX_REVIEW_PHOTOS} fotos por reseña")

    return out
