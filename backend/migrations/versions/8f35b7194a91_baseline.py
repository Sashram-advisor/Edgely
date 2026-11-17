from pathlib import Path
from typing import Sequence, Union

from alembic import op
from psycopg import ClientCursor

revision: str = "8f35b7194a91"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SQL_DIR = Path(__file__).resolve().parents[2] / "app" / "database" / "migrations"


def _run_sql_file(filename: str) -> None:
    sql = (SQL_DIR / filename).read_text()
    lines = [
        line
        for line in sql.splitlines(keepends=True)
        if line.strip().upper() not in {"BEGIN;", "COMMIT;"}
    ]
    connection = op.get_bind().connection.driver_connection
    with ClientCursor(connection) as cursor:
        cursor.execute("".join(lines))


def upgrade() -> None:
    _run_sql_file("Database_inital")
    _run_sql_file("20261102000100_ai_tutor_pgvector.sql")


def downgrade() -> None:
    pass