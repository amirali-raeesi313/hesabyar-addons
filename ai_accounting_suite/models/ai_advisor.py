# -*- coding: utf-8 -*-
import json
import logging
from datetime import date, timedelta

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class AiFinanceAdvisor(models.TransientModel):
    _name = "ai.finance.advisor"
    _description = "مشاور مالی هوشمند"

    summary_html = fields.Html("وضعیت لحظه‌ای", readonly=True)
    question = fields.Text("سؤال شما", help="مثال: اگر فروش ۲۰٪ کم شود سود خالص چه می‌شود؟")
    answer = fields.Html("پاسخ مشاور", readonly=True)

    @api.model
    def _gather_figures(self):
        aml = self.env["account.move.line"]
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)

        def s(domain, field="balance"):
            res = aml.read_group([("parent_state", "=", "posted")] + domain, [field], [])
            return res[0][field] or 0.0 if res else 0.0

        figures = {
            "موجودی نقد و بانک": s([("journal_id.type", "in", ["bank", "cash"])]),
            "حساب‌های دریافتنی (طلب از مشتریان)": s([("account_id.account_type", "=", "asset_receivable")]),
            "حساب‌های پرداختنی (بدهی به تامین‌کنندگان)": -s([("account_id.account_type", "=", "liability_payable")]),
            "درآمد از ابتدای ماه": -s([("account_id.account_type", "in", ["income", "income_other"]),
                                        ("date", ">=", str(month_start))]),
            "هزینه از ابتدای ماه": s([("account_id.account_type", "in", ["expense", "expense_depreciation", "expense_direct_cost"]),
                                       ("date", ">=", str(month_start))]),
            "درآمد از ابتدای سال": -s([("account_id.account_type", "in", ["income", "income_other"]),
                                        ("date", ">=", str(year_start))]),
            "هزینه از ابتدای سال": s([("account_id.account_type", "in", ["expense", "expense_depreciation", "expense_direct_cost"]),
                                       ("date", ">=", str(year_start))]),
        }
        figures["سود/زیان خالص سال (تقریبی)"] = figures["درآمد از ابتدای سال"] - figures["هزینه از ابتدای سال"]
        return figures

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        figures = self._gather_figures()
        rows = "".join(
            "<tr><td style='padding:4px 10px'>%s</td>"
            "<td style='padding:4px 10px;text-align:left;direction:ltr'><b>%s</b> ریال</td></tr>"
            % (k, f"{v:,.0f}") for k, v in figures.items()
        )
        res["summary_html"] = (
            "<table style='width:100%%;border-collapse:collapse'>%s</table>"
            "<p style='color:#888;font-size:12px'>محاسبه‌شده به‌صورت زنده از اسناد ثبت‌شده — %s</p>"
        ) % (rows, fields.Date.context_today(self))
        return res

    def action_ask(self):
        self.ensure_one()
        if not (self.question or "").strip():
            return self._reopen()
        figures = self._gather_figures()
        answer = self.env["ai.deepseek.client"].chat(
            "تو یک مشاور مالی ارشد ایرانی هستی. بر اساس ارقام واقعی شرکت که به تو داده می‌شود، "
            "به سؤال مدیر پاسخ بده. اگر سؤال شرطی است (چه می‌شود اگر...)، شبیه‌سازی عددی کن و "
            "محاسباتت را مرحله به مرحله نشان بده. مبالغ به ریال هستند. کوتاه، دقیق و کاربردی جواب بده.",
            "ارقام فعلی شرکت:\n%s\n\nسؤال مدیر: %s" % (
                json.dumps(figures, ensure_ascii=False, indent=1), self.question),
            max_tokens=1500,
        )
        self.answer = "<div style='white-space:pre-wrap'>%s</div>" % answer
        return self._reopen()

    def _reopen(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    # ------------------------------------------------------------------
    @api.model
    def _cron_weekly_report(self):
        """Weekly cash-flow forecast + narrative for the manager."""
        aml = self.env["account.move.line"]
        today = fields.Date.context_today(self)

        # last 12 months net cash movement
        groups = aml.read_group(
            [("parent_state", "=", "posted"),
             ("journal_id.type", "in", ["bank", "cash"]),
             ("date", ">=", str(today - timedelta(days=365)))],
            ["balance"], ["date:month"])
        series = [(g["date:month"], g["balance"] or 0.0) for g in groups]

        # simple linear trend forecast for next 6 months
        forecast = []
        if series:
            ys = [v for (_k, v) in series]
            n = len(ys)
            xs = list(range(n))
            mean_x = sum(xs) / n
            mean_y = sum(ys) / n
            denom = sum((x - mean_x) ** 2 for x in xs) or 1
            slope = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n)) / denom
            base = sum(ys[-3:]) / min(3, n)
            forecast = [round(base + slope * (i + 1)) for i in range(6)]

        ar_due = aml.read_group(
            [("parent_state", "=", "posted"),
             ("account_id.account_type", "=", "asset_receivable"),
             ("amount_residual", "!=", 0),
             ("date_maturity", "<=", str(today + timedelta(days=60)))],
            ["amount_residual"], [])
        ap_due = aml.read_group(
            [("parent_state", "=", "posted"),
             ("account_id.account_type", "=", "liability_payable"),
             ("amount_residual", "!=", 0),
             ("date_maturity", "<=", str(today + timedelta(days=60)))],
            ["amount_residual"], [])
        data = {
            "گردش خالص نقد ماهانه (۱۲ ماه اخیر)": {k: round(v) for k, v in series},
            "پیش‌بینی خالص ۶ ماه آینده": forecast,
            "مطالبات سررسید ۶۰ روز آینده": round(ar_due[0]["amount_residual"] or 0) if ar_due else 0,
            "بدهی‌های سررسید ۶۰ روز آینده": round(-(ap_due[0]["amount_residual"] or 0)) if ap_due else 0,
            "ارقام کلی": {k: round(v) for k, v in self._gather_figures().items()},
        }
        body = "📈 گزارش هفتگی مشاور مالی — %s" % today
        try:
            if self.env["ir.config_parameter"].sudo().get_param("ai_suite.deepseek_api_key"):
                narrative = self.env["ai.deepseek.client"].chat(
                    "تو مشاور مالی شرکت هستی. بر اساس داده‌های زیر یک گزارش هفتگی کوتاه فارسی برای مدیر بنویس: "
                    "وضعیت کلی، پیش‌بینی نقدینگی، ریسک‌ها و ۲-۳ توصیه عملی. ساده و بدون اصطلاحات پیچیده. مبالغ ریال است.",
                    json.dumps(data, ensure_ascii=False, default=str), max_tokens=1200)
                body += "\n\n" + narrative
            else:
                body += "\n" + json.dumps(data, ensure_ascii=False, default=str)
        except Exception:
            _logger.exception("weekly narrative failed")
            body += "\n" + json.dumps(data, ensure_ascii=False, default=str)
        self.env["ai.audit.alert"]._post_to_channel("📈 مشاور مالی هوشمند", body.replace("\n", "<br/>"))
        return True
