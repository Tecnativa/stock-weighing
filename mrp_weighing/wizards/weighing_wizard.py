# Copyright 2024 Tecnativa - Sergio Teruel
# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo import api, fields, models


class StockMoveWeightWizard(models.TransientModel):
    _inherit = "weighing.wizard"

    component_quant_id = fields.Many2one(
        string="Select component lot",
        comodel_name="stock.quant",
        domain="[('id', 'in', component_available_stock_quant_ids)]",
    )
    component_available_stock_quant_ids = fields.Many2many(
        comodel_name="stock.quant",
        compute="_compute_component_available_stock_quant_ids",
    )
    is_production = fields.Boolean(
        compute="_compute_is_production",
        store=True,
        help="The move belongs to the transfer following a manufacturing order",
    )
    lot_id = fields.Many2one(compute="_compute_lot_id")

    def _origin_production(self):
        move = self.move_id or self.selected_move_line_id.move_id
        return move._weighing_origin_production() if move else move.production_id

    @api.depends("move_id")
    def _compute_is_production(self):
        for wizard in self:
            wizard.is_production = bool(wizard._origin_production())

    @api.depends("component_quant_id")
    def _compute_lot_id(self):
        result = super()._compute_lot_id()
        for wizard in self.filtered(
            lambda w: w.is_production and w.component_quant_id and not w.lot_id
        ):
            wizard.lot_id = wizard._origin_production()._weighing_lot_from_component(
                wizard.component_quant_id
            )
        return result

    @api.depends("product_id")
    def _compute_component_available_stock_quant_ids(self):
        self.component_available_stock_quant_ids = False
        for wizard in self:
            production = wizard._origin_production()
            if not production:
                continue
            wizard.component_available_stock_quant_ids = self.env["stock.quant"].search(
                [
                    ("product_id", "in", production.move_raw_ids.product_id.ids),
                    ("quantity", ">", 0),
                    ("location_id.usage", "=", "internal"),
                ],
                order="create_date desc",
                limit=5,
            )

    def add_operation_and_record(self):
        return super(
            StockMoveWeightWizard, self.with_context(show_lot_product=True)
        ).add_operation_and_record()

    def record_weight(self):
        line = self.selected_move_line_id
        move = line.move_id
        component_quant = self.component_quant_id or line.selected_quant_id
        lot = self.lot_id
        action = super().record_weight()
        production = move._weighing_origin_production()
        if production and production.state not in ("done", "cancel"):
            if component_quant and line.exists():
                line.selected_quant_id = component_quant
            production._weighing_sync_from_transfer(
                move, component_quant=component_quant, lot=lot
            )
        return action
