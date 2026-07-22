# -*- coding: utf-8 -*-
import json
import logging

import requests

from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

API_URL = "https://api.deepseek.com/chat/completions"


def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy - 1600
    days = 365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
    days += g_d_m[gm - 1] + (gd - 1)
    if gm > 2 and ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0):
        days += 1
    j_day_no = days - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053
    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461
    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365
    if j_day_no < 186:
        jm = 1 + j_day_no // 31
        jd = 1 + j_day_no % 31
    else:
        jm = 7 + (j_day_no - 186) // 30
        jd = 1 + (j_day_no - 186) % 30
    return jy, jm, jd


def jalali_to_gregorian(jy, jm, jd):
    jy2 = jy - 979
    j_day_no = 365 * jy2 + (jy2 // 33) * 8 + ((jy2 % 33) + 3) // 4 + (jd - 1)
    if jm <= 7:
        j_day_no += (jm - 1) * 31
    else:
        j_day_no += 186 + (jm - 7) * 30
    g_day_no = j_day_no + 79
    gy = 1600 + 400 * (g_day_no // 146097)
    g_day_no %= 146097
    leap = True
    if g_day_no >= 36525:
        g_day_no -= 1
        gy += 100 * (g_day_no // 36524)
        g_day_no %= 36524
        if g_day_no >= 365:
            g_day_no += 1
        else:
            leap = False
    gy += 4 * (g_day_no // 1461)
    g_day_no %= 1461
    if g_day_no >= 366:
        leap = False
        g_day_no -= 1
        gy += g_day_no // 365
        g_day_no %= 365
    gd = g_day_no + 1
    months = [0, 31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    for i in range(1, 13):
        if gd <= months[i]:
            gm = i
            break
        gd -= months[i]
    return gy, gm, gd


class DeepseekClient(models.AbstractModel):
    _name = "ai.deepseek.client"
    _description = "DeepSeek API client"

    def _get_api_key(self):
        key = self.env["ir.config_parameter"].sudo().get_param("ai_suite.deepseek_api_key")
        if not key:
            raise UserError(_(
                "کلید API تنظیم نشده است. در «تنظیمات ← فنی ← پارامترهای سیستم» "
                "پارامتر ai_suite.deepseek_api_key را وارد کنید."
            ))
        return key

    def chat(self, system_msg, user_msg, json_mode=False, temperature=0.2, max_tokens=4000):
        """Send a chat request to DeepSeek and return the assistant text.

        NOTE: parameter names must not shadow `user` — Odoo's translation
        helper inspects caller frames and chokes on a local named `user`.
        """
        payload = {
            "model": self.env["ir.config_parameter"].sudo().get_param(
                "ai_suite.deepseek_model", "deepseek-chat"),
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        try:
            resp = requests.post(
                API_URL,
                json=payload,
                headers={"Authorization": "Bearer %s" % self._get_api_key()},
                timeout=(15, 150),
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except UserError:
            raise
        except requests.exceptions.ConnectionError as e:
            _logger.warning("DeepSeek unreachable: %s", e)
            raise UserError(_(
                "سرویس هوش مصنوعی در دسترس نیست (مشکل اتصال اینترنت به api.deepseek.com). "
                "چند دقیقه دیگر دوباره تلاش کنید."
            ))
        except Exception as e:
            _logger.exception("DeepSeek call failed")
            raise UserError(_("خطا در ارتباط با سرویس هوش مصنوعی: %s") % e)

    def chat_json(self, system_msg, user_msg, **kw):
        raw = self.chat(system_msg, user_msg, json_mode=True, **kw)
        txt = raw.strip()
        if txt.startswith("```"):
            txt = txt.strip("`")
            if txt.lower().startswith("json"):
                txt = txt[4:]
        return json.loads(txt)
