# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStockRemoteMeasure(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.scale = cls.env["remote.measure.device"].create(
            {
                "name": "Dock scale",
                "uom_id": cls.env.ref("uom.product_uom_kgm").id,
                "protocol": "f501",
                "connection_mode": "tcp",
                "host": "127.0.0.1:1234",
            }
        )
        cls.picking_type = cls.env.ref("stock.picking_type_in")
        cls.picking_type.remote_scale_id = cls.scale
        Product = cls.env["product.product"]
        cls.product_kg = Product.create(
            {
                "name": "Weighed",
                "is_storable": True,
                "uom_id": cls.env.ref("uom.product_uom_gram").id,
            }
        )
        cls.product_unit = Product.create({"name": "Counted", "is_storable": True})

    def test_scale_of_compatible_units(self):
        supplier = self.env.ref("stock.stock_location_suppliers")
        stock = self.env.ref("stock.warehouse0").lot_stock_id
        picking = (
            self.env["stock.picking"]
            .with_context(default_picking_type_id=self.picking_type.id)
            .create(
                {
                    "picking_type_id": self.picking_type.id,
                    "location_id": supplier.id,
                    "location_dest_id": stock.id,
                    "move_ids": [
                        Command.create(
                            {
                                "product_id": product.id,
                                "product_uom_qty": 1,
                                "location_id": supplier.id,
                                "location_dest_id": stock.id,
                            }
                        )
                        for product in (self.product_kg, self.product_unit)
                    ],
                }
            )
        )
        self.assertEqual(picking.remote_scale_id, self.scale)
        moves = picking.move_ids
        # A scale in kg measures grams, not units
        self.assertEqual(
            moves.filtered(lambda m: m.product_id == self.product_kg).remote_scale_id,
            self.scale,
        )
        self.assertFalse(
            moves.filtered(lambda m: m.product_id == self.product_unit).remote_scale_id
        )
