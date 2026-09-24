def welcome(name):
    return (
        f"👋 سلام {name} عزیز!\n\n"
        "☕️ به ربات کافه هرمس خوش آمدید.\n\n"
        "از منوی پایین می‌توانید سرویس موردنظر خود را انتخاب کنید."
    )


def join_required(channel):
    return (
        "🔒 برای استفاده از ربات ابتدا باید عضو کانال شوید.\n\n"
        f"📢 کانال: {channel}\n\n"
        "بعد از عضویت روی «✅ بررسی عضویت» بزنید."
    )


def payment(card, name):
    card = str(card).strip()
    name = str(name).strip()

    return (
        "💳 اطلاعات پرداخت\n\n"
        "شماره کارت (برای کپی لمس کنید):\n"
        f"<code>{card}</code>\n\n"
        f"به نام:\n{name}\n\n"
        "بعد از پرداخت، عکس رسید را همینجا ارسال کنید."
    )


def order_text(service, username, discount, final_price, order_type="buy"):
    if order_type == "renew":
        title = "🔄 تمدید سرویس"
        intro = "اطلاعات تمدید سرویس شما:"
        action = "اگر اطلاعات صحیح است، روی «✅ تأیید تمدید» بزنید."
    else:
        title = "🧾 خرید سرویس"
        intro = "اطلاعات سرویس انتخابی شما:"
        action = "اگر اطلاعات صحیح است، روی «✅ تأیید خرید» بزنید."

    text = (
        f"{title}\n\n"
        f"{intro}\n\n"
        f"📦 سرویس: {service['name']}\n"
        f"💾 حجم: {service['volume_gb']}GB\n"
        f"👤 نام کاربری: {username}\n\n"
        f"💰 قیمت اصلی: {service['price']:,} تومان\n"
    )

    if discount:
        text += f"🎟️ تخفیف: {discount}%\n"

    text += (
        f"💵 مبلغ قابل پرداخت: {final_price:,} تومان\n\n"
        f"{action}"
    )

    return text


def order_created(order_id, order_type="buy"):
    if order_type == "renew":
        return (
            "✅ درخواست تمدید ثبت شد.\n\n"
            f"🧾 شماره تمدید: #{order_id}\n\n"
            "💳 مبلغ تمدید را پرداخت کنید و عکس رسید را ارسال کنید."
        )

    return (
        "✅ سفارش خرید ثبت شد.\n\n"
        f"🧾 شماره سفارش: #{order_id}\n\n"
        "💳 مبلغ را پرداخت کنید و عکس رسید را ارسال کنید."
    )


def receipt_received():
    return (
        "✅ رسید شما دریافت شد.\n\n"
        "رسید برای مدیریت ارسال شد.\n"
        "بعد از بررسی، نتیجه از طریق ربات اعلام می‌شود."
    )


def no_services():
    return (
        "❌ در حال حاضر هیچ سرویسی فعال نیست.\n\n"
        "لطفاً بعداً دوباره امتحان کنید."
    )
