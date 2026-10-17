# Copyright 2024 Tecnativa - Sergio Teruel
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo import api, fields, models


class WeighingWizard(models.TransientModel):
    _inherit = "weighing.wizard"

    stock_weighing_auto_package = fields.Boolean(
        compute="_compute_stock_weighing_auto_package",
        inverse="_inverse_stock_weighing_auto_package",
        string="Auto package",
    )

    @api.depends("product_id")
    def _compute_stock_weighing_auto_package(self):
        for wiz in self:
            wiz.stock_weighing_auto_package = wiz.product_id.stock_weighing_auto_package

    def _inverse_stock_weighing_auto_package(self):
        for wiz in self:
            wiz.product_id.sudo().stock_weighing_auto_package = (
                wiz.stock_weighing_auto_package
            )

    def _get_capture_values(self):
        """Each weighing goes to a new package of its own when the product
        asks for it and no package is chosen"""
        values = super()._get_capture_values()
        if not self.result_package_id and self.stock_weighing_auto_package:
            values["result_package"] = self.env["stock.package"].create({})
        return values
