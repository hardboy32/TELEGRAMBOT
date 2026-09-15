import asyncio
import json

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
        return json.load(f)


async def main():

    config = load_config()

    # ساخت دیتابیس در صورت نیاز
    init_db()

    app = Client(
        "cafe_hermes_bot",
        api_id=config["api_id"],
        api_hash=config["api_hash"],
        bot_token=config["bot_token"]
    )

    # ثبت Handler های کاربران
    register_users(
        app,
        config
    )

    # ثبت Handler های ادمین
    register_admin(
        app,
        config
    )

    print("Cafe Hermes Bot started.")

    await app.start()

    try:
        await asyncio.Event().wait()
    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
