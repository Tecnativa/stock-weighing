# Copyright 2024 Tecnativa - Sergio Teruel
# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
import ast

from odoo import api, fields, models
from odoo.fields import Domain


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    weighing_operations = fields.Boolean(related="picking_type_id.weighing_operations")
    has_weighing_operations = fields.Boolean(
        compute="_compute_has_weighing_operations",
        search="_search_has_weighing_operations",
    )

    @api.depends("move_finished_ids")
    def _compute_has_weighing_operations(self):
        for production in self:
            production.has_weighing_operations = bool(production.move_finished_ids)

    def _search_has_weighing_operations(self, operator, value):
        """Orders with something to weigh, as the production orders tile of
        the start screen lists them"""
        if operator != "in":
            return NotImplemented
        with_weighing = Domain("move_finished_ids", "!=", False)
        if True in value and False in value:
            return Domain.TRUE
        return with_weighing if True in value else ~with_weighing

    def action_weighing_operations(self):
        """Weighing operations of the product to manufacture and byproducts.

        Their weights are captured on the order by mrp_capture: the product to
        manufacture adds to the quantity to produce and the byproducts are
        produced as weighed.
        """
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock_weighing.weighing_operation_action"
        )
        action["name"] = self.env._("Weighing operations for %(name)s", name=self.name)
        action["domain"] = [("id", "in", self.move_finished_ids.ids)]
        context = dict(
            self.env.context,
            **ast.literal_eval(action["context"]),
            group_by=["production_id"],
            show_weight_detail_buttons=True,
        )
        # Manufacturing operations are weighed before they are ready
        context.pop("search_default_ready", None)
        action["context"] = context
        return action

    def _weighing_sync_from_transfer(self, move, component_quant=None, lot=None):
        """Produce what was weighed on the next transfer of the order.

        The quantity to produce is the quantity captured on the move of the
        transfer, the components are consumed as the bill of materials says,
        the selected component lot is the one consumed and its name gives the
        lot of the product to manufacture.
        """
        self.ensure_one()
        quantity = move.uom_id._compute_quantity(
            move.captured_quantity, self.uom_id, round=False
        )
        self.capture_qty_producing = quantity
        self.qty_producing = quantity
        if component_quant and not lot:
            lot = self._weighing_lot_from_component(component_quant)
        if lot and lot not in self.lot_producing_ids:
            self.lot_producing_ids = lot
        self._capture_set_qty_producing()
        if component_quant:
            self._weighing_consume_component_lot(component_quant)

    def _weighing_lot_from_component(self, component_quant):
        """Lot of the product to manufacture named as the component lot"""
        lot_name = component_quant.lot_id.name
        if not lot_name or not self.product_id.tracking:
            return self.env["stock.lot"]
        lot = self.env["stock.lot"].search(
            [
                ("product_id", "=", self.product_id.id),
                ("company_id", "in", [False, self.company_id.id]),
                ("name", "=", lot_name),
            ],
            limit=1,
        )
        return lot or self.env["stock.lot"].create(
            {
                "product_id": self.product_id.id,
                "company_id": self.company_id.id,
                "name": lot_name,
            }
        )

    def _weighing_consume_component_lot(self, component_quant):
        """The component lot selected on the weighing is the consumed one, for
        what is not consumed from other lots"""
        move = self.move_raw_ids.filtered(
            lambda m: (
                m.product_id == component_quant.product_id
                and m.state not in ("done", "cancel")
            )
        )[:1]
        if not move:
            return
        others = move.move_line_ids.filtered(
            lambda ml: ml.picked and ml.lot_id != component_quant.lot_id
        )
        needed = move.should_consume_qty - sum(
            line.uom_id._compute_quantity(line.quantity, move.uom_id, round=False)
            for line in others
        )
        line = move.move_line_ids.filtered(
            lambda ml: ml.picked and ml.lot_id == component_quant.lot_id
        )[:1]
        if line:
            line._capture_set_quantity(
                move.uom_id._compute_quantity(max(needed, 0.0), line.uom_id)
            )
        elif move.uom_id.compare(needed, 0) > 0:
            move._capture_quantity(
                needed,
                lot=component_quant.lot_id,
                location=component_quant.location_id,
                package=component_quant.package_id,
                owner=component_quant.owner_id,
            )
