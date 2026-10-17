# Copyright 2024 Tecnativa - Sergio Teruel
# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo import models
from odoo.fields import Domain
from odoo.tools.safe_eval import safe_eval


class QuickStartScreenAction(models.Model):
    _inherit = "quick.start.screen.action"

    def run_action(self):
        """The production orders tile lists the orders to weigh"""
        self.ensure_one()
        action = super().run_action()
        target = self.env.ref(
            "mrp_weighing.quick_start_screen_action_productions_orders",
            raise_if_not_found=False,
        )
        if self != target:
            return action
        any_operation_actions = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_bool("stock_weighing.any_operation_actions")
        )
        action = self.env["stock.move"].action_mrp_production_weighing()
        domain = action.get("domain") or []
        if isinstance(domain, str):
            domain = safe_eval(domain)
        if not any_operation_actions:
            domain = Domain.AND([domain, [("has_weighing_operations", "=", True)]])
        action["domain"] = list(Domain(domain))
        return action
