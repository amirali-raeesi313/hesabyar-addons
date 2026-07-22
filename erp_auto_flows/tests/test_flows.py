# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestErpAutoFlows(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.icp = cls.env["ir.config_parameter"].sudo()
        cls.partner = cls.env["res.partner"].create({"name": "مشتری تست جریان"})
        cls.product = cls.env["product.product"].create({
            "name": "کالای تست حاشیه",
            "list_price": 50.0,
            "standard_price": 100.0,
        })
        cls.approver = cls.env["res.users"].create({
            "name": "تأییدکننده تست",
            "login": "erp_auto_flows_approver",
            "groups_id": [
                (4, cls.env.ref("erp_auto_core.group_erp_auto_manager").id),
                (4, cls.env.ref("sales_team.group_sale_manager").id),
            ],
        })

    def _make_order(self):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "order_line": [(0, 0, {
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "price_unit": 50.0,
            })],
        })

    def test_margin_guard_off_by_default(self):
        self.icp.set_param("erp_auto.min_margin_percent", "0")
        order = self._make_order()
        order.action_confirm()
        self.assertEqual(order.state, "sale", "با کنترل خاموش، سفارش باید تأیید شود")

    def test_margin_guard_blocks_low_margin(self):
        self.icp.set_param("erp_auto.min_margin_percent", "10")
        order = self._make_order()
        res = order.action_confirm()
        self.assertNotEqual(order.state, "sale", "سفارش کم‌حاشیه نباید تأیید شود")
        self.assertEqual(res.get("tag"), "display_notification")
        approval = self.env["erp.auto.approval"].search([
            ("approval_type", "=", "sale_below_margin"),
            ("res_id", "=", order.id),
            ("state", "=", "pending"),
        ])
        self.assertEqual(len(approval), 1, "باید یک درخواست تأیید ساخته شود")
        order.action_confirm()
        approval2 = self.env["erp.auto.approval"].search([
            ("approval_type", "=", "sale_below_margin"),
            ("res_id", "=", order.id),
        ])
        self.assertEqual(len(approval2), 1, "کلیک دوباره نباید درخواست تکراری بسازد")

    def test_margin_guard_passes_after_approval(self):
        self.icp.set_param("erp_auto.min_margin_percent", "10")
        order = self._make_order()
        order.action_confirm()
        approval = self.env["erp.auto.approval"].search([
            ("approval_type", "=", "sale_below_margin"),
            ("res_id", "=", order.id),
            ("state", "=", "pending"),
        ])
        approval.with_user(self.approver).action_approve()
        order.action_confirm()
        self.assertEqual(order.state, "sale", "بعد از تأیید مدیر، سفارش باید تأیید شود")

    def test_stale_quote_activity(self):
        self.icp.set_param("erp_auto.stale_quote_days", "7")
        order = self._make_order()
        self.env.cr.execute(
            "UPDATE sale_order SET write_date = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(days=10), order.id))
        order.invalidate_recordset(["write_date"])
        self.env["erp.auto.flows"]._cron_stale_quotes()
        acts = self.env["mail.activity"].search([
            ("res_model", "=", "sale.order"), ("res_id", "=", order.id)])
        self.assertTrue(acts, "برای پیش‌فاکتور راکد باید فعالیت پیگیری ساخته شود")
        self.env["erp.auto.flows"]._cron_stale_quotes()
        acts2 = self.env["mail.activity"].search([
            ("res_model", "=", "sale.order"), ("res_id", "=", order.id)])
        self.assertEqual(len(acts), len(acts2), "اجرای دوباره کرون نباید فعالیت تکراری بسازد")

    def test_expiry_alert(self):
        product = self.env["product.product"].create({
            "name": "کالای تاریخ‌دار تست",
            "is_storable": True,
            "tracking": "lot",
            "use_expiration_date": True,
        })
        lot = self.env["stock.lot"].create({
            "name": "LOT-EXP-1",
            "product_id": product.id,
            "expiration_date": fields.Datetime.now() + timedelta(days=5),
        })
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        self.env["stock.quant"].create({
            "product_id": product.id,
            "lot_id": lot.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 7,
        })
        self.env["erp.auto.flows"]._cron_expiry_alerts()
        alert = self.env["ai.audit.alert"].search([
            ("exception_type", "=", "expiry"),
            ("name", "like", "LOT-EXP-1"),
        ])
        self.assertTrue(alert, "برای سری نزدیک انقضا باید هشدار ساخته شود")
        self.env["erp.auto.flows"]._cron_expiry_alerts()
        alert2 = self.env["ai.audit.alert"].search([
            ("exception_type", "=", "expiry"),
            ("name", "like", "LOT-EXP-1"),
        ])
        self.assertEqual(len(alert), len(alert2), "هشدار تکراری نباید ساخته شود")
