# -*- coding: utf-8 -*-
"""بازرسی کیفیت: یک نمونه‌ی واقعی از کنترل روی یک کالا/محموله."""
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class ErpAutoQualityCheck(models.Model):
    _name = "erp.auto.quality.check"
    _description = "بازرسی کیفیت"
    _inherit = ["mail.thread"]
    _order = "id desc"

    name = fields.Char("شماره", required=True, copy=False, readonly=True, default="/")
    point_id = fields.Many2one("erp.auto.quality.point", string="نقطه کنترل",
                               ondelete="set null")
    product_id = fields.Many2one("product.product", string="کالا", required=True)
    lot_id = fields.Many2one("stock.lot", string="سریال/بچ")
    picking_id = fields.Many2one("stock.picking", string="حواله انبار")
    partner_id = fields.Many2one("res.partner", string="تأمین‌کننده/مشتری")
    quantity = fields.Float("مقدار", default=1.0)

    measure_type = fields.Selection(related="point_id.measure_type", store=True, readonly=True)
    measure_value = fields.Float("مقدار اندازه‌گیری‌شده")
    spec_min = fields.Float(related="point_id.spec_min", readonly=True)
    spec_max = fields.Float(related="point_id.spec_max", readonly=True)

    result = fields.Selection([
        ("none", "بررسی‌نشده"),
        ("pass", "قبول"),
        ("fail", "رد"),
    ], default="none", string="نتیجه", tracking=True)
    state = fields.Selection([
        ("to_check", "در انتظار بازرسی"),
        ("passed", "قبول"),
        ("failed", "رد"),
        ("quarantine", "قرنطینه"),
    ], default="to_check", string="وضعیت", tracking=True, index=True)

    inspector_id = fields.Many2one("res.users", string="بازرس",
                                   default=lambda self: self.env.user)
    check_date = fields.Datetime("تاریخ بازرسی")
    note = fields.Text("توضیح")
    alert_id = fields.Many2one("erp.auto.quality.alert", string="عدم انطباق", readonly=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "erp.auto.quality.check") or "/"
        return super().create(vals_list)

    # ------------------------------------------------------------------
    def _evaluate(self):
        """برای بازرسی کمی: قبول/رد خودکار بر اساس بازه مجاز."""
        self.ensure_one()
        if self.measure_type != "quantitative" or not self.point_id:
            return None
        val = self.measure_value
        ok = True
        if self.point_id.spec_min or self.point_id.spec_max:
            if self.point_id.spec_min and val < self.point_id.spec_min:
                ok = False
            if self.point_id.spec_max and val > self.point_id.spec_max:
                ok = False
        return ok

    def action_pass(self):
        for check in self:
            check.write({
                "result": "pass", "state": "passed",
                "check_date": fields.Datetime.now(),
            })
            self.env["erp.auto.audit.log"].log(
                _("بازرسی قبول: %s") % check.product_id.display_name, record=check,
                action="other", source="manual")

    def action_fail(self):
        for check in self:
            quarantine = check.point_id.quarantine_on_fail if check.point_id else True
            check.write({
                "result": "fail",
                "state": "quarantine" if quarantine else "failed",
                "check_date": fields.Datetime.now(),
            })
            check._create_capa()
            self.env["erp.auto.audit.log"].log(
                _("بازرسی رد: %s") % check.product_id.display_name, record=check,
                action="other", source="manual",
                reason=check.note, data={"quarantine": quarantine})

    def action_evaluate(self):
        """اجرای ارزیابی کمی و اعمال نتیجه."""
        for check in self:
            ok = check._evaluate()
            if ok is None:
                continue
            if ok:
                check.action_pass()
            else:
                check.action_fail()

    def _create_capa(self):
        self.ensure_one()
        if self.alert_id:
            return self.alert_id
        alert = self.env["erp.auto.quality.alert"].create({
            "name": _("عدم انطباق: %s") % self.product_id.display_name,
            "check_id": self.id,
            "product_id": self.product_id.id,
            "partner_id": self.partner_id.id,
            "alert_type": "supplier" if self.partner_id else "nonconformity",
            "severity": "high",
            "description": self.note or _("بازرسی کیفیت رد شد."),
            "responsible_id": (self.point_id.team_responsible_id.id
                               if self.point_id and self.point_id.team_responsible_id
                               else self.env.uid),
            "deadline": fields.Date.context_today(self),
        })
        self.alert_id = alert.id
        return alert

    def action_open_alert(self):
        self.ensure_one()
        if not self.alert_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "erp.auto.quality.alert",
            "res_id": self.alert_id.id,
            "view_mode": "form",
        }
