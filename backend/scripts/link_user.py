"""Link an existing Supabase login to a platform user (P0-5).

    cd backend
    python scripts/link_user.py --email someone@example.com

Looks the email up in Supabase Auth with the service key, then calls
provision_user() - the same code POST /users/me runs - so the user row and
learner profile are created exactly as a real first login would create them.
Running it again for the same email is safe.

Needs SUPABASE_URL, SUPABASE_SECRET_KEY and DATABASE_URL in backend/.env.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND / ".env")

from app.core.db import SessionLocal, close_db  # noqa: E402
from app.services.user_service import provision_user  # noqa: E402

PAGE_SIZE = 1000


def supabase_user_id(email: str) -> str:
    """Return the Supabase auth id for email, searching every page of users."""
    base = os.environ["SUPABASE_URL"].rstrip("/")
    secret = os.environ["SUPABASE_SECRET_KEY"]
    wanted = email.strip().lower()

    page = 1
    while True:
        response = httpx.get(
            f"{base}/auth/v1/admin/users",
            headers={"apikey": secret, "Authorization": f"Bearer {secret}"},
            params={"page": page, "per_page": PAGE_SIZE},
            timeout=30,
        )
        response.raise_for_status()
        users = response.json().get("users", [])
        for user in users:
            if (user.get("email") or "").lower() == wanted:
                return user["id"]
        if len(users) < PAGE_SIZE:
            raise SystemExit(f"No Supabase login found for {email}")
        page += 1


async def link(email: str) -> dict:
    auth_id = supabase_user_id(email)
    try:
        async with SessionLocal() as db:
            row = await provision_user(db, auth_id, email=email.strip())
    finally:
        # Close pooled connections before the event loop ends, so the script
        # exits without "Event loop is closed" noise.
        await close_db()
    print(f"platform id={row['id']} auth id={row['external_auth_id']} email={row['email']}")
    return row


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    asyncio.run(link(args.email))
