# Copyright 2024 Tecnativa - David Vidal
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import ast

from odoo import api, fields, models
from odoo.fields import Domain


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    weighing_operations = fields.Boolean(related="picking_type_id.weighing_operations")
    has_weighing_operations = fields.Boolean(
        compute="_compute_has_weighing_operations",
        search="_search_has_weighing_operations",
    )

    @api.depends("picking_ids")
    def _compute_has_weighing_operations(self):
        for batch in self:
            batch.has_weighing_operations = bool(
                batch.picking_ids.filtered("has_weighing_operations")
            )

    def _search_has_weighing_operations(self, operator, value):
        """Batches with something to weigh, as the batch tile of the start
        screen lists them"""
        if operator != "in":
            return NotImplemented
        if True in value and False in value:
            return Domain.TRUE
        if (
            self.env["ir.config_parameter"]
            .sudo()
            .get_bool("stock_weighing.any_operation_actions")
        ):
            with_weighing = Domain("picking_ids", "!=", False)
        else:
            with_weighing = Domain("picking_ids.move_ids.has_weight", "=", True)
        return with_weighing if True in value else ~with_weighing

    def action_weighing_operations(self):
        """Weight operations for this picking"""
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock_weighing.weighing_operation_action"
        )
        any_operation_actions = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_bool("stock_weighing.any_operation_actions")
        )
        weighings = (
            self.move_ids
            if any_operation_actions
            else self.move_ids.filtered("has_weight")
        )
        action["name"] = self.env._("Weighing operations for %(name)s", name=self.name)
        action["domain"] = [("id", "in", weighings.ids)]
        action["context"] = dict(
            self.env.context,
            **ast.literal_eval(action["context"]),
            group_by=["picking_id"],
        )
        return action
