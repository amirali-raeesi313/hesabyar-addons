# -*- coding: utf-8 -*-
"""ERP Autopilot: management-by-exception dashboard data + conversational manager."""
import html as html_lib
import json
import logging
import re
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AiAutopilot(models.AbstractModel):
    _name = "ai.autopilot"
    _description = "اتوپایلوت ERP"

    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_data(self):
        """Live data for the 4-section autopilot dashboard. All real queries."""
        env = self.env
        today = fields.Date.context_today(self)

        def cnt(model, domain):
            try:
                return env[model].search_count(domain)
            except Exception:
                return 0

        # ---- ۱) کارهای خودکار امروز (شمارش واقعی) ----
        auto_ops = [
            {"label": "سند حسابداری ثبت‌شده امروز", "count": cnt("account.move", [("date", "=", str(today)), ("state", "=", "posted")]),
             "model": "account.move", "domain": [["date", "=", str(today)], ["state", "=", "posted"]]},
            {"label": "انتقال انبار انجام‌شده امروز", "count": cnt("stock.picking", [("date_done", ">=", str(today))]),
             "model": "stock.picking", "domain": [["date_done", ">=", str(today)]]},
            {"label": "پرداخت ثبت‌شده امروز", "count": cnt("account.payment", [("date", "=", str(today))]),
             "model": "account.payment", "domain": [["date", "=", str(today)]]},
            {"label": "تحلیل هوشمند سند (AI)", "count": cnt("ai.document.capture", [("create_date", ">=", str(today))]),
             "model": "ai.document.capture", "domain": []},
            {"label": "قانون اتوماسیون فعال", "count": cnt("base.automation", [("active", "=", True)]),
             "model": "base.automation", "domain": []},
        ]

        # ---- ۲) نیازمند تصمیم مدیر ----
        approvals = [
            {"label": "سفارش خرید در انتظار تأیید", "count": cnt("purchase.order", [("state", "=", "to approve")]),
             "model": "purchase.order", "domain": [["state", "=", "to approve"]]},
            {"label": "فاکتور پیش‌نویس (نیازمند نهایی‌سازی)", "count": cnt("account.move", [("state", "=", "draft"), ("move_type", "in", ["in_invoice", "out_invoice"])]),
             "model": "account.move", "domain": [["state", "=", "draft"], ["move_type", "in", ["in_invoice", "out_invoice"]]]},
            {"label": "سند هوشمند در انتظار تأیید حسابدار", "count": cnt("ai.document.capture", [("state", "=", "analyzed")]),
             "model": "ai.document.capture", "domain": [["state", "=", "analyzed"]]},
            {"label": "درخواست مرخصی در انتظار", "count": cnt("hr.leave", [("state", "in", ["confirm", "validate1"])]),
             "model": "hr.leave", "domain": [["state", "in", ["confirm", "validate1"]]]},
        ]

        # ---- ۳) استثناها و خطرها ----
        Alert = env["ai.audit.alert"]
        open_alerts = Alert.search([("state", "=", "new")], limit=6, order="id desc")
        exceptions = {
            "critical": cnt("ai.audit.alert", [("state", "=", "new"), ("severity", "=", "critical")]),
            "warning": cnt("ai.audit.alert", [("state", "=", "new"), ("severity", "=", "warning")]),
            "info": cnt("ai.audit.alert", [("state", "=", "new"), ("severity", "=", "info")]),
            "items": [{"id": a.id, "name": a.name, "severity": a.severity,
                       "reason": (a.reason or "")[:120], "suggestion": (a.suggestion or "")[:120]}
                      for a in open_alerts],
        }

        # ---- ۴) پیشنهادهای هوشمند (آخرین پیام کانال‌های AI) ----
        suggestions = []
        for ch_name in ["📈 مشاور مالی هوشمند", "🧾 دستیار مالیاتی", "🔍 بازرس هوشمند"]:
            ch = env["discuss.channel"].sudo().search([("name", "=", ch_name)], limit=1)
            if ch:
                msg = env["mail.message"].sudo().search([("res_id", "=", ch.id), ("model", "=", "discuss.channel")],
                                                        limit=1, order="id desc")
                if msg:
                    body = html_lib.unescape(msg.body or "")
                    body = re.sub(r"<[^>]+>", " ", body)
                    body = re.sub(r"\s+", " ", body)
                    suggestions.append({"source": ch_name, "text": body.strip()[:220],
                                        "date": str(msg.date or "")[:10]})
        low_stock = cnt("stock.warehouse.orderpoint", [("qty_forecast", "<", 0)])
        if low_stock:
            suggestions.append({"source": "🏭 انبار", "date": str(today),
                                "text": "%s کالا زیر نقطه سفارش مجدد است — پیشنهاد خرید/تولید فعال شده." % low_stock})

        return {
            "date": str(today),
            "auto_ops": auto_ops,
            "auto_total": sum(x["count"] for x in auto_ops),
            "approvals": approvals,
            "approval_total": sum(x["count"] for x in approvals),
            "exceptions": exceptions,
            "suggestions": suggestions,
        }

    # ------------------------------------------------------------------
    @api.model
    def ask(self, question):
        """Conversational manager: answers with live company data as context."""
        question = (question or "").strip()
        if not question:
            return "سؤالی بنویسید."
        try:
            figures = self.env["ai.finance.advisor"]._gather_figures()
            alerts = self.env["ai.audit.alert"].search([("state", "=", "new")], limit=8, order="id desc")
            data = self.get_dashboard_data()
            context = {
                "ارقام مالی": {k: round(v) for k, v in figures.items()},
                "استثناهای باز": [{"عنوان": a.name, "شدت": a.severity, "شرح": (a.reason or "")[:150]} for a in alerts],
                "در انتظار تأیید": {x["label"]: x["count"] for x in data["approvals"]},
                "عملیات امروز": {x["label"]: x["count"] for x in data["auto_ops"]},
            }
            return self.env["ai.deepseek.client"].chat(
                "تو «مدیر هوشمند» یک ERP ایرانی هستی. با داده‌های واقعی شرکت که به تو داده می‌شود به فارسی، "
                "کوتاه و اجرایی پاسخ بده. اگر سؤال شرطی است شبیه‌سازی عددی کن. اگر اقدامی لازم است، "
                "دقیقاً بگو در کدام منوی سیستم انجام شود. مبالغ به ریال است. هرگز عدد از خودت نساز؛ "
                "فقط از داده‌های زیر استفاده کن و اگر داده‌ای نداری صادقانه بگو.",
                "داده‌های زنده شرکت:\n%s\n\nپیام مدیر: %s" % (
                    json.dumps(context, ensure_ascii=False, default=str), question),
                max_tokens=1200,
            )
        except Exception as e:
            _logger.exception("autopilot ask failed")
            return "خطا: %s" % e
