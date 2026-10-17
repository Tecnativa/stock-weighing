# Copyright 2024 Tecnativa - Sergio Teruel
# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo import api, models


class StockQuant(models.Model):
    _inherit = "stock.quant"

    @api.depends_context("show_lot_product")
    def _compute_display_name(self):
        if not self.env.context.get("show_lot_product"):
            return super()._compute_display_name()
        for quant in self:
            quant.display_name = (
                f"{quant.lot_id.name or ''} - "
                f"{quant.location_id.display_name}/{quant.product_id.display_name} "
                f"({quant.quantity} {quant.uom_id.name})"
            )
