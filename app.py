import asyncio
import json
import os

from pyrogram import Client

from bot.database import init_db
from bot.user_handlers import register as register_users
from bot.admin_handlers import register as register_admin
from bot.store_control import register as register_store_control
from bot.purchase_display import register as register_purchase_display
from bot.service_management import register as register_service_management

from bot.remote_storage import (
    stop_storage,
    restore_from_remote,
    start_file_watcher,
)
from bot.remote_storage_bootstrap import start_storage

from bot.remote_state_monitor import (
    start_remote_state_monitor,
    stop_remote_state_monitor,
    mark_remote_state_ready,
)


# Deployment source marker: this file belongs to the current main branch.


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

    if "purchase_open" not in config:
        config["purchase_open"] = True

    if "renew_open" not in config:
        config["renew_open"] = True

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

            restored = await restore_from_remote()

            if restored:
                mark_remote_state_ready()

        else:

            print(
                "Remote Storage is not available."
            )

        print(
            "Loading final configuration..."
        )

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

        register_store_control(
            app,
            config
        )

        register_purchase_display(
            app,
            config
        )

        register_service_management(
            app,
            config
        )

        if storage_started:

            start_file_watcher()
            start_remote_state_monitor()

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

                await stop_remote_state_monitor()

            except Exception as e:

                print(
                    f"Remote State Monitor stop error: {e}"
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
