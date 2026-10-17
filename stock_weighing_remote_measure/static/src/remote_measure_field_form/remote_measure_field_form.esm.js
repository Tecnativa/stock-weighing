/* Copyright 2024 Tecnativa - David Vidal
 * Copyright 2026 Tecnativa - Carlos Dauden
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html). */
import {
    RemoteMeasureField,
    remoteMeasureField,
} from "@web_widget_remote_measure/remote_measure_field/remote_measure_field.esm";
import {t, useProps} from "@odoo/owl";
import {DeviceDialog} from "../device_dialog/device_dialog.esm";
import {_t} from "@web/core/l10n/translation";
import {floatFieldProps} from "@web/views/fields/float/float_field";
import {formatFloat} from "@web/views/fields/formatters";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

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
        this.manualTare = 0;
        this.formatFloat = (value) =>
            formatFloat(value, {
                digits: this.props.record.fields[this.props.name].digits,
            });
        this.colors = ["success", "info", "warning", "danger", "primary"];
    }

    get extraMeasures() {
        return super.extraMeasures + this.measureState.tare;
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
