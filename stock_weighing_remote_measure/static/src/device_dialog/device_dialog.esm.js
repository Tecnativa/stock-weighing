/* Copyright 2024 Tecnativa - David Vidal
 * Copyright 2026 Tecnativa - Carlos Dauden
 * License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html). */
import {Component, onWillStart, t, useProps} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {useService} from "@web/core/utils/hooks";
import {user} from "@web/core/user";

export class DeviceDialog extends Component {
    static template = "stock_weighing_remote_measure.DeviceDialog";
    static components = {Dialog};
    props = useProps({
        close: t.function(),
        device_field: t.object(),
    });

    setup() {
        this.orm = useService("orm");
        onWillStart(async () => {
            this.devices = await this.orm.searchRead(
                "remote.measure.device",
                [],
                ["id", "name"]
            );
        });
    }

    async onClickDevice(device) {
        await this.orm.write("res.users", [user.userId], {
            remote_measure_device_id: device.id,
        });
        const field = this.props.device_field;
        field.remote_device_data = {id: device.id};
        field.uom = field.uom && {id: field.uom.id};
        await field._assignDevice();
        this.props.close();
    }
}
