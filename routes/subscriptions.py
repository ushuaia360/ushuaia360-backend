"""
RevenueCat webhook — sincroniza el estado de suscripción con la DB.

RevenueCat envía un POST con:
  Authorization: <REVENUECAT_WEBHOOK_SECRET>
  Body JSON: { "event": { "type": "...", "app_user_id": "...", ... } }

Eventos que nos interesan:
  INITIAL_PURCHASE / RENEWAL / UNCANCELLATION  → activar premium
  CANCELLATION / EXPIRATION / BILLING_ISSUE    → desactivar premium
"""
import hashlib
import hmac
import logging
from datetime import datetime, timezone

from db import get_conn
from quart import Blueprint, current_app, jsonify, request

subscriptions_bp = Blueprint("subscriptions", __name__)
logger = logging.getLogger(__name__)

ACTIVATE_EVENTS = {"INITIAL_PURCHASE", "RENEWAL", "UNCANCELLATION", "TRANSFER"}
DEACTIVATE_EVENTS = {"CANCELLATION", "EXPIRATION", "BILLING_ISSUE", "SUBSCRIBER_ALIAS"}


def _verify_secret(incoming: str, expected: str) -> bool:
    """Comparación segura contra timing attacks."""
    if not expected:
        return True  # Sin secreto configurado: aceptar en dev
    return hmac.compare_digest(incoming.encode(), expected.encode())


@subscriptions_bp.route("/webhooks/revenuecat", methods=["POST"])
async def revenuecat_webhook():
    secret = current_app.config.get("REVENUECAT_WEBHOOK_SECRET", "")
    incoming = request.headers.get("Authorization", "")

    if not _verify_secret(incoming, secret):
        logger.warning("RevenueCat webhook: secreto inválido")
        return jsonify({"error": "Unauthorized"}), 401

    payload = await request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "Payload vacío"}), 400

    event = payload.get("event", {})
    event_type: str = event.get("type", "")
    app_user_id: str = event.get("app_user_id", "")
    expires_at_ms: int | None = event.get("expiration_at_ms")
    store: str = event.get("store", "")  # APP_STORE | PLAY_STORE
    transaction_id: str = event.get("transaction_id", "") or event.get("id", "")

    if not app_user_id:
        return jsonify({"error": "app_user_id faltante"}), 400

    logger.info("RevenueCat event=%s user=%s store=%s", event_type, app_user_id, store)

    expires_dt: datetime | None = None
    if expires_at_ms:
        expires_dt = datetime.fromtimestamp(expires_at_ms / 1000, tz=timezone.utc)

    async with get_conn() as conn:
        user = await conn.fetchrow(
            "SELECT id FROM users WHERE id = $1::uuid", app_user_id
        )
        if not user:
            # RevenueCat puede llamar antes de que el user exista; ignorar silenciosamente
            logger.info("RevenueCat webhook: usuario %s no encontrado, ignorando", app_user_id)
            return jsonify({"ok": True}), 200

        if event_type in ACTIVATE_EVENTS:
            await conn.execute(
                """
                UPDATE users
                SET is_premium = TRUE,
                    premium_until = $1,
                    updated_at = NOW()
                WHERE id = $2::uuid
                """,
                expires_dt,
                app_user_id,
            )
            provider = "apple" if store == "APP_STORE" else "google"
            await conn.execute(
                """
                INSERT INTO subscriptions (user_id, provider, external_id, started_at, expires_at)
                VALUES ($1::uuid, $2, $3, NOW(), $4)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    provider    = EXCLUDED.provider,
                    external_id = EXCLUDED.external_id,
                    expires_at  = EXCLUDED.expires_at,
                    updated_at  = NOW()
                """,
                app_user_id,
                provider,
                transaction_id,
                expires_dt,
            )

        elif event_type in DEACTIVATE_EVENTS:
            await conn.execute(
                """
                UPDATE users
                SET is_premium = FALSE,
                    premium_until = NULL,
                    updated_at = NOW()
                WHERE id = $1::uuid
                """,
                app_user_id,
            )

    return jsonify({"ok": True}), 200
