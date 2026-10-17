# Copyright 2024 Tecnativa - David Vidal
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Weighing assistant",
    "summary": "Weighing assistant for stock operations",
    "version": "20.0.1.0.0",
    "author": "Tecnativa, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/stock-weighing",
    "license": "AGPL-3",
    "category": "Inventory",
    "depends": [
        "barcodes",
        "stock_capture",
        "web_quick_start_screen",
        "web_filter_header_button",
        "web_widget_numeric_step",
    ],
    "data": [
        "security/ir.access.csv",
        "report/report_deliveryslip.xml",
        "views/stock_move_line_views.xml",
        "views/stock_move_views.xml",
        "views/stock_picking_views.xml",
        "views/stock_picking_type_views.xml",
        "wizards/weighing_wizard_views.xml",
        "data/quick_start_screens.xml",
    ],
    "demo": [
        "demo/weight_label_demo.xml",
        "demo/picking_type_demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "stock_weighing/static/src/base_weight_record_kanban/**/*",
        ],
    },
    "post_init_hook": "post_init_hook",
    "pre_init_hook": "pre_init_hook",
    "maintainers": ["chienandalu", "sergio-teruel", "carlosdauden"],
}
