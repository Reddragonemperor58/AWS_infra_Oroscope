"""alter_diagnoses_categorical_strings

Revision ID: b092118496c4
Revises: 02556c4224d6
Create Date: 2026-08-13 18:58:43.150004

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b092118496c4'
down_revision: Union[str, Sequence[str], None] = '02556c4224d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # DESTRUCTIVE: sets every row's value to NULL, not a real bool->string cast.
    # Safe only because `diagnoses` is confirmed empty as of this migration.
    # Do not reuse this pattern against a populated table.
    op.alter_column('diagnoses', 'has_ulcer',
                    new_column_name='ulcer',
                    existing_type=sa.BOOLEAN(),
                    type_=sa.String(length=255),
                    postgresql_using='NULL')
    
    # DESTRUCTIVE: sets every row's value to NULL, not a real bool->string cast.
    # Safe only because `diagnoses` is confirmed empty as of this migration.
    # Do not reuse this pattern against a populated table.
    op.alter_column('diagnoses', 'has_patch',
                    new_column_name='patch',
                    existing_type=sa.BOOLEAN(),
                    type_=sa.String(length=255),
                    postgresql_using='NULL')
    
    # DESTRUCTIVE: sets every row's value to NULL, not a real bool->string cast.
    # Safe only because `diagnoses` is confirmed empty as of this migration.
    # Do not reuse this pattern against a populated table.
    op.alter_column('diagnoses', 'has_growth',
                    new_column_name='growth',
                    existing_type=sa.BOOLEAN(),
                    type_=sa.String(length=255),
                    postgresql_using='NULL')


def downgrade() -> None:
    # DESTRUCTIVE: sets every row's value to False, not a real string->bool cast.
    op.alter_column('diagnoses', 'ulcer',
                    new_column_name='has_ulcer',
                    existing_type=sa.String(length=255),
                    type_=sa.BOOLEAN(),
                    postgresql_using='False')
                    
    # DESTRUCTIVE: sets every row's value to False, not a real string->bool cast.
    op.alter_column('diagnoses', 'patch',
                    new_column_name='has_patch',
                    existing_type=sa.String(length=255),
                    type_=sa.BOOLEAN(),
                    postgresql_using='False')
                    
    # DESTRUCTIVE: sets every row's value to False, not a real string->bool cast.
    op.alter_column('diagnoses', 'growth',
                    new_column_name='has_growth',
                    existing_type=sa.String(length=255),
                    type_=sa.BOOLEAN(),
                    postgresql_using='False')