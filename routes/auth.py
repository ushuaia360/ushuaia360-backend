"""
Authentication routes
"""
from quart import Blueprint, request, jsonify, current_app
from passlib.hash import bcrypt
from db import get_conn
import jwt
from jwt import PyJWKClient
import datetime
from quart.wrappers.response import Response
from quart.utils import run_sync
from werkzeug.security import check_password_hash, generate_password_hash
from typing import Optional
from services.email_service import send_verification_email, send_password_reset_email

APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
APPLE_TEAM_ID = "V3VDNCJULN"
APPLE_BUNDLE_ID = "com.ushuaia360.ios"

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUER = "https://accounts.google.com"

auth_bp = Blueprint("auth", __name__)


def verify_password(stored_hash: Optional[str], plain: str) -> bool:
    """Verify password against stored hash"""
    stored = (stored_hash or "").strip()
    if not stored:
        return False
    try:
        if is_bcrypt_hash(stored):
            return bcrypt.verify(plain, stored)
        return check_password_hash(stored, plain)
    except ValueError:
        return False


def is_bcrypt_hash(h: str) -> bool:
    """Check if hash is bcrypt format"""
    h = (h or "").strip()
    return h.startswith(("$2a$", "$2b$", "$2y$")) and len(h) >= 60


def generate_jwt_token(user_id: str, expiration_seconds: int = None) -> str:
    """Generate JWT token for user (user_id is UUID string)"""
    if expiration_seconds is None:
        expiration_seconds = current_app.config.get('JWT_EXPIRATION_SECONDS', 60 * 60 * 24 * 14)
    
    payload = {
        "user_id": str(user_id),  # Ensure UUID is string
        "exp": datetime.datetime.utcnow() + datetime.timedelta(seconds=expiration_seconds)
    }
    return jwt.encode(payload, current_app.config.get('JWT_SECRET'), algorithm="HS256")


def decode_jwt_token(token: str) -> dict:
    """Decode and verify JWT token"""
    try:
        payload = jwt.decode(
            token,
            current_app.config.get('JWT_SECRET'),
            algorithms=["HS256"],
            leeway=10
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expirado")
    except jwt.InvalidTokenError:
        raise ValueError("Token inválido")


# Registro
@auth_bp.route("/register", methods=["POST"])
async def register():
    """Register a new user"""
    data = await request.get_json()
    email = data.get("email")
    full_name = data.get("full_name")
    password = data.get("password")
    confirm_password = data.get("confirm_password")
    language = data.get("language", "es")

    if not email or not full_name or not password or not confirm_password:
        return jsonify({"error": "Email, nombre completo y contraseña son obligatorios"}), 400

    if password != confirm_password:
        return jsonify({"error": "Las contraseñas no coinciden"}), 400

    if len(password) < 8:
        return jsonify({"error": "La contraseña debe tener al menos 8 caracteres"}), 400

    async with get_conn() as conn:
        # Check if user already exists
        existing_user = await conn.fetchrow(
            "SELECT * FROM users WHERE email = $1",
            email.lower()
        )
        if existing_user:
            return jsonify({"error": "El email ya está en uso"}), 400

        # Hash password
        hashed_password = bcrypt.hash(password)
        
        # Create user first
        await conn.execute(
            """
            INSERT INTO users (email, full_name, password_hash, language, email_verified)
            VALUES ($1, $2, $3, $4, FALSE)
            """,
            email.lower(), full_name, hashed_password, language
        )

        # Get created user
        user = await conn.fetchrow("SELECT * FROM users WHERE email = $1", email.lower())
        
        # Generate verification token with user_id
        verification_token = generate_jwt_token(str(user["id"]), 60 * 60 * 24)  # 24 hours
        verification_expires = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        
        # Update user with verification token
        await conn.execute(
            """
            UPDATE users 
            SET verification_token = $1, verification_token_expires = $2
            WHERE id = $3
            """,
            verification_token, verification_expires, user["id"]
        )

    # Send verification email
    try:
        await send_verification_email(email, verification_token)
    except Exception as e:
        # Log error but don't fail registration
        current_app.logger.error(f"Error sending verification email: {str(e)}")

    return jsonify({
        "message": "Registro exitoso. Por favor, verificá tu email para activar tu cuenta.",
        "user": {
            "id": str(user["id"]),
            "email": user["email"],
            "full_name": user["full_name"],
            "language": user.get("language", "es")
        }
    }), 201


# Login Web (with cookies) - Solo para admin
@auth_bp.route("/login", methods=["POST"])
async def login():
    """Login for web admin panel (sets cookie) - Solo usuarios admin"""
    data = await request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email y contraseña requeridos"}), 400

    async with get_conn() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE email = $1",
            email.lower()
        )
        if not user:
            return jsonify({"error": "Credenciales inválidas"}), 401

        if not user["password_hash"]:
            return jsonify({"error": "Credenciales inválidas"}), 401

        if not verify_password(user["password_hash"], password):
            return jsonify({"error": "Credenciales inválidas"}), 401

        if not user.get("email_verified", False):
            return jsonify({"error": "Cuenta no verificada, revisá tu email"}), 403

        # Verificar que el usuario sea admin
        if not user.get("is_admin", False):
            return jsonify({"error": "No tenés permisos de administrador"}), 403

    # Generate token
    token = generate_jwt_token(str(user["id"]))

    # Create response with user data
    response: Response = await run_sync(jsonify)({
        "message": "Login exitoso",
        "user": {
            "id": str(user["id"]),
            "email": user["email"],
            "full_name": user["full_name"],
            "avatar_url": user.get("avatar_url"),
            "language": user.get("language", "es"),
            "is_admin": user.get("is_admin", False),
            "is_premium": user.get("is_premium", False)
        }
    })

    # Set cookie
    is_secure = not current_app.config.get('DEBUG', False)
    response.set_cookie(
        "token",
        token,
        httponly=True,
        samesite="Lax",
        secure=is_secure,
        path="/",
        max_age=60 * 60 * 24 * 14  # 14 days
    )
    return response


