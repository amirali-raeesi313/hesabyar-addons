# -*- coding: utf-8 -*-
"""ابزارهای آماری قطعی + پل اختیاری به LLM.

هسته‌ی پیش‌بینی کاملاً قاعده‌محور و قابل حسابرسی است. LLM فقط برای «توضیح
انسانی» استفاده می‌شود و نبودنش هیچ عددی را تغییر نمی‌دهد.
"""
import logging

_logger = logging.getLogger(__name__)


def mean(values):
    return sum(values) / len(values) if values else 0.0


def variance(values):
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return sum((v - m) ** 2 for v in values) / len(values)


def linear_trend(values):
    """شیب رگرسیون خطی ساده (تغییر هر دوره)؛ برای روند صعودی/نزولی."""
    n = len(values)
    if n < 2:
        return 0.0
    xs = list(range(n))
    mx = mean(xs)
    my = mean(values)
    denom = sum((x - mx) ** 2 for x in xs)
    if not denom:
        return 0.0
    return sum((xs[i] - mx) * (values[i] - my) for i in range(n)) / denom


def confidence_score(values):
    """اطمینان بر اساس تعداد داده و ضریب تغییرات (CV). خروجی ۰.۳ تا ۰.۹۵."""
    n = len(values)
    if n < 2:
        return 0.3
    m = mean(values)
    cv = (variance(values) ** 0.5 / m) if m else 1.0
    score = 0.5 + 0.08 * n - min(cv, 0.6)
    return round(max(0.3, min(0.95, score)), 2)


def llm_narrative(env, system_msg, user_msg):
    """توضیح اختیاری با DeepSeek؛ در نبود کلید/سرویس → None (بدون خطا)."""
    client = env.get("ai.deepseek.client")
    if client is None:
        return None
    if not env["ir.config_parameter"].sudo().get_param("ai_suite.deepseek_api_key"):
        return None
    try:
        return client.chat(system_msg, user_msg, max_tokens=220)
    except Exception:
        _logger.exception("erp_auto_ai: LLM narrative failed")
        return None
