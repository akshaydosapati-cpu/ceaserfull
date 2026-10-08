"""Associate conversations with projects.

Revision ID: 20260828_0041
Revises: 20260821_0040
"""

from alembic import op
import sqlalchemy as sa


revision = "20260828_0041"
down_revision = "20260821_0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("project_id", sa.String(), nullable=True))
    op.create_index(op.f("ix_conversations_project_id"), "conversations", ["project_id"], unique=False)
    op.create_foreign_key(
        "fk_conversations_project_id_projects",
        "conversations",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_conversations_project_id_projects", "conversations", type_="foreignkey")
    op.drop_index(op.f("ix_conversations_project_id"), table_name="conversations")
    op.drop_column("conversations", "project_id")
