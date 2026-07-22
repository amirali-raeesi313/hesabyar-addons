/** @odoo-module **/
/*
 * Jalali (Shamsi) display for date/datetime values.
 *
 * Overrides the "date" and "datetime" entries of the formatters registry so
 * that list, kanban and other read-only renderings show Jalali dates when the
 * current user has enabled the "Use Jalali Calendar" preference.
 *
 * Conversion relies on the browser's Intl API (ca-persian), so no external
 * library is required and the conversion is always astronomically correct.
 */
import { registry } from "@web/core/registry";
import { session } from "@web/session";

const formatters = registry.category("formatters");

function isEnabled() {
    return !!session.use_jalali_calendar;
}

const JALALI_DATE = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
});
const JALALI_TIME = new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
});

function toJSDate(value) {
    // value is a luxon DateTime in Odoo 17/18 formatters
    if (value && typeof value.toJSDate === "function") {
        return value.toJSDate();
    }
    return value instanceof Date ? value : null;
}

export function formatJalaliDate(value) {
    const d = toJSDate(value);
    return d ? JALALI_DATE.format(d) : "";
}

export function formatJalaliDateTime(value) {
    const d = toJSDate(value);
    return d ? `${JALALI_DATE.format(d)} ${JALALI_TIME.format(d)}` : "";
}

const origDate = formatters.get("date");
const origDatetime = formatters.get("datetime");

formatters.add(
    "date",
    (value, options) => {
        if (isEnabled() && value) {
            try {
                return formatJalaliDate(value);
            } catch {
                /* fall through to the original formatter */
            }
        }
        return origDate(value, options);
    },
    { force: true }
);

formatters.add(
    "datetime",
    (value, options) => {
        if (isEnabled() && value) {
            try {
                return formatJalaliDateTime(value);
            } catch {
                /* fall through to the original formatter */
            }
        }
        return origDatetime(value, options);
    },
    { force: true }
);
