import os
import json
import asyncio
import sqlite3
import zipfile
import shutil
from datetime import datetime

from pyrogram import filters
from pyrogram.types import InputMediaDocument


DB_PATH = "data/cafe_hermes.db"
CONFIG_PATH = "config.json"
STATE_MARKER = "CAFE_HERMES_STATE"
STATE_ARCHIVE = "data/.remote_state.zip"

STORAGE_CHAT_ID = os.getenv("STORAGE_CHAT_ID")

_storage_app = None
_storage_started = False
_storage_chat = None
_storage_ready_event = None
_storage_observer_registered = False

_state_message_id = None

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


async def _connect_from_channel_message(message):
    global _storage_chat
    global _storage_started

    if not STORAGE_CHAT_ID:
        return

    try:
        target_id = int(STORAGE_CHAT_ID)
    except (TypeError, ValueError):
        return

    if not message or not message.chat:
        return

    if message.chat.id != target_id:
        return

    _storage_chat = message.chat
    _storage_started = True

    print(
        "Remote Storage: storage channel detected from a new channel post: "
        f"{_storage_chat.id}"
    )

    if _storage_ready_event and not _storage_ready_event.is_set():
        _storage_ready_event.set()


async def _register_storage_observer(app):
    global _storage_ready_event
    global _storage_observer_registered

    if _storage_observer_registered:
        return

    _storage_ready_event = asyncio.Event()

    @app.on_message(filters.channel, group=-1000)
    async def _storage_channel_observer(client, message):
        await _connect_from_channel_message(message)

    _storage_observer_registered = True


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
            "Remote Storage: connecting to storage channel..."
        )

        try:
            _storage_chat = await _storage_app.get_chat(target_id)
        except Exception as e:
            print(
                f"Remote Storage: direct channel lookup unavailable: {e}"
            )
            _storage_chat = None

        if _storage_chat is None:
            await _register_storage_observer(_storage_app)

            print(
                "Remote Storage: waiting for a new post from the storage channel..."
            )
            print(
                "Send any new message in the private storage channel while the bot is starting."
            )

            try:
                await asyncio.wait_for(
                    _storage_ready_event.wait(),
                    timeout=30
                )
            except asyncio.TimeoutError:
                print(
                    "Remote Storage: storage channel was not detected within 30 seconds."
                )
                _storage_started = False
                return False

        if _storage_chat is None or _storage_chat.id != target_id:
            print(
                "Remote Storage: storage channel could not be confirmed."
            )
            _storage_started = False
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
    global _state_message_id

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
    _state_message_id = None


def _chat_id():
    if _storage_chat:
        return _storage_chat.id
    return int(STORAGE_CHAT_ID)


def _sanitized_config():
    if not os.path.exists(CONFIG_PATH):
        return None

    try:
        with open(
            CONFIG_PATH,
            "r",
            encoding="utf-8"
        ) as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return None

        for key in (
            "api_id",
            "api_hash",
            "bot_token"
        ):
            data.pop(key, None)

        return data

    except Exception as e:
        print(
            f"Remote config snapshot error: {e}"
        )
        return None


def _create_state_archive():
    if not os.path.exists(DB_PATH):
        return None

    config = _sanitized_config()

    if config is None:
        return None

    os.makedirs(
        "data",
        exist_ok=True
    )

    snapshot_path = "data/.remote_database_snapshot.db"
    config_snapshot_path = "data/.remote_config_snapshot.json"

    try:
        if os.path.exists(STATE_ARCHIVE):
            os.remove(STATE_ARCHIVE)

        source = None
        destination = None

        try:
            source = sqlite3.connect(DB_PATH)
            destination = sqlite3.connect(snapshot_path)
            source.backup(destination)

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

        with open(
            config_snapshot_path,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                config,
                f,
                ensure_ascii=False,
                indent=2
            )

        with zipfile.ZipFile(
            STATE_ARCHIVE,
            "w",
            compression=zipfile.ZIP_DEFLATED
        ) as archive:
            archive.write(
                snapshot_path,
                arcname="cafe_hermes.db"
            )
            archive.write(
                config_snapshot_path,
                arcname="config.json"
            )

        return STATE_ARCHIVE

    except Exception as e:
        print(
            f"Remote state archive error: {e}"
        )
        return None

    finally:
        for path in (
            snapshot_path,
            config_snapshot_path
        ):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass


def _cleanup_extract():
    try:
        shutil.rmtree(
            "data/.remote_state_extract",
            ignore_errors=True
        )
    except Exception:
        pass


def _cleanup_archive():
    try:
        if os.path.exists(STATE_ARCHIVE):
            os.remove(STATE_ARCHIVE)
    except Exception:
        pass


async def _refresh_storage_chat():
    global _storage_chat

    if not _storage_app or not _storage_chat:
        return None

    try:
        _storage_chat = await _storage_app.get_chat(
            _storage_chat.id
        )
    except Exception as e:
        print(
            f"Remote Storage: chat refresh error: {e}"
        )
        return None

    return _storage_chat


