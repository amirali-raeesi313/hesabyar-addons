# -*- coding: utf-8 -*-
{
    "name": "هوش مصنوعی مالی (AI Accounting Suite)",
    "summary": "Smart document capture, AI auditor, finance advisor, tax assistant and cash-flow forecasting powered by DeepSeek",
    "version": "18.0.2.0.0",
    "category": "Accounting",
    "author": "Community",
    "license": "LGPL-3",
    "depends": ["account", "mail", "om_hr_payroll", "stock", "purchase", "hr_holidays", "base_automation"],
    "data": [
        "security/ir.model.access.csv",
        "data/data.xml",
        "views/views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ai_accounting_suite/static/src/css/autopilot.css",
            "ai_accounting_suite/static/src/js/autopilot_dashboard.js",
            "ai_accounting_suite/static/src/xml/autopilot_dashboard.xml",
        ],
    },
    "installable": True,
    "application": True,
}
