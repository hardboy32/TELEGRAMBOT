import json
from pathlib import Path


CONFIG_PATH = Path("config.json")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def format_number(number):
    return f"{int(number):,}"


def calculate_discount(price, percent):
    discount = int(price * percent / 100)
    final_price = price - discount

    return discount, final_price


def is_admin(user_id, config):
    return user_id in config.get("admin_ids", [])


def replace_payment_info(text, config):
    return text.replace(
        "{PAYMENT_CARD}",
        config.get("payment_card", "")
    ).replace(
        "{PAYMENT_NAME}",
        config.get("payment_name", "")
    )


def make_referral_link(bot_username, user_id):
    return f"https://t.me/{bot_username}?start=ref_{user_id}"
