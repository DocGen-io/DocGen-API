"""Phase 6: Team management system schema additions

Revision ID: c7e1f2a3b4d5
Revises: 8f596fa12dd3
Create Date: 2026-04-05 22:00:00.000000

Adds:
- slug, is_public, invite_token columns to teams
- MAINTAINER value to teamrole enum
- team_invitations table
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'c7e1f2a3b4d5'
down_revision: Union[str, Sequence[str], None] = '8f596fa12dd3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extend teamrole enum with MAINTAINER ─────────────────────────────────
    # PostgreSQL requires ALTER TYPE to add enum values (no table drop needed)
    op.execute("ALTER TYPE teamrole ADD VALUE IF NOT EXISTS 'MAINTAINER' AFTER 'ADMIN'")

    # ── Add new columns to teams ──────────────────────────────────────────────
    op.add_column('teams', sa.Column('slug', sa.String(), nullable=True))
    op.add_column('teams', sa.Column('is_public', sa.Boolean(), nullable=True, server_default='true'))
    op.add_column('teams', sa.Column('invite_token', sa.String(), nullable=True))

    # Back-fill slug for existing teams using team id as fallback
    op.execute("UPDATE teams SET slug = id WHERE slug IS NULL")
    op.execute("UPDATE teams SET is_public = true WHERE is_public IS NULL")
    op.execute("UPDATE teams SET invite_token = gen_random_uuid()::text WHERE invite_token IS NULL")

    # Now enforce NOT NULL and UNIQUE
    op.alter_column('teams', 'slug', nullable=False)
    op.alter_column('teams', 'is_public', nullable=False)
    op.create_unique_constraint('uq_teams_slug', 'teams', ['slug'])
    op.create_unique_constraint('uq_teams_invite_token', 'teams', ['invite_token'])
    op.create_index('ix_teams_slug', 'teams', ['slug'], unique=True)

    # ── Add unique constraint on (team_id, user_id) in team_members ───────────
    # Guard: only add if it doesn't exist already
    op.create_unique_constraint('uq_team_member', 'team_members', ['team_id', 'user_id'])

    # ── Create team_invitations table ─────────────────────────────────────────
    op.create_table(
        'team_invitations',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('team_id', sa.String(), nullable=False),
        sa.Column('invitee_user_id', sa.String(), nullable=False),
        sa.Column('actor_user_id', sa.String(), nullable=False),
        sa.Column('type', sa.Enum('INVITE', 'REQUEST', name='invitationtype'), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'ACCEPTED', 'DECLINED', name='invitationstatus'),
                  nullable=False, server_default='PENDING'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invitee_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('team_invitations')
    op.execute("DROP TYPE IF EXISTS invitationstatus")
    op.execute("DROP TYPE IF EXISTS invitationtype")

    op.drop_constraint('uq_team_member', 'team_members', type_='unique')

    op.drop_index('ix_teams_slug', table_name='teams')
    op.drop_constraint('uq_teams_slug', 'teams', type_='unique')
    op.drop_constraint('uq_teams_invite_token', 'teams', type_='unique')
    op.drop_column('teams', 'invite_token')
    op.drop_column('teams', 'is_public')
    op.drop_column('teams', 'slug')

    # Note: PostgreSQL cannot remove enum values — MAINTAINER remains in the enum on downgrade.
