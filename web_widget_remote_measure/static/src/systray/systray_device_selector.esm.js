/* Copyright 2025 Tecnativa - Carlos Roca
 * License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl). */
import {Component, onWillStart} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {user} from "@web/core/user";

export class SelectRemoteDeviceMenu extends Component {
    static template = "web_widget_remote_measure.RemoteDeviceSelectorButton";
    setup() {
        this.action = useService("action");
        onWillStart(async () => {
            this.isRemoteDeviceUser = await user.hasGroup(
                "web_widget_remote_measure.remote_device_button_group"
            );
        });
    }

    /**
     * Select the remote device of the user
     * @private
     */
    async onClickSelectRemoteDevice() {
        const action = await this.action.loadAction(
            "web_widget_remote_measure.action_user_remote_device_selector"
        );
        action.res_id = user.userId;
        this.action.doAction(action);
    }
}

registry
    .category("systray")
    .add(
        "web_widget_remote_measure.remote_device_selector_button",
        {Component: SelectRemoteDeviceMenu},
        {sequence: 100}
    );