# Login Mobile App (returns token in response)
@auth_bp.route("/login-app", methods=["POST"])
async def login_app():
    """Login for mobile app (returns token in response)"""
    data = await request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email y contraseña requeridos"}), 400

    async with get_conn() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE email = $1",
            email.lower()
        )
        if not user:
            return jsonify({"error": "Credenciales inválidas"}), 401

        if not user["password_hash"]:
            return jsonify({"error": "Credenciales inválidas"}), 401

        if not verify_password(user["password_hash"], password):
            return jsonify({"error": "Credenciales inválidas"}), 401

        if not user.get("email_verified", False):
            return jsonify({"error": "Cuenta no verificada, revisá tu email"}), 403

    # Generate token
    token = generate_jwt_token(str(user["id"]))

    return jsonify({
        "message": "Login exitoso",
        "token": token,
        "user": {
            "id": str(user["id"]),
            "email": user["email"],
            "full_name": user["full_name"],
            "avatar_url": user.get("avatar_url"),
            "language": user.get("language", "es"),
            "is_admin": user.get("is_admin", False),
            "is_premium": user.get("is_premium", False)
        }
    })


# Get current user (Web - from cookies)
@auth_bp.route("/me", methods=["GET"])
async def me():
    """Get current user from cookie (web)"""
    token = request.cookies.get("token")
    if not token:
        return jsonify({"error": "No autenticado"}), 401

    try:
        payload = decode_jwt_token(token)
        user_id = payload["user_id"]
    except ValueError as e:
        return jsonify({"error": str(e)}), 401

    async with get_conn() as conn:
        user = await conn.fetchrow(
            "SELECT id, email, full_name, avatar_url, language, is_admin, is_premium, email_verified, created_at FROM users WHERE id = $1",
            user_id
        )

        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

    # Convert UUID to string for JSON serialization
    user_dict = dict(user)
    user_dict["id"] = str(user_dict["id"])
    return jsonify({"user": user_dict})


