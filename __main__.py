import asyncio
import json
import os

from pyrogram import Client

from bot.database import init_db
from bot.user_handlers import register as register_users
from bot.admin_handlers import register as register_admin

from bot.remote_storage import (
    start_storage,
    stop_storage,
    restore_from_remote,
    sync_all,
    start_file_watcher,
)


def load_config():

    if not os.path.exists(
        "config.json"
    ):

        raise RuntimeError(
            "فایل config.json پیدا نشد."
        )

    with open(
        "config.json",
        "r",
        encoding="utf-8"
    ) as f:

        config = json.load(f)

    api_id = os.getenv(
        "API_ID"
    )

    api_hash = os.getenv(
        "API_HASH"
    )

    bot_token = os.getenv(
        "BOT_TOKEN"
    )

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

        api_id = int(
            api_id
        )

    except ValueError:

        raise RuntimeError(
            "API_ID باید عدد باشد."
        )

    config["api_id"] = api_id
    config["api_hash"] = api_hash
    config["bot_token"] = bot_token

    return config


async def main():

    app = None
    storage_started = False

    try:

        print(
            "Starting Cafe Hermes Bot..."
        )

        first_config = load_config()

        app = Client(
            "cafe_hermes_bot",
            api_id=first_config["api_id"],
            api_hash=first_config["api_hash"],
            bot_token=first_config["bot_token"],

            # More workers = better handling when
            # several Telegram updates arrive together.
            workers=32
        )

        print(
            "Starting Telegram client..."
        )

        await app.start()

        print(
            "Telegram client started."
        )

        print(
            "Starting Remote Storage..."
        )

        storage_started = await start_storage(
            app
        )

        if storage_started:

            print(
                "Checking Remote Storage..."
            )

            await restore_from_remote()

        else:

            print(
                "Remote Storage is not available."
            )

        # IMPORTANT:
        # Load config AFTER remote restore.
        config = load_config()

        print(
            "Initializing database..."
        )

        init_db()

        print(
            "Registering bot handlers..."
        )

        register_admin(
            app,
            config
        )

        register_users(
            app,
            config
        )

        if storage_started:

            start_file_watcher()

            # First synchronization creates the
            # initial remote state.
            try:

                await sync_all(
                    force=True
                )

            except Exception as e:

                print(
                    f"Initial remote sync error: {e}"
                )

        print(
            "Cafe Hermes Bot started successfully."
        )

        await asyncio.Event().wait()

    except KeyboardInterrupt:

        print(
            "Stopping bot..."
        )

    except Exception as e:

        print(
            f"Fatal error: {e}"
        )

        raise

    finally:

        if storage_started:

            try:

                print(
                    "Final remote synchronization..."
                )

                await sync_all(
                    force=True
                )

            except Exception as e:

                print(
                    f"Final remote sync error: {e}"
                )

            try:

                await stop_storage()

            except Exception as e:

                print(
                    f"Remote Storage stop error: {e}"
                )

        if app:

            try:

                await app.stop()

            except Exception as e:

                print(
                    f"Telegram client stop error: {e}"
                )

        print(
            "Cafe Hermes Bot stopped."
        )


if __name__ == "__main__":

    asyncio.run(main())
