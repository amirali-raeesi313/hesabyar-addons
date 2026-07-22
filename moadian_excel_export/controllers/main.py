# -*- coding: utf-8 -*-
import io

from odoo import http
from odoo.http import request


def _gregorian_to_jalali(gy, gm, gd):
    """Convert a Gregorian date to Jalali (Shamsi). Pure python, no deps."""
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


def _jalali_str(d):
    if not d:
        return ""
    jy, jm, jd = _gregorian_to_jalali(d.year, d.month, d.day)
    return "%04d/%02d/%02d" % (jy, jm, jd)


MOVE_TYPE_FA = {
    "out_invoice": "فروش",
    "out_refund": "برگشت از فروش",
    "in_invoice": "خرید",
    "in_refund": "برگشت از خرید",
}


class MoadianExport(http.Controller):

    @http.route("/moadian/export", type="http", auth="user")
    def export(self, ids="", **kwargs):
        import xlsxwriter  # bundled with Odoo

        move_ids = [int(i) for i in ids.split(",") if i.strip().isdigit()]
        moves = request.env["account.move"].browse(move_ids).filtered(
            lambda mv: mv.move_type in MOVE_TYPE_FA
        )

        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {"in_memory": True})
        ws = wb.add_worksheet("مودیان")
        ws.right_to_left()

        head_fmt = wb.add_format({
            "bold": True, "bg_color": "#714B67", "font_color": "#FFFFFF",
            "border": 1, "align": "center", "valign": "vcenter",
        })
        num_fmt = wb.add_format({"num_format": "#,##0", "border": 1})
        txt_fmt = wb.add_format({"border": 1})

        headers = [
            "ردیف", "نوع", "شماره فاکتور", "تاریخ (شمسی)", "نام طرف حساب",
            "شناسه ملی/اقتصادی", "کد پستی", "شرح کالا/خدمت", "شناسه کالا",
            "تعداد", "واحد", "مبلغ واحد", "تخفیف ٪", "مبلغ قبل از مالیات",
            "مالیات ارزش افزوده", "مبلغ کل",
        ]
        for c, h in enumerate(headers):
            ws.write(0, c, h, head_fmt)
        widths = [6, 14, 18, 13, 28, 18, 12, 34, 14, 9, 9, 15, 9, 17, 16, 17]
        for c, w in enumerate(widths):
            ws.set_column(c, c, w)

        row = 1
        n = 0
        for mv in moves:
            for line in mv.invoice_line_ids.filtered(lambda l: l.display_type == "product"):
                n += 1
                tax_amount = line.price_total - line.price_subtotal
                ws.write(row, 0, n, num_fmt)
                ws.write(row, 1, MOVE_TYPE_FA.get(mv.move_type, ""), txt_fmt)
                ws.write(row, 2, mv.name or "", txt_fmt)
                ws.write(row, 3, _jalali_str(mv.invoice_date or mv.date), txt_fmt)
                ws.write(row, 4, mv.partner_id.name or "", txt_fmt)
                ws.write(row, 5, mv.partner_id.vat or "", txt_fmt)
                ws.write(row, 6, mv.partner_id.zip or "", txt_fmt)
                ws.write(row, 7, line.name or (line.product_id.name or ""), txt_fmt)
                ws.write(row, 8, line.product_id.default_code or line.product_id.barcode or "", txt_fmt)
                ws.write(row, 9, line.quantity, num_fmt)
                ws.write(row, 10, line.product_uom_id.name or "", txt_fmt)
                ws.write(row, 11, line.price_unit, num_fmt)
                ws.write(row, 12, line.discount, num_fmt)
                ws.write(row, 13, line.price_subtotal, num_fmt)
                ws.write(row, 14, tax_amount, num_fmt)
                ws.write(row, 15, line.price_total, num_fmt)
                row += 1

        wb.close()
        buf.seek(0)
        return request.make_response(buf.read(), headers=[
            ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            ("Content-Disposition", "attachment; filename=moadian_export.xlsx"),
        ])
