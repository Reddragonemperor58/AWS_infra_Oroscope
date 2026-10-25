"""problem_reports table

Revision ID: fb50dc5a8587
Revises: 0db257443e1a
"""
from alembic import op
import sqlalchemy as sa

revision = "fb50dc5a8587"
down_revision = "0db257443e1a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "problem_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("doctor_id", sa.String(36), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_problem_reports_doctor_id", "problem_reports", ["doctor_id"])


def downgrade() -> None:
    op.drop_index("ix_problem_reports_doctor_id", table_name="problem_reports")
    op.drop_table("problem_reports")
