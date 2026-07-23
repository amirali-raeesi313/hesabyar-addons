# -*- coding: utf-8 -*-
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo.tests import TransactionCase, tagged
from odoo.addons.erp_auto_ai.models import helpers


@tagged("post_install", "-at_install")
class TestErpAutoAi(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Forecast = cls.env["erp.auto.forecast"]
        cls.Churn = cls.env["erp.auto.churn"]
        cls.partner = cls.env["res.partner"].create({"name": "مشتری پیش‌بین"})
        cls.product = cls.env["product.product"].create({
            "name": "کالای پیش‌بین", "type": "consu", "list_price": 100.0})

    def _invoice(self, when, qty):
        inv = self.env["account.move"].create({
            "move_type": "out_invoice", "partner_id": self.partner.id,
            "invoice_date": when,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id, "quantity": qty, "price_unit": 100.0})],
        })
        inv.action_post()
        return inv

    # ---------------- ابزار آماری ----------------
    def test_helpers_math(self):
        self.assertEqual(helpers.mean([2, 4, 6]), 4.0)
        self.assertAlmostEqual(helpers.linear_trend([1, 2, 3, 4]), 1.0, places=5)
        self.assertEqual(helpers.linear_trend([5, 5, 5]), 0.0)
        c = helpers.confidence_score([10, 10, 10, 10])
        self.assertGreater(c, 0.5)
        self.assertLessEqual(c, 0.95)

    # ---------------- پیش‌بینی فروش ----------------
    def test_forecast_generates_and_is_idempotent(self):
        today = date.today()
        for m in range(4, 0, -1):
            self._invoice(today - relativedelta(months=m), qty=10)
        recs = self.Forecast.generate(lookback_months=6)
        fc = self.Forecast.search([("product_id", "=", self.product.id)])
        self.assertEqual(len(fc), 1, "یک پیش‌بینی برای کالا")
        self.assertGreater(fc.forecast_30, 0, "پیش‌بینی ۳۰روزه باید مثبت باشد")
        self.assertGreater(fc.forecast_90, fc.forecast_30, "افق بلندتر = عدد بزرگ‌تر")
        self.assertEqual(fc.periods_used, 4)
        # اجرای دوباره نباید رکورد تکراری بسازد
        self.Forecast.generate(lookback_months=6)
        self.assertEqual(
            self.Forecast.search_count([("product_id", "=", self.product.id)]), 1)

    def test_forecast_trend_up(self):
        today = date.today()
        for i, m in enumerate(range(4, 0, -1)):
            self._invoice(today - relativedelta(months=m), qty=5 + i * 5)  # 5,10,15,20
        self.Forecast.generate(lookback_months=6)
        fc = self.Forecast.search([("product_id", "=", self.product.id)])
        self.assertGreater(fc.trend, 0, "فروش صعودی باید روند مثبت بدهد")

    # ---------------- ریزش مشتری ----------------
    def test_churn_high_risk(self):
        today = date.today()
        # سه خرید با فاصله‌ی ~۳۰ روز، ولی آخری خیلی وقت پیش → روزِ گذشته زیاد
        self._invoice(today - relativedelta(days=200), 1)
        self._invoice(today - relativedelta(days=170), 1)
        self._invoice(today - relativedelta(days=140), 1)  # avg interval 30, days_since 140 -> score ~4.6
        self.Churn.generate()
        ch = self.Churn.search([("partner_id", "=", self.partner.id)])
        self.assertEqual(len(ch), 1)
        self.assertEqual(ch.risk_level, "high", "نسبت بالای ۲.۵ = ریزش شدید")
        self.assertGreater(ch.churn_score, 2.5)

    def test_churn_low_risk_recent(self):
        today = date.today()
        self._invoice(today - relativedelta(days=60), 1)
        self._invoice(today - relativedelta(days=30), 1)
        self._invoice(today - relativedelta(days=5), 1)  # recent -> low
        self.Churn.generate()
        ch = self.Churn.search([("partner_id", "=", self.partner.id)])
        self.assertEqual(ch.risk_level, "low")

    def test_churn_needs_two_orders(self):
        other = self.env["res.partner"].create({"name": "تک‌خرید"})
        inv = self.env["account.move"].create({
            "move_type": "out_invoice", "partner_id": other.id,
            "invoice_date": date.today() - relativedelta(days=10),
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id, "quantity": 1, "price_unit": 100.0})],
        })
        inv.action_post()
        self.Churn.generate()
        self.assertFalse(self.Churn.search([("partner_id", "=", other.id)]),
                         "مشتری با یک خرید نباید امتیاز ریزش بگیرد")
