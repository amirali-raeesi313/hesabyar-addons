# -*- coding: utf-8 -*-
import logging
from datetime import timedelta

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class AiAuditAlert(models.Model):
    _name = "ai.audit.alert"
    _description = "هشدار بازرس هوشمند"
    _order = "id desc"

    name = fields.Char("عنوان", required=True)
    severity = fields.Selection([
        ("info", "اطلاع"),
        ("warning", "هشدار"),
        ("critical", "بحرانی"),
    ], default="warning", string="شدت")
    exception_type = fields.Selection([
        ("duplicate", "فاکتور تکراری"),
        ("anomaly", "مبلغ غیرعادی"),
        ("negative_stock", "موجودی منفی"),
        ("credit_limit", "عبور از سقف اعتبار"),
        ("overdue", "مطالبات معوق"),
        ("cheque_due", "سررسید چک"),
        ("bank", "مغایرت بانکی"),
        ("other", "سایر"),
    ], default="other", string="نوع استثنا")
    move_id = fields.Many2one("account.move", string="سند مرتبط")
    partner_id = fields.Many2one("res.partner", string="طرف حساب")
    amount = fields.Float("مبلغ")
    reason = fields.Text("شرح / علت")
    suggestion = fields.Text("پیشنهاد سیستم")
    user_id = fields.Many2one("res.users", string="مسئول رسیدگی",
                              default=lambda self: self.env.user)
    deadline = fields.Date("مهلت رسیدگی")
    resolution = fields.Text("اقدام و نتیجه نهایی")
    state = fields.Selection([("new", "جدید"), ("reviewed", "بررسی شد")], default="new")
    detected_on = fields.Date(default=fields.Date.context_today)

    def action_review(self):
        self.write({"state": "reviewed"})

    @api.model
    def _make_alert(self, dedupe_key, vals):
        """Create an alert unless the same open alert already exists."""
        if self.search_count([("name", "=", vals.get("name")), ("state", "=", "new")]):
            return self.browse()
        return self.create(vals)

    # ---------------- آشکارسازهای Exception Center ----------------
    @api.model
    def _cron_autopilot_scan(self):
        today = fields.Date.context_today(self)
        new = self.browse()

        # ۱) موجودی منفی
        try:
            quants = self.env["stock.quant"].search([
                ("quantity", "<", 0),
                ("location_id.usage", "=", "internal"),
            ], limit=20)
            for q in quants:
                new |= self._make_alert(q.product_id.id, {
                    "name": "موجودی منفی: %s" % q.product_id.display_name,
                    "severity": "critical",
                    "exception_type": "negative_stock",
                    "amount": q.quantity,
                    "reason": "موجودی کالا در «%s» برابر %s است. موجودی منفی یعنی خروجی بدون ورودی ثبت شده."
                              % (q.location_id.display_name, q.quantity),
                    "suggestion": "انبارگردانی این کالا را انجام دهید یا رسیدهای ثبت‌نشده را وارد کنید.",
                    "deadline": today + timedelta(days=2),
                })
        except Exception:
            _logger.exception("negative stock scan failed")

        # ۲) عبور از سقف اعتبار مشتری
        try:
            partners = self.env["res.partner"].search([
                ("credit_limit", ">", 0),
            ], limit=200)
            for p in partners.filtered(lambda p: p.credit > p.credit_limit):
                new |= self._make_alert(p.id, {
                    "name": "عبور از سقف اعتبار: %s" % p.name,
                    "severity": "warning",
                    "exception_type": "credit_limit",
                    "partner_id": p.id,
                    "amount": p.credit,
                    "reason": "بدهی مشتری %s ریال است؛ سقف اعتبار %s ریال."
                              % (f"{p.credit:,.0f}", f"{p.credit_limit:,.0f}"),
                    "suggestion": "فروش جدید را متوقف یا نقدی کنید و پیگیری وصول را شروع کنید.",
                    "deadline": today + timedelta(days=3),
                })
        except Exception:
            _logger.exception("credit scan failed")

        # ۳) مطالبات معوق (بیش از ۱۵ روز از سررسید)
        try:
            overdue = self.env["account.move"].read_group(
                [("move_type", "=", "out_invoice"), ("state", "=", "posted"),
                 ("payment_state", "in", ["not_paid", "partial"]),
                 ("invoice_date_due", "<", str(today - timedelta(days=15)))],
                ["amount_residual"], ["partner_id"], limit=10)
            for g in overdue:
                pname = g["partner_id"][1] if g.get("partner_id") else "نامشخص"
                new |= self._make_alert(pname, {
                    "name": "مطالبات معوق: %s" % pname,
                    "severity": "warning",
                    "exception_type": "overdue",
                    "partner_id": g["partner_id"][0] if g.get("partner_id") else False,
                    "amount": g["amount_residual"],
                    "reason": "%s ریال بیش از ۱۵ روز از سررسید گذشته است." % f"{g['amount_residual']:,.0f}",
                    "suggestion": "تماس وصول مطالبات + در صورت نیاز مسدودسازی اعتبار.",
                    "deadline": today + timedelta(days=5),
                })
        except Exception:
            _logger.exception("overdue scan failed")

        # ۴) چک‌های نزدیک سررسید (۷ روز آینده در دفاتر چک)
        try:
            cheque_journals = self.env["account.journal"].search([("code", "in", ["CHKIN", "CHKOUT"])])
            if cheque_journals:
                lines = self.env["account.move.line"].search([
                    ("journal_id", "in", cheque_journals.ids),
                    ("date_maturity", ">=", str(today)),
                    ("date_maturity", "<=", str(today + timedelta(days=7))),
                    ("amount_residual", "!=", 0),
                    ("parent_state", "=", "posted"),
                ], limit=20)
                for l in lines:
                    new |= self._make_alert(l.id, {
                        "name": "سررسید چک %s — %s" % (l.date_maturity, l.partner_id.name or ""),
                        "severity": "warning",
                        "exception_type": "cheque_due",
                        "partner_id": l.partner_id.id,
                        "amount": abs(l.amount_residual),
                        "reason": "چک به مبلغ %s ریال در تاریخ %s سررسید می‌شود."
                                  % (f"{abs(l.amount_residual):,.0f}", l.date_maturity),
                        "suggestion": "موجودی حساب را برای پاس‌شدن/وصول چک آماده کنید.",
                        "deadline": l.date_maturity,
                    })
        except Exception:
            _logger.exception("cheque scan failed")

        return new

    # ------------------------------------------------------------------
    @api.model
    def _post_to_channel(self, channel_name, body):
        channel = self.env["discuss.channel"].sudo().search([("name", "=", channel_name)], limit=1)
        if not channel:
            channel = self.env["discuss.channel"].sudo().create({
                "name": channel_name, "channel_type": "channel",
            })
        channel.message_post(body=body, message_type="comment", subtype_xmlid="mail.mt_comment")
        return channel

    @api.model
    def _cron_daily_audit(self):
        """Daily anomaly scan over recent journal entries."""
        Move = self.env["account.move"]
        today = fields.Date.context_today(self)
        since = today - timedelta(days=2)
        new_alerts = self.env["ai.audit.alert"]

        recent = Move.search([
            ("state", "=", "posted"),
            ("move_type", "in", ["in_invoice", "out_invoice"]),
            ("invoice_date", ">=", since),
        ])
        for mv in recent:
            if self.search_count([("move_id", "=", mv.id)]):
                continue
            # 1) duplicate suspicion: same partner + same total within 30 days
            dup = Move.search_count([
                ("id", "!=", mv.id),
                ("partner_id", "=", mv.partner_id.id),
                ("move_type", "=", mv.move_type),
                ("amount_total", "=", mv.amount_total),
                ("state", "=", "posted"),
                ("invoice_date", ">=", mv.invoice_date - timedelta(days=30)),
                ("invoice_date", "<=", mv.invoice_date + timedelta(days=30)),
            ])
            if dup:
                new_alerts |= self.create({
                    "name": _("احتمال فاکتور تکراری: %s") % mv.name,
                    "severity": "critical",
                    "move_id": mv.id,
                    "partner_id": mv.partner_id.id,
                    "amount": mv.amount_total,
                    "reason": _("سند دیگری با همین طرف حساب و همین مبلغ (%s) در بازه ۳۰ روزه وجود دارد.") % f"{mv.amount_total:,.0f}",
                })
                continue
            # 2) amount anomaly vs partner history (needs >=3 previous docs)
            history = Move.search([
                ("id", "!=", mv.id),
                ("partner_id", "=", mv.partner_id.id),
                ("move_type", "=", mv.move_type),
                ("state", "=", "posted"),
                ("invoice_date", "<", mv.invoice_date),
            ], limit=50)
            if len(history) >= 3:
                avg = sum(history.mapped("amount_total")) / len(history)
                if avg and mv.amount_total > 5 * avg:
                    new_alerts |= self.create({
                        "name": _("مبلغ غیرعادی: %s") % mv.name,
                        "severity": "warning",
                        "move_id": mv.id,
                        "partner_id": mv.partner_id.id,
                        "amount": mv.amount_total,
                        "reason": _("مبلغ سند %s است در حالی که میانگین سوابق این طرف حساب %s است (بیش از ۵ برابر).")
                                  % (f"{mv.amount_total:,.0f}", f"{avg:,.0f}"),
                    })

        # 3) unreconciled bank items summary (daily reconciliation nudge)
        unreconciled = self.env["account.bank.statement.line"].search_count([
            ("is_reconciled", "=", False)])

        # 4) exception-center detectors (negative stock, credit, overdue, cheques)
        new_alerts |= self._cron_autopilot_scan()

        if new_alerts or unreconciled:
            lines = ["🔍 گزارش روزانه بازرس هوشمند — %s" % fields.Date.context_today(self)]
            for a in new_alerts:
                lines.append("• [%s] %s — %s" % (dict(a._fields["severity"].selection).get(a.severity), a.name, a.reason))
            if unreconciled:
                lines.append("• %s قلم بانکی تطبیق‌نشده منتظر بررسی است." % unreconciled)
            body = "\n".join(lines)
            # optional AI summary
            try:
                if self.env["ir.config_parameter"].sudo().get_param("ai_suite.deepseek_api_key") and new_alerts:
                    ai = self.env["ai.deepseek.client"].chat(
                        "تو یک بازرس مالی هستی. یافته‌های زیر را در ۲-۳ جمله فارسی جمع‌بندی و اولویت‌بندی کن.",
                        body, max_tokens=400)
                    body = body + "\n\n🤖 جمع‌بندی: " + ai
            except Exception:
                _logger.exception("AI summary failed")
            self._post_to_channel("🔍 بازرس هوشمند", body.replace("\n", "<br/>"))
        return True
