# -*- coding: utf-8 -*-
"""عدم انطباق و اقدام اصلاحی/پیشگیرانه (CAPA)."""
from odoo import fields, models, _


class ErpAutoQualityAlert(models.Model):
    _name = "erp.auto.quality.alert"
    _description = "عدم انطباق / اقدام اصلاحی (CAPA)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char("عنوان", required=True, tracking=True)
    check_id = fields.Many2one("erp.auto.quality.check", string="بازرسی مرتبط",
                               ondelete="set null")
    product_id = fields.Many2one("product.product", string="کالا", tracking=True)
    partner_id = fields.Many2one("res.partner", string="طرف حساب (تأمین‌کننده/مشتری)")
    alert_type = fields.Selection([
        ("defect", "عیب"),
        ("nonconformity", "عدم انطباق"),
        ("supplier", "کیفیت تأمین‌کننده"),
        ("customer_complaint", "شکایت مشتری"),
    ], string="نوع", default="nonconformity", required=True, tracking=True)
    severity = fields.Selection([
        ("low", "کم"),
        ("medium", "متوسط"),
        ("high", "زیاد"),
        ("critical", "بحرانی"),
    ], string="شدت", default="medium", tracking=True)

    description = fields.Text("شرح مشکل")
    root_cause = fields.Text("علت ریشه‌ای")
    corrective_action = fields.Text("اقدام اصلاحی")
    preventive_action = fields.Text("اقدام پیشگیرانه")
    effectiveness = fields.Text("ارزیابی اثربخشی")

    responsible_id = fields.Many2one("res.users", string="مسئول رسیدگی",
                                     default=lambda self: self.env.user, tracking=True)
    deadline = fields.Date("مهلت")
    state = fields.Selection([
        ("new", "جدید"),
        ("in_progress", "در حال رسیدگی"),
        ("done", "اقدام انجام شد"),
        ("closed", "بسته (اثربخش)"),
    ], default="new", string="وضعیت", tracking=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    def action_start(self):
        self.write({"state": "in_progress"})

    def action_done(self):
        self.write({"state": "done"})

    def action_close(self):
        for alert in self:
            alert.state = "closed"
            self.env["erp.auto.audit.log"].log(
                _("عدم انطباق بسته شد: %s") % alert.name, record=alert,
                action="other", source="manual", reason=alert.effectiveness)
