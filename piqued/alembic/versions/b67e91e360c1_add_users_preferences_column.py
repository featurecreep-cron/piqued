"""add users preferences column

Revision ID: b67e91e360c1
Revises: 9eb79e2a68ea
Create Date: 2026-04-06 08:47:41.202362

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b67e91e360c1"
down_revision: Union[str, Sequence[str], None] = "9eb79e2a68ea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add users.preferences JSON blob column."""
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "preferences",
                sa.Text(),
                nullable=False,
                server_default="{}",
            )
        )


def downgrade() -> None:
    """Remove users.preferences."""
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("preferences")
