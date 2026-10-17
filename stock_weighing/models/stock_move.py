# Copyright 2024 Tecnativa - David Vidal
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
import ast

from odoo import api, fields, models
from odoo.fields import Domain


class StockMove(models.Model):
    _name = "stock.move"
    _inherit = ("stock.move", "weighing.mixin")

    recorded_weight = fields.Float(
        compute="_compute_recorded_weight", digits="Product Unit"
    )
    move_lines_weighed = fields.Boolean(compute="_compute_recorded_weight")
    weighing_state = fields.Selection(
        selection=[
            ("weighed", "Weighed"),
            ("weighing", "Weighing"),
            ("to_weigh", "To weigh"),
        ],
        compute="_compute_weighing_state",
        store=True,
    )
    weighing_label_report_id = fields.Many2one(
        related="picking_type_id.weighing_label_report_id"
    )
    show_weighing_print_button = fields.Boolean(
        compute="_compute_show_weighing_print_button"
    )
    # HACK: To show the kanban of this move in its own form
    self_move_ids = fields.Many2many(
        comodel_name="stock.move", compute="_compute_self_move_ids"
    )
    weighing_state_color = fields.Integer(compute="_compute_weighing_state_color")

    @api.depends()
    @api.depends_context("weight_operation_details")
    def _compute_display_name(self):
        if not self.env.context.get("weight_operation_details"):
            return super()._compute_display_name()
        for move in self:
            move.display_name = self.env._(
                "%(name)s details", name=move.product_id.display_name
            )

    def _compute_self_move_ids(self):
        for move in self:
            move.self_move_ids = move

    @api.depends("move_line_ids.recorded_weight", "move_line_ids.picked")
    def _compute_recorded_weight(self):
        for move in self:
            move.recorded_weight = sum(move.move_line_ids.mapped("recorded_weight"))
            move.move_lines_weighed = bool(move.move_line_ids) and not (
                move._get_lines_to_weigh()
            )

    def _get_lines_to_weigh(self):
        """Detailed operations still to weigh.

        Weighing less than the reserved quantity of a detailed operation leaves
        the rest reserved on an unpicked one with the same goods, which doesn't
        need to be weighed: the weighing was done.
        """
        self.ensure_one()
        weighed_lines = self.move_line_ids.filtered("has_recorded_weight")
        return self.move_line_ids.filtered(
            lambda ml: (
                not ml.has_recorded_weight
                and not (
                    not ml.picked
                    and any(line._capture_same_place(ml) for line in weighed_lines)
                )
            )
        )

    @api.depends(
        "move_line_ids.recorded_weight",
        "move_line_ids.picked",
        "move_line_ids.quantity",
        "state",
        "product_id",
        "product_uom_qty",
    )
    def _compute_weighing_state(self):
        """Only products with weight will trigger this state"""
        self.weighing_state = False
        for move in self.filtered("has_weight"):
            move_to_do = move.state not in {"draft", "cancel", "done"}
            weighed = any(move.move_line_ids.mapped("has_recorded_weight"))
            if weighed and (
                move.move_lines_weighed
                # Force the operation weighing state if the weighed quantity
                # overpasses the demand
                or move.uom_id.compare(move.captured_quantity, move.product_uom_qty)
                >= 0
            ):
                move.weighing_state = "weighed"
            elif move.recorded_weight and move_to_do:
                move.weighing_state = "weighing"
            elif not move.recorded_weight and move_to_do and not move.picked:
                move.weighing_state = "to_weigh"

    @api.depends("move_line_ids.picked", "picking_type_id.weighing_label_report_id")
    def _compute_show_weighing_print_button(self):
        self.show_weighing_print_button = False
        self.filtered(
            lambda x: x.picked and x.picking_type_id.weighing_label_report_id
        ).show_weighing_print_button = True

    def _compute_weighing_state_color(self):
        state_map = {"weighed": 10, "to_weigh": 1, "weighing": 3}
        for move in self:
            move.weighing_state_color = state_map.get(move.weighing_state)

    def _has_weigh_domain(self):
        """Show variable weight types only"""
        return Domain.AND([super()._has_weigh_domain(), [("product_uom_qty", ">", 0)]])

    def _search_has_weight(self, operator, value):
        domain = super()._search_has_weight(operator, value)
        positive = (operator == "=") == value
        if domain is NotImplemented or not positive:
            return domain
        return Domain.AND([domain, [("product_uom_qty", ">", 0)]])

    def search_fetch(self, domain, field_names=None, offset=0, limit=None, order=None):
        # We need to sort by move sub-fields. Don't force if we have a given order
        moves = super().search_fetch(
            domain, field_names, offset=offset, limit=limit, order=order
        )
        if self.env.context.get("outgoing_weighing_order") and not order:
            moves = moves.sorted(
                lambda x: (
                    x.location_id.name or "",
                    x.product_id.default_code or "",
                    x.product_id.name or "",
                )
            )
        return moves

    def action_lock_weighing_operation(self):
        """Avoid that other users modify the weight operation"""
        self.ensure_one()
        self._capture_lock()

    def action_unlock_weigh_operation(self):
        """Unlock the weigh operation"""
        self.ensure_one()
        self._capture_unlock()

    def _get_default_print_label(self):
        """Can be extended with other modules to add checks"""
        return self.picking_type_id.print_weighing_label

    def action_weighing(self):
        """Open the wizard to record weights"""
        self.action_lock_weighing_operation()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock_weighing.weighing_wizard_action"
        )
        move_line = self.move_line_ids[:1]
        action["name"] = move_line._get_action_weighing_name()
        action["context"] = dict(
            self.env.context,
            default_selected_move_line_id=move_line.id,
            default_weight=self.recorded_weight or self.quantity,
            default_move_line_ids=self.move_line_ids.ids,
            default_print_label=self._get_default_print_label(),
            default_move_id=self.id,
        )
        return action

    def action_add_move_line(self):
        """Open the weight wizard to add a new operation weight"""
        action = self.action_weighing()
        action["context"].update(
            default_wizard_state="new_move_line",
            default_move_id=self.id,
            default_weight=0,
        )
        del action["context"]["default_selected_move_line_id"]
        action["name"] = self.env._(
            "New operation for %(product)s (%(operation)s) "
            "%(remain).2f %(uom)s remaining",
            product=self.product_id.name,
            operation=self.reference,
            remain=max((self.product_uom_qty - self.captured_quantity), 0),
            uom=self.uom_id.name,
        )
        return action

    def action_weight_detailed_operations(self):
        """Weight detailed operations for this picking"""
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock_weighing.weighing_operation_action"
        )
        action["display_name"] = self.env._(
            "Detailed operations for %(name)s", name=self.product_id.display_name
        )
        action["domain"] = [("id", "=", self.id)]
        action["view_mode"] = "form"
        action["res_id"] = self.id
        action["views"] = [
            (view, mode) for view, mode in action["views"] if mode == "form"
        ]
        action["context"] = dict(
            self.env.context,
            **ast.literal_eval(action["context"]),
            weight_operation_details=True,
        )
        # Clean context key show_weight_detail_buttons if any module add it
        action["context"].pop("show_weight_detail_buttons", None)
        return action

    def action_print_weight_record_label(self):
        """Get operations labels"""
        return self.move_line_ids.action_print_weight_record_label()

    def action_reset_weights(self):
        """Restore stock move lines weights"""
        self.move_line_ids.action_reset_weights()

    def action_force_weighed(self):
        self.weighing_state = "weighed"

    def set_product_uom_qty_to_qty_done_from_weighing(self):
        """Capture what is left of the operations without weight"""
        moves = self.filtered(lambda move: not move.has_weight)
        moves.action_capture_remaining()
        for move_line in moves.move_line_ids.filtered("picked"):
            move_line.write(
                {"recorded_weight": move_line.quantity, "has_recorded_weight": True}
            )

    def action_weighing_scan(self, barcode):
        """Weigh the operation of a barcode read on the weighing screen.

        The barcode is interpreted as the other capture screens do, and the
        operation of its product among these ones is opened to be weighed, on
        the detailed operation of the lot read if there is one.
        """
        values = self.picking_id._capture_parse_barcode(barcode)
        product = values.get("product_id")
        moves = self.filtered(
            lambda move: (
                move.product_id == product
                and move.state not in ("draft", "done", "cancel")
            )
        )
        if not moves:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "message": self.env._(
                        "No operation to weigh for %(barcode)s", barcode=barcode
                    ),
                    "type": "warning",
                },
            }
        move = moves[:1]
        lot = values.get("lot_id")
        line = move.move_line_ids.filtered(lambda ml: lot and ml.lot_id == lot)[:1]
        if line:
            return line.action_weighing()
        action = move.action_weighing()
        if lot:
            action["context"]["default_lot_id"] = lot.id
        return action
