# -*- coding: utf-8 -*-
"""رکورد اجرای عامل: هر تصمیم/اقدام یک عامل، با دلیل، اطمینان، منبع داده و پیوند
به تأیید (در صورت حساس‌بودن). قابل لغو تا پیش از اجرا/تأیید."""
import logging

from odoo import fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ErpAutoAgentRun(models.Model):
    _name = "erp.auto.agent.run"
    _description = "اجرای عامل هوشمند"
    _order = "id desc"

    agent_id = fields.Many2one("erp.auto.agent", string="عامل", required=True,
                               ondelete="cascade", index=True)
    agent_type = fields.Selection(related="agent_id.agent_type", store=True)
    trigger = fields.Selection([
        ("manual", "دستی"),
        ("cron", "زمان‌بندی‌شده"),
        ("event", "رویدادی"),
        ("webhook", "Webhook"),
    ], default="manual", string="محرک")

    input_summary = fields.Char("ورودی")
    decision = fields.Text("تصمیم")
    reason = fields.Text("دلیل")
    data_sources = fields.Char("منبع داده")
    confidence = fields.Float("اطمینان", help="۰ تا ۱")
    action_taken = fields.Text("اقدام انجام‌شده")

    model_name = fields.Char("مدل هدف")
    res_id = fields.Integer("شناسه رکورد")
    res_display = fields.Char("رکورد")
    amount = fields.Monetary("مبلغ", currency_field="currency_id")
    currency_id = fields.Many2one("res.currency",
                                  default=lambda self: self.env.company.currency_id)

    approval_id = fields.Many2one("erp.auto.approval", string="درخواست تأیید")
    state = fields.Selection([
        ("suggested", "فقط پیشنهاد (اطمینان پایین)"),
        ("pending_approval", "در انتظار تأیید"),
        ("executed", "اجرا شد"),
        ("rejected", "رد شد"),
        ("failed", "خطا"),
        ("cancelled", "لغو شد"),
    ], default="suggested", string="وضعیت", index=True)
    error = fields.Text("خطا")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    def action_cancel(self):
        for run in self:
            if run.state not in ("suggested", "pending_approval"):
                raise UserError(_("فقط اجرای پیشنهادی یا در انتظار تأیید قابل لغو است."))
            if run.approval_id and run.approval_id.state == "pending":
                run.approval_id.action_cancel()
            run.state = "cancelled"
            self.env["erp.auto.audit.log"].log(
                _("اجرای عامل لغو شد: %s") % (run.decision or run.agent_id.name),
                record=run, action="ai", source="manual")

    def action_open_record(self):
        self.ensure_one()
        if not (self.model_name and self.res_id):
            raise UserError(_("رکورد مرتبطی ثبت نشده است."))
        return {
            "type": "ir.actions.act_window",
            "res_model": self.model_name,
            "res_id": self.res_id,
            "view_mode": "form",
            "target": "current",
        }
