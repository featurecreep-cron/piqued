"""bump max_articles_per_cycle default

Bumps existing settings rows where max_articles_per_cycle is the old
default of '3' to the new default '25'. Users who explicitly chose a
different value are left alone.

Revision ID: c8a4f12d0e91
Revises: b67e91e360c1
Create Date: 2026-04-06 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8a4f12d0e91"
down_revision: Union[str, Sequence[str], None] = "b67e91e360c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _settings_table_exists() -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return "settings" in inspector.get_table_names()


def upgrade() -> None:
    """Bump existing max_articles_per_cycle='3' to '25'.

    Skipped on legacy DBs that haven't created the settings table yet —
    `create_all` runs after the bootstrap upgrade and will pick up the
    new default from DEFAULTS on first read.
    """
    if not _settings_table_exists():
        return
    op.execute(
        sa.text(
            "UPDATE settings SET value='25' "
            "WHERE key='max_articles_per_cycle' AND value='3'"
        )
    )


def downgrade() -> None:
    """Revert max_articles_per_cycle='25' back to '3'."""
    if not _settings_table_exists():
        return
    op.execute(
        sa.text(
            "UPDATE settings SET value='3' "
            "WHERE key='max_articles_per_cycle' AND value='25'"
        )
    )
