# -*- coding: utf-8 -*-
"""چارچوب عامل هوشمند.

هر عامل: دامنه‌ی محدود (مدل‌های مجاز)، سقف مبلغ، ابزارهای whitelisted و
کلید خاموش‌کردن فوری. اقدام حساس هرگز مستقیم اجرا نمی‌شود؛ در صف تأیید
(erp.auto.approval) قرار می‌گیرد. همه‌ی اقدام‌ها در erp.auto.audit.log ثبت
می‌شوند. تماس با LLM اختیاری و از طریق ai.deepseek.client است؛ نبودنش عامل را
از کار نمی‌اندازد (منطق تصمیم قاعده‌محور است).
"""
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

AGENT_TYPES = [
    ("manager", "مدیر هوشمند"),
    ("sales", "فروش"),
    ("crm", "ارتباط با مشتری (CRM)"),
    ("collections", "وصول مطالبات"),
    ("purchase", "خرید"),
    ("inventory", "انبار"),
    ("production", "تولید"),
    ("accounting", "حسابداری"),
    ("treasury", "خزانه‌داری"),
    ("hr", "منابع انسانی"),
    ("marketing", "بازاریابی"),
    ("support", "پشتیبانی"),
    ("analytics", "تحلیل داده"),
]


class ErpAutoAgent(models.Model):
    _name = "erp.auto.agent"
    _description = "عامل هوشمند"
    _order = "sequence, id"

    name = fields.Char("نام عامل", required=True, translate=True)
    code = fields.Char("کد فنی", required=True, index=True,
                       help="کلید یکتا مانند collections_followup یا purchase_shortage")
    agent_type = fields.Selection(AGENT_TYPES, string="نوع", required=True, default="manager")
    sequence = fields.Integer(default=10)
    active = fields.Boolean("فعال", default=True,
                            help="خاموش‌کردن فوری: عامل غیرفعال هیچ اقدامی نمی‌کند.")

    # --- دامنه و اختیارات ---
    allowed_model_ids = fields.Many2many("ir.model", string="مدل‌های مجاز (Scope)",
                                         help="عامل فقط روی این مدل‌ها می‌تواند اقدام کند.")
    max_amount = fields.Monetary("سقف مبلغ خودکار", currency_field="currency_id",
                                 help="اقدام مالی بیش از این مبلغ همیشه به تأیید انسانی می‌رود.")
    requires_approval = fields.Boolean("همیشه نیازمند تأیید", default=False)
    confidence_threshold = fields.Float("آستانه اطمینان", default=0.7,
                                        help="اطمینان کمتر از این حد → عامل فقط پیشنهاد می‌دهد.")
    approver_group_id = fields.Many2one("res.groups", string="گروه تأییدکننده")
    use_llm = fields.Boolean("استفاده از LLM برای توضیح", default=False,
                             help="در صورت فعال‌بودن و تنظیم کلید، دلیل تصمیم با هوش مصنوعی غنی می‌شود.")

    tool_ids = fields.One2many("erp.auto.agent.tool", "agent_id", string="ابزارهای مجاز")
    instruction = fields.Text("دستور سیستمی (برای LLM)")
    currency_id = fields.Many2one("res.currency", string="ارز",
                                  default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one("res.company", string="شرکت",
                                 default=lambda self: self.env.company)

    run_count = fields.Integer("تعداد اجرا", compute="_compute_run_count")
    last_run = fields.Datetime("آخرین اجرا", readonly=True)

    _sql_constraints = [
        ("code_company_uniq", "unique(code, company_id)", "کد عامل باید در هر شرکت یکتا باشد."),
    ]

    def _compute_run_count(self):
        Run = self.env["erp.auto.agent.run"]
        for agent in self:
            agent.run_count = Run.search_count([("agent_id", "=", agent.id)]) if agent.id else 0

    # ------------------------------------------------------------------
    # کنترل‌های ایمنی
    # ------------------------------------------------------------------
    def _check_scope(self, model_name):
        """اطمینان از اینکه مدل هدف در دامنه‌ی مجاز عامل است."""
        self.ensure_one()
        allowed = self.allowed_model_ids.mapped("model")
        if allowed and model_name not in allowed:
            raise UserError(_(
                "عامل «%s» اجازه‌ی کار روی مدل %s را ندارد (خارج از دامنه).")
                % (self.name, model_name))

    def _tool_for(self, model_name, method_name):
        self.ensure_one()
        return self.tool_ids.filtered(
            lambda t: t.model_name == model_name and t.method_name == method_name)[:1]

    def _is_sensitive(self, amount=0.0, risk="low"):
        """آیا اقدام باید به تأیید انسانی برود؟"""
        self.ensure_one()
        if self.requires_approval:
            return True
        if risk in ("high", "critical"):
            return True
        if self.max_amount and amount and amount > self.max_amount:
            return True
        return False

    # ------------------------------------------------------------------
    # LLM اختیاری (غنی‌سازی دلیل تصمیم؛ هرگز عدد نمی‌سازد)
    # ------------------------------------------------------------------
    def _llm_reason(self, context_text):
        self.ensure_one()
        if not self.use_llm:
            return None
        client = self.env.get("ai.deepseek.client")
        if client is None:
            return None
        if not self.env["ir.config_parameter"].sudo().get_param("ai_suite.deepseek_api_key"):
            return None
        try:
            return client.chat(
                self.instruction or _(
                    "تو یک عامل ERP هستی. یافته‌ها را در یک جمله‌ی فارسی کوتاه و "
                    "اجرایی توضیح بده. هرگز عدد جدید نساز؛ فقط از داده‌ی داده‌شده استفاده کن."),
                context_text, max_tokens=200)
        except Exception:
            _logger.exception("agent LLM reason failed for %s", self.code)
            return None

    # ------------------------------------------------------------------
    # اجرای عامل
    # ------------------------------------------------------------------
    def run_agent(self, trigger="manual"):
        """اجرای همه‌ی عامل‌های انتخاب‌شده. به متد داخلی _run_<code> واگذار می‌کند."""
        all_runs = self.env["erp.auto.agent.run"]
        for agent in self:
            if not agent.active:
                _logger.info("agent %s is disabled, skipping", agent.code)
                continue
            handler = getattr(agent, "_run_%s" % (agent.code or ""), None)
            if handler is None:
                _logger.warning("agent %s has no handler _run_%s", agent.code, agent.code)
                continue
            try:
                runs = handler(trigger)
                all_runs |= runs
            except Exception as e:
                _logger.exception("agent %s failed", agent.code)
                self.env["erp.auto.audit.log"].log(
                    _("اجرای عامل %s شکست خورد") % agent.name,
                    action="ai", source="ai", reason=str(e)[:500])
            agent.last_run = fields.Datetime.now()
        return all_runs

    def action_run_now(self):
        runs = self.run_agent(trigger="manual")
        return {
            "type": "ir.actions.act_window",
            "name": _("اجراهای عامل"),
            "res_model": "erp.auto.agent.run",
            "view_mode": "list,form",
            "domain": [("id", "in", runs.ids)],
        }

    def action_toggle_active(self):
        for agent in self:
            agent.active = not agent.active
            self.env["erp.auto.audit.log"].log(
                _("عامل %s %s شد") % (agent.name, _("فعال") if agent.active else _("غیرفعال")),
                record=agent, action="ai", source="manual")

    @api.model
    def _cron_run_agents(self):
        self.search([("active", "=", True)]).run_agent(trigger="cron")
        return True


class ErpAutoAgentTool(models.Model):
    _name = "erp.auto.agent.tool"
    _description = "ابزار مجاز عامل"

    agent_id = fields.Many2one("erp.auto.agent", required=True, ondelete="cascade")
    name = fields.Char("نام ابزار", required=True)
    model_name = fields.Char("مدل هدف", required=True)
    method_name = fields.Char("متد مجاز", required=True)
    risk = fields.Selection([
        ("low", "کم"),
        ("medium", "متوسط"),
        ("high", "زیاد"),
        ("critical", "بحرانی"),
    ], default="low", string="سطح ریسک")
