# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form, TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestStockWeighing(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.kg = cls.env.ref("uom.product_uom_kgm")
        cls.gram = cls.env.ref("uom.product_uom_gram")
        cls.unit = cls.env.ref("uom.product_uom_unit")
        cls.stock = cls.env.ref("stock.stock_location_stock")
        cls.customers = cls.env.ref("stock.stock_location_customers")
        cls.env.user.group_ids = [
            Command.link(cls.env.ref("stock.group_production_lot").id),
            Command.link(cls.env.ref("stock.group_tracking_lot").id),
        ]
        cls.picking_type_out = cls.env.ref("stock.picking_type_out")
        cls.picking_type_out.write(
            {"create_backorder": "ask", "weighing_operations": True}
        )
        cls.product_kg = cls.env["product.product"].create(
            {"name": "Product by weight", "is_storable": True, "uom_id": cls.kg.id}
        )
        cls.product_unit = cls.env["product.product"].create(
            {"name": "Product by unit", "is_storable": True, "uom_id": cls.unit.id}
        )
        for product in cls.product_kg | cls.product_unit:
            cls.env["stock.quant"]._update_available_quantity(product, cls.stock, 20)

    def _create_delivery(self, products):
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.picking_type_out.id,
                "location_id": self.stock.id,
                "location_dest_id": self.customers.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "uom_id": product.uom_id.id,
                            "product_uom_qty": 10,
                            "location_id": self.stock.id,
                            "location_dest_id": self.customers.id,
                        }
                    )
                    for product in products
                ],
            }
        )
        picking.action_assign()
        return picking

    def _open_wizard(self, action):
        return Form(self.env[action["res_model"]].with_context(**action["context"]))

    def _record_weight(self, move_line, weight):
        wizard_form = self._open_wizard(move_line.action_weighing())
        wizard_form.weight = weight
        return wizard_form.save().record_weight()

    def _add_operation(self, move, weight, **values):
        wizard_form = self._open_wizard(move.action_add_move_line())
        wizard_form.weight = weight
        for field, value in values.items():
            setattr(wizard_form, field, value)
        wizard = wizard_form.save()
        wizard.add_operation_and_record()
        return wizard.selected_move_line_id

    def _validate_with_backorder(self, picking):
        action = picking.button_validate()
        self.assertEqual(action["res_model"], "stock.backorder.confirmation")
        Form(
            self.env[action["res_model"]].with_context(**action["context"])
        ).save().process()
        self.assertEqual(picking.state, "done")
        return self.env["stock.picking"].search([("backorder_id", "=", picking.id)])

    def _reserved(self, product):
        return sum(
            self.env["stock.quant"]
            ._gather(product, self.stock)
            .mapped("reserved_quantity")
        )

    def test_weight_products(self):
        picking = self._create_delivery(self.product_kg | self.product_unit)
        move_kg = picking.move_ids.filtered(lambda m: m.product_id == self.product_kg)
        self.assertTrue(move_kg.has_weight)
        self.assertFalse((picking.move_ids - move_kg).has_weight)
        self.assertEqual(
            self.env["stock.move"].search(
                [("picking_id", "=", picking.id), ("has_weight", "=", True)]
            ),
            move_kg,
        )
        self.assertTrue(picking.has_weighing_operations)
        self.assertIn(move_kg, self.picking_type_out.weight_move_ids)

    def test_weighed_quantity_in_move_unit(self):
        # Ten kilograms demanded, the line is weighed in grams
        picking = self._create_delivery(self.product_kg)
        move = picking.move_ids
        move.move_line_ids.write({"uom_id": self.gram.id, "quantity": 10000})
        self._record_weight(move.move_line_ids, 8500)
        self.assertEqual(move.captured_quantity, 8.5)

    def test_weigh_less_than_demand(self):
        picking = self._create_delivery(self.product_kg)
        line = picking.move_line_ids
        self._record_weight(line, 8.5)
        self.assertTrue(line.picked)
        self.assertEqual(line.quantity, 8.5)
        self.assertEqual(line.recorded_weight, 8.5)
        # The rest stays reserved
        rest = picking.move_line_ids - line
        self.assertFalse(rest.picked)
        self.assertEqual(rest.quantity, 1.5)
        self.assertEqual(self._reserved(self.product_kg), 10)
        self.assertEqual(picking.move_ids.captured_quantity, 8.5)
        backorder = self._validate_with_backorder(picking)
        self.assertEqual(picking.move_ids.quantity, 8.5)
        self.assertEqual(backorder.move_ids.product_uom_qty, 1.5)

    def test_weigh_again(self):
        picking = self._create_delivery(self.product_kg)
        line = picking.move_line_ids
        self._record_weight(line, 8.5)
        self._record_weight(line, 9.2)
        self.assertEqual(line.quantity, 9.2)
        self.assertEqual((picking.move_line_ids - line).quantity, 0.8)
        self.assertEqual(self._reserved(self.product_kg), 10)

    def test_weighing_state(self):
        picking = self._create_delivery(self.product_kg)
        move = picking.move_ids
        self.assertEqual(move.weighing_state, "to_weigh")
        self._record_weight(move.move_line_ids, 8.5)
        self.assertEqual(move.weighing_state, "weighed")

    def test_weigh_more_than_demand(self):
        picking = self._create_delivery(self.product_kg)
        self._record_weight(picking.move_line_ids, 10.4)
        self.assertEqual(self._reserved(self.product_kg), 10.4)
        picking.button_validate()
        self.assertEqual(picking.state, "done")
        self.assertEqual(picking.move_ids.quantity, 10.4)

    def test_operations_not_weighed_go_to_backorder(self):
        # Once weighing has started, only the picked operations are validated
        picking = self._create_delivery(self.product_kg | self.product_unit)
        move_kg = picking.move_ids.filtered(lambda m: m.product_id == self.product_kg)
        self._record_weight(move_kg.move_line_ids, 10)
        backorder = self._validate_with_backorder(picking)
        self.assertEqual(backorder.move_ids.product_id, self.product_unit)
        self.assertEqual(backorder.move_ids.product_uom_qty, 10)

    def test_operation_done_from_weighing(self):
        picking = self._create_delivery(self.product_kg | self.product_unit)
        move_kg = picking.move_ids.filtered(lambda m: m.product_id == self.product_kg)
        move_unit = picking.move_ids - move_kg
        self._record_weight(move_kg.move_line_ids, 10)
        move_unit.set_product_uom_qty_to_qty_done_from_weighing()
        self.assertTrue(move_unit.picked)
        picking.button_validate()
        self.assertEqual(picking.state, "done")
        self.assertEqual(move_unit.quantity, 10)

    def test_lines_without_weight_left_out(self):
        shelves = self.env["stock.location"].create(
            [
                {"name": f"Shelf {index}", "location_id": self.stock.id}
                for index in range(2)
            ]
        )
        product = self.env["product.product"].create(
            {"name": "Product on shelves", "is_storable": True, "uom_id": self.kg.id}
        )
        for shelf in shelves:
            self.env["stock.quant"]._update_available_quantity(product, shelf, 5)
        picking = self._create_delivery(product)
        move = picking.move_ids
        self.assertEqual(len(move.move_line_ids), 2)
        self._record_weight(move.move_line_ids[0], 6)
        self.assertEqual(move.weighing_state, "weighing")
        backorder = self._validate_with_backorder(picking)
        self.assertEqual(move.move_line_ids.location_id, shelves[0])
        self.assertEqual(move.quantity, 6)
        self.assertEqual(backorder.move_ids.product_uom_qty, 4)

    def test_reset_weights(self):
        # Without any weight the reserved quantities are validated as usual
        picking = self._create_delivery(self.product_kg)
        self._record_weight(picking.move_line_ids, 8.5)
        self.assertEqual(len(picking.move_line_ids), 2)
        picking.move_ids.action_reset_weights()
        # The weighed part joins the rest of the operation again
        self.assertEqual(picking.move_line_ids.mapped("quantity"), [10])
        self.assertFalse(any(picking.move_line_ids.mapped("picked")))
        self.assertFalse(any(picking.move_line_ids.mapped("has_recorded_weight")))
        self.assertEqual(picking.move_ids.captured_quantity, 0)
        self.assertEqual(picking.move_ids.weighing_state, "to_weigh")
        picking.button_validate()
        self.assertEqual(picking.state, "done")
        self.assertEqual(picking.move_ids.quantity, 10)

    def test_add_detailed_operations(self):
        # Each weighing gets a detailed operation of its own to label it
        picking = self._create_delivery(self.product_kg)
        move = picking.move_ids
        line_1 = self._add_operation(move, 3)
        line_2 = self._add_operation(move, 2)
        self.assertNotEqual(line_1, line_2)
        self.assertEqual((line_1 | line_2).mapped("recorded_weight"), [3, 2])
        self.assertEqual(move.captured_quantity, 5)
        unpicked = move.move_line_ids.filtered(lambda ml: not ml.picked)
        self.assertEqual(unpicked.quantity, 5)
        self.assertEqual(self._reserved(self.product_kg), 10)
        self._validate_with_backorder(picking)
        self.assertEqual(move.quantity, 5)

    def test_add_operation_from_quant_and_package(self):
        self.product_kg.tracking = "lot"
        lot = self.env["stock.lot"].create(
            {"name": "WEIGHING-LOT", "product_id": self.product_kg.id}
        )
        self.env["stock.quant"]._update_available_quantity(
            self.product_kg, self.stock, 5, lot_id=lot
        )
        quant = (
            self.env["stock.quant"]
            ._gather(self.product_kg, self.stock, lot_id=lot, strict=True)
            .filtered(lambda q: q.lot_id == lot)
        )
        package = self.env["stock.package"].create({"name": "WEIGHING-PACK"})
        picking = self._create_delivery(self.product_kg)
        move = picking.move_ids
        line = self._add_operation(move, 4, quant_id=quant, result_package_id=package)
        self.assertEqual(line.lot_id, lot)
        self.assertEqual(line.result_package_id, package)
        self.assertEqual(line.quantity, 4)
        self.assertEqual(move.quantity, 10)

    def test_add_operation_requires_lot(self):
        self.product_kg.tracking = "lot"
        picking = self._create_delivery(self.product_kg)
        with self.assertRaises(UserError):
            self._add_operation(picking.move_ids, 4)

    def test_clear_quant(self):
        picking = self._create_delivery(self.product_kg)
        quant = self.env["stock.quant"]._gather(self.product_kg, self.stock)[:1]
        wizard_form = self._open_wizard(picking.move_ids.action_add_move_line())
        wizard_form.quant_id = quant
        wizard = wizard_form.save()
        action = wizard.action_clear_quant()
        self.assertFalse(wizard.quant_id)
        self.assertEqual(action["res_id"], wizard.id)

    def test_lock_operation(self):
        picking = self._create_delivery(self.product_kg)
        move = picking.move_ids
        move.action_weighing()
        self.assertEqual(move.capture_user_id, self.env.user)
        other_user = new_test_user(
            self.env, login="weighing_other", groups="stock.group_stock_user"
        )
        self.assertTrue(move.with_user(other_user).is_capture_locked)
        with self.assertRaises(UserError):
            move.with_user(other_user).action_weighing()
        move.action_unlock_weigh_operation()
        self.assertFalse(move.capture_user_id)

    def test_print_label_after_weighing(self):
        report = self.env.ref(
            "stock_weighing.label_weight_record", raise_if_not_found=False
        )
        if not report:
            self.skipTest("The weighing label comes with the demo data")
        self.picking_type_out.write(
            {"print_weighing_label": True, "weighing_label_report_id": report.id}
        )
        picking = self._create_delivery(self.product_kg)
        action = self._record_weight(picking.move_line_ids, 8.5)
        self.assertEqual(action["tag"], "do_multi_print")
        self.assertEqual(
            action["params"]["reports"][0]["report_name"], report.report_name
        )
        self.assertEqual(
            action["params"]["anotherAction"]["type"], "ir.actions.act_window_close"
        )
        self.assertTrue(picking.move_ids.show_weighing_print_button)

    def test_print_label_without_label_report(self):
        self.picking_type_out.write(
            {"print_weighing_label": True, "weighing_label_report_id": False}
        )
        picking = self._create_delivery(self.product_kg)
        action = self._record_weight(picking.move_line_ids, 8.5)
        # The weight is recorded and the wizard closes without printing
        self.assertEqual(action["type"], "ir.actions.act_window_close")
        self.assertEqual(picking.move_ids.recorded_weight, 8.5)

    def test_delivery_slip_shows_weighed_quantity(self):
        picking = self._create_delivery(self.product_kg)
        self._record_weight(picking.move_line_ids, 8.5)
        html = (
            self.env["ir.actions.report"]
            ._render_qweb_html("stock.action_report_delivery", picking.ids)[0]
            .decode()
        )
        self.assertIn('<span class="text-nowrap">8.5</span>', html)

    def test_scan_on_weighing_screen(self):
        picking = self._create_delivery(self.product_kg | self.product_unit)
        moves = picking.move_ids
        move_kg = moves.filtered(lambda m: m.product_id == self.product_kg)
        self.product_kg.barcode = "WEIGHING-KG"
        action = moves.action_weighing_scan("WEIGHING-KG")
        self.assertEqual(action["res_model"], "weighing.wizard")
        self.assertEqual(action["context"]["default_move_id"], move_kg.id)
        self.assertEqual(move_kg.capture_user_id, self.env.user)
        action = moves.action_weighing_scan("NOT-A-BARCODE")
        self.assertEqual(action["tag"], "display_notification")
