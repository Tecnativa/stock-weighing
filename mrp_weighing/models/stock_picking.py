# Copyright 2024 Tecnativa - Sergio Teruel
# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo import fields, models
from odoo.tools.misc import clean_context


class PickingType(models.Model):
    _inherit = "stock.picking.type"

    close_production = fields.Boolean(
        help="Validating a transfer of this type marks as done the "
        "manufacturing orders producing its products, with what was weighed",
    )


class Picking(models.Model):
    _inherit = "stock.picking"

    close_production = fields.Boolean(related="picking_type_id.close_production")

    def _close_production(self):
        productions = self.move_ids.move_orig_ids.production_id.filtered(
            lambda production: production.state not in ("done", "cancel")
        )
        if productions:
            context = dict(clean_context(self.env.context), skip_backorder=True)
            productions.with_context(**context).button_mark_done()
        return True

    def button_validate(self):
        self.filtered("close_production")._close_production()
        return super().button_validate()
