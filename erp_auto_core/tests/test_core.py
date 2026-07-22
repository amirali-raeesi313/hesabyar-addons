# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestErpAutoCore(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Job = cls.env["erp.auto.job"]
        cls.Approval = cls.env["erp.auto.approval"]
        cls.Audit = cls.env["erp.auto.audit.log"]
        cls.other_user = cls.env["res.users"].create({
            "name": "کاربر تست تأیید",
            "login": "erp_auto_test_approver",
            "groups_id": [(4, cls.env.ref("erp_auto_core.group_erp_auto_manager").id)],
        })

    # ---------------- idempotency ----------------
    def test_job_enqueue_idempotent(self):
        j1 = self.Job.enqueue("k1", "کار تست", "erp.auto.job", "_selftest_ok")
        j2 = self.Job.enqueue("k1", "کار تست تکراری", "erp.auto.job", "_selftest_ok")
        self.assertEqual(j1, j2, "enqueue با کلید تکراری نباید رکورد جدید بسازد")

    def test_job_success(self):
        j = self.Job.enqueue("k2", "کار موفق", "erp.auto.job", "_selftest_ok")
        j._execute()
        self.assertEqual(j.state, "done")
        self.assertEqual(j.result, "ok")

    def test_job_retry_then_fail(self):
        j = self.Job.enqueue("k3", "کار شکست‌خورده", "erp.auto.job",
                             "_selftest_fail", max_attempts=2)
        j._execute()
        self.assertEqual(j.state, "pending", "بعد از تلاش اول باید در صف بماند")
        self.assertEqual(j.attempts, 1)
        self.assertTrue(j.next_retry, "زمان تلاش بعدی باید تنظیم شود")
        j.next_retry = False
        j._execute()
        self.assertEqual(j.state, "failed", "بعد از حداکثر تلاش باید شکست نهایی شود")

    # ---------------- approval ----------------
    def test_approval_idempotent(self):
        partner = self.env["res.partner"].create({"name": "طرف تست"})
        a1 = self.Approval.request("test_type", "تأیید تست", record=partner)
        a2 = self.Approval.request("test_type", "تأیید تست ۲", record=partner)
        self.assertEqual(a1, a2, "درخواست باز تکراری نباید ساخته شود")

    def test_approval_sod(self):
        a = self.Approval.request("test_sod", "تأیید SoD")
        with self.assertRaises(UserError, msg="سازنده نباید بتواند خودش تأیید کند"):
            a.action_approve()
        a.with_user(self.other_user).action_approve()
        self.assertEqual(a.state, "approved")
        self.assertEqual(a.decided_by, self.other_user)

    def test_approval_double_decision_blocked(self):
        a = self.Approval.request("test_double", "تأیید دوباره")
        a.with_user(self.other_user).action_approve()
        with self.assertRaises(UserError):
            a.with_user(self.other_user).action_reject()

    # ---------------- audit ----------------
    def test_audit_immutable(self):
        log = self.Audit.log("رویداد تست", action="other")
        with self.assertRaises(UserError):
            log.write({"name": "دستکاری"})
        with self.assertRaises(UserError):
            log.unlink()

    def test_audit_written_on_approval(self):
        before = self.Audit.search_count([])
        self.Approval.request("test_audit", "تأیید با لاگ")
        self.assertGreater(self.Audit.search_count([]), before,
                           "ایجاد درخواست تأیید باید لاگ حسابرسی بسازد")
