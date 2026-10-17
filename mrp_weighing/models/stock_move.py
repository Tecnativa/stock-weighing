# Copyright 2024 Tecnativa - Sergio Teruel
# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class StockMove(models.Model):
    _inherit = "stock.move"

    is_has_production = fields.Boolean(compute="_compute_is_has_production")

    @api.depends("move_line_ids", "move_orig_ids")
    def _compute_is_has_production(self):
        for move in self:
            move.is_has_production = bool(
                move.created_production_id or move.move_orig_ids.production_id
            )

    def _weighing_origin_production(self):
        """Order producing the product of this move of its next transfer"""
        self.ensure_one()
        production = self.move_orig_ids.production_id
        if production and self.product_id in production.product_id:
            return production[:1]
        return self.env["mrp.production"]

    @api.model
    def action_mrp_production_weighing(self):
        """Used in the start screen"""
        action = self.env["ir.actions.actions"]._for_xml_id("mrp.mrp_production_action")
        action["views"] = [[False, "kanban"], [False, "list"], [False, "form"]]
        action["context"] = {"search_default_todo": True}
        return action

    def action_add_move_line(self):
        action = super().action_add_move_line()
        production = self.production_id
        if not production:
            origin = self._weighing_origin_production()
            if origin and origin.state == "done":
                raise ValidationError(
                    self.env._("You can not add weight, the MO is done.")
                )
            return action
        lot = self.env["stock.lot"]
        if self.product_id == production.product_id:
            lot = production.lot_producing_ids[:1]
        elif self.move_line_ids.lot_id:
            lot = self.move_line_ids.lot_id[-1:]
        elif self.has_tracking and production.lot_producing_ids:
            # Byproducts take the lot named as the one of the order
            name = production.lot_producing_ids[:1].name
            lot = self.env["stock.lot"].search(
                [
                    ("company_id", "in", [False, self.company_id.id]),
                    ("product_id", "=", self.product_id.id),
                    ("name", "=", name),
                ],
                limit=1,
            ) or self.env["stock.lot"].create(
                {
                    "name": name,
                    "product_id": self.product_id.id,
                    "company_id": self.company_id.id,
                }
            )
        if lot:
            action["context"] = dict(action.get("context") or {}, default_lot_id=lot.id)
        return action