# Get current user (Mobile App - from Authorization header or cookie)
@auth_bp.route("/me-app", methods=["GET"])
async def me_app():
    """Get current user from Authorization header or cookie (mobile app)"""
    token = request.cookies.get("token")
    
    if not token:
        authz = request.headers.get("Authorization", "")
        if authz.startswith("Bearer "):
            token = authz.split(" ", 1)[1].strip()

    if not token:
        return jsonify({"error": "No autenticado"}), 401

    try:
        payload = decode_jwt_token(token)
        user_id = payload["user_id"]
    except ValueError as e:
        return jsonify({"error": str(e)}), 401

    async with get_conn() as conn:
        user = await conn.fetchrow(
            "SELECT id, email, full_name, avatar_url, language, is_admin, is_premium, email_verified, created_at FROM users WHERE id = $1",
            user_id
        )

        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

    # Convert UUID to string for JSON serialization
    user_dict = dict(user)
    user_dict["id"] = str(user_dict["id"])
    return jsonify({"user": user_dict})


# Get all users
@auth_bp.route("/users", methods=["GET"])
async def get_users():
    """Get all users (admin only)"""
    # Check authentication
    token = request.cookies.get("token")
    if not token:
        authz = request.headers.get("Authorization", "")
        if authz.startswith("Bearer "):
            token = authz.split(" ", 1)[1].strip()
    
    if not token:
        return jsonify({"error": "No autenticado"}), 401

    try:
        payload = decode_jwt_token(token)
        user_id = payload["user_id"]
    except ValueError as e:
        return jsonify({"error": str(e)}), 401

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


# Verify email
@auth_bp.route("/verify-email", methods=["POST"])
async def verify_email():
    """Verify user email with token"""
    data = await request.get_json()
    token = data.get("token")

    if not token:
        return jsonify({"error": "Token requerido"}), 400

    try:
        payload = decode_jwt_token(token)
        user_id = payload["user_id"]
    except ValueError as e:
        return jsonify({"error": str(e)}), 401

    async with get_conn() as conn:
        # Find user by id and verify token matches
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE id = $1",
            user_id
        )

        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        # Verify token matches
        if user["verification_token"] != token:
            return jsonify({"error": "Token inválido"}), 400

        # Check if token expired
        if user["verification_token_expires"] and user["verification_token_expires"] < datetime.datetime.utcnow():
            return jsonify({"error": "Token expirado"}), 400

        # Verify user
        await conn.execute(
            """
            UPDATE users 
            SET email_verified = TRUE, verification_token = NULL, verification_token_expires = NULL
            WHERE id = $1
            """,
            user["id"]
        )

    return jsonify({"message": "Email verificado exitosamente"})


# Resend verification email
@auth_bp.route("/resend-verification", methods=["POST"])
async def resend_verification():
    """Resend verification email"""
    data = await request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email requerido"}), 400

    async with get_conn() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE email = $1", email.lower())

        if not user:
            # Don't reveal if user exists
            return jsonify({"message": "Si el email existe, se envió un nuevo enlace de verificación"}), 200

        if user["email_verified"]:
            return jsonify({"error": "El email ya está verificado"}), 400

        # Generate new verification token with user_id
        verification_token = generate_jwt_token(str(user["id"]), 60 * 60 * 24)  # 24 hours
        verification_expires = datetime.datetime.utcnow() + datetime.timedelta(hours=24)

        await conn.execute(
            """
            UPDATE users 
            SET verification_token = $1, verification_token_expires = $2
            WHERE id = $3
            """,
            verification_token, verification_expires, user["id"]
        )

    # Send verification email
    try:
        await send_verification_email(email, verification_token)
    except Exception as e:
        current_app.logger.error(f"Error sending verification email: {str(e)}")
        return jsonify({"error": "Error al enviar el email"}), 500

    return jsonify({"message": "Email de verificación enviado"})


