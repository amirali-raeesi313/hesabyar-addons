# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestErpAutoAgent(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Agent = cls.env["erp.auto.agent"]
        cls.Run = cls.env["erp.auto.agent.run"]
        cls.collections = cls.env.ref("erp_auto_agent.agent_collections")
        cls.purchase = cls.env.ref("erp_auto_agent.agent_purchase")

    # ---------------- گاردریل‌های چارچوب ----------------
    def test_sensitivity_rules(self):
        # requires_approval → همیشه حساس
        self.assertTrue(self.purchase._is_sensitive(amount=0.0, risk="low"))
        # ریسک بالا → حساس
        self.assertTrue(self.collections._is_sensitive(amount=0.0, risk="high"))
        # عادی و کم‌ریسک → غیرحساس
        self.assertFalse(self.collections._is_sensitive(amount=0.0, risk="low"))

    def test_max_amount_forces_approval(self):
        agent = self.Agent.create({
            "name": "تست سقف", "code": "t_cap", "agent_type": "accounting",
            "max_amount": 1000.0, "requires_approval": False,
        })
        self.assertFalse(agent._is_sensitive(amount=500, risk="low"))
        self.assertTrue(agent._is_sensitive(amount=5000, risk="low"),
                        "مبلغ بالای سقف باید تأیید بخواهد")

    def test_scope_enforced(self):
        with self.assertRaises(UserError, msg="مدل خارج از دامنه باید رد شود"):
            self.collections._check_scope("res.users")
        # داخل دامنه → بدون خطا
        self.collections._check_scope("account.move")

    def test_disabled_agent_does_nothing(self):
        self.collections.active = False
        runs = self.collections.run_agent(trigger="manual")
        self.assertFalse(runs, "عامل غیرفعال نباید اجرا شود (کلید خاموش)")

    def test_toggle_active_writes_audit(self):
        before = self.env["erp.auto.audit.log"].search_count([])
        self.purchase.action_toggle_active()
        self.assertGreater(self.env["erp.auto.audit.log"].search_count([]), before)

    # ---------------- عامل وصول (یکپارچه) ----------------
    def _make_overdue_invoice(self):
        partner = self.env["res.partner"].create({"name": "مشتری تست وصول"})
        product = self.env["product.product"].create({
            "name": "خدمت تست", "type": "service", "list_price": 1000.0})
        inv = self.env["account.move"].create({
            "move_type": "out_invoice", "partner_id": partner.id,
            "invoice_date": date.today() - timedelta(days=40),
            "invoice_date_due": date.today() - timedelta(days=20),
            "invoice_line_ids": [(0, 0, {
                "product_id": product.id, "quantity": 1, "price_unit": 1000.0})],
        })
        inv.action_post()
        return inv

    def test_collections_agent_creates_activity_idempotent(self):
        inv = self._make_overdue_invoice()
        SUMMARY = "پیگیری وصول مطالبه (عامل هوشمند)"
        self.collections.run_agent(trigger="manual")
        acts = self.env["mail.activity"].search_count([
            ("res_model", "=", "account.move"), ("res_id", "=", inv.id),
            ("summary", "=", SUMMARY)])
        self.assertEqual(acts, 1, "باید دقیقاً یک یادآور ساخته شود")
        run = self.Run.search([("res_id", "=", inv.id),
                               ("agent_id", "=", self.collections.id)], limit=1)
        self.assertEqual(run.state, "executed")
        # اجرای دوباره نباید یادآور تکراری بسازد
        self.collections.run_agent(trigger="manual")
        acts2 = self.env["mail.activity"].search_count([
            ("res_model", "=", "account.move"), ("res_id", "=", inv.id),
            ("summary", "=", SUMMARY)])
        self.assertEqual(acts2, 1, "اجرای مجدد نباید یادآور تکراری بسازد (Idempotent)")

    # ---------------- عامل خرید (یکپارچه) ----------------
    def test_purchase_agent_creates_approval_idempotent(self):
        product = self.env["product.product"].create({
            "name": "کالای انبار تست", "type": "consu", "is_storable": True})
        wh = self.env["stock.warehouse"].search([], limit=1)
        self.env["stock.warehouse.orderpoint"].create({
            "product_id": product.id, "warehouse_id": wh.id,
            "location_id": wh.lot_stock_id.id,
            "product_min_qty": 10.0, "product_max_qty": 20.0,
        })
        self.purchase.run_agent(trigger="manual")
        appr = self.env["erp.auto.approval"].search([
            ("approval_type", "=", "purchase_shortage")])
        self.assertTrue(appr, "برای کالای کمبود باید درخواست تأیید ساخته شود")
        run = self.Run.search([("agent_id", "=", self.purchase.id)], limit=1)
        self.assertEqual(run.state, "pending_approval")
        n1 = len(appr)
        # اجرای دوباره → درخواست تکراری نسازد
        self.purchase.run_agent(trigger="manual")
        n2 = self.env["erp.auto.approval"].search_count([
            ("approval_type", "=", "purchase_shortage")])
        self.assertEqual(n1, n2, "اجرای مجدد نباید درخواست خرید تکراری بسازد")
