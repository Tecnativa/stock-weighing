# Copyright 2024 Tecnativa - David Vidal
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import api, fields, models


class WeightMixin(models.AbstractModel):
    _name = "weighing.mixin"
    _description = "To be used by stock.move and stock.move.line"

    has_weight = fields.Boolean(
        compute="_compute_has_weight", search="_search_has_weight"
    )

    @api.model
    def _get_weight_reference_uom(self):
        """Units of weight are the ones measured relative to the gram"""
        return self.env.ref("uom.product_uom_gram")

    @api.model
    def _has_weigh_domain(self):
        """Plug in to change behavior"""
        return [
            (
                "uom_id.parent_path",
                "=like",
                f"{self._get_weight_reference_uom().parent_path}%",
            ),
        ]

    @api.depends("uom_id")
    def _compute_has_weight(self):
        """Product UOM is a weighed one"""
        self.has_weight = False
        self.filtered_domain(self._has_weigh_domain()).has_weight = True

    def _search_has_weight(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            return NotImplemented
        domain = self._has_weigh_domain()
        positive = (operator == "=") == value
        return domain if positive else ["!", *domain]