# Change password
@auth_bp.route("/change-password", methods=["POST"])
async def change_password():
    """Change password (requires authentication or reset token)"""
    data = await request.get_json()
    old_password = data.get("old_password")
    new_password = data.get("new_password")
    reset_token = data.get("reset_token")  # For password reset flow

    if not new_password:
        return jsonify({"error": "Nueva contraseña requerida"}), 400

    if len(new_password) < 8:
        return jsonify({"error": "La contraseña debe tener al menos 8 caracteres"}), 400

    # If reset_token provided, it's a password reset
    if reset_token:
        try:
            payload = decode_jwt_token(reset_token)
            user_id = payload["user_id"]
            async with get_conn() as conn:
                user = await conn.fetchrow(
                    "SELECT * FROM users WHERE id = $1",
                    user_id
                )
                if not user:
                    return jsonify({"error": "Usuario no encontrado"}), 404

                # Verify token matches
                if user.get("password_reset_token") != reset_token:
                    return jsonify({"error": "Token inválido"}), 400

                # Check if token expired
                if user.get("password_reset_expires") and user["password_reset_expires"] < datetime.datetime.utcnow():
                    return jsonify({"error": "Token expirado"}), 400

                # Update password
                hashed_password = bcrypt.hash(new_password)
                await conn.execute(
                    """
                    UPDATE users 
                    SET password_hash = $1, password_reset_token = NULL, password_reset_expires = NULL
                    WHERE id = $2
                    """,
                    hashed_password, user["id"]
                )

            return jsonify({"message": "Contraseña actualizada exitosamente"})
        except ValueError as e:
            return jsonify({"error": str(e)}), 401

    # Otherwise, require authentication and old password
    token = request.cookies.get("token")
    if not token:
        authz = request.headers.get("Authorization", "")
        if authz.startswith("Bearer "):
            token = authz.split(" ", 1)[1].strip()

    if not token:
        return jsonify({"error": "No autenticado"}), 401

    if not old_password:
        return jsonify({"error": "Contraseña actual requerida"}), 400

    try:
        payload = decode_jwt_token(token)
        user_id = payload["user_id"]
    except ValueError as e:
        return jsonify({"error": str(e)}), 401

    async with get_conn() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

        if not user:
            return jsonify({"error": "Usuario no encontrado"}), 404

        if not verify_password(user["password_hash"], old_password):
            return jsonify({"error": "Contraseña actual incorrecta"}), 401

        # Update password
        hashed_password = bcrypt.hash(new_password)
        await conn.execute(
            "UPDATE users SET password_hash = $1 WHERE id = $2",
            hashed_password, user_id
        )

    return jsonify({"message": "Contraseña actualizada exitosamente"})


# Request password reset
@auth_bp.route("/forgot-password", methods=["POST"])
async def forgot_password():
    """Request password reset email"""
    data = await request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"error": "Email requerido"}), 400

    async with get_conn() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE email = $1", email.lower())

        if not user:
            return jsonify({"message": "Si el email existe, se envió un enlace para restablecer la contraseña"}), 200

        reset_token = generate_jwt_token(str(user["id"]), 60 * 60)  # 1 hour
        reset_expires = datetime.datetime.utcnow() + datetime.timedelta(hours=1)

        await conn.execute(
            """
            UPDATE users 
            SET password_reset_token = $1, password_reset_expires = $2
            WHERE id = $3
            """,
            reset_token, reset_expires, user["id"]
        )

    # Send reset email
    try:
        await send_password_reset_email(email, reset_token)
    except Exception as e:
        current_app.logger.error(f"Error sending password reset email: {str(e)}")
        return jsonify({"error": "Error al enviar el email"}), 500

    return jsonify({"message": "Si el email existe, se envió un enlace para restablecer la contraseña"})


