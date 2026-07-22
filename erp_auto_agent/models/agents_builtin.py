# -*- coding: utf-8 -*-
"""عامل‌های آماده‌ی حساب‌یار (فاز ۷ - اسپرینت ۱).

هر عامل واقعی است: داده‌ی زنده را می‌خواند، تصمیم قاعده‌محور می‌گیرد، اقدام
کم‌ریسک را مستقیم اجرا و اقدام حساس را به صف تأیید می‌فرستد، و همه‌چیز را در
لاگ حسابرسی ثبت می‌کند. اجرای تکراری، رکورد/فعالیت/تأیید تکراری نمی‌سازد.
"""
import logging

from odoo import fields, models, _

_logger = logging.getLogger(__name__)


class ErpAutoAgentBuiltin(models.Model):
    _inherit = "erp.auto.agent"

    # ------------------------------------------------------------------
    def _new_run(self, vals):
        vals.setdefault("agent_id", self.id)
        return self.env["erp.auto.agent.run"].create(vals)

    # ------------------------------------------------------------------
    # عامل وصول مطالبات: روی فاکتورهای فروش معوق یادآور پیگیری می‌سازد
    # ------------------------------------------------------------------
    def _run_collections_followup(self, trigger):
        self.ensure_one()
        self._check_scope("account.move")
        Move = self.env["account.move"]
        Activity = self.env["mail.activity"]
        runs = self.env["erp.auto.agent.run"]
        today = fields.Date.context_today(self)
        act_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        move_model_id = self.env["ir.model"]._get_id("account.move")
        SUMMARY = "پیگیری وصول مطالبه (عامل هوشمند)"

        overdue = Move.search([
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "in", ["not_paid", "partial"]),
            ("invoice_date_due", "<", today),
        ], limit=50)

        for mv in overdue:
            # Idempotency: یک یادآور باز از همین عامل کافی است
            if Activity.search_count([
                    ("res_model", "=", "account.move"),
                    ("res_id", "=", mv.id),
                    ("summary", "=", SUMMARY)]):
                continue

            amount = mv.amount_residual
            days = (today - mv.invoice_date_due).days if mv.invoice_date_due else 0
            reason = _("فاکتور %s به مبلغ %s ریال، %s روز از سررسید (%s) گذشته است.") % (
                mv.name, "{:,.0f}".format(amount), days, mv.invoice_date_due)
            confidence = 0.95
            run_vals = {
                "agent_id": self.id, "trigger": trigger, "input_summary": mv.name,
                "decision": _("ایجاد یادآور پیگیری وصول"),
                "reason": self._llm_reason(reason) or reason,
                "data_sources": "account.move #%s" % mv.id, "confidence": confidence,
                "model_name": "account.move", "res_id": mv.id, "res_display": mv.display_name,
                "amount": amount, "currency_id": mv.currency_id.id or self.currency_id.id,
            }

            if self._is_sensitive(amount=0.0, risk="low"):
                # عامل تنظیم‌شده برای تأیید اجباری
                approval = self.env["erp.auto.approval"].request(
                    "collections_followup", _("پیگیری وصول: %s") % mv.name, record=mv,
                    amount=amount, reason=reason,
                    approver_group_id=self.approver_group_id.id)
                run_vals["state"] = "pending_approval"
                run = self._new_run(run_vals)
                run.approval_id = approval.id
            elif confidence < (self.confidence_threshold or 0.0):
                run_vals["state"] = "suggested"
                run = self._new_run(run_vals)
            else:
                if act_type:
                    Activity.create({
                        "activity_type_id": act_type.id,
                        "res_model_id": move_model_id, "res_id": mv.id,
                        "summary": SUMMARY, "note": reason,
                        "user_id": mv.invoice_user_id.id or self.env.uid,
                        "date_deadline": today,
                    })
                    run_vals.update({"state": "executed",
                                     "action_taken": _("یادآور پیگیری روی فاکتور ایجاد شد.")})
                else:
                    run_vals["state"] = "suggested"
                run = self._new_run(run_vals)

            self.env["erp.auto.audit.log"].log(
                _("عامل وصول: %s") % run.decision, record=mv, action="ai", source="ai",
                reason=run.reason, data={"run": run.id, "confidence": confidence})
            runs |= run
        return runs

    # ------------------------------------------------------------------
    # عامل خرید: کالاهای زیر نقطه سفارش را شناسایی و درخواست تأیید خرید می‌سازد
    # ------------------------------------------------------------------
    def _run_purchase_shortage(self, trigger):
        self.ensure_one()
        self._check_scope("stock.warehouse.orderpoint")
        Orderpoint = self.env["stock.warehouse.orderpoint"]
        Approval = self.env["erp.auto.approval"]
        runs = self.env["erp.auto.agent.run"]

        # qty_forecast محاسباتی است؛ همه را می‌خوانیم و در پایتون فیلتر می‌کنیم
        ops = Orderpoint.search([], limit=200)
        for op in ops:
            try:
                forecast = op.qty_forecast
                min_qty = op.product_min_qty
            except Exception:
                continue
            if forecast >= min_qty:
                continue

            # Idempotency: اگر درخواست باز برای همین کالا هست، رد شو
            if Approval.search_count([
                    ("approval_type", "=", "purchase_shortage"),
                    ("model_name", "=", "stock.warehouse.orderpoint"),
                    ("res_id", "=", op.id), ("state", "=", "pending")]):
                continue

            qty_needed = max(op.product_max_qty - forecast, min_qty - forecast)
            est_amount = qty_needed * (op.product_id.standard_price or 0.0)
            reason = _("موجودی پیش‌بینی‌شده‌ی «%s» برابر %s و زیر حداقل %s است؛ "
                       "پیشنهاد تأمین %s واحد (برآورد %s ریال).") % (
                op.product_id.display_name, forecast, min_qty, qty_needed,
                "{:,.0f}".format(est_amount))

            # خرید = اقدام حساس → همیشه تأیید انسانی
            approval = Approval.request(
                "purchase_shortage", _("پیشنهاد خرید: %s") % op.product_id.display_name,
                record=op, amount=est_amount, reason=reason,
                approver_group_id=self.approver_group_id.id)
            run = self._new_run({
                "agent_id": self.id, "trigger": trigger,
                "input_summary": op.product_id.display_name,
                "decision": _("درخواست تأیید خرید کالای کمبود"),
                "reason": self._llm_reason(reason) or reason,
                "data_sources": "stock.warehouse.orderpoint #%s" % op.id,
                "confidence": 0.85,
                "model_name": "stock.warehouse.orderpoint", "res_id": op.id,
                "res_display": op.display_name, "amount": est_amount,
                "currency_id": self.currency_id.id,
                "state": "pending_approval", "approval_id": approval.id,
            })
            self.env["erp.auto.audit.log"].log(
                _("عامل خرید: %s") % run.decision, record=op, action="ai", source="ai",
                reason=reason, data={"run": run.id})
            runs |= run
        return runs
