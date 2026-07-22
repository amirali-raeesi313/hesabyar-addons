# هسته اتوماسیون حساب‌یار (erp_auto_core)

زیرساخت مشترک همه اتوماسیون‌های حساب‌یار. سه سرویس پایه:

| مدل | کاربرد |
|---|---|
| `erp.auto.audit.log` | لاگ حسابرسی تغییرناپذیر — `env["erp.auto.audit.log"].log(name, record, action, source, reason, data)` |
| `erp.auto.approval` | صف تأیید یکپارچه با SoD — `env["erp.auto.approval"].request(type, name, record, amount, reason, ...)` |
| `erp.auto.job` | اجرای ایمن با Idempotency و Retry — `env["erp.auto.job"].enqueue(key, name, model, method, args)` |
| `erp.auto.notify` | اعلان به کانال گفتگو — `env["erp.auto.notify"].post_channel(name, body)` |

## قواعد
- لاگ حسابرسی قابل ویرایش/حذف نیست (حتی برای مدیر).
- درخواست‌کننده تأیید نمی‌تواند خودش تصمیم بگیرد (تفکیک وظایف).
- درخواست/کار تکراری با همان کلید ساخته نمی‌شود (Idempotent).
- کارهای شکست‌خورده با تأخیر نمایی (۵، ۱۰، ۲۰ دقیقه…) دوباره تلاش می‌شوند؛ شکست نهایی به کانال «⚙️ خطاهای اتوماسیون» اعلان می‌رود.
- کرون پردازش صف هر ۱۰ دقیقه اجرا می‌شود.

## نصب
```
odoo-bin -d <db> -i erp_auto_core
```

## تست
```
odoo-bin -d <db_test> -i erp_auto_core --test-enable --test-tags /erp_auto_core --stop-after-init
```

## نقشه بعدی
- `ai_accounting_suite` به‌تدریج به این هسته وابسته می‌شود (هشدارها → approval/audit، فراخوانی‌های AI → job).
- کانال اعلان پیامک/ایمیل به `erp.auto.notify` اضافه می‌شود.