# Apple Sign-In (Mobile)
@auth_bp.route("/apple-app", methods=["POST"])
async def apple_login_app():
    """Login/register with Apple Sign-In for mobile app"""
    data = await request.get_json()
    identity_token = data.get("identity_token")
    full_name = data.get("full_name")

    if not identity_token:
        return jsonify({"error": "identity_token requerido"}), 400

    try:
        jwks_client = PyJWKClient(APPLE_JWKS_URL)
        signing_key = jwks_client.get_signing_key_from_jwt(identity_token)
        claims = jwt.decode(
            identity_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=APPLE_BUNDLE_ID,
        )
        apple_user_id = claims["sub"]
        email = claims.get("email")
    except Exception as e:
        current_app.logger.error(f"Apple token validation failed: {e}")
        return jsonify({"error": "Token de Apple inválido"}), 401

    async with get_conn() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE apple_user_id = $1", apple_user_id
        )

        if not user and email:
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE email = $1", email.lower()
            )
            if user:
                await conn.execute(
                    "UPDATE users SET apple_user_id = $1 WHERE id = $2",
                    apple_user_id, user["id"]
                )

        if not user:
            name = full_name or (email.split("@")[0] if email else "Usuario Apple")
            user_email = (email or f"{apple_user_id}@privaterelay.appleid.com").lower()
            await conn.execute(
                """
                INSERT INTO users (email, full_name, apple_user_id, email_verified, language)
                VALUES ($1, $2, $3, TRUE, 'es')
                """,
                user_email, name, apple_user_id
            )
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE apple_user_id = $1", apple_user_id
            )

    token = generate_jwt_token(str(user["id"]))
    return jsonify({
        "token": token,
        "user": {
            "id": str(user["id"]),
            "email": user["email"],
            "full_name": user["full_name"],
            "avatar_url": user.get("avatar_url"),
            "language": user.get("language", "es"),
            "is_admin": user.get("is_admin", False),
            "is_premium": user.get("is_premium", False),
        }
    })


# Google Sign-In (Mobile)
@auth_bp.route("/google-app", methods=["POST"])
async def google_login_app():
    """Login/register with Google Sign-In for mobile app"""
    data = await request.get_json()
    id_token = data.get("id_token")

    if not id_token:
        return jsonify({"error": "id_token requerido"}), 400

    google_web_client_id = current_app.config.get("GOOGLE_WEB_CLIENT_ID")
    google_ios_client_id = current_app.config.get("GOOGLE_IOS_CLIENT_ID")
    if not google_web_client_id:
        current_app.logger.error("GOOGLE_WEB_CLIENT_ID no configurado")
        return jsonify({"error": "Google Sign-In no configurado"}), 500

    # Aceptar tanto el web client ID como el iOS client ID como audiencias válidas
    valid_audiences = [a for a in [google_web_client_id, google_ios_client_id] if a]

    try:
        jwks_client = PyJWKClient(GOOGLE_JWKS_URL)
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=valid_audiences,
            issuer=GOOGLE_ISSUER,
        )
        google_user_id = claims["sub"]
        email = claims.get("email")
        full_name = claims.get("name")
        avatar_url = claims.get("picture")
    except Exception as e:
        current_app.logger.error(f"Google token validation failed: {e}")
        return jsonify({"error": "Token de Google inválido"}), 401

    async with get_conn() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE google_user_id = $1", google_user_id
        )

        if not user and email:
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE email = $1", email.lower()
            )
            if user:
                await conn.execute(
                    "UPDATE users SET google_user_id = $1 WHERE id = $2",
                    google_user_id, user["id"]
                )

        if not user:
            name = full_name or (email.split("@")[0] if email else "Usuario Google")
            user_email = (email or f"{google_user_id}@google.com").lower()
            await conn.execute(
                """
                INSERT INTO users (email, full_name, google_user_id, avatar_url, email_verified, language)
                VALUES ($1, $2, $3, $4, TRUE, 'es')
                """,
                user_email, name, google_user_id, avatar_url
            )
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE google_user_id = $1", google_user_id
            )

    token = generate_jwt_token(str(user["id"]))
    return jsonify({
        "token": token,
        "user": {
            "id": str(user["id"]),
            "email": user["email"],
            "full_name": user["full_name"],
            "avatar_url": user.get("avatar_url"),
            "language": user.get("language", "es"),
            "is_admin": user.get("is_admin", False),
            "is_premium": user.get("is_premium", False),
        }
    })


# Logout
@auth_bp.route("/logout", methods=["POST"])
async def logout():
    """Logout user (clear cookie)"""
    response: Response = await run_sync(jsonify)({"message": "Logout exitoso"})
    
    is_secure = not current_app.config.get('DEBUG', False)
    response.delete_cookie(
        "token",
        path="/",
        httponly=True,
        samesite="Lax",
        secure=is_secure
    )
    return response
