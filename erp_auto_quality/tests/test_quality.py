# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestErpAutoQuality(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Point = cls.env["erp.auto.quality.point"]
        cls.Check = cls.env["erp.auto.quality.check"]
        cls.Alert = cls.env["erp.auto.quality.alert"]
        cls.product = cls.env["product.product"].create({
            "name": "کالای بازرسی تست", "type": "consu", "is_storable": True})
        cls.category = cls.product.categ_id

    # ---------------- تطبیق دامنه ----------------
    def test_point_matches_all_when_empty(self):
        p = self.Point.create({"name": "همه کالاها", "trigger_type": "receipt"})
        self.assertTrue(p._matches_product(self.product))

    def test_point_matches_specific_product(self):
        other = self.env["product.product"].create({"name": "دیگر", "type": "consu"})
        p = self.Point.create({
            "name": "فقط این کالا", "trigger_type": "receipt",
            "product_ids": [(6, 0, [self.product.id])]})
        self.assertTrue(p._matches_product(self.product))
        self.assertFalse(p._matches_product(other))

    def test_point_matches_category(self):
        p = self.Point.create({
            "name": "بر اساس دسته", "trigger_type": "receipt",
            "product_category_id": self.category.id})
        self.assertTrue(p._matches_product(self.product))

    # ---------------- رد → CAPA + قرنطینه ----------------
    def test_fail_creates_capa_and_quarantine(self):
        point = self.Point.create({
            "name": "بازرسی", "trigger_type": "manual",
            "quarantine_on_fail": True})
        check = self.Check.create({
            "point_id": point.id, "product_id": self.product.id,
            "note": "آسیب ظاهری"})
        audits_before = self.env["erp.auto.audit.log"].search_count([])
        check.action_fail()
        self.assertEqual(check.state, "quarantine", "رد با قرنطینه باید کالا را مسدود کند")
        self.assertTrue(check.alert_id, "رد باید عدم انطباق (CAPA) بسازد")
        self.assertEqual(check.alert_id.alert_type, "nonconformity")
        self.assertGreater(self.env["erp.auto.audit.log"].search_count([]), audits_before,
                           "رد بازرسی باید در لاگ حسابرسی ثبت شود")

    def test_fail_idempotent_capa(self):
        point = self.Point.create({"name": "ب", "trigger_type": "manual"})
        check = self.Check.create({"point_id": point.id, "product_id": self.product.id})
        check.action_fail()
        first = check.alert_id
        check.action_fail()
        self.assertEqual(check.alert_id, first, "رد دوباره نباید CAPA تکراری بسازد")
        self.assertEqual(self.Alert.search_count([("check_id", "=", check.id)]), 1)

    def test_supplier_quality_alert_type(self):
        partner = self.env["res.partner"].create({"name": "تأمین‌کننده تست"})
        point = self.Point.create({"name": "ورودی", "trigger_type": "receipt"})
        check = self.Check.create({
            "point_id": point.id, "product_id": self.product.id,
            "partner_id": partner.id})
        check.action_fail()
        self.assertEqual(check.alert_id.alert_type, "supplier",
                         "رد کالای دارای تأمین‌کننده = عدم انطباق تأمین‌کننده")

    # ---------------- ارزیابی کمی ----------------
    def test_quantitative_pass(self):
        point = self.Point.create({
            "name": "وزن", "trigger_type": "manual", "measure_type": "quantitative",
            "spec_min": 9.0, "spec_max": 11.0})
        check = self.Check.create({
            "point_id": point.id, "product_id": self.product.id, "measure_value": 10.0})
        check.action_evaluate()
        self.assertEqual(check.state, "passed")

    def test_quantitative_fail(self):
        point = self.Point.create({
            "name": "وزن", "trigger_type": "manual", "measure_type": "quantitative",
            "spec_min": 9.0, "spec_max": 11.0, "quarantine_on_fail": False})
        check = self.Check.create({
            "point_id": point.id, "product_id": self.product.id, "measure_value": 15.0})
        check.action_evaluate()
        self.assertEqual(check.state, "failed")
        self.assertTrue(check.alert_id)

    # ---------------- CAPA lifecycle ----------------
    def test_capa_lifecycle(self):
        alert = self.Alert.create({"name": "تست CAPA", "effectiveness": "تأیید شد"})
        alert.action_start()
        self.assertEqual(alert.state, "in_progress")
        alert.action_done()
        self.assertEqual(alert.state, "done")
        before = self.env["erp.auto.audit.log"].search_count([])
        alert.action_close()
        self.assertEqual(alert.state, "closed")
        self.assertGreater(self.env["erp.auto.audit.log"].search_count([]), before)

    # ---------------- گارد اتصال انبار ----------------
    def test_picking_guard_skips_non_done(self):
        """بازرسی خودکار فقط برای حواله‌ی نهایی‌شده ساخته شود."""
        wh = self.env["stock.warehouse"].search([], limit=1)
        picking = self.env["stock.picking"].create({
            "picking_type_id": wh.in_type_id.id,
            "location_id": self.env.ref("stock.stock_location_suppliers").id,
            "location_dest_id": wh.lot_stock_id.id,
        })
        # draft picking → هیچ بازرسی‌ای نباید ساخته شود
        picking._erp_auto_create_quality_checks()
        self.assertEqual(
            self.Check.search_count([("picking_id", "=", picking.id)]), 0)
