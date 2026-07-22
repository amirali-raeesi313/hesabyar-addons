# -*- coding: utf-8 -*-
{
    "name": "عامل‌های هوشمند حساب‌یار (ERP Auto Agent)",
    "summary": "چارچوب Agentهای هوشمند با ابزار محدود، سقف مبلغ، تأیید انسانی و Audit کامل",
    "version": "18.0.1.0.0",
    "category": "Technical",
    "author": "Hesabyar",
    "license": "LGPL-3",
    "depends": ["erp_auto_core", "mail", "account", "stock"],
    "data": [
        "security/ir.model.access.csv",
        "views/views.xml",
        "data/agents.xml",
    ],
    "installable": True,
    "application": False,
}
