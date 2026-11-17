"""hot path indexes

Revision ID: 4e24c9c49854
Revises: 8f35b7194a91
Create Date: 2026-11-16 11:43:11.165311

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e24c9c49854'
down_revision: Union[str, Sequence[str], None] = '8f35b7194a91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("messages_conversation_id_idx", "messages", ["conversation_id"])
    op.create_index("conversations_user_id_idx", "conversations", ["user_id"])
    op.create_index("message_citations_chunk_id_idx", "message_citations", ["chunk_id"])
    op.create_index("documents_certification_status_idx", "documents", ["certification_id", "status"])


def downgrade() -> None:
    op.drop_index("documents_certification_status_idx", table_name="documents")
    op.drop_index("message_citations_chunk_id_idx", table_name="message_citations")
    op.drop_index("conversations_user_id_idx", table_name="conversations")
    op.drop_index("messages_conversation_id_idx", table_name="messages")