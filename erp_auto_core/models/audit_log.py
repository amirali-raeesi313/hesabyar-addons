# -*- coding: utf-8 -*-
import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ErpAutoAuditLog(models.Model):
    """لاگ حسابرسی تغییرناپذیر: هر عملیات مهم (دستی، خودکار یا AI) اینجا ثبت می‌شود."""
    _name = "erp.auto.audit.log"
    _description = "لاگ حسابرسی اتوماسیون"
    _order = "id desc"

    name = fields.Char("عنوان", required=True)
    model_name = fields.Char("مدل", index=True)
    res_id = fields.Integer("شناسه رکورد")
    res_display = fields.Char("رکورد")
    action = fields.Selection([
        ("create", "ایجاد"),
        ("write", "ویرایش"),
        ("unlink", "حذف"),
        ("approve", "تأیید"),
        ("reject", "رد"),
        ("automation", "اجرای خودکار"),
        ("ai", "عملیات AI"),
        ("other", "سایر"),
    ], default="other", string="عملیات", required=True, index=True)
    source = fields.Selection([
        ("manual", "دستی"),
        ("automation", "اتوماسیون"),
        ("ai", "هوش مصنوعی"),
    ], default="automation", string="منبع")
    user_id = fields.Many2one("res.users", string="کاربر",
                              default=lambda self: self.env.user, readonly=True)
    reason = fields.Text("دلیل / شرح")
    data_json = fields.Text("داده (JSON)")
    company_id = fields.Many2one("res.company", string="شرکت",
                                 default=lambda self: self.env.company)

    @api.model
    def log(self, name, record=None, action="other", source="automation",
            reason=None, data=None):
        """Single entry point used by all Hesabyar automations."""
        vals = {
            "name": name,
            "action": action,
            "source": source,
            "reason": reason,
        }
        if record is not None and getattr(record, "id", False):
            vals.update({
                "model_name": record._name,
                "res_id": record.id,
                "res_display": record.display_name,
            })
        if data is not None:
            try:
                vals["data_json"] = json.dumps(data, ensure_ascii=False, default=str)
            except Exception:
                vals["data_json"] = repr(data)
        return self.sudo().create(vals)

    def write(self, vals):
        raise UserError(_("لاگ حسابرسی قابل ویرایش نیست."))

    def unlink(self):
        raise UserError(_("لاگ حسابرسی قابل حذف نیست."))
