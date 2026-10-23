"""add provisional_diagnosis to diagnoses

Revision ID: 5e12d1392533
Revises: b1b0ca109afd
Create Date: 2026-10-22 15:54:24.206421

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e12d1392533'
down_revision: Union[str, Sequence[str], None] = 'b1b0ca109afd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("diagnoses", sa.Column("provisional_diagnosis", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("diagnoses", "provisional_diagnosis")
