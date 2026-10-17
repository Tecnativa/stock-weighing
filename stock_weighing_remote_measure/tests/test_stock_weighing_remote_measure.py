# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
from odoo import Command
from odoo.exceptions import ValidationError
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

    def test_widget_tares(self):
        """The configured tares are offered in the unit of the weighing"""
        kg = self.env.ref("uom.product_uom_kgm")
        tares = self.env["weighing.tare"].get_widget_tares(kg.id)
        # The default tares, in grams, converted to kilograms
        tare_100 = next(tare for tare in tares if tare["name"] == "100 gr.")
        self.assertAlmostEqual(tare_100["tare"], 0.1)
        self.assertEqual(tare_100["text_color"], "#FFFFFF")
        # Archived tares and tares in units of other kind are not offered
        self.env.ref("stock_weighing_remote_measure.weighing_tare_100").active = False
        self.assertNotIn(
            "100 gr.",
            [
                tare["name"]
                for tare in self.env["weighing.tare"].get_widget_tares(kg.id)
            ],
        )
        unit = self.env.ref("uom.product_uom_unit")
        self.assertFalse(self.env["weighing.tare"].get_widget_tares(unit.id))

    def test_configure_tares(self):
        """The tares dropped in the configuration wizard are removed"""
        tare_50 = self.env.ref("stock_weighing_remote_measure.weighing_tare_50")
        wizard = self.env["weighing.tare.wizard"].create({})
        self.assertIn(tare_50, wizard.tare_ids)
        wizard.tare_ids -= tare_50
        wizard.action_apply()
        self.assertFalse(tare_50.exists())

    def test_tare_color(self):
        tare = self.env["weighing.tare"].create(
            {"name": "Box", "value": 1, "color": "#FFFF00"}
        )
        # Dark text on light colors
        self.assertEqual(tare.text_color, "#000000")
        self.assertIn("Box", tare.preview)
        with self.assertRaises(ValidationError):
            tare.color = "yellow"
