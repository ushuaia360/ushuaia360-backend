"""
Script para crear un usuario administrador.
Uso: python scripts/create_admin.py [--email EMAIL] [--password PASSWORD] [--name NOMBRE]
"""
import asyncio
import argparse
import secrets
import string
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import asyncpg
from passlib.hash import bcrypt


def generate_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        has_upper = any(c.isupper() for c in pwd)
        has_lower = any(c.islower() for c in pwd)
        has_digit = any(c.isdigit() for c in pwd)
        has_special = any(c in "!@#$%^&*" for c in pwd)
        if has_upper and has_lower and has_digit and has_special:
            return pwd


async def create_admin(email: str, password: str, full_name: str):
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL no está configurado en .env")
        sys.exit(1)

    password_hash = bcrypt.hash(password)

    conn = await asyncpg.connect(dsn=database_url, statement_cache_size=0)
    try:
        existing = await conn.fetchrow("SELECT id, is_admin FROM users WHERE email = $1", email.lower())
        if existing:
            if existing["is_admin"]:
                print(f"El usuario {email} ya existe y ya es admin.")
                return
            await conn.execute(
                "UPDATE users SET is_admin = TRUE, email_verified = TRUE WHERE id = $1",
                existing["id"],
            )
            print(f"Usuario {email} actualizado a admin.")
            return

        user_id = await conn.fetchval(
            """
            INSERT INTO users (email, full_name, password_hash, language, is_admin, email_verified)
            VALUES ($1, $2, $3, 'es', TRUE, TRUE)
            RETURNING id
            """,
            email.lower(),
            full_name,
            password_hash,
        )
        print(f"\nAdmin creado exitosamente:")
        print(f"  ID:       {user_id}")
        print(f"  Email:    {email}")
        print(f"  Nombre:   {full_name}")
        print(f"  Password: {password}")
        print(f"\nGuarda la password en un lugar seguro, no se puede recuperar.\n")
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crear usuario admin")
    parser.add_argument("--email", default="admin@ushuaia360.com")
    parser.add_argument("--name", default="Admin Ushuaia360")
    parser.add_argument("--password", default=None, help="Si no se pasa, se genera una segura automáticamente")
    args = parser.parse_args()

    password = args.password or generate_password()
    asyncio.run(create_admin(args.email, password, args.name))
