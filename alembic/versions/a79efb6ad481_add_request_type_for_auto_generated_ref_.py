"""add request type for auto-generated ref no

Revision ID: a79efb6ad481
Revises: 0b014ef379ee
Create Date: 2026-09-15 09:06:48.257780

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a79efb6ad481'
down_revision: Union[str, Sequence[str], None] = '0b014ef379ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'jobs',
        sa.Column(
            'request_type',
            sa.Enum('FOC', 'SR', name='requesttype', native_enum=False),
            nullable=False,
            server_default='FOC',
        ),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('jobs', 'request_type')
    # ### end Alembic commands ###