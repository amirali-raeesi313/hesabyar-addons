# -*- coding: utf-8 -*-
import base64
import io
import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .deepseek_client import jalali_to_gregorian


ANALYZE_SYSTEM = """تو یک حسابدار خبره ایرانی هستی. متن یک فاکتور یا سند مالی به تو داده می‌شود.
اطلاعات را استخراج کن و فقط یک JSON معتبر با این ساختار برگردان (بدون هیچ متن اضافه):
{
 "partner_name": "نام فروشنده/خریدار",
 "invoice_date_gregorian": "YYYY-MM-DD (تاریخ میلادی؛ اگر تاریخ سند شمسی است آن را دقیق تبدیل کن)",
 "invoice_date_jalali": "YYYY/MM/DD",
 "amount_untaxed": 0,
 "tax_amount": 0,
 "amount_total": 0,
 "lines": [
   {"description": "شرح قلم", "quantity": 1, "price_unit": 0,
    "account_code": "کد حساب معین مناسب از لیست داده شده",
    "reason": "دلیل انتخاب این حساب در یک جمله"}
 ],
 "note": "توضیح کوتاه فارسی درباره سند و هر نکته مبهم"
}
قوانین:
- مبالغ را به عدد خالص (ریال) بنویس، بدون جداکننده.
- account_code را حتماً فقط از لیست حساب‌های داده شده انتخاب کن و «نام حساب» باید دقیقاً با ماهیت قلم همخوان باشد
  (مثلاً هزینه حمل باید به حسابی با نام مرتبط با حمل/باربری برود، نه هر حساب هزینه‌ای).
  قبل از پاسخ، یک بار کد انتخابی را با نامش در لیست چک کن. اگر حساب کاملاً مناسبی نبود،
  عمومی‌ترین حساب هزینه/درآمد مرتبط را انتخاب کن و در reason صریح بنویس که مطمئن نیستی.
- اگر فاکتور چند قلم دارد هر قلم را جدا بنویس؛ اگر قابل تفکیک نیست یک سطر با کل مبلغ بنویس.
- اگر مالیات ارزش افزوده در سند هست آن را در tax_amount بگذار و در سطرها لحاظ نکن."""


