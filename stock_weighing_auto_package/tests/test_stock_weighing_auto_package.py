# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStockWeighingAutoPackage(TransactionCase):
    def test_package_per_weighing(self):
        product = self.env["product.product"].create(
            {
                "name": "Fish",
                "is_storable": True,
                "uom_id": self.env.ref("uom.product_uom_kgm").id,
            }
        )
        stock = self.env.ref("stock.warehouse0").lot_stock_id
        customers = self.env.ref("stock.stock_location_customers")
        self.env["stock.quant"]._update_available_quantity(product, stock, 10)
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.env.ref("stock.picking_type_out").id,
                "location_id": stock.id,
                "location_dest_id": customers.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": 5,
                            "location_id": stock.id,
                            "location_dest_id": customers.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.action_assign()
        move = picking.move_ids

        def weigh(weight):
            action = move.action_add_move_line()
            wizard = (
                self.env["weighing.wizard"]
                .with_context(**action["context"])
                .create({"weight": weight})
            )
            wizard.stock_weighing_auto_package = True
            wizard.add_operation_and_record()
            return wizard.selected_move_line_id

        first, second = weigh(2), weigh(1.5)
        # The option is kept on the product for the next weighings
        self.assertTrue(product.stock_weighing_auto_package)
        self.assertTrue(first.result_package_id)
        self.assertTrue(second.result_package_id)
        self.assertNotEqual(first.result_package_id, second.result_package_id)
        self.assertEqual(move.captured_quantity, 3.5)
