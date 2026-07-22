# -*- coding: utf-8 -*-
import io

from odoo import http
from odoo.http import request

from ..models.deepseek_client import jalali_to_gregorian


class AiSuiteController(http.Controller):

    @http.route("/ai_suite/insurance_list", type="http", auth="user")
    def insurance_list(self, jyear="0", jmonth="0", **kw):
        import xlsxwriter

        jy, jm = int(jyear), int(jmonth)
        gy1, gm1, gd1 = jalali_to_gregorian(jy, jm, 1)
        days = 31 if jm <= 6 else 30 if jm <= 11 else 29
        gy2, gm2, gd2 = jalali_to_gregorian(jy, jm, days)
        d1 = "%04d-%02d-%02d" % (gy1, gm1, gd1)
        d2 = "%04d-%02d-%02d" % (gy2, gm2, gd2)

        slips = request.env["hr.payslip"].search([
            ("date_from", "<=", d2), ("date_to", ">=", d1),
        ])

        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {"in_memory": True})
        ws = wb.add_worksheet("لیست بیمه")
        ws.right_to_left()
        head = wb.add_format({"bold": True, "bg_color": "#714B67", "font_color": "#FFF",
                              "border": 1, "align": "center"})
        num = wb.add_format({"num_format": "#,##0", "border": 1})
        txt = wb.add_format({"border": 1})
        note = wb.add_format({"font_color": "#888888"})

        headers = ["ردیف", "نام کارمند", "کد ملی", "شماره بیمه", "حقوق پایه",
                   "جمع مشمول بیمه", "بیمه سهم کارگر (۷٪)", "بیمه سهم کارفرما (۲۳٪)", "خالص پرداختی"]
        for c, h in enumerate(headers):
            ws.write(0, c, h, head)
        for c, w in enumerate([6, 26, 14, 14, 16, 16, 16, 16, 16]):
            ws.set_column(c, c, w)

        row = 1
        for i, slip in enumerate(slips, start=1):
            def total(code):
                return sum(l.total for l in slip.line_ids if l.code == code)
            emp = slip.employee_id
            ws.write(row, 0, i, num)
            ws.write(row, 1, emp.name or "", txt)
            ws.write(row, 2, emp.identification_id or "", txt)
            ws.write(row, 3, emp.ssnid or "", txt)
            ws.write(row, 4, total("BASIC"), num)
            ws.write(row, 5, total("GROSS"), num)
            ws.write(row, 6, abs(total("INSUR")), num)
            ws.write(row, 7, total("INSUR_EMP"), num)
            ws.write(row, 8, total("NET"), num)
            row += 1
        ws.write(row + 1, 0,
                 "این فایل کمکی است و قالب رسمی سامانه تأمین اجتماعی نیست — بازه: %s تا %s" % (d1, d2),
                 note)
        wb.close()
        buf.seek(0)
        return request.make_response(buf.read(), headers=[
            ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("Content-Disposition", "attachment; filename=insurance_%s_%02d.xlsx" % (jy, jm)),
        ])
