# -*- coding: utf-8 -*-
"""کرون‌های جریان کار: پیگیری پیش‌فاکتور راکد + هشدار انقضای کالا."""
import logging
from datetime import timedelta

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class AiAuditAlert(models.Model):
    _inherit = "ai.audit.alert"

    exception_type = fields.Selection(
        selection_add=[("expiry", "نزدیک انقضا")],
        ondelete={"expiry": "set default"})


class ErpAutoFlows(models.AbstractModel):
    _name = "erp.auto.flows"
    _description = "اتوماسیون‌های جریان کار حساب‌یار"

    @api.model
    def _param_int(self, key, default):
        icp = self.env["ir.config_parameter"].sudo()
        try:
            return int(icp.get_param(key, str(default)) or default)
        except ValueError:
            return default

    # ------------------------------------------------------------------
    @api.model
    def _cron_stale_quotes(self):
        """پیش‌فاکتورهایی که چند روز بدون حرکت مانده‌اند → فعالیت پیگیری برای فروشنده."""
        days = self._param_int("erp_auto.stale_quote_days", 7)
        cutoff = fields.Datetime.now() - timedelta(days=days)
        quotes = self.env["sale.order"].search([
            ("state", "in", ["draft", "sent"]),
            ("write_date", "<", cutoff),
        ], limit=50)
        touched = self.env["sale.order"]
        for quote in quotes:
            has_open_activity = self.env["mail.activity"].search_count([
                ("res_model", "=", "sale.order"),
                ("res_id", "=", quote.id),
            ])
            if has_open_activity:
                continue
            quote.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=(quote.user_id or self.env.user).id,
                summary=_("پیگیری پیش‌فاکتور راکد"),
                note=_("این پیش‌فاکتور %s روز است بدون تغییر مانده. با مشتری "
                       "تماس بگیرید یا آن را لغو کنید.") % days,
            )
            touched |= quote
        if touched:
            self.env["erp.auto.audit.log"].log(
                _("پیگیری خودکار %s پیش‌فاکتور راکد برنامه‌ریزی شد") % len(touched),
                action="automation", reason=_("کرون پیش‌فاکتور راکد"),
                data={"orders": touched.mapped("name")})
            self.env["erp.auto.notify"].post_channel(
                "🛒 دستیار فروش",
                _("%(count)s پیش‌فاکتور بیش از %(days)s روز بدون حرکت مانده و برای "
                  "فروشنده‌ها فعالیت پیگیری ثبت شد: %(names)s")
                % {"count": len(touched), "days": days,
                   "names": "، ".join(touched.mapped("name"))})
        return True

    # ------------------------------------------------------------------
    @api.model
    def _cron_expiry_alerts(self):
        """کالاهای نزدیک انقضا → هشدار در مرکز استثناها (اجرای FEFO دستی/تخفیف/انتقال)."""
        days = self._param_int("erp_auto.expiry_alert_days", 15)
        horizon = fields.Datetime.now() + timedelta(days=days)
        lots = self.env["stock.lot"].search([
            ("expiration_date", "!=", False),
            ("expiration_date", "<=", horizon),
        ], limit=200)
        Alert = self.env["ai.audit.alert"]
        today = fields.Date.context_today(self)
        made = Alert.browse()
        for lot in lots.filtered(lambda l: l.product_qty > 0):
            made |= Alert._make_alert(lot.id, {
                "name": _("نزدیک انقضا: %(product)s (سری %(lot)s)")
                        % {"product": lot.product_id.display_name, "lot": lot.name},
                "severity": "warning",
                "exception_type": "expiry",
                "amount": lot.product_qty,
                "reason": _("%(qty)s واحد از این سری در تاریخ %(date)s منقضی می‌شود.")
                          % {"qty": lot.product_qty,
                             "date": fields.Datetime.to_datetime(lot.expiration_date).date()},
                "suggestion": _("فروش با تخفیف، انتقال به شعبه پرمصرف، یا خروج از "
                                "چرخه فروش پیش از انقضا."),
                "deadline": min(
                    fields.Datetime.to_datetime(lot.expiration_date).date(),
                    today + timedelta(days=days)),
            })
        if made:
            self.env["erp.auto.audit.log"].log(
                _("%s هشدار انقضای کالا ایجاد شد") % len(made),
                action="automation", reason=_("کرون هشدار انقضا"))
        return True
