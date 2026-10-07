"""add diagnosis clinical input fields

Revision ID: f1c8fef203a1
Revises: c7cf938107bc
Create Date: 2026-10-06 12:04:49.646542

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1c8fef203a1'
down_revision: Union[str, Sequence[str], None] = 'c7cf938107bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column("diagnoses", sa.Column("sharp_objects", sa.String(255), nullable=True))
    op.add_column("diagnoses", sa.Column("pigmentation", sa.String(255), nullable=True))
    op.add_column("diagnoses", sa.Column("oral_mapping", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("diagnoses", "oral_mapping")
    op.drop_column("diagnoses", "pigmentation")
    op.drop_column("diagnoses", "sharp_objects")