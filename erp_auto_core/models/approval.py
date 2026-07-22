# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ErpAutoApproval(models.Model):
    """صف تأیید یکپارچه: هر اتوماسیونی که به تصمیم انسان می‌رسد، اینجا درخواست می‌سازد.

    قواعد ثابت:
    - درخواست باز برای همان رکورد/نوع تکرار نمی‌شود (Idempotent).
    - سازنده درخواست نمی‌تواند خودش آن را تأیید کند (تفکیک وظایف / SoD).
    - هر تصمیم در لاگ حسابرسی ثبت می‌شود.
    """
    _name = "erp.auto.approval"
    _description = "صف تأیید اتوماسیون"
    _inherit = ["mail.thread"]
    _order = "id desc"

    name = fields.Char("عنوان", required=True, tracking=True)
    approval_type = fields.Char("نوع تأیید", required=True, index=True,
                                help="کلید فنی مانند purchase_over_limit یا payment_release")
    model_name = fields.Char("مدل", index=True)
    res_id = fields.Integer("شناسه رکورد")
    res_display = fields.Char("رکورد")
    amount = fields.Float("مبلغ (ریال)")
    reason = fields.Text("دلیل درخواست")
    requested_by = fields.Many2one("res.users", string="درخواست‌کننده",
                                   default=lambda self: self.env.user, readonly=True)
    approver_group_id = fields.Many2one("res.groups", string="گروه تأییدکننده")
    decided_by = fields.Many2one("res.users", string="تصمیم‌گیرنده", readonly=True)
    decision_note = fields.Text("توضیح تصمیم")
    deadline = fields.Date("مهلت")
    state = fields.Selection([
        ("pending", "در انتظار"),
        ("approved", "تأیید شد"),
        ("rejected", "رد شد"),
        ("cancelled", "لغو شد"),
    ], default="pending", string="وضعیت", tracking=True, index=True)
    company_id = fields.Many2one("res.company", string="شرکت",
                                 default=lambda self: self.env.company)

    # ------------------------------------------------------------------
    @api.model
    def request(self, approval_type, name, record=None, amount=0.0,
                reason=None, approver_group_id=False, deadline=False):
        """Idempotent: returns the existing open request for the same
        record/type instead of creating a duplicate."""
        domain = [("approval_type", "=", approval_type), ("state", "=", "pending")]
        if record is not None and getattr(record, "id", False):
            domain += [("model_name", "=", record._name), ("res_id", "=", record.id)]
        else:
            domain += [("name", "=", name)]
        existing = self.search(domain, limit=1)
        if existing:
            return existing
        vals = {
            "approval_type": approval_type,
            "name": name,
            "amount": amount,
            "reason": reason,
            "approver_group_id": approver_group_id,
            "deadline": deadline,
        }
        if record is not None and getattr(record, "id", False):
            vals.update({
                "model_name": record._name,
                "res_id": record.id,
                "res_display": record.display_name,
            })
        req = self.create(vals)
        self.env["erp.auto.audit.log"].log(
            _("درخواست تأیید ایجاد شد: %s") % name, record=req,
            action="automation", reason=reason)
        return req

    # ------------------------------------------------------------------
    def _check_can_decide(self):
        self.ensure_one()
        if self.state != "pending":
            raise UserError(_("این درخواست قبلاً تعیین تکلیف شده است."))
        if self.env.user == self.requested_by:
            raise UserError(_(
                "تفکیک وظایف: درخواست‌کننده نمی‌تواند خودش درخواست را تأیید یا رد کند."))
        if self.approver_group_id and self.approver_group_id not in self.env.user.groups_id:
            raise UserError(_("شما عضو گروه تأییدکننده این درخواست نیستید."))

    def action_approve(self):
        for req in self:
            req._check_can_decide()
            req.write({"state": "approved", "decided_by": self.env.user.id})
            self.env["erp.auto.audit.log"].log(
                _("تأیید شد: %s") % req.name, record=req,
                action="approve", source="manual", reason=req.decision_note)

    def action_reject(self):
        for req in self:
            req._check_can_decide()
            req.write({"state": "rejected", "decided_by": self.env.user.id})
            self.env["erp.auto.audit.log"].log(
                _("رد شد: %s") % req.name, record=req,
                action="reject", source="manual", reason=req.decision_note)

    def action_cancel(self):
        for req in self:
            if req.state != "pending":
                raise UserError(_("فقط درخواست در انتظار قابل لغو است."))
            req.write({"state": "cancelled", "decided_by": self.env.user.id})
            self.env["erp.auto.audit.log"].log(
                _("لغو شد: %s") % req.name, record=req,
                action="other", source="manual")

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
