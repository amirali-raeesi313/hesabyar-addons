# -*- coding: utf-8 -*-
from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        res = super().session_info()
        user = self.env.user
        try:
            res["use_jalali_calendar"] = bool(user.use_jalali_calendar) if not user._is_public() else False
        except Exception:
            res["use_jalali_calendar"] = False
        return res
