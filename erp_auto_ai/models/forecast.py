# -*- coding: utf-8 -*-
"""پیش‌بینی فروش/تقاضا به‌ازای هر کالا.

روش قطعی: تجمیع مقدار فروش ماهانه از فاکتورهای فروش نهایی‌شده، سپس میانگین
متحرک + روند خطی. افق‌های ۷/۳۰/۹۰ روزه با سطح اطمینان مبتنی بر تعداد داده و
پراکندگی. توضیح متنی اختیاری با LLM.
"""
import logging
from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from . import helpers

_logger = logging.getLogger(__name__)


class ErpAutoForecast(models.Model):
    _name = "erp.auto.forecast"
    _description = "پیش‌بینی فروش کالا"
    _order = "forecast_30 desc"

    product_id = fields.Many2one("product.product", string="کالا", required=True, index=True)
    method = fields.Selection([
        ("statistical", "آماری (میانگین متحرک + روند)"),
    ], default="statistical", string="روش")
    avg_monthly = fields.Float("میانگین ماهانه", digits="Product Unit of Measure")
    trend = fields.Float("روند (تغییر ماهانه)", digits="Product Unit of Measure")
    forecast_7 = fields.Float("پیش‌بینی ۷ روز", digits="Product Unit of Measure")
    forecast_30 = fields.Float("پیش‌بینی ۳۰ روز", digits="Product Unit of Measure")
    forecast_90 = fields.Float("پیش‌بینی ۹۰ روز", digits="Product Unit of Measure")
    confidence = fields.Float("سطح اطمینان", help="۰ تا ۱")
    periods_used = fields.Integer("تعداد دوره‌ی داده")
    factors = fields.Text("عوامل مؤثر / توضیح")
    suggested_reorder = fields.Float("پیشنهاد تأمین", digits="Product Unit of Measure",
                                     help="کسری پیش‌بینی ۳۰روزه نسبت به موجودی قابل‌فروش")
    shortage_risk = fields.Boolean("ریسک کمبود")
    computed_on = fields.Date("تاریخ محاسبه", default=fields.Date.context_today)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    _sql_constraints = [
        ("product_uniq", "unique(product_id, company_id)",
         "برای هر کالا فقط یک پیش‌بینی نگهداری می‌شود."),
    ]

    # ------------------------------------------------------------------
    @api.model
    def _gather_monthly_series(self, lookback_months=6):
        """{product: [qty_month_oldest, ..., qty_month_newest]} از فاکتورهای فروش."""
        today = fields.Date.context_today(self)
        start = today - relativedelta(months=lookback_months)
        # در Odoo 18 خط محصولِ فاکتور display_type='product' دارد (نه False).
        lines = self.env["account.move.line"].search([
            ("move_id.move_type", "=", "out_invoice"),
            ("move_id.state", "=", "posted"),
            ("product_id", "!=", False),
            ("display_type", "=", "product"),
            ("date", ">=", start),
        ])
        buckets = defaultdict(lambda: defaultdict(float))
        for line in lines:
            if not line.date:
                continue
            key = (line.date.year, line.date.month)
            buckets[line.product_id][key] += abs(line.quantity)
        series = {}
        for product, months in buckets.items():
            series[product] = [months[k] for k in sorted(months)]
        return series

    @api.model
    def generate(self, lookback_months=6):
        """(باز)تولید پیش‌بینی همه‌ی کالاهای دارای سابقه. Idempotent (upsert)."""
        series = self._gather_monthly_series(lookback_months)
        today = fields.Date.context_today(self)
        result = self.browse()
        for product, qtys in series.items():
            if len(qtys) < 2:
                continue
            avg = helpers.mean(qtys)
            trend = helpers.linear_trend(qtys)
            monthly = max(avg + trend, 0.0)
            conf = helpers.confidence_score(qtys)
            f30 = monthly
            direction = _("صعودی") if trend > 0 else (_("نزولی") if trend < 0 else _("ثابت"))
            factors = _("میانگین ماهانه %.1f، روند %s (%.2f در ماه)، بر پایه %d دوره.") % (
                avg, direction, trend, len(qtys))

            forecast_stock = 0.0
            try:
                forecast_stock = product.qty_available
            except Exception:
                forecast_stock = 0.0
            reorder = max(f30 - forecast_stock, 0.0)

            vals = {
                "product_id": product.id,
                "method": "statistical",
                "avg_monthly": avg,
                "trend": trend,
                "forecast_7": monthly * 7.0 / 30.0,
                "forecast_30": f30,
                "forecast_90": monthly * 3.0,
                "confidence": conf,
                "periods_used": len(qtys),
                "factors": factors,
                "suggested_reorder": reorder,
                "shortage_risk": reorder > 0,
                "computed_on": today,
            }
            existing = self.search([("product_id", "=", product.id)], limit=1)
            if existing:
                existing.write(vals)
                result |= existing
            else:
                result |= self.create(vals)

        self.env["erp.auto.audit.log"].log(
            _("پیش‌بینی فروش %d کالا به‌روزرسانی شد") % len(result),
            action="ai", source="ai")
        return result

    def action_enrich_llm(self):
        """توضیح انسانی اختیاری با هوش مصنوعی (در صورت وجود کلید)."""
        for rec in self:
            txt = helpers.llm_narrative(
                self.env,
                _("تو تحلیلگر فروش هستی. در دو جمله فارسی کوتاه، پیش‌بینی زیر را "
                  "برای مدیر توضیح بده و یک اقدام پیشنهاد بده. عدد جدید نساز."),
                _("کالا: %s | پیش‌بینی ۳۰روزه: %.1f | روند: %.2f | اطمینان: %.0f%% | %s") % (
                    rec.product_id.display_name, rec.forecast_30, rec.trend,
                    rec.confidence * 100, rec.factors or ""))
            if txt:
                rec.factors = (rec.factors or "") + "\n\n🤖 " + txt

    @api.model
    def _cron_generate(self):
        self.generate()
        return True
