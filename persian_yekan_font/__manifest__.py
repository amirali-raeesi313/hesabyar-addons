# -*- coding: utf-8 -*-
{
    "name": "فونت یکان (Yekan Font)",
    "summary": "Applies the Yekan Persian font across the Odoo backend, website and PDF reports",
    "version": "18.0.1.0.0",
    "category": "Tools",
    "author": "Community",
    "license": "LGPL-3",
    "depends": ["web"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "persian_yekan_font/static/src/css/yekan_font.css",
        ],
        "web.assets_frontend": [
            "persian_yekan_font/static/src/css/yekan_font.css",
        ],
        "web.report_assets_common": [
            "persian_yekan_font/static/src/css/yekan_font.css",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
