# Copyright 2024 Tecnativa - David Vidal
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class StockMoveLine(models.Model):
    _name = "stock.move.line"
    _inherit = ("stock.move.line", "weighing.mixin")

    has_recorded_weight = fields.Boolean(help="The weight was set from the wizard")
    recorded_weight = fields.Float(digits="Product Unit")

    def _get_action_weighing_name(self):
        """Custom name to show in the wizard"""
        action_name = self.env._(
            "Weigh %(quantity)s %(uom)s of %(product)s",
            quantity=self.quantity,
            uom=self.uom_id.name,
            product=self.product_id.name,
        )
        if self.lot_id:
            action_name += f" ({self.lot_id.name})"
        return action_name

    def action_weighing(self):
        """Open the wizard to record weights"""
        self.move_id.action_lock_weighing_operation()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock_weighing.weighing_wizard_action"
        )
        action["name"] = self._get_action_weighing_name()
        action["context"] = dict(
            self.env.context,
            default_selected_move_line_id=self[0].id,
            default_weight=self[0].recorded_weight or self[0].quantity,
            default_move_line_ids=self.ids,
            default_print_label=self.move_id._get_default_print_label(),
            default_move_id=self.move_id.id,
        )
        return action

    def action_print_weight_record_label(self):
        """Get detailed operations weighing labels"""
        report = self.move_id.picking_type_id.weighing_label_report_id
        if not report:
            return False
        # Labels don't need the company document layout to be configured first
        return report.report_action(self, config=False)

    def _record_weight(self, weight):
        """Record a weight on this detailed operation as its picked quantity.

        The weight is captured on the line, so the rest of its reservation stays
        reserved on an unpicked line, and recording no weight undoes it.
        """
        self.ensure_one()
        self._capture_set_quantity(weight)
        # Some captures drop their line when undone, e.g. the finished lines of
        # a manufacturing order
        self.exists().write(
            {
                "recorded_weight": weight,
                "has_recorded_weight": bool(weight),
            }
        )

    def action_reset_weights(self):
        """Restore stock move lines weights"""
        for line in self.filtered(lambda ml: ml.picked or ml.has_recorded_weight):
            line._capture_set_quantity(0)
        # Some captures drop their line when undone, e.g. the finished lines of
        # a manufacturing order
        self.exists().write({"recorded_weight": 0, "has_recorded_weight": False})
