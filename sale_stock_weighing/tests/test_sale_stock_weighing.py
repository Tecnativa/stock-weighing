# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSaleStockWeighing(TransactionCase):
    def test_sale_order_on_weighing_cards(self):
        product = self.env["product.product"].create(
            {
                "name": "Fish",
                "is_storable": True,
                "uom_id": self.env.ref("uom.product_uom_kgm").id,
            }
        )
        partner = self.env["res.partner"].create({"name": "Fish shop"})
        order = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "order_line": [
                    Command.create({"product_id": product.id, "product_uom_qty": 3})
                ],
            }
        )
        order.action_confirm()
        move = order.picking_ids.move_ids
        self.assertEqual(move.sale_order_id, order)
        # The weighing cards can be searched by sale order
        moves = self.env["stock.move"].search([("sale_order_id", "=", order.id)])
        self.assertEqual(moves, move)
