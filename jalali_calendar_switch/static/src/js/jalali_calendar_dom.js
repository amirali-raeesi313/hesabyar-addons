/** @odoo-module **/
/*
 * Jalali overlay for the fullcalendar-based Calendar view.
 *
 * The calendar view renders Gregorian day numbers and month titles. This
 * module rewrites them to their Jalali equivalents using a MutationObserver,
 * based on the ISO dates fullcalendar puts in data-date attributes, so it is
 * independent of the calendar's internal JS framework and cannot break it.
 */
import { session } from "@web/session";

function isEnabled() {
    return !!session.use_jalali_calendar;
}

const FA_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
];

const DAY_FMT = new Intl.DateTimeFormat("fa-IR-u-ca-persian", { day: "numeric" });
const PARTS_FMT = new Intl.DateTimeFormat("en-US-u-ca-persian-nu-latn", {
    year: "numeric",
    month: "numeric",
    day: "numeric",
});

function parseISO(iso) {
    if (!iso) {
        return null;
    }
    const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
    return isNaN(d) ? null : d;
}

function jalaliParts(date) {
    const parts = {};
    for (const p of PARTS_FMT.formatToParts(date)) {
        if (p.type !== "literal") {
            parts[p.type] = parseInt(p.value, 10);
        }
    }
    return parts; // {year, month, day}
}

function faDigits(n) {
    return String(n).replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[d]);
}

let scheduled = false;

function updateCalendars() {
    scheduled = false;
    if (!isEnabled()) {
        return;
    }
    for (const fc of document.querySelectorAll(".o_calendar_container .fc")) {
        try {
            // Day numbers in the month grid.
            for (const cell of fc.querySelectorAll(".fc-daygrid-day[data-date]")) {
                const d = parseISO(cell.getAttribute("data-date"));
                if (!d) {
                    continue;
                }
                const numEl = cell.querySelector(".fc-daygrid-day-number");
                if (numEl) {
                    const jDay = DAY_FMT.format(d);
                    if (numEl.textContent !== jDay) {
                        numEl.textContent = jDay;
                    }
                }
            }
            // Column headers in week/day views.
            for (const th of fc.querySelectorAll(".fc-col-header-cell[data-date]")) {
                const d = parseISO(th.getAttribute("data-date"));
                if (!d) {
                    continue;
                }
                const cushion = th.querySelector(".fc-col-header-cell-cushion");
                if (cushion && !cushion.dataset.jalaliDone) {
                    const p = jalaliParts(d);
                    cushion.textContent = `${d.toLocaleDateString("fa-IR", { weekday: "short" })} ${faDigits(p.day)} ${FA_MONTHS[p.month - 1]}`;
                    cushion.dataset.jalaliDone = "1";
                }
            }
            // Toolbar title: derive the Jalali month(s) from visible day cells.
            const titleEl = fc.querySelector(".fc-toolbar-title");
            const dayCells = fc.querySelectorAll(".fc-daygrid-day[data-date]:not(.fc-day-other)");
            if (titleEl && dayCells.length) {
                const first = jalaliParts(parseISO(dayCells[0].getAttribute("data-date")));
                const last = jalaliParts(parseISO(dayCells[dayCells.length - 1].getAttribute("data-date")));
                let title;
                if (first.year === last.year && first.month === last.month) {
                    title = `${FA_MONTHS[first.month - 1]} ${faDigits(first.year)}`;
                } else if (first.year === last.year) {
                    title = `${FA_MONTHS[first.month - 1]} – ${FA_MONTHS[last.month - 1]} ${faDigits(first.year)}`;
                } else {
                    title = `${FA_MONTHS[first.month - 1]} ${faDigits(first.year)} – ${FA_MONTHS[last.month - 1]} ${faDigits(last.year)}`;
                }
                if (titleEl.textContent !== title) {
                    titleEl.textContent = title;
                }
            }
        } catch {
            // Never break the calendar view because of a display overlay.
        }
    }
}

function schedule() {
    if (!scheduled) {
        scheduled = true;
        requestAnimationFrame(updateCalendars);
    }
}

function startObserver() {
    try {
        if (typeof MutationObserver === "undefined" || !document.body) {
            return;
        }
        const observer = new MutationObserver((mutations) => {
            if (!isEnabled()) {
                return;
            }
            for (const m of mutations) {
                const t = m.target;
                // Ignore mutations we caused ourselves to avoid loops.
                if (t.nodeType === 1 && t.closest && t.closest(".fc")) {
                    schedule();
                    return;
                }
                if (t.nodeType === 3 && t.parentElement && t.parentElement.closest(".fc")) {
                    schedule();
                    return;
                }
            }
        });
        observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    } catch {
        // A display overlay must never break the web client.
    }
}

// The assets bundle executes in <head>, before <body> exists — wait for it.
if (document.body) {
    startObserver();
} else {
    document.addEventListener("DOMContentLoaded", startObserver);
}