async def _get_state_message():
    global _state_message_id

    if not _storage_started:
        return None

    chat = await _refresh_storage_chat()

    if not chat:
        return None

    pinned = getattr(
        chat,
        "pinned_message",
        None
    )

    if pinned:
        caption = pinned.caption or pinned.text or ""

        if caption.startswith(
            STATE_MARKER
        ):
            _state_message_id = pinned.id
            return pinned

    if _state_message_id:
        try:
            message = await _storage_app.get_messages(
                _chat_id(),
                _state_message_id
            )

            if message:
                caption = message.caption or message.text or ""

                if caption.startswith(
                    STATE_MARKER
                ):
                    return message

        except Exception:
            pass

    return None


async def _create_or_replace_state():
    global _state_message_id

    archive_path = _create_state_archive()

    if not archive_path:
        return False

    caption = (
        f"{STATE_MARKER}\n"
        "Contains: database + configuration\n"
        f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    try:
        existing = await _get_state_message()

        if existing:
            try:
                edited = await _storage_app.edit_message_media(
                    _chat_id(),
                    existing.id,
                    InputMediaDocument(
                        archive_path,
                        caption=caption
                    )
                )

                _state_message_id = (
                    edited.id
                    if edited
                    else existing.id
                )

                print(
                    "Remote Storage: state message updated."
                )

                return True

            except Exception as e:
                print(
                    f"Remote Storage: state message edit failed: {e}"
                )

        sent = await _storage_app.send_document(
            _chat_id(),
            archive_path,
            caption=caption
        )

        if not sent:
            return False

        _state_message_id = sent.id

        try:
            await _storage_app.pin_chat_message(
                _chat_id(),
                sent.id,
                disable_notification=True
            )
        except Exception as e:
            print(
                f"Remote Storage: pin failed: {e}"
            )

        print(
            "Remote Storage: new state message created."
        )

        return True

    except Exception as e:
        print(
            f"Remote Storage: state upload error: {e}"
        )
        return False

    finally:
        _cleanup_archive()


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

        result = await _create_or_replace_state()

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

    if (
        _sync_task
        and not _sync_task.done()
    ):
        return

    _sync_task = loop.create_task(
        _sync_worker()
    )


async def _sync_worker():
    global _sync_task
    global _dirty

    try:
        await asyncio.sleep(1.5)

        while (
            _storage_started
            and _dirty
        ):
            await sync_all(
                force=False
            )

            if _dirty:
                await asyncio.sleep(1)

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

    _last_db_mtime = _mtime(DB_PATH)
    _last_config_mtime = _mtime(CONFIG_PATH)

    while _storage_started:
        try:
            await asyncio.sleep(3)

            db_mtime = _mtime(DB_PATH)
            config_mtime = _mtime(CONFIG_PATH)

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
            await asyncio.sleep(5)


def start_file_watcher():
    global _watcher_task

    if not _storage_started:
        return

    if (
        _watcher_task
        and not _watcher_task.done()
    ):
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


async def restore_from_remote():
    if not _storage_started:
        return False

    print(
        "Remote Storage: checking remote state..."
    )

    message = await _get_state_message()

    if not message:
        print(
            "Remote Storage: no pinned state backup found."
        )
        return False

    os.makedirs(
        "data",
        exist_ok=True
    )

    temp_archive = "data/.remote_state_restore.zip"
    extract_root = "data/.remote_state_extract"

    _cleanup_extract()

    try:
        await _storage_app.download_media(
            message,
            file_name=temp_archive
        )

        if not os.path.exists(temp_archive):
            return False

        os.makedirs(
            extract_root,
            exist_ok=True
        )

        with zipfile.ZipFile(
            temp_archive,
            "r"
        ) as archive:
            names = set(archive.namelist())

            if not {
                "cafe_hermes.db",
                "config.json"
            }.issubset(names):
                raise RuntimeError(
                    "Remote state archive is incomplete."
                )

            archive.extract(
                "cafe_hermes.db",
                extract_root
            )
            archive.extract(
                "config.json",
                extract_root
            )

        extracted_db = (
            "data/.remote_state_extract/cafe_hermes.db"
        )
        extracted_config = (
            "data/.remote_state_extract/config.json"
        )

        if not os.path.exists(extracted_db):
            raise RuntimeError(
                "Restored database is missing."
            )

        if not os.path.exists(extracted_config):
            raise RuntimeError(
                "Restored config is missing."
            )

        with open(
            extracted_config,
            "r",
            encoding="utf-8"
        ) as f:
            restored_config = json.load(f)

        if not isinstance(
            restored_config,
            dict
        ):
            raise RuntimeError(
                "Restored config is invalid."
            )

        if os.path.exists(DB_PATH):
            try:
                os.replace(
                    DB_PATH,
                    "data/cafe_hermes_before_restore.db"
                )
            except Exception:
                pass

        os.replace(
            extracted_db,
            DB_PATH
        )

        os.replace(
            extracted_config,
            CONFIG_PATH
        )

        print(
            "Remote state restored successfully."
        )

        return True

    except Exception as e:
        print(
            f"Remote state restore error: {e}"
        )
        return False

    finally:
        try:
            if os.path.exists(temp_archive):
                os.remove(temp_archive)
        except Exception:
            pass

        _cleanup_extract()
