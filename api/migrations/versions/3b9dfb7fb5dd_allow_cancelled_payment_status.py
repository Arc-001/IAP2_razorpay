"""allow cancelled payment status

Revision ID: 3b9dfb7fb5dd
Revises: 847cdb675421
Create Date: 2026-08-26 12:05:37.462646

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3b9dfb7fb5dd'
down_revision: str | Sequence[str] | None = '847cdb675421'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("payment_mandates_status_check", "payment_mandates", type_="check")
    op.create_check_constraint(
        "payment_mandates_status_check",
        "payment_mandates",
        "status IN ('pending','executed','failed','cancelled')",
    )


def downgrade() -> None:
    op.drop_constraint("payment_mandates_status_check", "payment_mandates", type_="check")
    op.create_check_constraint(
        "payment_mandates_status_check",
        "payment_mandates",
        "status IN ('pending','executed','failed')",
    )
