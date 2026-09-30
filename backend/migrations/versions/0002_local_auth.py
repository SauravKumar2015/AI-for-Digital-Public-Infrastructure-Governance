"""Add local password accounts and rotating refresh-token sessions."""

from alembic import op
import sqlalchemy as sa

revision = "0002_local_auth"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "auth_accounts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False, server_default="citizen"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_auth_accounts_email"),
    )
    op.create_index("ix_auth_accounts_email", "auth_accounts", ["email"])

    op.create_table(
        "auth_refresh_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("family_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["account_id"], ["auth_accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash", name="uq_auth_refresh_sessions_token_hash"),
    )
    op.create_index("ix_auth_refresh_sessions_account_id", "auth_refresh_sessions", ["account_id"])
    op.create_index("ix_auth_refresh_sessions_family", "auth_refresh_sessions", ["family_id"])


def downgrade():
    op.drop_index("ix_auth_refresh_sessions_family", table_name="auth_refresh_sessions")
    op.drop_index("ix_auth_refresh_sessions_account_id", table_name="auth_refresh_sessions")
    op.drop_table("auth_refresh_sessions")
    op.drop_index("ix_auth_accounts_email", table_name="auth_accounts")
    op.drop_table("auth_accounts")
