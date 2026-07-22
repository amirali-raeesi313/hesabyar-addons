# -*- coding: utf-8 -*-
{
    "name": "تقویم شمسی (Jalali Calendar Switch)",
    "summary": "Per-user toggle to display dates in the Jalali (Shamsi) calendar",
    "version": "18.0.1.1.0",
    "category": "Tools",
    "author": "ersan0874, Community",
    "license": "LGPL-3",
    "website": "https://github.com/ersan0874/jalali-calendar-switch-odoo18",
    "depends": ["base", "web"],
    "data": [
        "views/res_users_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "jalali_calendar_switch/static/src/js/jalali_formatters.js",
            "jalali_calendar_switch/static/src/js/jalali_calendar_dom.js",
        ],
    },
    "installable": True,
    "application": False,
}
