import asyncio
import json
import os

from pyrogram import Client

from bot.database import init_db, get_setting, set_setting
from bot.helpers import save_config
from bot.user_handlers import register as register_users
from bot.admin_handlers import register as register_admin
from bot.store_control import register as register_store_control
from bot.purchase_display import register as register_purchase_display
from bot.service_management import register as register_service_management

from bot.remote_storage import (
    stop_storage,
    restore_from_remote,
    database_is_usable,
    storage_enabled,
    start_file_watcher,
    sync_all,
    cleanup_temporary_files,
    start_temporary_cleanup,
    stop_temporary_cleanup,
)
from bot.remote_storage_bootstrap import start_storage
from bot.hermes import start_hermes_monitor, stop_hermes_monitor

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
    restored = False

    try:

        # Remove only known disposable temp files; never touch the live database.
        cleanup_temporary_files(force=True)

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
            "Checking local database..."
        )

        # Never let init_db() silently create a fresh empty database when a
        # configured remote backup should contain the user's existing data.
        if storage_enabled() and not database_is_usable():
            raise RuntimeError(
                "دیتابیس محلی وجود ندارد یا سالم نیست و نسخه معتبر قابل بازیابی "
                "از تلگرام تأیید نشده است؛ برای جلوگیری از شروع با اطلاعات خالی، "
                "ربات متوقف شد. بکاپ تلگرام و دسترسی کانال‌های ذخیره‌سازی را بررسی کنید."
            )

        print(
            "Initializing database..."
        )

        init_db()

        # Migrate legacy payment details out of config.json into the private
        # SQLite settings table. Existing DB settings are canonical; env vars
        # seed a fresh DB and legacy config is the final migration fallback.
        for key, env_name in (
            ("payment_card", "PAYMENT_CARD"),
            ("payment_name", "PAYMENT_NAME"),
        ):
            env_value = os.getenv(env_name)
            stored_value = get_setting(key)
            legacy_value = config.get(key)

            if stored_value:
                value = stored_value
            elif env_value:
                value = env_value.strip()
            else:
                value = legacy_value or ""

            config[key] = value
            if value:
                set_setting(key, value)

        # save_config filters private values, ensuring the local config file
        # is scrubbed after any legacy restore/migration.
        save_config(config)

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

        start_hermes_monitor(app, config)

        if storage_started:

            start_file_watcher()
            start_remote_state_monitor(config)
            start_temporary_cleanup()

            # Initial backup runs in the background after handlers are ready,
            # so startup syncing does not delay member-facing responses.
            async def initial_remote_sync():
                try:
                    synced = await sync_all(force=True)
                    if synced:
                        mark_remote_state_ready()
                except Exception as e:
                    print(f"Remote Storage: initial background sync error: {e}")

            asyncio.create_task(initial_remote_sync())

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

        try:
            await stop_hermes_monitor()
        except Exception as e:
            print(f"Hermes monitor stop error: {e}")

        if storage_started:

            try:
                await stop_temporary_cleanup()
            except Exception as e:
                print(f"Temporary cleanup stop error: {e}")

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
