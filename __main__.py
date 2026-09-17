import asyncio
import json
import os

from pyrogram import Client

from bot.database import init_db

from bot.user_handlers import register as register_users
from bot.admin_handlers import register as register_admin

from bot.backup import auto_backup_loop

from bot.remote_storage import (
    start_storage,
    stop_storage,
    restore_from_remote,
    sync_all,
)


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

    print("Starting Remote Storage...")

    storage_started = await start_storage()

    if storage_started:

        print(
            "Checking Remote Storage for previous data..."
        )

        restored = await restore_from_remote()

        if restored:

            print(
                "Remote data restored successfully."
            )

    else:

        print(
            "Remote Storage is not available."
        )

    print("Initializing database...")

    init_db()

    print("Starting Cafe Hermes Bot...")

    app = Client(
        "cafe_hermes_bot",
        api_id=config["api_id"],
        api_hash=config["api_hash"],
        bot_token=config["bot_token"]
    )

    register_admin(
        app,
        config
    )

    register_users(
        app,
        config
    )

    await app.start()

    print(
        "Cafe Hermes Bot started successfully."
    )

    # اولین ذخیره بعد از بالا آمدن ربات
    if storage_started:

        try:

            await sync_all()

        except Exception as e:

            print(
                f"Initial remote sync error: {e}"
            )

    asyncio.create_task(
        auto_backup_loop(
            app,
            config
        )
    )

    try:

        await asyncio.Event().wait()

    except KeyboardInterrupt:

        print(
            "Stopping bot..."
        )

    finally:

        if storage_started:

            try:

                print(
                    "Final remote synchronization..."
                )

                await sync_all()

            except Exception as e:

                print(
                    f"Final remote sync error: {e}"
                )

        await app.stop()

        await stop_storage()

        print(
            "Cafe Hermes Bot stopped."
        )


if __name__ == "__main__":

    asyncio.run(main())
