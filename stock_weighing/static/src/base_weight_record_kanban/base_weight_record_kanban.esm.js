/* Copyright 2024 Tecnativa - David Vidal
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl). */
import {BarcodePlugin} from "@barcodes/barcode_plugin";
import {KanbanController} from "@web/views/kanban/kanban_controller";
import {KanbanHeader} from "@web/views/kanban/kanban_header";
import {KanbanRenderer} from "@web/views/kanban/kanban_renderer";
import {kanbanView} from "@web/views/kanban/kanban_view";
import {registry} from "@web/core/registry";
import {useBus, useService} from "@web/core/utils/hooks";
import {usePlugin} from "@odoo/owl";

export class WeightRecordingKanbanHeader extends KanbanHeader {
    static template = "stock_weighing.KanbanHeader";

    setup() {
        super.setup();
        this.action = useService("action");
    }
    /**
     * Show print button only when there are operations to print
     */
    get showWeighingPrintButton() {
        return this.group.list.records.some(
            (move) => move.data.show_weighing_print_button
        );
    }
    /**
     * Fold or unfold the group
     */
    onToggleGroup() {
        return this.group.toggle();
    }
    /**
     * Print all the labels from a group
     */
    async onPrintLabels() {
        const moveIds = this.group.list.records.map((record) => record.resId);
        const action = await this.orm.call(
            "stock.move",
            "action_print_weight_record_label",
            [moveIds]
        );
        if (action) {
            await this.action.doAction(action);
        }
    }
    /**
     * Opens the related form view.
     */
    onOpenColumn() {
        this.action.doAction({
            context: {create: false},
            type: "ir.actions.act_window",
            target: "current",
            views: [[false, "form"]],
            res_model: this.group.groupByField.relation,
            res_id: this.group.serverValue,
            view_mode: "form",
        });
    }
}

export class WeightRecordingKanbanRenderer extends KanbanRenderer {
    static components = {
        ...KanbanRenderer.components,
        KanbanHeader: WeightRecordingKanbanHeader,
    };
}

/**
 * Weighs the operation of the product read with a barcode scanner, interpreting
 * the barcode as the other capture screens do.
 */
export class WeightRecordingKanbanController extends KanbanController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.barcode = usePlugin(BarcodePlugin);
        useBus(this.barcode.bus, "barcode_scanned", (ev) =>
            this.onBarcodeScanned(ev.detail.barcode)
        );
    }

    get shownMoveIds() {
        const root = this.model.root;
        const lists = root.isGrouped ? root.groups.map((group) => group.list) : [root];
        return lists.flatMap((list) =>
            (list.records || []).map((record) => record.resId)
        );
    }

    async onBarcodeScanned(barcode) {
        const action = await this.orm.call("stock.move", "action_weighing_scan", [
            this.shownMoveIds,
            barcode,
        ]);
        await this.actionService.doAction(action, {
            onClose: () => this.model.load(),
        });
    }
}

export const WeightRecordingKanbanView = {
    ...kanbanView,
    Controller: WeightRecordingKanbanController,
    Renderer: WeightRecordingKanbanRenderer,
};

registry.category("views").add("base_weight_record_kanban", WeightRecordingKanbanView);
