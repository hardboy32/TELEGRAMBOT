from decimal import Decimal, ROUND_DOWN


def calc(price, percent):
    """
    محاسبه مبلغ تخفیف و مبلغ نهایی
    """
    price = int(price)
    percent = int(percent)

    if percent < 0:
        percent = 0

    if percent > 100:
        percent = 100

    discount = int(
        (Decimal(price) * Decimal(percent) / Decimal(100))
        .quantize(Decimal("1"), rounding=ROUND_DOWN)
    )

    final_price = price - discount

    return discount, final_price


def admin(uid, config):
    return int(uid) in [
        int(x) for x in config.get("admin_ids", [])
    ]


def referral_link(username, uid):
    username = str(username).replace("@", "").strip()

    return f"https://t.me/{username}?start=ref_{uid}"


def format_price(value):
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "0"


def safe_text(value):
    if value is None:
        return ""

    return str(value)


def normalize_username(username):
    username = str(username).strip()

    if username.startswith("@"):
        username = username[1:]

    return username


def valid_username(username):
    username = normalize_username(username)

    if not username:
        return False

    if len(username) < 3 or len(username) > 32:
        return False

    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"

    return all(char in allowed for char in username)


def mask_card(card):
    card = str(card).replace(" ", "")

    if len(card) <= 8:
        return card

    return f"{card[:4]} **** **** {card[-4:]}"
