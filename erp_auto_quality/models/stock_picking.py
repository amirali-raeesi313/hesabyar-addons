# -*- coding: utf-8 -*-
"""اتصال ایمن به انبار: پس از تأیید رسید ورودی، بازرسی‌های لازم خودکار ساخته شوند.

override روی button_validate است نه هسته؛ اگر ساخت بازرسی خطا دهد جریان انبار
مسدود نمی‌شود (try/except). ساخت بازرسی Idempotent است.
"""
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        res = super().button_validate()
        try:
            self._erp_auto_create_quality_checks()
        except Exception:
            _logger.exception("erp_auto_quality: auto-create checks failed")
        return res

    def _erp_auto_create_quality_checks(self):
        Point = self.env["erp.auto.quality.point"]
        Check = self.env["erp.auto.quality.check"]
        points = Point.search([("trigger_type", "=", "receipt"), ("active", "=", True)])
        if not points:
            return
        for picking in self.filtered(lambda p: p.state == "done"
                                     and p.picking_type_id.code == "incoming"):
            for move in picking.move_ids:
                product = move.product_id
                for point in points:
                    if not point._matches_product(product):
                        continue
                    if Check.search_count([
                            ("point_id", "=", point.id),
                            ("picking_id", "=", picking.id),
                            ("product_id", "=", product.id)]):
                        continue
                    Check.create({
                        "point_id": point.id,
                        "product_id": product.id,
                        "picking_id": picking.id,
                        "partner_id": picking.partner_id.id,
                        "quantity": move.quantity,
                    })
