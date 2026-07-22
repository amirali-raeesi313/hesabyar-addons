# -*- coding: utf-8 -*-
"""کنترل حاشیه سود هنگام تأیید سفارش فروش.

پارامتر سیستم `erp_auto.min_margin_percent` (مثلاً 10 یعنی ۱۰٪) حد مجاز را
تعیین می‌کند؛ مقدار 0 یا خالی یعنی کنترل خاموش است. سفارشی که حاشیه‌اش کمتر
از حد باشد تأیید نمی‌شود و به صف تأیید (erp.auto.approval) می‌رود؛ بعد از
تأیید یک کاربر دیگر، دکمه تأیید سفارش عبور می‌کند.
"""
import logging

from odoo import _, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _erp_auto_margin_threshold(self):
        icp = self.env["ir.config_parameter"].sudo()
        try:
            return float(icp.get_param("erp_auto.min_margin_percent", "0") or 0)
        except ValueError:
            return 0.0

    def action_confirm(self):
        threshold = self._erp_auto_margin_threshold()
        if not threshold or self.env.context.get("erp_auto_skip_margin_check"):
            return super().action_confirm()

        Approval = self.env["erp.auto.approval"]
        blocked = self.browse()
        for order in self:
            if not order.amount_untaxed:
                continue
            margin_pct = (order.margin_percent or 0.0) * 100.0
            if margin_pct >= threshold:
                continue
            already_approved = Approval.search_count([
                ("approval_type", "=", "sale_below_margin"),
                ("model_name", "=", "sale.order"),
                ("res_id", "=", order.id),
                ("state", "=", "approved"),
            ])
            if already_approved:
                continue
            req = Approval.request(
                "sale_below_margin",
                _("فروش زیر حاشیه مجاز: %s") % order.name,
                record=order,
                amount=order.amount_total,
                reason=_("حاشیه سود این سفارش %(margin).1f%% است؛ حد مجاز %(limit).1f%%.")
                       % {"margin": margin_pct, "limit": threshold},
            )
            order.message_post(body=_(
                "تأیید سفارش متوقف شد: حاشیه سود %(margin).1f%% کمتر از حد مجاز "
                "%(limit).1f%% است. درخواست تأیید #%(req)s در «هسته اتوماسیون ← "
                "صف تأیید» ثبت شد و باید توسط کاربر دیگری تأیید شود.")
                % {"margin": margin_pct, "limit": threshold, "req": req.id})
            blocked |= order

        if blocked:
            self.env["erp.auto.audit.log"].log(
                _("سفارش(های) زیر حاشیه مجاز متوقف شد: %s")
                % ", ".join(blocked.mapped("name")),
                action="automation", reason=_("کنترل حاشیه سود فروش"))
            remaining = self - blocked
            if remaining:
                super(SaleOrder, remaining).action_confirm()
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "type": "warning",
                    "sticky": True,
                    "title": _("سفارش به صف تأیید رفت"),
                    "message": _(
                        "%s به دلیل حاشیه سود پایین‌تر از حد مجاز، در انتظار "
                        "تأیید مدیر است.") % ", ".join(blocked.mapped("name")),
                },
            }
        return super().action_confirm()
