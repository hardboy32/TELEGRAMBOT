from decimal import Decimal, ROUND_DOWN
import json


SECRET_CONFIG_KEYS = (
    "api_id",
    "api_hash",
    "bot_token"
)


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


def save_config(config, path="config.json"):
    data = {}

    for key, value in config.items():
        if key in SECRET_CONFIG_KEYS:
            continue

        data[key] = value

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


def apply_restored_config(config, path="config.json"):
    with open(path, "r", encoding="utf-8") as f:
        restored = json.load(f)

    for key, value in restored.items():
        if key in SECRET_CONFIG_KEYS:
            continue

        config[key] = value
