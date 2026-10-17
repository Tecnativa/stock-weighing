# Copyright 2024 Tecnativa - David Vidal
# Copyright 2024 Tecnativa - Sergio Teruel
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import clean_context

from odoo.addons.web.controllers.utils import clean_action


class StockMoveWeightWizard(models.TransientModel):
    _name = "weighing.wizard"
    _description = "Record weights over detailed operations"

    wizard_state = fields.Selection(
        selection=[
            ("weight", "Weight"),
            ("new_move_line", "Add Operation"),
        ],
        default="weight",
    )
    move_id = fields.Many2one(comodel_name="stock.move")
    product_id = fields.Many2one(
        comodel_name="product.product", related="move_id.product_id", store=True
    )
    available_lot_ids = fields.Many2many(
        comodel_name="stock.lot", compute="_compute_available_lot_ids"
    )
    lot_id = fields.Many2one(
        comodel_name="stock.lot",
        domain="[('id', 'in', available_lot_ids)]",
        compute="_compute_lot_id",
        store=True,
        readonly=False,
    )
    available_result_package_ids = fields.Many2many(
        comodel_name="stock.package",
        compute="_compute_available_result_package_ids",
    )
    result_package_id = fields.Many2one(
        "stock.package",
        "Destination Package",
        domain="[('id', 'in', available_result_package_ids)]",
        help="If set, the operations are packed into this package",
    )
    product_tracking = fields.Selection(related="product_id.tracking")
    selected_move_line_id = fields.Many2one(comodel_name="stock.move.line")
    move_line_ids = fields.Many2many(comodel_name="stock.move.line")
    weight = fields.Float(digits="Product Unit")
    print_label = fields.Boolean(help="Print label after the weight record")
    label_report_id = fields.Many2one(comodel_name="ir.actions.report")
    has_weight = fields.Boolean(compute="_compute_has_weight", readonly=False)
    # Dummy fields for use quant_id field to get info from quants
    quant_id = fields.Many2one("stock.quant", "Pick From")
    location_id = fields.Many2one(
        comodel_name="stock.location", related="move_id.location_id"
    )
    location_dest_id = fields.Many2one(
        comodel_name="stock.location", related="move_id.location_dest_id"
    )
    package_id = fields.Many2one(
        comodel_name="stock.package", related="selected_move_line_id.package_id"
    )
    owner_id = fields.Many2one(
        comodel_name="res.partner", related="selected_move_line_id.owner_id"
    )
    show_quant = fields.Boolean(related="move_id.show_quant")

    @api.depends("quant_id")
    def _compute_lot_id(self):
        for wiz in self.filtered(lambda w: w.quant_id.lot_id):
            wiz.lot_id = wiz.quant_id.lot_id

    @api.depends("product_id")
    def _compute_available_lot_ids(self):
        self.available_lot_ids = False
        for wiz in self.filtered(lambda x: x.product_id.tracking):
            wiz.available_lot_ids = self.env["stock.lot"].search(
                wiz._available_lot_domain(),
                order="create_date desc",
                limit=8,
            )
            # Add to available lots any lot coming in context as default key
            default_lot_id = self.env.context.get("default_lot_id", False)
            if default_lot_id:
                wiz.available_lot_ids = [(4, default_lot_id)]

    @api.depends("product_id")
    def _compute_available_result_package_ids(self):
        self.available_result_package_ids = False
        for wiz in self:
            wiz.available_result_package_ids = self.env["stock.package"].search(
                [],
                order="create_date desc",
                limit=10,
            )

    @api.depends("move_id", "selected_move_line_id")
    def _compute_has_weight(self):
        self.has_weight = False
        for wiz in self:
            wiz.has_weight = (
                wiz.move_id.has_weight or wiz.selected_move_line_id.has_weight
            )

    def _available_lot_domain(self):
        return [("product_id", "=", self.product_id.id)]

    def _lot_creation_constraints(self):
        """To be hooked by stock_picking_auto_create_lot or others"""
        return [bool(self.product_tracking), not self.lot_id]

    def _check_lot_creation(self):
        """Avoid adding a detailed operation when no lot is set and it is required.
        This method can be a hook to allow using stock_picking_auto_create_lot to
        create the lots on the fly"""
        self.ensure_one()
        if all(self._lot_creation_constraints()):
            raise UserError(self.env._("You need to supply a Lot/Serial Number"))

    def _post_add_detailed_operation(self):
        """To be hooked if necessary"""

    def _get_capture_values(self):
        """Characteristics of the detailed operation to add"""
        values = {
            "lot": self.lot_id or None,
            "result_package": self.result_package_id or None,
        }
        if self.quant_id:
            values.update(
                lot=self.quant_id.lot_id,
                location=self.quant_id.location_id,
                package=self.quant_id.package_id,
                owner=self.quant_id.owner_id,
            )
        return values

    def add_operation_and_record(self):
        """New detailed operation from the kanban card.

        The weight is captured on the move as a detailed operation of its own,
        so it can be labeled, taking it from the reservation of the move.
        """
        if self.quant_id:
            # Maintains lot selection wizard
            self.lot_id = self.quant_id.lot_id
        self._check_lot_creation()
        lines = self.move_id.with_context(
            **clean_context(self.env.context)
        )._capture_quantity(self.weight, merge=False, **self._get_capture_values())
        self.selected_move_line_id = lines[:1]
        self._post_add_detailed_operation()
        # A weight taken from the reservation of several lots or locations
        # gets a detailed operation for each of them
        for line in lines[1:]:
            line._record_weight(line.quantity)
        self.weight = self.selected_move_line_id.quantity
        return self.record_weight()

    def record_weight(self):
        """Register the operation weight"""
        selected_line = self.selected_move_line_id
        move = selected_line.move_id
        selected_line._record_weight(self.weight)
        # Unlock the operation
        move.action_unlock_weigh_operation()
        self.weight = 0.0
        action_list = []
        other_action = False
        # A weight removed can drop its line, e.g. on manufacturing orders
        if self.print_label and selected_line.exists():
            # Nothing to print when the operation type has no label report
            action = selected_line.action_print_weight_record_label()
            if action:
                clean_action(action, self.env)
                action_list.append(action)
        if self.env.context.get("reload_wizard_action", False):
            other_action = self.reload_action_wizard()
            clean_action(other_action, self.env)
        return self._actions_after_record_weight(action_list, other_action=other_action)

    @api.model
    def _actions_after_record_weight(self, actions, other_action=False):
        """Print the labels and then close the wizard or run another action.

        Odoo prints the reports one after the other and then runs the next
        action, so the workflow is not broken.
        """
        next_action = other_action or {"type": "ir.actions.act_window_close"}
        if not actions:
            return next_action
        return {
            "type": "ir.actions.client",
            "tag": "do_multi_print",
            "params": {"reports": actions, "anotherAction": next_action},
        }

    def action_clear_quant(self):
        """Clear the source stock and its lot, keeping the wizard open"""
        self.write({"quant_id": False, "lot_id": False})
        return self.reload_action_wizard()

    def action_close(self):
        """Close but unlock the operation"""
        (
            self.move_id or self.selected_move_line_id.move_id
        ).action_unlock_weigh_operation()

    def unlink(self):
        """Ensure that the wizard cleanup releases the weighing operations"""
        (self.move_id | self.selected_move_line_id.move_id)._capture_unlock()
        return super().unlink()

    def reload_action_wizard(self):
        """Helper method to be called by buttons in weighing wizard"""
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
            "name": self.env.context.get("weighing_wizard_name"),
            "context": dict(self.env.context, reload_wizard_action=False),
        }
