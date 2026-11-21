"""Create users and tasks."""

from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(6), server_default="member", nullable=False),
        sa.CheckConstraint("role IN ('member', 'admin')", name="user_role"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.String(5000)),
        sa.Column("status", sa.String(11), server_default="todo", nullable=False),
        sa.Column("priority", sa.String(6), server_default="medium", nullable=False),
        sa.Column("due_date", sa.Date()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('todo', 'in_progress', 'done')", name="task_status"),
        sa.CheckConstraint("priority IN ('low', 'medium', 'high')", name="task_priority"),
    )
    op.create_index("ix_tasks_created_id", "tasks", ["created_at", "id"])
    op.create_index("ix_tasks_owner_created_id", "tasks", ["owner_id", "created_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_tasks_owner_created_id", table_name="tasks")
    op.drop_index("ix_tasks_created_id", table_name="tasks")
    op.drop_table("tasks")
    op.drop_table("users")
