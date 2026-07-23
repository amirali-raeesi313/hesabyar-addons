# -*- coding: utf-8 -*-
{
    "name": "مدیریت کیفیت حساب‌یار (ERP Auto Quality)",
    "summary": "کنترل کیفیت، بازرسی، قرنطینه و اقدام اصلاحی/پیشگیرانه (CAPA) — جایگزین Community برای ماژول Enterprise کیفیت",
    "version": "18.0.1.0.0",
    "category": "Manufacturing/Quality",
    "author": "Hesabyar",
    "license": "LGPL-3",
    "depends": ["erp_auto_core", "stock", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/data.xml",
        "views/quality_point_views.xml",
        "views/quality_check_views.xml",
        "views/quality_alert_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "application": True,
}
