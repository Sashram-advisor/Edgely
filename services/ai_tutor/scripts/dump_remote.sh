#!/usr/bin/env bash
# Read-only dump of the hosted Supabase DB (schema + data) for local testing.
set -euo pipefail
cd "$(dirname "$0")/.."

DBURL=$(python3 scripts/_db_url.py)

npx supabase db dump --db-url "$DBURL" -f supabase/migrations/20261029000000_remote_schema.sql
npx supabase db dump --db-url "$DBURL" --data-only -f supabase/seed.sql
echo "Done."
