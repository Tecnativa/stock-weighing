# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo.tools import SQL


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    return bool(cr.fetchone())


def _copy_column(cr, table, old, new):
    if _column_exists(cr, table, old):
        cr.execute(
            SQL(
                "UPDATE %s SET %s = %s WHERE %s IS NOT NULL",
                SQL.identifier(table),
                SQL.identifier(new),
                SQL.identifier(old),
                SQL.identifier(old),
            )
        )


def migrate(cr, version):
    # The weighed quantities (qty_picked) are captured when stock_capture is
    # installed. The user weighing an operation locks it, now in stock_capture
    _copy_column(cr, "stock_move", "weighing_user_id", "capture_user_id")
