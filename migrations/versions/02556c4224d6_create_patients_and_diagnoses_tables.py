"""create patients and diagnoses tables

Revision ID: 02556c4224d6
Revises: 0dc5525a9c8b
Create Date: 2026-08-04 16:19:26.561950

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '02556c4224d6'
down_revision: Union[str, Sequence[str], None] = '0dc5525a9c8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


"""create patients and diagnoses tables

Revision ID: 02556c4224d6
Revises: 0dc5525a9c8b
Create Date: 2026-08-04 16:19:26.561950

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '02556c4224d6'
down_revision: Union[str, Sequence[str], None] = '0dc5525a9c8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create Patients Table
    op.create_table(
        'patients',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('doctor_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('age', sa.Integer(), nullable=True),
        sa.Column('gender', sa.String(length=20), nullable=True),
        sa.Column('contact_number', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )

    # 2. Bulletproof ENUM creation bypassing Data API catalog checks
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE diagnosis_status AS ENUM ('pending', 'processing', 'complete', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # Tell SQLAlchemy the type exists and NOT to try creating it
    diagnosis_status = postgresql.ENUM('pending', 'processing', 'complete', 'failed', name='diagnosis_status', create_type=False)

    # 3. Create Diagnoses Table
    op.create_table(
        'diagnoses',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('patient_id', sa.String(length=36), sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('doctor_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('mucosal_type', sa.String(length=100), nullable=True),
        sa.Column('has_ulcer', sa.Boolean(), nullable=True),
        sa.Column('has_patch', sa.Boolean(), nullable=True),
        sa.Column('has_growth', sa.Boolean(), nullable=True),
        sa.Column('symptoms', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('habits', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('dl_image_s3_key', sa.String(length=255), nullable=True),
        sa.Column('optical_image_1_s3_key', sa.String(length=255), nullable=True),
        sa.Column('optical_image_2_s3_key', sa.String(length=255), nullable=True),
        sa.Column('status', diagnosis_status, nullable=False, server_default='pending'),
        sa.Column('rules_match_result', sa.String(length=255), nullable=True),
        sa.Column('optical_deviation_index', sa.Numeric(), nullable=True),
        sa.Column('dl_label', sa.String(length=50), nullable=True),
        sa.Column('dl_confidence', sa.Numeric(), nullable=True),
        sa.Column('final_score', sa.Numeric(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )

    # 4. Create Indexes (Composite and FKs)
    op.create_index('ix_patients_doctor_id', 'patients', ['doctor_id'])
    op.create_index('ix_diagnoses_doctor_id', 'diagnoses', ['doctor_id'])
    op.create_index('ix_diagnoses_patient_id_created_at', 'diagnoses', ['patient_id', 'created_at'])


def downgrade() -> None:
    # 1. Drop Indexes
    op.drop_index('ix_diagnoses_patient_id_created_at', table_name='diagnoses')
    op.drop_index('ix_diagnoses_doctor_id', table_name='diagnoses')
    op.drop_index('ix_patients_doctor_id', table_name='patients')
    
    # 2. Drop Tables
    op.drop_table('diagnoses')
    op.drop_table('patients')
    
    # 3. Drop ENUM natively
    op.execute("DROP TYPE IF EXISTS diagnosis_status;")