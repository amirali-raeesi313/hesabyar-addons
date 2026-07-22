# -*- coding: utf-8 -*-
import json
import logging
from datetime import timedelta

from odoo import api, fields, models, _

from .deepseek_client import gregorian_to_jalali, jalali_to_gregorian

_logger = logging.getLogger(__name__)


class AiTaxAssistant(models.AbstractModel):
    _name = "ai.tax.assistant"
    _description = "دستیار مالیاتی هوشمند"

    @api.model
    def _cron_monthly_vat_draft(self):
        """Draft VAT (ارزش افزوده) summary for the previous Jalali month."""
        today = fields.Date.context_today(self)
        jy, jm, _jd = gregorian_to_jalali(today.year, today.month, today.day)
        # previous jalali month
        pjm, pjy = (jm - 1, jy) if jm > 1 else (12, jy - 1)
        gy1, gm1, gd1 = jalali_to_gregorian(pjy, pjm, 1)
        days = 31 if pjm <= 6 else 30 if pjm <= 11 else 29
        gy2, gm2, gd2 = jalali_to_gregorian(pjy, pjm, days)
        d1 = "%04d-%02d-%02d" % (gy1, gm1, gd1)
        d2 = "%04d-%02d-%02d" % (gy2, gm2, gd2)

        aml = self.env["account.move.line"]
        res = {}
        for use, label in [("sale", "مالیات فروش (خروجی)"), ("purchase", "مالیات خرید (ورودی)")]:
            g = aml.read_group(
                [("parent_state", "=", "posted"),
                 ("tax_line_id.type_tax_use", "=", use),
                 ("date", ">=", d1), ("date", "<=", d2)],
                ["balance", "tax_base_amount"], [])
            bal = (g[0]["balance"] or 0.0) if g else 0.0
            base = (g[0]["tax_base_amount"] or 0.0) if g else 0.0
            res[label] = {"مالیات": round(abs(bal)), "مأخذ": round(abs(base))}
        payable = res["مالیات فروش (خروجی)"]["مالیات"] - res["مالیات خرید (ورودی)"]["مالیات"]

        body = "🧾 پیش‌نویس اظهارنامه ارزش افزوده — %s/%02d\n" % (pjy, pjm)
        body += "بازه میلادی: %s تا %s\n" % (d1, d2)
        body += json.dumps(res, ensure_ascii=False, indent=1)
        body += "\nمانده قابل پرداخت (فروش - خرید): %s ریال" % f"{payable:,.0f}"
        try:
            if self.env["ir.config_parameter"].sudo().get_param("ai_suite.deepseek_api_key"):
                note = self.env["ai.deepseek.client"].chat(
                    "تو مشاور مالیاتی ایرانی هستی. بر اساس خلاصه ارزش افزوده زیر، یک یادداشت کوتاه فارسی بنویس: "
                    "چه مبلغی باید در سامانه اظهار شود، مهلت قانونی اظهارنامه فصلی، و هر نکته مهم. "
                    "یادآوری کن که ارقام پیش‌نویس است و حسابدار باید تأیید کند.",
                    body, max_tokens=600)
                body += "\n\n🤖 " + note
        except Exception:
            _logger.exception("vat note failed")
        self.env["ai.audit.alert"]._post_to_channel("🧾 دستیار مالیاتی", body.replace("\n", "<br/>"))
        return True


class AiInsuranceExportWizard(models.TransientModel):
    _name = "ai.insurance.export.wizard"
    _description = "خروجی لیست بیمه ماهانه"

    jyear = fields.Integer("سال شمسی", required=True,
                           default=lambda self: self._default_jalali()[0])
    jmonth = fields.Selection(
        [(str(i), n) for i, n in enumerate(
            ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
             "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"], start=1)],
        string="ماه", required=True,
        default=lambda self: str(self._default_jalali()[1]))

    def _default_jalali(self):
        today = fields.Date.context_today(self)
        jy, jm, _jd = gregorian_to_jalali(today.year, today.month, today.day)
        return jy, jm

    def action_export(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": "/ai_suite/insurance_list?jyear=%s&jmonth=%s" % (self.jyear, int(self.jmonth)),
            "target": "new",
        }
