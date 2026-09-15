def welcome(name):
    return (
        f"👋 سلام {name} عزیز!\n\n"
        "☕️ به ربات کافه هرمس خوش آمدید.\n\n"
        "👇 از منوی زیر انتخاب کنید:"
    )


def join_required():
    return (
        "🔒 برای استفاده از ربات ابتدا باید عضو کانال شوید.\n\n"
        "بعد از عضویت روی دکمه «✅ بررسی عضویت» بزنید."
    )


def payment(card, name):
    return (
        "💳 اطلاعات پرداخت:\n\n"
        f"شماره کارت:\n{card}\n\n"
        f"به نام:\n{name}"
    )


def order_text(service, username, discount, final_price):
    text = (
        "🧾 سفارش شما\n\n"
        f"📦 سرویس: {service['name']}\n"
        f"👤 نام کاربری: {username}\n"
        f"💰 قیمت اصلی: {service['price']:,} تومان\n"
    )

    if discount:
        text += f"🎟️ تخفیف: {discount}%\n"

    text += (
        f"💵 مبلغ قابل پرداخت: "
        f"{final_price:,} تومان"
    )

    return text
