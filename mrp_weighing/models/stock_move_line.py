# Copyright 2024 Tecnativa - Sergio Teruel
# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo import fields, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    selected_quant_id = fields.Many2one(
        comodel_name="stock.quant",
        readonly=True,
        help="Component stock selected when this line was weighed on the "
        "transfer following its manufacturing order",
    )

    def action_reset_weights(self):
        moves = self.move_id
        result = super().action_reset_weights()
        # The orders produce what is left weighed on their next transfers
        for move in moves:
            production = move._weighing_origin_production()
            if production and production.state not in ("done", "cancel"):
                production._weighing_sync_from_transfer(move)
        return result
