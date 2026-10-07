"""add advice to diagnosis

Revision ID: b1b0ca109afd
Revises: f1c8fef203a1
Create Date: 2026-10-07 15:00:10.915544

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1b0ca109afd'
down_revision: Union[str, Sequence[str], None] = 'f1c8fef203a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "diagnoses",
        sa.Column("advise", sa.Text(), nullable=True),
    )

def downgrade() -> None:
    op.drop_column("diagnoses", "advise")