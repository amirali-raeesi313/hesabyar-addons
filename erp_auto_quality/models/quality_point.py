# -*- coding: utf-8 -*-
"""نقطه‌ی کنترل کیفیت: قاعده‌ی «کجا و روی چه کالایی و با چه معیاری بازرسی شود»."""
from odoo import fields, models


class ErpAutoQualityPoint(models.Model):
    _name = "erp.auto.quality.point"
    _description = "نقطه کنترل کیفیت"
    _order = "sequence, id"

    name = fields.Char("عنوان", required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    trigger_type = fields.Selection([
        ("receipt", "دریافت کالا (ورودی)"),
        ("delivery", "تحویل / خروج"),
        ("production", "حین/پایان تولید"),
        ("manual", "دستی"),
    ], string="محرک بازرسی", default="receipt", required=True)

    # دامنه‌ی کالا
    product_ids = fields.Many2many("product.product", string="کالاهای مشمول")
    product_category_id = fields.Many2one("product.category", string="دسته کالا")

    # معیار پذیرش
    measure_type = fields.Selection([
        ("pass_fail", "قبول / رد"),
        ("quantitative", "کمی (بازه مجاز)"),
    ], string="نوع اندازه‌گیری", default="pass_fail", required=True)
    spec_min = fields.Float("حداقل مجاز")
    spec_max = fields.Float("حداکثر مجاز")
    spec_target = fields.Float("مقدار هدف")
    uom_label = fields.Char("واحد اندازه")

    team_responsible_id = fields.Many2one("res.users", string="مسئول کیفیت")
    quarantine_on_fail = fields.Boolean("قرنطینه در صورت رد", default=True,
                                        help="کالای مردود تا رسیدگی، قرنطینه (مسدود) شود.")
    instruction = fields.Text("دستورالعمل بازرسی")
    check_count = fields.Integer("بازرسی‌ها", compute="_compute_check_count")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    def _compute_check_count(self):
        Check = self.env["erp.auto.quality.check"]
        for point in self:
            point.check_count = Check.search_count([("point_id", "=", point.id)]) if point.id else 0

    def _matches_product(self, product):
        """آیا این نقطه روی کالای داده‌شده اعمال می‌شود؟"""
        self.ensure_one()
        if self.product_ids:
            return product in self.product_ids
        if self.product_category_id:
            return product.categ_id == self.product_category_id
        # بدون محدودیت = همه‌ی کالاها
        return True

    def action_view_checks(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "بازرسی‌ها",
            "res_model": "erp.auto.quality.check",
            "view_mode": "list,form",
            "domain": [("point_id", "=", self.id)],
            "context": {"default_point_id": self.id},
        }
