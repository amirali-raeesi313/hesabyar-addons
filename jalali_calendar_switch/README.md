# Jalali Calendar Switch - Odoo 18

پلاگین تغییر تقویم بین میلادی و جلالی برای Odoo 18

## 📋 ویژگی‌ها

- ✅ تغییر بین تقویم میلادی و جلالی
- ✅ نمایش تاریخ‌ها در تقویم Odoo با فرمت جلالی
- ✅ تبدیل دقیق تاریخ‌ها با استفاده از jalali-moment
- ✅ دکمه تغییر سریع در پروفایل کاربر
- ✅ پشتیبانی از اعداد فارسی و لاتین
- ✅ سازگاری کامل با Odoo 18

## 🚀 نصب و راه‌اندازی

### 1. کپی کردن فایل‌ها
```bash
# کپی پلاگین به مسیر addons
cp -r jalali_calendar_switch /path/to/odoo/addons/
```

### 2. تنظیم مجوزها
```bash
# تنظیم مجوزهای مناسب
chmod -R 755 /path/to/odoo/addons/jalali_calendar_switch
chown -R odoo:odoo /path/to/odoo/addons/jalali_calendar_switch
```

### 3. راه‌اندازی مجدد Odoo
```bash
# راه‌اندازی مجدد سرویس Odoo
sudo systemctl restart odoo
```

### 4. نصب پلاگین در Odoo
1. وارد Odoo شوید
2. به **Apps** بروید
3. "Jalali Calendar Switch" را جستجو کنید
4. روی **Install** کلیک کنید

## 🔧 استفاده

### فعال‌سازی تقویم جلالی
1. به **Settings** > **Users & Companies** > **Users** بروید
2. پروفایل خود را باز کنید
3. فیلد **"Use Jalali Calendar"** را فعال کنید
4. یا از دکمه **"Toggle Jalali Calendar"** استفاده کنید

### تست عملکرد
1. به **Calendar** بروید
2. تاریخ‌ها باید به صورت جلالی نمایش داده شوند
3. نام ماه‌ها به فارسی نمایش داده می‌شود

## 🐛 عیب‌یابی

### مشکل: پلاگین نصب نمی‌شود
```bash
# بررسی لاگ‌های Odoo
tail -f /var/log/odoo/odoo.log

# بررسی مسیر addons در odoo.conf
grep addons_path /etc/odoo/odoo.conf
```

### مشکل: فیلدها نمایش داده نمی‌شوند
1. به **Settings** > **Technical** > **User Interface** > **Views** بروید
2. دکمه **Clear Cache** را بزنید
3. صفحه را refresh کنید

### مشکل: JavaScript کار نمی‌کند
1. Developer Tools را باز کنید (F12)
2. به تب Console بروید
3. خطاهای JavaScript را بررسی کنید

## 📁 ساختار فایل‌ها

```
jalali_calendar_switch/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── main.py
├── models/
│   ├── __init__.py
│   └── res_users.py
├── static/
│   └── src/
│       ├── js/
│       │   ├── moment.min.js
│       │   ├── jalali-moment.min.js
│       │   ├── jalaali_utils.js
│       │   ├── jalali_toggle.js
│       │   ├── jalali_date_patch.js
│       │   └── calendar_jalali_patch.js
│       └── xml/
│           └── jalali_templates.xml
├── views/
│   └── res_users_views.xml
└── tests/
    ├── __init__.py
    └── test_jalali_calendar.py
```

## 🔄 به‌روزرسانی

برای به‌روزرسانی پلاگین:
1. فایل‌های جدید را کپی کنید
2. به **Apps** بروید
3. پلاگین را **Upgrade** کنید

## 📞 پشتیبانی

در صورت بروز مشکل:
1. لاگ‌های Odoo را بررسی کنید
2. Developer Tools را چک کنید
3. مطمئن شوید تمام وابستگی‌ها نصب شده‌اند

## 📄 مجوز

این پلاگین تحت مجوز LGPL-3 منتشر شده است.

## 🎯 نسخه 1.0.0

- استفاده از jalali-moment برای تبدیل دقیق تاریخ‌ها
- حذف الگوریتم سفارشی و استفاده از کتابخانه استاندارد
- بهبود دقت تبدیل تاریخ‌ها
- تست‌های جامع و مستندات کامل
