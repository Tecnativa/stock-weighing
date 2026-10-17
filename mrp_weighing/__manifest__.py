# Copyright 2024 Tecnativa - Sergio Teruel
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)
{
    "name": "Weighing assistant in manufacturing orders",
    "summary": "Weigh the products of manufacturing orders and close them from "
    "their next transfers",
    "version": "20.0.1.0.0",
    "author": "Tecnativa, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/stock-weighing",
    "license": "AGPL-3",
    "category": "MRP",
    "depends": ["stock_weighing", "mrp_capture"],
    "data": [
        "data/quick_start_screens.xml",
        "views/mrp_production_view.xml",
        "views/stock_picking_views.xml",
        "views/stock_move_views.xml",
        "wizards/weighing_wizard_views.xml",
    ],
}
