import asyncio
import json
import os

from pyrogram import Client

from bot.database import init_db
from bot.user_handlers import register as register_users
from bot.admin_handlers import register as register_admin


def load_config():

    with open(
        "config.json",
        "r",
        encoding="utf-8"
    ) as f:

        config = json.load(f)

    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    bot_token = os.getenv("BOT_TOKEN")

    if not api_id:
        raise RuntimeError(
            "API_ID در Environment Variables تنظیم نشده است."
        )

    if not api_hash:
        raise RuntimeError(
            "API_HASH در Environment Variables تنظیم نشده است."
        )

    if not bot_token:
        raise RuntimeError(
            "BOT_TOKEN در Environment Variables تنظیم نشده است."
        )

    try:
        api_id = int(api_id)

    except ValueError:
        raise RuntimeError(
            "API_ID باید عدد باشد."
        )

    config["api_id"] = api_id
    config["api_hash"] = api_hash
    config["bot_token"] = bot_token

    return config


async def main():

    print("Loading configuration...")

    config = load_config()

    print("Initializing database...")

    init_db()

    print("Starting Cafe Hermes Bot...")

    app = Client(
        "cafe_hermes_bot",
        api_id=config["api_id"],
        api_hash=config["api_hash"],
        bot_token=config["bot_token"]
    )

    # مهم:
    # اول handler های ادمین ثبت می‌شوند.
    register_admin(
        app,
        config
    )

    # بعد handler های کاربر
    register_users(
        app,
        config
    )

    await app.start()

    print(
        "Cafe Hermes Bot started successfully."
    )

    try:

        await asyncio.Event().wait()

    except KeyboardInterrupt:

        print(
            "Stopping bot..."
        )

    finally:

        await app.stop()

        print(
            "Cafe Hermes Bot stopped."
        )


if __name__ == "__main__":
    asyncio.run(main())
