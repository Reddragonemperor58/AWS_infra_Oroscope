"""create clinical_rules table

Revision ID: c7cf938107bc
Revises: b092118496c4
Create Date: 2026-10-02 18:50:24.620365

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7cf938107bc'
down_revision: Union[str, Sequence[str], None] = 'b092118496c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'clinical_rules',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('ulcer', sa.String(255), nullable=False),
        sa.Column('patch', sa.String(255), nullable=False),
        sa.Column('growth', sa.String(255), nullable=False),
        sa.Column('mucosal_condition', sa.String(255), nullable=False),
        sa.Column('sharp_objects', sa.String(255), nullable=False),
        sa.Column('pigmentation', sa.String(255), nullable=False),
        sa.Column('symptoms', sa.String(255), nullable=False),
        sa.Column('habits', sa.String(255), nullable=False),
        sa.Column('oral_mapping', sa.String(255), nullable=False),
        sa.Column('provisional_diagnosis', sa.String(255), nullable=False),
        sa.Column('differential_diagnosis', sa.String(255), nullable=False),
        sa.Column('advise', sa.Text(), nullable=False),
    )
    # Enforces the empirically-proven one-row-per-combination guarantee at
    # the database level — a future bad load that violates it fails loudly.
    op.create_index(
        'ix_clinical_rules_lookup',
        'clinical_rules',
        ['ulcer', 'patch', 'growth', 'mucosal_condition', 'sharp_objects',
         'pigmentation', 'symptoms', 'habits', 'oral_mapping', 'provisional_diagnosis'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('ix_clinical_rules_lookup', table_name='clinical_rules')
    op.drop_table('clinical_rules')
