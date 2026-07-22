# -*- coding: utf-8 -*-
import json
import logging
from datetime import timedelta

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

RETRY_BASE_MINUTES = 5


class ErpAutoJob(models.Model):
    """اجرای ایمن عملیات خودکار: Idempotency + Retry + ثبت خطا.

    هر اتوماسیون به‌جای اجرای مستقیم، کار را با یک کلید یکتا (job_key)
    اینجا صف می‌کند. اجرای تکراری با همان کلید، رکورد جدید نمی‌سازد؛
    خطاها با تأخیر نمایی دوباره تلاش می‌شوند و شکست نهایی اعلان می‌گیرد.
    """
    _name = "erp.auto.job"
    _description = "کار خودکار (Idempotent + Retry)"
    _order = "id desc"

    name = fields.Char("عنوان", required=True)
    job_key = fields.Char("کلید یکتایی", required=True, index=True,
                          help="Idempotency Key — اجرای دوباره با همین کلید، کار تکراری نمی‌سازد.")
    model_name = fields.Char("مدل", required=True)
    method_name = fields.Char("متد", required=True,
                              help="نام متد روی مدل؛ با api.model یا روی recordset خالی صدا زده می‌شود.")
    args_json = fields.Text("آرگومان‌ها (JSON list)")
    state = fields.Selection([
        ("pending", "در صف"),
        ("done", "انجام شد"),
        ("failed", "شکست نهایی"),
        ("cancelled", "لغو شد"),
    ], default="pending", string="وضعیت", index=True)
    attempts = fields.Integer("تعداد تلاش", default=0)
    max_attempts = fields.Integer("حداکثر تلاش", default=3)
    next_retry = fields.Datetime("تلاش بعدی")
    last_error = fields.Text("آخرین خطا")
    result = fields.Text("نتیجه")
    company_id = fields.Many2one("res.company", string="شرکت",
                                 default=lambda self: self.env.company)

    _sql_constraints = [
        ("job_key_uniq", "unique(job_key)", "کاری با این کلید یکتایی قبلاً ثبت شده است."),
    ]

    # ------------------------------------------------------------------
    @api.model
    def enqueue(self, job_key, name, model_name, method_name,
                args=None, max_attempts=3):
        """Idempotent enqueue: same job_key returns the existing job."""
        existing = self.search([("job_key", "=", job_key)], limit=1)
        if existing:
            return existing
        return self.create({
            "job_key": job_key,
            "name": name,
            "model_name": model_name,
            "method_name": method_name,
            "args_json": json.dumps(args or [], ensure_ascii=False, default=str),
            "max_attempts": max_attempts,
        })

    # ------------------------------------------------------------------
    def _execute(self):
        for job in self:
            if job.state != "pending":
                continue
            job.attempts += 1
            try:
                args = json.loads(job.args_json or "[]")
                model = self.env[job.model_name]
                method = getattr(model, job.method_name)
                with self.env.cr.savepoint():
                    res = method(*args)
                job.write({
                    "state": "done",
                    "result": (str(res) if res is not None else "")[:2000],
                    "last_error": False,
                })
                self.env["erp.auto.audit.log"].log(
                    _("کار خودکار انجام شد: %s") % job.name, record=job,
                    action="automation")
            except Exception as e:
                _logger.exception("erp.auto.job %s failed", job.job_key)
                if job.attempts >= job.max_attempts:
                    job.write({"state": "failed", "last_error": str(e)[:2000]})
                    self.env["erp.auto.audit.log"].log(
                        _("شکست نهایی کار خودکار: %s") % job.name, record=job,
                        action="automation", reason=str(e)[:500])
                    try:
                        self.env["erp.auto.notify"].post_channel(
                            "⚙️ خطاهای اتوماسیون",
                            _("کار «%s» پس از %s تلاش شکست خورد: %s")
                            % (job.name, job.attempts, str(e)[:300]))
                    except Exception:
                        _logger.exception("notify failed for job %s", job.job_key)
                else:
                    delay = RETRY_BASE_MINUTES * (2 ** (job.attempts - 1))
                    job.write({
                        "last_error": str(e)[:2000],
                        "next_retry": fields.Datetime.now() + timedelta(minutes=delay),
                    })
        return True

    @api.model
    def _cron_process(self, limit=20):
        now = fields.Datetime.now()
        jobs = self.search([
            ("state", "=", "pending"),
            "|", ("next_retry", "=", False), ("next_retry", "<=", now),
        ], limit=limit, order="id")
        jobs._execute()
        return True

    def action_retry_now(self):
        self.filtered(lambda j: j.state in ("pending", "failed")).write({
            "state": "pending", "next_retry": False})
        self._execute()

    def action_cancel(self):
        self.filtered(lambda j: j.state == "pending").write({"state": "cancelled"})

    # ---- smoke-test helpers (used by unit tests) ----
    @api.model
    def _selftest_ok(self):
        return "ok"

    @api.model
    def _selftest_fail(self):
        raise ValueError("selftest failure")
