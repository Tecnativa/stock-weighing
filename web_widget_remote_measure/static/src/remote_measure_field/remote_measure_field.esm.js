/* Copyright 2023 Tecnativa - David Vidal
 * Copyright 2026 Tecnativa - Carlos Dauden
 * License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl). */
import {
    FloatField,
    floatField,
    floatFieldProps,
} from "@web/views/fields/float/float_field";
import {
    onMounted,
    onWillDestroy,
    onWillStart,
    onWillUnmount,
    proxy,
    t,
    useOnChange,
    useProps,
} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {rpc} from "@web/core/network/rpc";
import {useService} from "@web/core/utils/hooks";
import {user} from "@web/core/user";

export class RemoteMeasureField extends FloatField {
    static template = "web_widget_remote_measure.RemoteMeasureField";
    props = useProps({
        ...floatFieldProps,
        remote_device_field: t.string().optional(),
        uom_field: t.string().optional(),
        default_user_device: t.boolean().optional(),
        allow_additive_measure: t.boolean().optional(),
    });

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.amount = 0;
        this.remote_device_data = {};
        const setting =
            this.props.default_user_device && user.settings.remote_measure_device_id;
        this.default_user_device = Array.isArray(setting)
            ? setting[0]
            : (setting && setting.id) || setting || false;
        const record = this.props.record;
        // When we're in the own device, we already have the data
        if (record.resModel === "remote.measure.device" && record.resId) {
            this.remote_device_data.id = record.resId;
            this.uom = record.data.uom_id && {id: record.data.uom_id.id};
        } else if (this.props.remote_device_field) {
            const device = record.data[this.props.remote_device_field];
            this.remote_device_data.id = device && device.id;
        } else if (this.default_user_device) {
            this.remote_device_data.id = this.default_user_device;
        }
        if (!this.uom && this.props.uom_field) {
            const uom = record.data[this.props.uom_field];
            this.uom = uom && {id: uom.id};
        }
        this.default_ui_state = {
            stop: true,
            measuring: false,
            tick: false,
            // Additional class for colors and others
            class: "btn-secondary",
            input_val: this.value,
            start_add: false,
        };
        this.measureState = proxy({
            ...this.default_ui_state,
            additive_measure: false,
            device_name: false,
        });
        onMounted(() => {
            if (this.remote_device_data?.instant_read) {
                this.measure();
            }
        });
        onWillStart(async () => {
            await this._assignDevice();
        });
        // Reset states when we leave the button
        // Owl 3 effects take no dependencies: react to their changes instead
        useOnChange(
            () => [this.props.readonly],
            (readonly) => {
                if (readonly) {
                    this.measureState.stop = true;
                    this.measureState.measuring = false;
                }
            }
        );
        useOnChange(
            () => [this.value],
            (value) => {
                if (value > 0 && this.props.allow_additive_measure) {
                    this.measureState.additive_measure = true;
                }
            }
        );
        onWillDestroy(() => this._closeSocket());
        onWillUnmount(() => this._closeSocket());
    }

    /**
     * Getter to allow set extra measures to the main input
     */
    get extraMeasures() {
        return 0;
    }

    get hasDevice() {
        return Boolean(this.remote_device_data && this.remote_device_data.id);
    }

    // Private methods

    async _assignDevice() {
        if (!this.hasDevice || !this.uom || !this.uom.id) {
            return;
        }
        [this.uom] = await this.orm.read("uom.uom", [this.uom.id], ["factor", "name"]);
        [this.remote_device_data] = await this.orm.read(
            "remote.measure.device",
            [this.remote_device_data.id],
            [
                "name",
                "host",
                "protocol",
                "connection_mode",
                "uom_id",
                "uom_factor",
                "instant_read",
                "non_stop_read",
                "read_interval",
            ]
        );
        this._assigDeviceData();
    }

    /**
     * @private
     */
    _assigDeviceData() {
        if (!this.remote_device_data) {
            return;
        }
        Object.assign(this, {
            host: this.remote_device_data.host,
            protocol: this.remote_device_data.protocol,
            connection_mode: this.remote_device_data.connection_mode,
            device_uom: this.remote_device_data.uom_id[0],
        });
        this.measureState.device_name = this.remote_device_data.name;
    }

    /**
     * @override
     * @param {Event} ev
     * Auto select all the content
     */
    onFocusIn(ev) {
        super.onFocusIn(...arguments);
        ev.target.select();
    }
    /**
     * @override
     * Ensure that the socket is close
     */
    onFocusOut() {
        super.onFocusOut(...arguments);
        this._closeSocket();
    }

    // UX Methods

    async measure() {
        this.measureState.stop = false;
        this.measureState.measuring = true;
        await this[`_connect_to_${this.connection_mode}`]();
    }
    /**
     * Stop requesting measures from device
     */
    measure_stop() {
        this._closeSocket();
        this.measureState.stop = true;
        this.measureState.measuring = false;
        this._awaitingMeasure();
        this._recordMeasure();
    }
    /**
     * Start requesting measures from the remote device
     */
    onMeasure() {
        this.measure();
    }
    onMeasureAdd() {
        this.measureState.start_add = true;
        this.measure();
    }
    /**
     * Validate the requested measure
     */
    onValidateMeasure() {
        this.measure_stop();
    }

    /**
     * Once we consider the measure is stable render the button as green
     */
    _stableMeasure() {
        this.measureState.class = "btn-success";
    }
    /**
     * While a measure is not stable the button will be red
     */
    _unstableMeasure() {
        this.measureState.class = "btn-danger";
    }
    /**
     * While the widget isn't querying it will be purple as a signal that we can start
     */
    _awaitingMeasure() {
        Object.assign(this.measureState, this.default_ui_state);
    }
    /**
     * Set the field measure in the field
     */
    _recordMeasure() {
        this.measureState.start_add = false;
        this.measureState.input_val = this.amount;
    }
    /**
     * Convert the measured units to the units expected by the record. The
     * factors of 20.0 are the quantity of the reference unit in each unit.
     * @param {Number} amount
     * @returns {Number} converted amount
     */
    _compute_quantity(amount) {
        if (!this.uom || this.uom.id === this.device_uom) {
            return amount;
        }
        return (amount * this.remote_device_data.uom_factor) / this.uom.factor;
    }
    /**
     * Set value
     */
    async _setMeasure() {
        if (isNaN(this.amount)) {
            return;
        }
        this.amount = this._compute_quantity(this.amount);
        if (this.measureState.start_add) {
            this.amount += this.measureState.input_val;
        }
        this.props.record.update({[this.props.name]: this.amount + this.extraMeasures});
    }
    /**
     * Show that a measure was received
     */
    nextStateIcon() {
        this.measureState.tick = !this.measureState.tick;
    }

    // Connection methods

    /**
     * F501 Protocol response:
     * [STX][status1][status2][data][ETX]
     * - status1 beign weight status: \x20 (space) for stable weight and ? for unstable
     * - status2 beign weight sign: + for positive and - for negative.
     * - data being the weight itself with 6 characters for weight and one . for the
     *   decimal dot
     *
     * @param {String} msg ASCII string
     * @returns {Object} with the value and the stable flag
     */
    _proccess_msg_f501(msg) {
        return {
            stable: msg[1] === "\x20",
            value: parseFloat(msg.slice(2, 10)),
        };
    }

    /**
     * Implemented for a continous remote stream
     */
    async _connect_to_websockets() {
        try {
            this.socket = new WebSocket(this.host);
        } catch (error) {
            // Avoid websockets security error. Local devices won't have wss normally
            if (error.code === 18) {
                return;
            }
            throw error;
        }
        var stream_success_counter = 10;
        this.socket.onmessage = async (msg) => {
            const data = await msg.data.text();
            const processed_data = this[`_proccess_msg_${this.protocol}`](data);
            if (processed_data.stable) {
                this._stableMeasure();
                if (!stream_success_counter) {
                    this._closeSocket();
                    this._awaitingMeasure();
                    this._recordMeasure();
                    return;
                }
            } else {
                stream_success_counter = 5;
                this._unstableMeasure();
            }
            if (stream_success_counter) {
                --stream_success_counter;
            }
            this.nextStateIcon();
            this.amount = processed_data.value;
            this._setMeasure();
        };
        this.socket.onerror = () => {
            this._awaitingMeasure();
        };
    }
    /**
     * Send read params to the remote device
     * @returns {Object}
     */
    _read_from_device_tcp_params() {
        return {command: false};
    }
    /**
     * Process call
     * @returns {Number}
     */
    async _read_from_device_tcp() {
        const data = await rpc(
            `/remote_measure_device/${this.remote_device_data.id}`,
            this._read_from_device_tcp_params()
        );
        if (!data) {
            return null;
        }
        const processed_data = this[`_proccess_msg_${this.protocol}`](data);
        if (isNaN(processed_data.value)) {
            processed_data.value = 0;
        }
        return processed_data;
    }
    /**
     * Connect to the local controller, which makes the direct connection to the
     * scale.
     */
    async _connect_to_tcp() {
        var stream_success_counter = 20;
        this._unstableMeasure();
        // Used to set the read interval if any
        const timer = (ms) => new Promise((res) => setTimeout(res, ms));
        // Don't keep going forever unless non stop reading
        for (
            let attemps_left = this.remote_device_data.non_stop_read ? Infinity : 1000;
            attemps_left > 0;
            attemps_left--
        ) {
            // Allow to break the loop manually
            if (this.measureState.stop) {
                break;
            }
            const processed_data = await this._read_from_device_tcp();
            if (!processed_data) {
                continue;
            }
            if (processed_data.stable) {
                this._stableMeasure();
            } else {
                this._unstableMeasure();
                stream_success_counter = 20;
            }
            if (processed_data.stable && stream_success_counter <= 0) {
                this._stableMeasure();
                this._awaitingMeasure();
                this._recordMeasure();
                break;
            } else if (this.remote_device_data.non_stop_read) {
                stream_success_counter = 20;
                this._recordMeasure();
            }
            if (stream_success_counter) {
                --stream_success_counter;
            }
            this.nextStateIcon();
            this.amount = processed_data.value;
            this._setMeasure();
            // Set sleep interval
            if (this.remote_device_data.read_interval) {
                await timer(this.remote_device_data.read_interval);
            }
        }
    }
    /**
     * Implement for your device protocol service
     */
    _connect_to_webservices() {
        return;
    }
    /**
     * Procure to close the socket whenever the widget stops being used
     */
    _closeSocket() {
        if (this.socket) {
            this.socket.close();
            this.socket = undefined;
        }
    }
}

export const remoteMeasureField = {
    ...floatField,
    component: RemoteMeasureField,
    supportedOptions: [
        ...floatField.supportedOptions,
        {
            label: _t("UoM"),
            name: "uom_field",
            type: "field",
            availableTypes: ["many2one"],
        },
        {
            label: _t("Remote device"),
            name: "remote_device_field",
            type: "field",
            availableTypes: ["many2one"],
        },
        {
            label: _t("Use default device"),
            name: "default_user_device",
            type: "boolean",
        },
        {
            label: _t("Additive Measure"),
            name: "allow_additive_measure",
            type: "boolean",
        },
    ],
    extractProps({options}) {
        const props = floatField.extractProps(...arguments);
        props.remote_device_field = options.remote_device_field;
        props.uom_field = options.uom_field;
        props.default_user_device = options.default_user_device;
        props.allow_additive_measure = options.allow_additive_measure;
        return props;
    },
};

registry.category("fields").add("remote_measure", remoteMeasureField);
