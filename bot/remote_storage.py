import os
import json
import asyncio
import sqlite3
from datetime import datetime


DB_PATH = "data/cafe_hermes.db"
CONFIG_PATH = "config.json"

STORAGE_CHAT_ID = os.getenv("STORAGE_CHAT_ID")


_storage_app = None
_storage_started = False
_storage_chat = None

_sync_task = None
_sync_lock = asyncio.Lock()

_dirty = False
_last_db_mtime = None
_last_config_mtime = None
_watcher_task = None


def storage_enabled():
    return bool(STORAGE_CHAT_ID)


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


async def start_storage(app):
    global _storage_app
    global _storage_started
    global _storage_chat

    _storage_app = app

    if not storage_enabled():
        print(
            "Remote Storage: STORAGE_CHAT_ID is not configured."
        )
        return False

    try:
        target_id = int(STORAGE_CHAT_ID)

    except (TypeError, ValueError):

        print(
            "Remote Storage: STORAGE_CHAT_ID is invalid."
        )

        return False

    try:
        print(
            "Remote Storage: finding storage channel..."
        )

        # First try the normal cached peer.
        try:
            _storage_chat = await _storage_app.get_chat(
                target_id
            )

        except Exception:
            _storage_chat = None

        # If the peer is not cached yet, inspect dialogs.
        if _storage_chat is None:

            async for dialog in _storage_app.get_dialogs():

                if not dialog.chat:
                    continue

                if dialog.chat.id == target_id:

                    _storage_chat = dialog.chat
                    break

        if _storage_chat is None:

            print(
                "Remote Storage: channel was not found "
                "in bot dialogs."
            )

            print(
                "Make sure the bot is an admin of the "
                "private channel and send one new message "
                "inside that channel."
            )

            return False

        _storage_started = True

        print(
            "Remote Storage connected successfully: "
            f"{_storage_chat.id}"
        )

        return True

    except Exception as e:

        print(
            f"Remote Storage connection error: {e}"
        )

        _storage_started = False
        _storage_chat = None

        return False


async def stop_storage():
    global _storage_started
    global _storage_app
    global _storage_chat
    global _sync_task
    global _watcher_task
    global _dirty

    if _watcher_task:

        try:
            _watcher_task.cancel()
            await _watcher_task

        except asyncio.CancelledError:
            pass

        except Exception:
            pass

    if _sync_task:

        try:
            _sync_task.cancel()
            await _sync_task

        except asyncio.CancelledError:
            pass

        except Exception:
            pass

    _watcher_task = None
    _sync_task = None
    _storage_app = None
    _storage_chat = None
    _storage_started = False
    _dirty = False


def _chat_id():
    if _storage_chat:
        return _storage_chat.id

    return int(STORAGE_CHAT_ID)


async def _find_latest(marker):
    if not _storage_started:
        return None

    latest = None

    try:

        async for message in _storage_app.get_chat_history(
            _chat_id()
        ):

            text = ""

            if message.caption:
                text = message.caption

            elif message.text:
                text = message.text

            if text.startswith(marker):

                latest = message
                break

    except Exception as e:

        print(
            f"Remote history error: {e}"
        )

    return latest


async def _delete_previous(marker):
    if not _storage_started:
        return

    try:

        message = await _find_latest(marker)

        if message:

            await _storage_app.delete_messages(
                _chat_id(),
                message.id
            )

    except Exception as e:

        print(
            f"Remote delete error: {e}"
        )


def _create_snapshot():
    if not os.path.exists(DB_PATH):
        return None

    os.makedirs(
        "data",
        exist_ok=True
    )

    path = (
        "data/.remote_database_snapshot.db"
    )

    source = None
    destination = None

    try:

        source = sqlite3.connect(
            DB_PATH
        )

        destination = sqlite3.connect(
            path
        )

        source.backup(
            destination
        )

        return path

    except Exception as e:

        print(
            f"Database snapshot error: {e}"
        )

        return None

    finally:

        if destination:

            try:
                destination.close()
            except Exception:
                pass

        if source:

            try:
                source.close()
            except Exception:
                pass