class AiDocumentCapture(models.Model):
    _name = "ai.document.capture"
    _description = "ثبت‌کننده هوشمند اسناد"
    _inherit = ["mail.thread"]
    _order = "id desc"

    name = fields.Char(default=lambda self: _("جدید"), copy=False, readonly=True)
    state = fields.Selection([
        ("draft", "پیش‌نویس"),
        ("analyzed", "تحلیل‌شده"),
        ("done", "سند ایجاد شد"),
    ], default="draft", tracking=True)
    move_type = fields.Selection([
        ("in_invoice", "فاکتور خرید (هزینه)"),
        ("out_invoice", "فاکتور فروش"),
    ], string="نوع سند", default="in_invoice", required=True)
    raw_text = fields.Text("متن سند", help="متن فاکتور، ایمیل یا رسید را اینجا بچسبانید")
    pdf_file = fields.Binary("فایل PDF")
    pdf_filename = fields.Char()
    partner_name = fields.Char("نام طرف حساب (استخراجی)", tracking=True)
    partner_id = fields.Many2one("res.partner", string="طرف حساب")
    invoice_date = fields.Date("تاریخ سند")
    invoice_date_jalali = fields.Char("تاریخ شمسی")
    amount_untaxed = fields.Float("مبلغ قبل از مالیات")
    tax_amount = fields.Float("مالیات ارزش افزوده")
    amount_total = fields.Float("مبلغ کل", tracking=True)
    ai_note = fields.Text("توضیح هوش مصنوعی")
    line_ids = fields.One2many("ai.document.capture.line", "capture_id", string="اقلام")
    move_id = fields.Many2one("account.move", string="سند حسابداری", readonly=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("جدید")) == _("جدید"):
                vals["name"] = self.env["ir.sequence"].next_by_code("ai.document.capture") or "DOC"
        return super().create(vals_list)

    # ------------------------------------------------------------------
    def _extract_pdf_text(self):
        self.ensure_one()
        if not self.pdf_file:
            return ""
        try:
            try:
                from pypdf import PdfReader
            except ImportError:
                from PyPDF2 import PdfReader
            reader = PdfReader(io.BytesIO(base64.b64decode(self.pdf_file)))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
            return text.strip()
        except Exception:
            return ""

    def _candidate_accounts(self):
        self.ensure_one()
        if self.move_type == "in_invoice":
            types = ["expense", "expense_depreciation", "expense_direct_cost",
                     "asset_current", "asset_fixed", "asset_non_current", "asset_prepayments"]
        else:
            types = ["income", "income_other"]
        accounts = self.env["account.account"].search(
            [("account_type", "in", types), ("deprecated", "=", False)], limit=500, order="code")
        return accounts, "\n".join("%s | %s" % (a.code, a.name) for a in accounts)

    def action_analyze(self):
        for rec in self:
            text = (rec.raw_text or "").strip()
            if not text:
                text = rec._extract_pdf_text()
                if text:
                    rec.raw_text = text
            if not text:
                raise UserError(_(
                    "متنی برای تحلیل وجود ندارد. متن فاکتور را در «متن سند» بچسبانید "
                    "یا یک PDF متنی بارگذاری کنید. (اسکن تصویری هنوز پشتیبانی نمی‌شود)"
                ))
            accounts, account_list = rec._candidate_accounts()
            user_msg = (
                "نوع سند: %s\nتاریخ امروز میلادی: %s\n\n=== لیست حساب‌های مجاز (کد | نام) ===\n%s\n\n"
                "=== متن سند ===\n%s"
            ) % (
                dict(rec._fields["move_type"].selection).get(rec.move_type),
                fields.Date.context_today(rec),
                account_list,
                text[:12000],
            )
            data = self.env["ai.deepseek.client"].chat_json(ANALYZE_SYSTEM, user_msg)

            rec.line_ids.unlink()
            lines = []
            for l in data.get("lines", []):
                account = accounts.filtered(lambda a: a.code == str(l.get("account_code", "")).strip())
                lines.append((0, 0, {
                    "description": l.get("description") or "",
                    "quantity": float(l.get("quantity") or 1),
                    "price_unit": float(l.get("price_unit") or 0),
                    "account_id": account[:1].id,
                    "ai_reason": l.get("reason") or "",
                }))
            partner_name = (data.get("partner_name") or "").strip()
            partner = self.env["res.partner"].search([("name", "ilike", partner_name)], limit=1) if partner_name else self.env["res.partner"]
            # تبدیل دقیق تاریخ شمسی با فرمول (به مدل اعتماد نمی‌کنیم)
            invoice_date = data.get("invoice_date_gregorian") or False
            jalali = (data.get("invoice_date_jalali") or "").replace("-", "/").strip()
            try:
                parts = [int(p) for p in jalali.split("/")]
                if len(parts) == 3 and parts[0] > 1200:
                    gy, gm, gd = jalali_to_gregorian(*parts)
                    invoice_date = "%04d-%02d-%02d" % (gy, gm, gd)
            except Exception:
                pass
            rec.write({
                "partner_name": partner_name,
                "partner_id": partner.id,
                "invoice_date": invoice_date,
                "invoice_date_jalali": data.get("invoice_date_jalali") or "",
                "amount_untaxed": float(data.get("amount_untaxed") or 0),
                "tax_amount": float(data.get("tax_amount") or 0),
                "amount_total": float(data.get("amount_total") or 0),
                "ai_note": data.get("note") or "",
                "line_ids": lines,
                "state": "analyzed",
            })
            rec.message_post(body=_("تحلیل هوش مصنوعی انجام شد: %s قلم استخراج شد.") % len(lines))
        return True

    def action_create_move(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("هیچ قلمی برای ایجاد سند وجود ندارد."))
            partner = rec.partner_id
            if not partner and rec.partner_name:
                partner = self.env["res.partner"].create({
                    "name": rec.partner_name,
                    "supplier_rank": 1 if rec.move_type == "in_invoice" else 0,
                    "customer_rank": 1 if rec.move_type == "out_invoice" else 0,
                })
                rec.partner_id = partner
            if not partner:
                raise UserError(_("طرف حساب مشخص نیست."))
            tax = self.env["account.tax"]
            if rec.tax_amount:
                tax = self.env["account.tax"].search([
                    ("type_tax_use", "=", "purchase" if rec.move_type == "in_invoice" else "sale"),
                    ("amount", ">", 0),
                ], limit=1)
            move = self.env["account.move"].create({
                "move_type": rec.move_type,
                "partner_id": partner.id,
                "invoice_date": rec.invoice_date or fields.Date.context_today(rec),
                "invoice_line_ids": [(0, 0, {
                    "name": l.description or "/",
                    "quantity": l.quantity or 1,
                    "price_unit": l.price_unit,
                    "account_id": l.account_id.id or False,
                    "tax_ids": [(6, 0, tax.ids)] if tax else False,
                }) for l in rec.line_ids],
            })
            rec.write({"move_id": move.id, "state": "done"})
            rec.message_post(body=_("سند پیش‌نویس %s ایجاد شد — منتظر تأیید نهایی حسابدار.") % move.name)
        return self.action_view_move()

    def action_view_move(self):
        self.ensure_one()
        if not self.move_id:
            return True
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.move_id.id,
            "view_mode": "form",
        }

    def action_reset(self):
        self.write({"state": "draft"})


class AiDocumentCaptureLine(models.Model):
    _name = "ai.document.capture.line"
    _description = "قلم سند هوشمند"

    capture_id = fields.Many2one("ai.document.capture", ondelete="cascade")
    description = fields.Char("شرح")
    quantity = fields.Float("تعداد", default=1)
    price_unit = fields.Float("مبلغ واحد")
    subtotal = fields.Float("جمع", compute="_compute_subtotal", store=True)
    account_id = fields.Many2one("account.account", string="حساب معین (پیشنهاد AI)")
    ai_reason = fields.Char("دلیل انتخاب حساب")

    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for l in self:
            l.subtotal = (l.quantity or 0) * (l.price_unit or 0)
