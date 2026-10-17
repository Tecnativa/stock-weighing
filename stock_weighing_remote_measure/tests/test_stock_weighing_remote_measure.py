# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStockWeighingRemoteMeasure(TransactionCase):
    def test_weighing_wizard_device(self):
        scale = self.env["remote.measure.device"].create(
            {
                "name": "Weighing scale",
                "uom_id": self.env.ref("uom.product_uom_kgm").id,
                "protocol": "f501",
                "connection_mode": "tcp",
                "host": "127.0.0.1:1234",
            }
        )
        self.env.user.remote_measure_device_id = scale
        product = self.env["product.product"].create(
            {
                "name": "Fish",
                "is_storable": True,
                "uom_id": self.env.ref("uom.product_uom_kgm").id,
            }
        )
        stock = self.env.ref("stock.warehouse0").lot_stock_id
        self.env["stock.quant"]._update_available_quantity(product, stock, 10)
        customers = self.env.ref("stock.stock_location_customers")
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.env.ref("stock.picking_type_out").id,
                "location_id": stock.id,
                "location_dest_id": customers.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": 3,
                            "location_id": stock.id,
                            "location_dest_id": customers.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.action_assign()
        action = picking.move_ids.action_add_move_line()
        wizard = (
            self.env["weighing.wizard"].with_context(**action["context"]).create({})
        )
        # The scale of the user and the unit of the product are proposed
        self.assertEqual(wizard.measure_device_id, scale)
        self.assertEqual(wizard.uom_id, product.uom_id)
        # The weight read by the widget is the weight recorded
        wizard.weight_with_widget = 2.5
        wizard.add_operation_and_record()
        self.assertEqual(picking.move_ids.captured_quantity, 2.5)
