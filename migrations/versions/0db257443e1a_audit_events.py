"""audit events

Revision ID: 0db257443e1a
Revises: 5e12d1392533
Create Date: 2026-10-24 23:58:37.696508

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0db257443e1a'
down_revision: Union[str, Sequence[str], None] = '5e12d1392533'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("doctor_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("resource_type", sa.String(20), nullable=True),
        sa.Column("resource_id", sa.String(36), nullable=True),
        sa.Column("patient_id", sa.String(36), nullable=True),
        sa.Column("detail", sa.String(255), nullable=True),
        sa.Column("source_ip", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_audit_events_doctor_created", "audit_events", ["doctor_id", "created_at"])
    op.create_index("ix_audit_events_patient_id", "audit_events", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_patient_id", table_name="audit_events")
    op.drop_index("ix_audit_events_doctor_created", table_name="audit_events")
    op.drop_table("audit_events")
