"""Create initial AI for Digital Infrastructure & Governance backend tables."""
from alembic import op

from app.core.db import Base
from app.features.feedback import models  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    legacy_tables = [table for table in Base.metadata.sorted_tables
                     if table.name not in {"auth_accounts", "auth_refresh_sessions"}]
    Base.metadata.create_all(bind=op.get_bind(), tables=legacy_tables)


def downgrade():
    legacy_tables = [table for table in Base.metadata.sorted_tables
                     if table.name not in {"auth_accounts", "auth_refresh_sessions"}]
    Base.metadata.drop_all(bind=op.get_bind(), tables=legacy_tables)
