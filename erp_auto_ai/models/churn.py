# -*- coding: utf-8 -*-
"""تشخیص ریسک ریزش مشتری.

روش قطعی: برای هر مشتری با حداقل ۲ خرید، میانگین فاصله‌ی خرید محاسبه و با
مدت گذشته از آخرین خرید مقایسه می‌شود. نسبت > ۱.۵ = در معرض ریزش.
"""
import logging
from collections import defaultdict

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class ErpAutoChurn(models.Model):
    _name = "erp.auto.churn"
    _description = "ریسک ریزش مشتری"
    _order = "churn_score desc"

    partner_id = fields.Many2one("res.partner", string="مشتری", required=True, index=True)
    order_count = fields.Integer("تعداد خرید")
    last_order_date = fields.Date("آخرین خرید")
    avg_interval_days = fields.Float("میانگین فاصله خرید (روز)")
    days_since = fields.Integer("روز از آخرین خرید")
    churn_score = fields.Float("امتیاز ریزش", help="روزِ گذشته ÷ میانگین فاصله؛ >۱.۵ پرریسک")
    risk_level = fields.Selection([
        ("low", "کم"),
        ("medium", "متوسط"),
        ("high", "زیاد"),
    ], string="سطح ریسک", default="low", index=True)
    total_invoiced = fields.Monetary("مجموع خرید", currency_field="currency_id")
    currency_id = fields.Many2one("res.currency",
                                  default=lambda self: self.env.company.currency_id)
    reason = fields.Text("توضیح")
    computed_on = fields.Date("تاریخ محاسبه", default=fields.Date.context_today)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    _sql_constraints = [
        ("partner_uniq", "unique(partner_id, company_id)",
         "برای هر مشتری فقط یک رکورد ریزش نگهداری می‌شود."),
    ]

    @api.model
    def generate(self, min_orders=2):
        """(باز)تولید امتیاز ریزش برای مشتریان دارای سابقه‌ی خرید. Idempotent."""
        today = fields.Date.context_today(self)
        moves = self.env["account.move"].search([
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("partner_id", "!=", False),
        ])
        by_partner = defaultdict(list)
        totals = defaultdict(float)
        for mv in moves:
            if mv.invoice_date:
                by_partner[mv.partner_id].append(mv.invoice_date)
                totals[mv.partner_id] += mv.amount_total_signed

        result = self.browse()
        for partner, dates in by_partner.items():
            if len(dates) < min_orders:
                continue
            dates = sorted(dates)
            intervals = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
            avg_interval = sum(intervals) / len(intervals) if intervals else 0
            days_since = (today - dates[-1]).days
            score = (days_since / avg_interval) if avg_interval else 0.0
            if score >= 2.5:
                risk = "high"
            elif score >= 1.5:
                risk = "medium"
            else:
                risk = "low"
            reason = _("%d خرید، میانگین فاصله %.0f روز، %d روز از آخرین خرید گذشته "
                       "(نسبت %.1f).") % (len(dates), avg_interval, days_since, score)
            vals = {
                "partner_id": partner.id,
                "order_count": len(dates),
                "last_order_date": dates[-1],
                "avg_interval_days": avg_interval,
                "days_since": days_since,
                "churn_score": round(score, 2),
                "risk_level": risk,
                "total_invoiced": totals[partner],
                "reason": reason,
                "computed_on": today,
            }
            existing = self.search([("partner_id", "=", partner.id)], limit=1)
            if existing:
                existing.write(vals)
                result |= existing
            else:
                result |= self.create(vals)

        high = result.filtered(lambda r: r.risk_level == "high")
        if high:
            self.env["erp.auto.audit.log"].log(
                _("%d مشتری در معرض ریزش شدید شناسایی شد") % len(high),
                action="ai", source="ai")
        return result

    def action_create_followup(self):
        """ایجاد فعالیت پیگیری برای مشتری در معرض ریزش."""
        act_type = self.env.ref("mail.mail_activity_data_call", raise_if_not_found=False) \
            or self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        partner_model_id = self.env["ir.model"]._get_id("res.partner")
        for rec in self:
            if not act_type:
                continue
            self.env["mail.activity"].create({
                "activity_type_id": act_type.id,
                "res_model_id": partner_model_id,
                "res_id": rec.partner_id.id,
                "summary": _("پیگیری مشتری در معرض ریزش (هوش پیش‌بین)"),
                "note": rec.reason,
                "user_id": self.env.uid,
                "date_deadline": fields.Date.context_today(self),
            })
            self.env["erp.auto.audit.log"].log(
                _("پیگیری ریزش برای %s ایجاد شد") % rec.partner_id.display_name,
                record=rec.partner_id, action="ai", source="ai")

    @api.model
    def _cron_generate(self):
        self.generate()
        return True