async def upload_database():
    if not _storage_started:
        return False

    snapshot = _create_snapshot()

    if not snapshot:
        return False

    marker = "CAFE_HERMES_DATABASE"

    try:

        await _delete_previous(
            marker
        )

        await _storage_app.send_document(
            _chat_id(),
            snapshot,
            caption=(
                f"{marker}\n"
                f"Updated: "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        )

        print(
            "Remote database synchronized."
        )

        return True

    except Exception as e:

        print(
            f"Remote database upload error: {e}"
        )

        return False

    finally:

        try:
            os.remove(snapshot)
        except Exception:
            pass


async def upload_config():
    if not _storage_started:
        return False

    if not os.path.exists(CONFIG_PATH):
        return False

    marker = "CAFE_HERMES_CONFIG"

    try:

        await _delete_previous(
            marker
        )

        await _storage_app.send_document(
            _chat_id(),
            CONFIG_PATH,
            caption=(
                f"{marker}\n"
                f"Updated: "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        )

        print(
            "Remote config synchronized."
        )

        return True

    except Exception as e:

        print(
            f"Remote config upload error: {e}"
        )

        return False


async def sync_all(force=False):
    global _dirty

    if not _storage_started:
        return False

    async with _sync_lock:

        if not force and not _dirty:
            return True

        _dirty = False

        print(
            "Remote Storage: sync started."
        )

        db_ok = await upload_database()

        config_ok = await upload_config()

        result = (
            db_ok
            and config_ok
        )

        if result:

            print(
                "Remote Storage: sync completed."
            )

        else:

            _dirty = True

            print(
                "Remote Storage: sync failed."
            )

        return result


def schedule_sync():
    global _dirty
    global _sync_task

    if not _storage_started:
        return

    _dirty = True

    try:
        loop = asyncio.get_running_loop()

    except RuntimeError:
        return

    if _sync_task and not _sync_task.done():
        return

    _sync_task = loop.create_task(
        _sync_worker()
    )


async def _sync_worker():
    global _sync_task
    global _dirty

    try:

        # Small debounce prevents 10 quick database changes
        # from creating 10 Telegram uploads.
        await asyncio.sleep(1.5)

        while _storage_started and _dirty:

            await sync_all(
                force=False
            )

            if _dirty:

                await asyncio.sleep(
                    1
                )

    except asyncio.CancelledError:
        raise

    except Exception as e:

        print(
            f"Remote sync worker error: {e}"
        )

    finally:

        _sync_task = None


async def _watch_files():
    global _last_db_mtime
    global _last_config_mtime

    _last_db_mtime = _mtime(
        DB_PATH
    )

    _last_config_mtime = _mtime(
        CONFIG_PATH
    )

    while _storage_started:

        try:

            await asyncio.sleep(
                3
            )

            db_mtime = _mtime(
                DB_PATH
            )

            config_mtime = _mtime(
                CONFIG_PATH
            )

            if db_mtime != _last_db_mtime:

                _last_db_mtime = db_mtime

                schedule_sync()

            if config_mtime != _last_config_mtime:

                _last_config_mtime = config_mtime

                schedule_sync()

        except asyncio.CancelledError:
            raise

        except Exception as e:

            print(
                f"Remote watcher error: {e}"
            )

            await asyncio.sleep(
                5
            )


def start_file_watcher():

    global _watcher_task

    if not _storage_started:
        return

    if _watcher_task and not _watcher_task.done():
        return

    try:
        loop = asyncio.get_running_loop()

    except RuntimeError:
        return

    _watcher_task = loop.create_task(
        _watch_files()
    )

    print(
        "Remote Storage watcher started."
    )


async def restore_database_from_remote():
    if not _storage_started:
        return False

    message = await _find_latest(
        "CAFE_HERMES_DATABASE"
    )

    if not message:

        print(
            "Remote Storage: no database backup found."
        )

        return False

    os.makedirs(
        "data",
        exist_ok=True
    )

    temp_path = (
        "data/.remote_restore.db"
    )

    try:

        await _storage_app.download_media(
            message,
            file_name=temp_path
        )

        if not os.path.exists(temp_path):
            return False

        if os.path.exists(DB_PATH):

            old_path = (
                "data/cafe_hermes_before_restore.db"
            )

            try:

                os.replace(
                    DB_PATH,
                    old_path
                )

            except Exception:
                pass

        os.replace(
            temp_path,
            DB_PATH
        )

        print(
            "Remote database restored."
        )

        return True

    except Exception as e:

        print(
            f"Remote database restore error: {e}"
        )

        try:

            if os.path.exists(temp_path):
                os.remove(temp_path)

        except Exception:
            pass

        return False


async def restore_config_from_remote():
    if not _storage_started:
        return False

    message = await _find_latest(
        "CAFE_HERMES_CONFIG"
    )

    if not message:

        print(
            "Remote Storage: no config backup found."
        )

        return False

    os.makedirs(
        "data",
        exist_ok=True
    )

    temp_path = (
        "data/.remote_config.json"
    )

    try:

        await _storage_app.download_media(
            message,
            file_name=temp_path
        )

        if not os.path.exists(temp_path):
            return False

        with open(
            temp_path,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if not isinstance(data, dict):
            return False

        with open(
            CONFIG_PATH,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2
            )

        os.remove(
            temp_path
        )

        print(
            "Remote config restored."
        )

        return True

    except Exception as e:

        print(
            f"Remote config restore error: {e}"
        )

        try:

            if os.path.exists(temp_path):
                os.remove(temp_path)

        except Exception:
            pass

        return False


async def restore_from_remote():

    if not _storage_started:
        return False

    print(
        "Remote Storage: checking remote state..."
    )

    db_ok = await restore_database_from_remote()

    config_ok = await restore_config_from_remote()

    return (
        db_ok
        or config_ok
    )
