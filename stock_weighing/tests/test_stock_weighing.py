# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStockWeighing(TransactionCase):
    def test_move_qty_picked_in_move_unit(self):
        # One dozen demanded, twelve units picked on a line in units
        unit = self.env.ref("uom.product_uom_unit")
        dozen = self.env.ref("uom.product_uom_dozen")
        product = self.env["product.product"].create(
            {"name": "Product by unit", "is_storable": True, "uom_id": unit.id}
        )
        stock = self.env.ref("stock.stock_location_stock")
        supplier = self.env.ref("stock.stock_location_suppliers")
        move = self.env["stock.move"].create(
            {
                "name": product.name,
                "product_id": product.id,
                "product_uom": dozen.id,
                "product_uom_qty": 1,
                "location_id": supplier.id,
                "location_dest_id": stock.id,
            }
        )
        move._action_confirm()
        line = self.env["stock.move.line"].create(
            {
                "move_id": move.id,
                "product_id": product.id,
                "product_uom_id": unit.id,
                "location_id": supplier.id,
                "location_dest_id": stock.id,
                "qty_picked": 12,
            }
        )
        self.assertEqual(move.qty_picked, 1)
        line.product_uom_id = dozen
        line.qty_picked = 1
        self.assertEqual(move.qty_picked, 1)
