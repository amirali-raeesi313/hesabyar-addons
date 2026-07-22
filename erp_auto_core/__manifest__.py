# -*- coding: utf-8 -*-
{
    "name": "هسته اتوماسیون حساب‌یار (ERP Auto Core)",
    "summary": "زیرساخت مشترک اتوماسیون: لاگ حسابرسی، صف تأیید، اجرای ایمن با Retry و Idempotency",
    "version": "18.0.1.0.0",
    "category": "Technical",
    "author": "Hesabyar",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/views.xml",
        "data/cron.xml",
    ],
    "installable": True,
    "application": False,
}
