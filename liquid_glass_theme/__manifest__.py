{
    "name": "رابط حسابداری Liquid Glass",
    "summary": "پوسته سراسری شیشه‌ای، فارسی، RTL و واکنش‌گرا برای Backend اودو",
    "description": """
        بازطراحی دیداری مستقل برای Odoo 18 Community با تم روشن و تاریک،
        Sidebar پویا، صفحه برنامه‌ها، ورود فارسی و پوشش نماهای عمومی و حسابداری.
        این ماژول هیچ مدل، داده، دسترسی یا منطق مالی را تغییر نمی‌دهد.
    """,
    "version": "18.0.2.0.3",
    "category": "Themes/Backend",
    "author": "Liquid Glass UI",
    "license": "LGPL-3",
    "depends": ["web"],
    "data": [
        "views/login_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "liquid_glass_theme/static/src/js/theme_boot.js",
            "liquid_glass_theme/static/src/scss/variables.scss",
            "liquid_glass_theme/static/src/scss/light.scss",
            "liquid_glass_theme/static/src/scss/dark.scss",
            "liquid_glass_theme/static/src/scss/utilities.scss",
            "liquid_glass_theme/static/src/scss/base.scss",
            "liquid_glass_theme/static/src/scss/layout.scss",
            "liquid_glass_theme/static/src/scss/navbar.scss",
            "liquid_glass_theme/static/src/scss/sidebar.scss",
            "liquid_glass_theme/static/src/scss/control_panel.scss",
            "liquid_glass_theme/static/src/scss/components.scss",
            "liquid_glass_theme/static/src/scss/forms.scss",
            "liquid_glass_theme/static/src/scss/tables.scss",
            "liquid_glass_theme/static/src/scss/kanban.scss",
            "liquid_glass_theme/static/src/scss/dashboard.scss",
            "liquid_glass_theme/static/src/scss/dialogs.scss",
            "liquid_glass_theme/static/src/scss/chatter.scss",
            "liquid_glass_theme/static/src/scss/calendar.scss",
            "liquid_glass_theme/static/src/scss/reports.scss",
            "liquid_glass_theme/static/src/scss/responsive.scss",
            "liquid_glass_theme/static/src/js/systray_toggle.js",
            "liquid_glass_theme/static/src/xml/systray.xml",
        ],
        "web.assets_frontend": [
            "liquid_glass_theme/static/src/scss/login.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
