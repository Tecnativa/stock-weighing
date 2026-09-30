# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    # The picked quantity of the moves was the sum of their lines without unit
    # conversion: recompute the moves having a picked line in another unit
    env.cr.execute(
        """
        SELECT DISTINCT sm.id
        FROM stock_move sm
        JOIN stock_move_line sml ON sml.move_id = sm.id
        WHERE sml.product_uom_id != sm.product_uom AND sml.qty_picked != 0
        """
    )
    moves = env["stock.move"].browse([row[0] for row in env.cr.fetchall()])
    env.add_to_compute(moves._fields["qty_picked"], moves)
    moves._recompute_recordset(["qty_picked"])
