/* Copyright 2024 Tecnativa - David Vidal
 * Copyright 2026 Tecnativa - Carlos Roca
 * Copyright 2026 Tecnativa - Carlos Dauden
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html). */
import {
    RemoteMeasureField,
    remoteMeasureField,
} from "@web_widget_remote_measure/remote_measure_field/remote_measure_field.esm";
import {onWillStart, t, useProps} from "@odoo/owl";
import {DeviceDialog} from "../device_dialog/device_dialog.esm";
import {FormViewDialog} from "@web/views/view_dialogs/form_view_dialog";
import {_t} from "@web/core/l10n/translation";
import {floatFieldProps} from "@web/views/fields/float/float_field";
import {formatFloat} from "@web/views/fields/formatters";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {user} from "@web/core/user";

export class RemoteMeasureForm extends RemoteMeasureField {
    static template = "stock_weighing_remote_measure.RemoteMeasureForm";
    props = useProps({
        ...floatFieldProps,
        remote_device_field: t.string().optional(),
        uom_field: t.string().optional(),
        default_user_device: t.boolean().optional(),
        allow_additive_measure: t.boolean().optional(),
        tares: t.any().optional([]),
    });

    setup() {
        super.setup();
        this.dialog = useService("dialog");
        this.measureState.tare = 0;
        // Tares forced in the view options, or the configured ones
        this.measureState.tares = this.props.tares;
        this.measureState.can_configure_tares = false;
        this.manualTare = 0;
        this.formatFloat = (value) =>
            formatFloat(value, {
                digits: this.props.record.fields[this.props.name].digits,
            });
        this.colors = ["success", "info", "warning", "danger", "primary"];
        onWillStart(async () => {
            if (this.props.tares.length || !this.uom || !this.uom.id) {
                return;
            }
            this.measureState.can_configure_tares = await user.hasGroup(
                "stock.group_stock_manager"
            );
            await this._loadTares();
        });
    }

    /**
     * Fetch the configured tares, converted to the unit of the weight
     */
    async _loadTares() {
        this.measureState.tares = await this.orm.call(
            "weighing.tare",
            "get_widget_tares",
            [this.uom.id]
        );
    }

    get extraMeasures() {
        // The tare is subtracted from the measured weight
        return super.extraMeasures - this.measureState.tare;
    }

    get uomName() {
        return (this.uom && this.uom.name) || "";
    }

    _set_tare(tare) {
        this.measureState.tare += !tare || isNaN(tare) ? 0 : tare;
        this._setMeasure();
    }

    onClickTare(tare) {
        this._set_tare(parseFloat(tare));
    }

    onClickManualTare(ev) {
        // Remove the manual tare set to avoid increase the tare infinitely
        this._set_tare(-this.manualTare);
        const mode = ev.currentTarget.dataset.mode;
        const input = ev.currentTarget.parentElement.querySelector("input");
        if (mode === "minus") {
            input.stepDown();
        } else {
            input.stepUp();
        }
        this.manualTare = input.valueAsNumber;
        this._set_tare(this.manualTare);
    }

    onChangeTareManualTare(ev) {
        // Remove the manual tare set to avoid increase the tare infinitely
        this._set_tare(-this.manualTare);
        this.manualTare = ev.currentTarget.valueAsNumber;
        this._set_tare(this.manualTare);
    }

    onDeviceSelector() {
        this.dialog.add(DeviceDialog, {device_field: this});
    }

    /**
     * Open the tares configuration wizard and refresh the widget once saved
     */
    onConfigureTares() {
        this.measure_stop();
        this.dialog.add(FormViewDialog, {
            resModel: "weighing.tare.wizard",
            title: _t("Configure tares"),
            onRecordSaved: async (record) => {
                await this.orm.call("weighing.tare.wizard", "action_apply", [
                    [record.resId],
                ]);
                await this._loadTares();
            },
        });
    }
}

export const remoteMeasureForm = {
    ...remoteMeasureField,
    component: RemoteMeasureForm,
    supportedOptions: [
        ...remoteMeasureField.supportedOptions,
        {
            label: _t("Tares"),
            name: "tares",
            type: "string",
        },
    ],
    extractProps({options}) {
        const props = remoteMeasureField.extractProps(...arguments);
        props.tares = options.tares || [];
        return props;
    },
};

registry.category("fields").add("remote_measure_form", remoteMeasureForm);
