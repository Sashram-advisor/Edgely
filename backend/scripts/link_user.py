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

from app.core.db import SessionLocal
from app.services.user_service import provision_user


def supabase_user_id(email: str) -> str:
    base = os.environ["SUPABASE_URL"].rstrip("/")
    secret = os.environ["SUPABASE_SECRET_KEY"]
    response = httpx.get(
        f"{base}/auth/v1/admin/users",
        headers={"apikey": secret, "Authorization": f"Bearer {secret}"},
        params={"page": 1, "per_page": 1000},
        timeout=30,
    )
    response.raise_for_status()
    wanted = email.strip().lower()
    for user in response.json().get("users", []):
        if (user.get("email") or "").lower() == wanted:
            return user["id"]
    raise SystemExit(f"No Supabase login found for {email}")


async def link(email: str) -> None:
    auth_id = supabase_user_id(email)
    async with SessionLocal() as db:
        row = await provision_user(db, auth_id, email=email)
    print(f"platform id={row['id']} auth id={row['external_auth_id']} email={row['email']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    asyncio.run(link(args.email))