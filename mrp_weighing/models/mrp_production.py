# Copyright 2024 Tecnativa - Sergio Teruel
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
import ast

from odoo import _, api, fields, models
from odoo.tools import clean_context, float_compare


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    weighing_operations = fields.Boolean(related="picking_type_id.weighing_operations")
    has_weighing_operations = fields.Boolean(compute="_compute_has_weighing_operations")

    @api.depends("move_finished_ids")
    def _compute_has_weighing_operations(self):
        for mrp_production in self:
            mrp_production.has_weighing_operations = mrp_production.move_finished_ids

    def action_weighing_operations(self):
        """Weighing operations for this production order"""
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock_weighing.weighing_operation_action"
        )
        weight_moves = self.move_finished_ids
        action["name"] = _("Weighing operations for %(name)s", name=self.name)
        action["domain"] = [("id", "in", weight_moves.ids)]
        ctx = dict(
            self.env.context,
            **ast.literal_eval(action["context"]),
            group_by=["production_id"],
            show_weight_detail_buttons=True,
        )
        # We weigh mrp operations that are not in ready state
        ctx.pop("search_default_ready")
        action["context"] = ctx
        return action

    def _get_weighed_qty_producing(self):
        """Quantity to produce according to the recorded weights of the finished
        product, or False if it hasn't been weighed."""
        self.ensure_one()
        weighed_lines = self.move_finished_ids.filtered(
            lambda move: move.product_id == self.product_id
            and move.state not in ("done", "cancel")
        ).move_line_ids.filtered("has_recorded_weight")
        if not weighed_lines:
            return False
        return sum(
            line.product_uom_id._compute_quantity(
                line.qty_picked, self.product_uom_id, round=False
            )
            for line in weighed_lines
        )

    def _set_weighed_qty_producing(self):
        for production in self:
            weighed_qty = production._get_weighed_qty_producing()
            if weighed_qty is False or not float_compare(
                weighed_qty,
                production.qty_producing,
                precision_rounding=production.product_uom_id.rounding,
            ):
                continue
            # Weighing wizard context keys (e.g. default_lot_id) must not reach
            # the component move lines created by _set_qty_producing, so the
            # context has to be replaced instead of updated
            # pylint: disable=W8121
            production = production.with_context(clean_context(self.env.context))
            production.qty_producing = weighed_qty
            production._set_qty_producing(False)

    def pre_button_mark_done(self):
        self._set_weighed_qty_producing()
        return super().pre_button_mark_done()
