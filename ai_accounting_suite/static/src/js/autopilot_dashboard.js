/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class AutopilotDashboard extends Component {
    static template = "ai_accounting_suite.AutopilotDashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            data: null,
            error: "",
            question: "",
            answer: "",
            asking: false,
        });
        onWillStart(async () => {
            await this.reload();
        });
    }

    async reload() {
        try {
            this.state.data = await this.orm.call("ai.autopilot", "get_dashboard_data", []);
            this.state.error = "";
        } catch (e) {
            this.state.error = (e.data && e.data.message) || String(e);
        }
    }

    openList(item) {
        if (!item.model) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: item.label || item.name,
            res_model: item.model,
            views: [[false, "list"], [false, "form"]],
            domain: item.domain || [],
            target: "current",
        });
    }

    openExceptions() {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "استثناها",
            res_model: "ai.audit.alert",
            views: [[false, "list"], [false, "form"]],
            domain: [["state", "=", "new"]],
        });
    }

    async ask() {
        const q = this.state.question.trim();
        if (!q || this.state.asking) {
            return;
        }
        this.state.asking = true;
        this.state.answer = "";
        try {
            this.state.answer = await this.orm.call("ai.autopilot", "ask", [q]);
        } catch (e) {
            this.state.answer = "خطا: " + ((e.data && e.data.message) || e);
        } finally {
            this.state.asking = false;
        }
    }

    onKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.ask();
        }
    }
}

registry.category("actions").add("ai_autopilot_dashboard", AutopilotDashboard);
