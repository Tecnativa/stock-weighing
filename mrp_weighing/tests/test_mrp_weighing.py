# Copyright 2024 Tecnativa - Sergio Teruel
# Copyright 2026 Tecnativa - Carlos Dauden
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMrpWeighing(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids |= (
            cls.env.ref("stock.group_tracking_lot")
            | cls.env.ref("stock.group_adv_location")
            | cls.env.ref("stock.group_stock_multi_locations")
            | cls.env.ref("stock.group_production_lot")
        )
        cls.stock_production_lot_model = cls.env["stock.lot"]
        cls.manufacture_route = cls.env.ref("mrp.route_warehouse0_manufacture")
        cls.mto_route = cls.env.ref("stock.route_warehouse0_mto")
        cls.delivery_operation_type = cls.env.ref("stock.picking_type_out")
        cls.delivery_operation_type.write({"close_production": True})
        cls.mto_route.write({"active": True, "product_selectable": True})
        cls.manufacture_route.product_selectable = True
        cls.seller = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Product B",
                "type": "consu",
                "lst_price": 100.0,
                "standard_price": 10.0,
                "uom_id": cls.env.ref("uom.product_uom_unit").id,
                "tracking": "lot",
                "is_storable": True,
                "seller_ids": [
                    (0, 0, {"partner_id": cls.seller.id, "min_qty": 1, "price": 10.0})
                ],
            }
        )
        cls.component = cls.env["product.product"].create(
            {
                "name": "Test Component",
                "type": "consu",
                "uom_id": cls.env.ref("uom.product_uom_unit").id,
                "tracking": "lot",
                "is_storable": True,
            }
        )
        cls.component_lot_1 = cls.stock_production_lot_model.create(
            {
                "name": "COMPONENTLOT001",
                "product_id": cls.component.id,
                "company_id": cls.env.company.id,
            }
        )
        cls.quant_1 = cls.env["stock.quant"].create(
            {
                "lot_id": cls.component_lot_1.id,
                "quantity": 10,
                "location_id": cls.env.ref("stock.stock_location_stock").id,
                "company_id": cls.env.company.id,
                "product_id": cls.component.id,
            }
        )
        cls.component_lot_2 = cls.stock_production_lot_model.create(
            {
                "name": "COMPONENTLOT002",
                "product_id": cls.component.id,
                "company_id": cls.env.company.id,
            }
        )
        cls.quant_2 = cls.env["stock.quant"].create(
            {
                "lot_id": cls.component_lot_2.id,
                "quantity": 10,
                "location_id": cls.env.ref("stock.stock_location_stock").id,
                "company_id": cls.env.company.id,
                "product_id": cls.component.id,
            }
        )
        cls.quant_1.action_apply_inventory()
        cls.quant_2.action_apply_inventory()
        cls.product_lot = cls.stock_production_lot_model.create(
            {
                "name": "PRODUCTLOT001",
                "product_id": cls.product.id,
                "company_id": cls.env.company.id,
            }
        )
        cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": cls.product.product_tmpl_id.id,
                "uom_id": cls.env.ref("uom.product_uom_unit").id,
                "type": "normal",
                "bom_line_ids": [
                    (0, 0, {"product_id": cls.component.id, "product_qty": 1.1})
                ],
            }
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
            }
        )

    def _create_delivery(self):
        """A delivery of 5 units, made to order when the product is"""
        picking_form = Form(self.env["stock.picking"])
        picking_form.picking_type_id = self.delivery_operation_type
        picking_form.partner_id = self.partner
        with picking_form.move_ids.new() as move:
            move.product_id = self.product
            move.product_uom_qty = 5
        picking = picking_form.save()
        picking.move_ids.procure_method = (
            "make_to_order"
            if self.mto_route in self.product.route_ids
            else "make_to_stock"
        )
        picking.action_confirm()
        return picking

    def test_weighing_from_wizard(self):
        picking = self._create_delivery()
        wizard = self.env["weighing.wizard"].create(
            {
                "move_id": picking.move_ids[0].id,
            }
        )
        wizard.lot_id = self.product_lot
        wizard.weight = 5
        wizard.add_operation_and_record()
        self.assertEqual(5, picking.move_ids.captured_quantity)

    def test_weighing_from_wizard_with_manufacturing(self):
        self.product.write(
            {
                "route_ids": [(6, 0, [self.manufacture_route.id, self.mto_route.id])],
            }
        )
        picking = self._create_delivery()
        wizard = self.env["weighing.wizard"].create(
            {
                "move_id": picking.move_ids[0].id,
            }
        )
        wizard.component_quant_id = self.quant_1
        self.assertTrue(wizard.lot_id)
        wizard.weight = 4.5
        wizard.add_operation_and_record()
        production = picking.move_ids.move_orig_ids.production_id
        self.assertEqual(4.5, picking.move_ids.captured_quantity)
        self.assertEqual(4.5, production.qty_producing)
        self.assertEqual(wizard.lot_id, production.lot_producing_ids)
        self.assertEqual(
            self.component_lot_1,
            production.move_raw_ids.move_line_ids.filtered("picked").lot_id,
        )
        picking.with_context(skip_backorder=True, skip_expired=True).button_validate()
        self.assertEqual(picking.state, "done")
        self.assertEqual(production.state, "done")

    def test_weighing_from_wizard_with_manufacturing_more_one_lot(self):
        self.product.write(
            {
                "route_ids": [(6, 0, [self.manufacture_route.id, self.mto_route.id])],
            }
        )
        picking = self._create_delivery()
        wizard = self.env["weighing.wizard"].create(
            {
                "move_id": picking.move_ids[0].id,
            }
        )
        wizard.component_quant_id = self.quant_1
        self.assertTrue(wizard.lot_id)
        wizard.weight = 2.5
        wizard.with_context(reload_wizard_action=True).add_operation_and_record()
        wizard.component_quant_id = self.quant_2
        wizard.weight = 2
        wizard.with_context(reload_wizard_action=False).add_operation_and_record()
        production = picking.move_ids.move_orig_ids.production_id
        self.assertEqual(4.5, picking.move_ids.captured_quantity)
        self.assertEqual(4.5, production.qty_producing)
        self.assertEqual(wizard.lot_id, production.lot_producing_ids)
        picked = production.move_raw_ids.move_line_ids.filtered("picked")
        self.assertEqual(picked.lot_id, self.component_lot_1 | self.component_lot_2)
        self.assertAlmostEqual(
            4.95,  # Each unit of product requires 1.1 unit of the component
            sum(picked.mapped("quantity")),
        )
        picking.with_context(skip_backorder=True, skip_expired=True).button_validate()
        self.assertEqual(picking.state, "done")
        self.assertEqual(production.state, "done")

    def _create_production_to_weigh(self):
        self.env["stock.quant"]._update_available_quantity(
            self.component,
            self.env.ref("stock.stock_location_stock"),
            10,
            lot_id=self.component_lot_1,
        )
        production_form = Form(self.env["mrp.production"])
        production_form.product_id = self.product
        production_form.product_qty = 5
        production = production_form.save()
        production.action_confirm()
        production.action_generate_serial()
        return production

    def _weigh_finished_product(self, production, weight):
        finished_move = production.move_finished_ids.filtered(
            lambda move: move.product_id == self.product
        )
        action = finished_move.action_add_move_line()
        wizard = (
            self.env["weighing.wizard"]
            .with_context(**action["context"])
            .create({"weight": weight})
        )
        wizard.add_operation_and_record()
        return wizard.selected_move_line_id

    def _mark_production_done(self, production):
        production.with_context(
            skip_backorder=True, skip_consumption=True, skip_expired=True
        ).button_mark_done()
        self.assertEqual(production.state, "done")

    def test_weighing_production_finished_move(self):
        production = self._create_production_to_weigh()
        weighed_line = self._weigh_finished_product(production, 4.3)
        self.assertEqual(4.3, production.qty_producing)
        self.assertAlmostEqual(4.73, production.move_raw_ids.quantity)
        # The weighed quantity prevails over a different quantity to produce
        production.qty_producing = 5
        self._mark_production_done(production)
        self.assertEqual(4.3, production.qty_producing)
        finished_move = weighed_line.move_id
        self.assertEqual(4.3, finished_move.quantity)
        # The weighed line is the one done, so the weighing record is kept
        self.assertEqual(weighed_line, finished_move.move_line_ids)
        self.assertEqual(4.3, weighed_line.quantity)
        self.assertEqual(4.3, weighed_line.recorded_weight)
        self.assertEqual(production.lot_producing_ids, weighed_line.lot_id)

    def test_weighing_production_finished_move_several_weights(self):
        production = self._create_production_to_weigh()
        first_line = self._weigh_finished_product(production, 2)
        second_line = self._weigh_finished_product(production, 3.5)
        # Weighing more than the demand is allowed
        self.assertEqual(5.5, production.qty_producing)
        self.assertAlmostEqual(6.05, production.move_raw_ids.quantity)
        # Removing a weight produces the remaining ones
        first_line.action_reset_weights()
        self.assertEqual(3.5, production.qty_producing)
        self.assertAlmostEqual(3.85, production.move_raw_ids.quantity)
        self._mark_production_done(production)
        finished_move = second_line.move_id
        self.assertEqual(3.5, finished_move.quantity)
        self.assertEqual(second_line, finished_move.move_line_ids)

    def test_weighing_production_finished_move_weight_removed(self):
        production = self._create_production_to_weigh()
        weighed_line = self._weigh_finished_product(production, 4.3)
        finished_move = weighed_line.move_id
        action = weighed_line.action_weighing()
        wizard = (
            self.env["weighing.wizard"]
            .with_context(**action["context"])
            .create({"weight": 0})
        )
        wizard.record_weight()
        # The quantity to produce doesn't keep the removed weight
        self.assertEqual(0, production.qty_producing)
        # Without weights the order is done as if it had never been weighed
        self._mark_production_done(production)
        self.assertEqual(5, production.qty_producing)
        self.assertEqual(5, finished_move.quantity)

    def test_weighing_production_finished_product_not_picked(self):
        # The weighed finished product is not taken as already produced
        production = self._create_production_to_weigh()
        weighed_line = self._weigh_finished_product(production, 4.3)
        self.assertEqual(4.3, weighed_line.recorded_weight)
        self.assertEqual(4.3, weighed_line.move_id.captured_quantity)
        self.assertFalse(weighed_line.picked)
        self.assertFalse(weighed_line.move_id.picked)
        self.assertEqual(0, production.qty_produced)

    def test_weighing_operations_action(self):
        production = self._create_production_to_weigh()
        action = production.action_weighing_operations()
        self.assertEqual(
            action["domain"], [("id", "in", production.move_finished_ids.ids)]
        )
        self.assertNotIn("search_default_ready", action["context"])

    def test_production_orders_start_screen(self):
        production = self._create_production_to_weigh()
        tile = self.env.ref("mrp_weighing.quick_start_screen_action_productions_orders")
        action = tile.run_action()
        self.assertEqual("mrp.production", action["res_model"])
        productions = self.env["mrp.production"].search(action["domain"])
        self.assertIn(production, productions)
