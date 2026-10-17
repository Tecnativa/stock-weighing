# Copyright 2023 Tecnativa - David Vidal
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    remote_scale_id = fields.Many2one(
        comodel_name="remote.measure.device",
        compute="_compute_remote_scale_id",
        readonly=False,
    )

    @api.depends(
        "picking_id",
        "picking_id.picking_type_id.remote_scale_id",
        "picking_id.remote_scale_id",
        "uom_id",
    )
    @api.depends_context("force_user_measure_device", "uid")
    def _compute_remote_scale_id(self):
        """Avoid measuring when the scale and move units are not compatible."""
        for record in self:
            record.remote_scale_id = record._remote_scale_for(record.uom_id)

    def _remote_scale_for(self, uom):
        """Scale of the transfer, or of the user when forced, measuring in a
        unit compatible with the given one"""
        picking_scale = (
            self.picking_id.remote_scale_id
            or self.picking_id.picking_type_id.remote_scale_id
        )
        if picking_scale and uom._has_common_reference(picking_scale.uom_id):
            return picking_scale
        user_scale = self.env.user.remote_measure_device_id
        if (
            self.env.context.get("force_user_measure_device")
            and user_scale
            and uom._has_common_reference(user_scale.uom_id)
        ):
            return user_scale
        return self.env["remote.measure.device"]
