import os
import json
import asyncio
import sqlite3
import zipfile
import shutil
import time
from datetime import datetime

import aiohttp


DB_PATH = "data/cafe_hermes.db"
CONFIG_PATH = "config.json"

# Primary/current storage channel = user data.
STORAGE_CHAT_ID = os.getenv("STORAGE_CHAT_ID")

# Dedicated private storage channels.
# These are identifiers, not credentials.
STORAGE_CHAT_ID = -1004448775237
STORAGE_CONFIG_CHAT_ID = -1003851272792
STORAGE_FILES_CHAT_ID = -1004358599764

BOT_TOKEN = os.getenv("BOT_TOKEN")

DB_STATE_MARKER = "CAFE_HERMES_DB_STATE"
CONFIG_STATE_MARKER = "CAFE_HERMES_CONFIG_STATE"
LEGACY_STATE_MARKER = "CAFE_HERMES_STATE"

DB_ARCHIVE = "data/.remote_db_state.db"
CONFIG_ARCHIVE = "data/.remote_config_state.zip"
LEGACY_ARCHIVE = "data/.remote_state.zip"

_storage_app = None
_storage_started = False

_storage_data_chat_id = None
_storage_config_chat_id = None
_storage_files_chat_id = None

_sync_task = None
_sync_lock = asyncio.Lock()
_cleanup_task = None

# Only these generated temporary paths are disposable. Never remove DB_PATH,
# remote archives in Telegram, or the pre-restore recovery copy.
_TEMP_FILES = (
    "data/.remote_database_snapshot.db",
    "data/.remote_db_state.db",
    "data/.remote_db_state.zip",
    "data/.remote_db_download.tmp",
    "data/.remote_config_state.zip",
    "data/.remote_state.zip",
    "data/.remote_config_snapshot.json",
    "data/.remote_restore_tmp.zip",
)
_TEMP_DIRS = (
    "data/.remote_db_restore",
    "data/.remote_config_restore",
    "data/.remote_state_restore",
)

# Each committed database change schedules a fresh Telegram snapshot.
# A short debounce merges only writes that happen in the same burst.
MIN_SYNC_INTERVAL = 0
_last_sync_at = 0.0

_dirty = False
_last_db_mtime = None
_last_config_mtime = None
_watcher_task = None

_db_state_message_id = None
_config_state_message_id = None


def storage_enabled():
    return bool(
        STORAGE_CHAT_ID
        and STORAGE_CONFIG_CHAT_ID
        and STORAGE_FILES_CHAT_ID
        and BOT_TOKEN
    )


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


async def _bot_api(method, data=None, multipart=None):
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured.")

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    timeout = aiohttp.ClientTimeout(total=120)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        if multipart is not None:
            request = session.post(url, data=multipart)
        else:
            request = session.post(url, json=data or {})

        async with request as response:
            payload = await response.json(content_type=None)

            if not payload.get("ok"):
                description = payload.get(
                    "description",
                    "Telegram API error"
                )
                raise RuntimeError(description)

            return payload.get("result")


async def _get_chat_info(chat_id):
    try:
        target_id = int(chat_id)
    except (TypeError, ValueError):
        raise RuntimeError(
            "Storage chat id is invalid."
        )

    chat = await _bot_api(
        "getChat",
        {
            "chat_id": target_id
        }
    )

    if not chat or chat.get("id") != target_id:
        raise RuntimeError(
            "Telegram returned a different storage chat."
        )

    return chat


async def start_storage(app):
    global _storage_app
    global _storage_started
    global _storage_data_chat_id
    global _storage_config_chat_id
    global _storage_files_chat_id

    _storage_app = app

    if not BOT_TOKEN:
        print(
            "Remote Storage: BOT_TOKEN is not configured."
        )
        return False

    if not STORAGE_CHAT_ID:
        print(
            "Remote Storage: STORAGE_CHAT_ID is not configured."
        )
        return False

    if not STORAGE_CONFIG_CHAT_ID:
        print(
            "Remote Storage: STORAGE_CONFIG_CHAT_ID is not configured."
        )
        return False

    if not STORAGE_FILES_CHAT_ID:
        print(
            "Remote Storage: STORAGE_FILES_CHAT_ID is not configured."
        )
        return False

    try:
        print(
            "Remote Storage: resolving storage channels automatically..."
        )

        data_chat = await _get_chat_info(
            STORAGE_CHAT_ID
        )

        config_chat = await _get_chat_info(
            STORAGE_CONFIG_CHAT_ID
        )

        files_chat = await _get_chat_info(
            STORAGE_FILES_CHAT_ID
        )

        channel_ids = {
            data_chat["id"],
            config_chat["id"],
            files_chat["id"]
        }

        if len(channel_ids) != 3:
            raise RuntimeError(
                "Storage channels must be three different private channels."
            )

        _storage_data_chat_id = data_chat["id"]
        _storage_config_chat_id = config_chat["id"]
        _storage_files_chat_id = files_chat["id"]

        _storage_started = True

        print(
            "Remote Storage: data channel connected: "
            f"{_storage_data_chat_id}"
        )
        print(
            "Remote Storage: config channel connected: "
            f"{_storage_config_chat_id}"
        )
        print(
            "Remote Storage: files channel connected: "
            f"{_storage_files_chat_id}"
        )

        return True

    except Exception as e:
        _storage_started = False

        print(
            f"Remote Storage connection error: {e}"
        )
        print(
            "Remote Storage: make sure the bot is a member/admin "
            "of all configured storage channels."
        )

        return False


async def stop_storage():
    global _storage_app
    global _storage_started
    global _storage_data_chat_id
    global _storage_config_chat_id
    global _storage_files_chat_id
    global _sync_task
    global _watcher_task
    global _dirty
    global _db_state_message_id
    global _config_state_message_id

    for task_name in (
        "_watcher_task",
        "_sync_task"
    ):
        task = globals().get(task_name)

        if task:
            try:
                task.cancel()
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

    _watcher_task = None
    _sync_task = None
    _storage_app = None
    _storage_data_chat_id = None
    _storage_config_chat_id = None
    _storage_files_chat_id = None
    _storage_started = False
    _dirty = False
    _db_state_message_id = None
    _config_state_message_id = None


def _data_chat_id():
    if _storage_data_chat_id is not None:
        return _storage_data_chat_id

    return int(STORAGE_CHAT_ID)


def _config_chat_id():
    if _storage_config_chat_id is not None:
        return _storage_config_chat_id

    return int(STORAGE_CONFIG_CHAT_ID)


def _files_chat_id():
    if _storage_files_chat_id is not None:
        return _storage_files_chat_id

    return int(STORAGE_FILES_CHAT_ID)


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


def _create_db_archive():
    """Create a consistent SQLite backup without making a second ZIP copy.

    Keeping only one temporary database copy greatly reduces peak disk usage.
    The restore path below remains compatible with older ZIP backups.
    """
    if not os.path.exists(DB_PATH):
        return None

    os.makedirs("data", exist_ok=True)

    try:
        _cleanup_file(DB_ARCHIVE)

        source = sqlite3.connect(DB_PATH, timeout=30)
        destination = sqlite3.connect(DB_ARCHIVE, timeout=30)

        try:
            source.backup(destination)
            result = destination.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise RuntimeError("Database backup failed integrity_check.")
        finally:
            destination.close()
            source.close()

        return DB_ARCHIVE

    except Exception as e:
        print(f"Remote database archive error: {e}")
        _cleanup_file(DB_ARCHIVE)
        return None


def _create_config_archive():
    config = _sanitized_config()

    if config is None:
        return None

    os.makedirs(
        "data",
        exist_ok=True
    )

    snapshot_path = (
        "data/.remote_config_snapshot.json"
    )

    try:
        if os.path.exists(CONFIG_ARCHIVE):
            os.remove(CONFIG_ARCHIVE)

        with open(
            snapshot_path,
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
            CONFIG_ARCHIVE,
            "w",
            compression=zipfile.ZIP_DEFLATED
        ) as archive:
            archive.write(
                snapshot_path,
                arcname="config.json"
            )

        return CONFIG_ARCHIVE

    except Exception as e:
        print(
            f"Remote config archive error: {e}"
        )
        return None

    finally:
        try:
            if os.path.exists(snapshot_path):
                os.remove(snapshot_path)
        except Exception:
            pass


def _cleanup_file(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def cleanup_temporary_files(force=False):
    """Remove only known disposable artifacts; never touch the live database.

    Periodic cleanup removes only artifacts older than one hour to avoid
    interfering with an active restore or upload. Startup cleanup may force it.
    """
    now = time.time()
    max_age = 60 * 60

    for path in _TEMP_FILES:
        try:
            if not os.path.isfile(path):
                continue
            if force or now - os.path.getmtime(path) > max_age:
                _cleanup_file(path)
        except OSError:
            pass

    for path in _TEMP_DIRS:
        try:
            if not os.path.isdir(path):
                continue
            if force or now - os.path.getmtime(path) > max_age:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            pass


async def _temporary_cleanup_worker():
    while True:
        try:
            await asyncio.sleep(30 * 60)
            cleanup_temporary_files()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"Temporary cleanup error: {e}")
            await asyncio.sleep(60)


def start_temporary_cleanup():
    global _cleanup_task
    if _cleanup_task and not _cleanup_task.done():
        return
    try:
        _cleanup_task = asyncio.get_running_loop().create_task(
            _temporary_cleanup_worker()
        )
        print("Temporary cleanup scheduled every 30 minutes.")
    except RuntimeError:
        _cleanup_task = None


async def stop_temporary_cleanup():
    global _cleanup_task
    task = _cleanup_task
    _cleanup_task = None
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def _get_state_message(
    chat_id=None,
    marker=None
):
    if chat_id is None:
        chat_id = (
            _storage_data_chat_id
            if _storage_data_chat_id is not None
            else STORAGE_CHAT_ID
        )

    if marker is None:
        marker = DB_STATE_MARKER

    try:
        chat = await _get_chat_info(
            chat_id
        )
    except Exception as e:
        print(
            f"Remote Storage: state getChat failed: {e}"
        )
        return None

    pinned = (
        chat.get("pinned_message")
        if isinstance(chat, dict)
        else None
    )

    if not pinned:
        return None

    caption = (
        pinned.get("caption")
        or pinned.get("text")
        or ""
    )

    if not caption.startswith(marker):
        return None

    message_id = (
        pinned.get("message_id")
        or pinned.get("id")
    )

    if not message_id:
        return None

    return pinned


async def _send_document(
    chat_id,
    archive_path,
    caption
):
    form = aiohttp.FormData()

    form.add_field(
        "chat_id",
        str(chat_id)
    )
    form.add_field(
        "caption",
        caption
    )

    with open(
        archive_path,
        "rb"
    ) as document:
        form.add_field(
            "document",
            document,
            filename=os.path.basename(
                archive_path
            ),
            content_type="application/zip"
        )

        return await _bot_api(
            "sendDocument",
            multipart=form
        )


async def _edit_document(
    chat_id,
    message_id,
    archive_path,
    caption
):
    form = aiohttp.FormData()

    form.add_field(
        "chat_id",
        str(chat_id)
    )
    form.add_field(
        "message_id",
        str(message_id)
    )
    form.add_field(
        "media",
        json.dumps(
            {
                "type": "document",
                "media": "attach://statefile",
                "caption": caption
            }
        )
    )

    with open(
        archive_path,
        "rb"
    ) as document:
        form.add_field(
            "statefile",
            document,
            filename=os.path.basename(
                archive_path
            ),
            content_type="application/zip"
        )

        return await _bot_api(
            "editMessageMedia",
            multipart=form
        )


async def _pin_message(
    chat_id,
    message_id
):
    return await _bot_api(
        "pinChatMessage",
        {
            "chat_id": chat_id,
            "message_id": message_id,
            "disable_notification": True
        }
    )


async def _unpin_message(chat_id, message_id):
    return await _bot_api(
        "unpinChatMessage",
        {
            "chat_id": chat_id,
            "message_id": message_id
        }
    )


async def _create_or_replace_channel_state(
    chat_id,
    marker,
    label,
    archive_path,
    state_message_id=None
):
    # Keep one current backup message per channel. Telegram supports replacing
    # the document media in-place, so the message id and its pin remain stable.
    existing = await _get_state_message(chat_id, marker)

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    caption = (
        f"{marker}\n"
        f"Contains: {label}\n"
        f"Backup time: {stamp}"
    )

    if existing:
        message_id = existing.get("message_id") or existing.get("id")
        if not message_id:
            raise RuntimeError("Existing Telegram backup message has no message_id.")

        # Never fall back to sending a new post if editing fails: doing so
        # would recreate the unbounded archive accumulation this avoids.
        # The old document remains available and sync_all will retry later.
        edited = await _edit_document(
            chat_id,
            message_id,
            archive_path,
            caption
        )
        if not edited:
            raise RuntimeError("Telegram did not confirm the backup message edit.")

        print(
            f"Remote Storage: updated existing {label} backup "
            f"in message {message_id}."
        )
        return message_id

    # First run (or missing pinned restore point): create and pin the initial
    # state message. Subsequent syncs will edit this same message in-place.
    sent = await _send_document(chat_id, archive_path, caption)
    if not sent:
        raise RuntimeError("Telegram did not return the uploaded backup message.")

    message_id = sent.get("message_id") or sent.get("id")
    if not message_id:
        raise RuntimeError("Telegram backup message has no message_id.")

    await _pin_message(chat_id, message_id)
    return message_id


async def sync_all(force=False):
    global _dirty
    global _db_state_message_id
    global _config_state_message_id
    global _last_sync_at

    if not _storage_started:
        return False

    async with _sync_lock:
        if not force and not _dirty:
            return True

        _dirty = False
        _last_sync_at = time.monotonic()

        print("Remote Storage: sync started.")

        db_archive = None
        config_archive = None

        try:
            # Create one archive at a time and offload SQLite/compression work
            # from the Telegram event loop. This lowers peak disk use and keeps
            # member-facing handlers responsive.
            db_archive = await asyncio.to_thread(_create_db_archive)
            if not db_archive:
                raise RuntimeError("Could not create database archive.")

            _db_state_message_id = await _create_or_replace_channel_state(
                _data_chat_id(),
                DB_STATE_MARKER,
                "database / users / orders / subscriptions / services / coupons",
                db_archive,
                _db_state_message_id
            )

            # The database archive is no longer needed after Telegram confirms
            # the upload/edit. Delete it before creating the next archive.
            _cleanup_file(db_archive)
            db_archive = None

            config_archive = await asyncio.to_thread(_create_config_archive)
            if not config_archive:
                raise RuntimeError("Could not create config archive.")

            _config_state_message_id = await _create_or_replace_channel_state(
                _config_chat_id(),
                CONFIG_STATE_MARKER,
                "bot settings and configuration",
                config_archive,
                _config_state_message_id
            )

            print("Remote Storage: sync completed.")
            return True

        except Exception as e:
            _dirty = True
            print(f"Remote Storage: sync failed: {e}")
            return False

        finally:
            _cleanup_file(db_archive)
            _cleanup_file(config_archive)


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
        await asyncio.sleep(0.5)

        while (
            _storage_started
            and _dirty
        ):
            # Batch frequent database writes; do not create a full archive
            # more than once per minute during normal background syncing.
            remaining = MIN_SYNC_INTERVAL - (time.monotonic() - _last_sync_at)
            if remaining > 0:
                await asyncio.sleep(remaining)
                if not _storage_started or not _dirty:
                    break

            await sync_all(
                force=False
            )

            if _dirty:
                await asyncio.sleep(2)

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
            await asyncio.sleep(1)

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


async def _download_document(
    message,
    destination
):
    document = (
        message.get("document")
        if isinstance(message, dict)
        else None
    )

    if not document:
        raise RuntimeError(
            "Remote state message has no document."
        )

    file_id = document.get("file_id")

    if not file_id:
        raise RuntimeError(
            "Remote state file_id is missing."
        )

    file_info = await _bot_api(
        "getFile",
        {
            "file_id": file_id
        }
    )

    file_path = (
        file_info.get("file_path")
        if file_info
        else None
    )

    if not file_path:
        raise RuntimeError(
            "Telegram did not return a file path."
        )

    url = (
        f"https://api.telegram.org/file/"
        f"bot{BOT_TOKEN}/{file_path}"
    )

    timeout = aiohttp.ClientTimeout(
        total=180
    )

    async with aiohttp.ClientSession(
        timeout=timeout
    ) as session:
        async with session.get(
            url
        ) as response:
            if response.status != 200:
                raise RuntimeError(
                    "Telegram file download failed "
                    f"with HTTP {response.status}."
                )

            with open(
                destination,
                "wb"
            ) as output:
                while True:
                    chunk = await response.content.read(
                        1024 * 1024
                    )

                    if not chunk:
                        break

                    output.write(chunk)


async def _restore_archive(
    message,
    expected_name,
    extract_root
):
    temp_archive = os.path.join(
        "data",
        ".remote_restore_tmp.zip"
    )

    _cleanup_file(
        temp_archive
    )

    await _download_document(
        message,
        temp_archive
    )

    if not os.path.exists(
        temp_archive
    ):
        raise RuntimeError(
            "Remote archive download failed."
        )

    try:
        _cleanup_extract_root(
            extract_root
        )

        os.makedirs(
            extract_root,
            exist_ok=True
        )

        with zipfile.ZipFile(
            temp_archive,
            "r"
        ) as archive:
            names = set(
                archive.namelist()
            )

            if expected_name not in names:
                raise RuntimeError(
                    "Remote archive is incomplete."
                )

            archive.extract(
                expected_name,
                extract_root
            )

    finally:
        _cleanup_file(
            temp_archive
        )


def _cleanup_extract_root(
    extract_root
):
    try:
        shutil.rmtree(
            extract_root,
            ignore_errors=True
        )
    except Exception:
        pass


async def _restore_database_from_message(message):
    """Restore either the new raw SQLite backup or a legacy ZIP backup."""
    extract_root = "data/.remote_db_restore"
    temp_download = "data/.remote_db_download.tmp"
    recovery_copy = "data/cafe_hermes_before_restore.db"

    _cleanup_file(temp_download)
    await _download_document(message, temp_download)

    extracted_db = temp_download
    try:
        if zipfile.is_zipfile(temp_download):
            _cleanup_extract_root(extract_root)
            os.makedirs(extract_root, exist_ok=True)
            with zipfile.ZipFile(temp_download, "r") as archive:
                if "cafe_hermes.db" not in set(archive.namelist()):
                    raise RuntimeError("Remote ZIP backup has no database.")
                archive.extract("cafe_hermes.db", extract_root)
            extracted_db = os.path.join(extract_root, "cafe_hermes.db")

        if not os.path.isfile(extracted_db):
            raise RuntimeError("Restored database is missing.")

        # Validate the downloaded database before replacing the live one.
        check = sqlite3.connect(extracted_db, timeout=30)
        try:
            result = check.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise RuntimeError("Remote database failed integrity_check.")
        finally:
            check.close()

        # Keep one recovery copy during replacement only; remove it after the
        # restored database is in place to avoid permanently doubling disk use.
        _cleanup_file(recovery_copy)
        if os.path.exists(DB_PATH):
            os.replace(DB_PATH, recovery_copy)

        try:
            os.replace(extracted_db, DB_PATH)
        except Exception:
            if os.path.exists(recovery_copy) and not os.path.exists(DB_PATH):
                os.replace(recovery_copy, DB_PATH)
            raise

        _cleanup_file(recovery_copy)
        print("Remote Storage: temporary restore files cleaned up.")

    finally:
        _cleanup_file(temp_download)
        _cleanup_extract_root(extract_root)


async def _restore_config_from_message(
    message
):
    extract_root = (
        "data/.remote_config_restore"
    )

    await _restore_archive(
        message,
        "config.json",
        extract_root
    )

    extracted_config = os.path.join(
        extract_root,
        "config.json"
    )

    if not os.path.exists(
        extracted_config
    ):
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

    os.replace(
        extracted_config,
        CONFIG_PATH
    )

    _cleanup_extract_root(
        extract_root
    )


async def _restore_legacy_combined_state():
    legacy_message = await _get_state_message(
        _data_chat_id(),
        LEGACY_STATE_MARKER
    )

    if not legacy_message:
        return False

    extract_root = (
        "data/.remote_legacy_restore"
    )

    await _restore_archive(
        legacy_message,
        "cafe_hermes.db",
        extract_root
    )

    # Re-open the archive once to restore both files from the same legacy zip.
    temp_archive = (
        "data/.remote_legacy_restore.zip"
    )

    await _download_document(
        legacy_message,
        temp_archive
    )

    try:
        with zipfile.ZipFile(
            temp_archive,
            "r"
        ) as archive:
            names = set(
                archive.namelist()
            )

            if {
                "cafe_hermes.db",
                "config.json"
            }.issubset(names):
                legacy_root = (
                    "data/.remote_legacy_restore_full"
                )

                _cleanup_extract_root(
                    legacy_root
                )

                os.makedirs(
                    legacy_root,
                    exist_ok=True
                )

                archive.extract(
                    "cafe_hermes.db",
                    legacy_root
                )
                archive.extract(
                    "config.json",
                    legacy_root
                )

                legacy_db = os.path.join(
                    legacy_root,
                    "cafe_hermes.db"
                )

                legacy_config = os.path.join(
                    legacy_root,
                    "config.json"
                )

                if os.path.exists(
                    DB_PATH
                ):
                    try:
                        os.replace(
                            DB_PATH,
                            "data/cafe_hermes_before_restore.db"
                        )
                    except Exception:
                        pass

                os.replace(
                    legacy_db,
                    DB_PATH
                )

                os.replace(
                    legacy_config,
                    CONFIG_PATH
                )

                _cleanup_extract_root(
                    legacy_root
                )

                return True

    finally:
        _cleanup_file(
            temp_archive
        )
        _cleanup_extract_root(
            extract_root
        )

    return False


async def restore_from_remote():
    if not _storage_started:
        return False

    print(
        "Remote Storage: checking remote state..."
    )

    restored_any = False

    try:
        db_message = await _get_state_message(
            _data_chat_id(),
            DB_STATE_MARKER
        )

        config_message = await _get_state_message(
            _config_chat_id(),
            CONFIG_STATE_MARKER
        )

        if db_message:
            try:
                await _restore_database_from_message(
                    db_message
                )
                restored_any = True
                print(
                    "Remote Storage: database restored."
                )
            except Exception as e:
                print(
                    f"Remote database restore error: {e}"
                )

        if config_message:
            try:
                await _restore_config_from_message(
                    config_message
                )
                restored_any = True
                print(
                    "Remote Storage: configuration restored."
                )
            except Exception as e:
                print(
                    f"Remote config restore error: {e}"
                )

        if restored_any:
            print(
                "Remote state restored successfully."
            )
            return True

        legacy_restored = (
            await _restore_legacy_combined_state()
        )

        if legacy_restored:
            print(
                "Remote state restored successfully "
                "from legacy combined backup."
            )
            return True

        print(
            "Remote Storage: no remote state backup found."
        )
        return False

    except Exception as e:
        print(
            f"Remote state restore error: {e}"
        )
        return False


async def store_media_message(message):
    """Store a durable copy of uploaded media in the dedicated files channel.

    Telegram's copyMessage returns only a MessageId, so it does not expose the
    copied file_id. Instead, send the existing media file_id directly to the
    dedicated files channel and read the returned Message object.
    """

    if not _storage_started:
        return None

    if not message:
        return None

    chat_id = _files_chat_id()
    caption = getattr(
        message,
        "caption",
        None
    ) or ""

    try:
        result = None

        if getattr(message, "document", None):
            result = await _bot_api(
                "sendDocument",
                {
                    "chat_id": chat_id,
                    "document": message.document.file_id,
                    "caption": caption
                }
            )

        elif getattr(message, "video", None):
            result = await _bot_api(
                "sendVideo",
                {
                    "chat_id": chat_id,
                    "video": message.video.file_id,
                    "caption": caption
                }
            )

        elif getattr(message, "animation", None):
            result = await _bot_api(
                "sendAnimation",
                {
                    "chat_id": chat_id,
                    "animation": message.animation.file_id,
                    "caption": caption
                }
            )

        elif getattr(message, "photo", None):
            result = await _bot_api(
                "sendPhoto",
                {
                    "chat_id": chat_id,
                    "photo": message.photo.file_id,
                    "caption": caption
                }
            )

        if not isinstance(result, dict):
            print(
                "Remote Storage: media upload returned no message object."
            )
            return None

        copied_message_id = (
            result.get("message_id")
            or result.get("id")
        )

        file_id = None

        if result.get("document"):
            file_id = result["document"].get("file_id")

        elif result.get("video"):
            file_id = result["video"].get("file_id")

        elif result.get("animation"):
            file_id = result["animation"].get("file_id")

        elif result.get("photo"):
            photos = result["photo"]
            if isinstance(photos, list) and photos:
                file_id = photos[-1].get("file_id")

        if not file_id:
            print(
                "Remote Storage: media was uploaded but no file_id was returned."
            )
            return {
                "message_id": copied_message_id,
                "file_id": None
            }

        print(
            "Remote Storage: media stored in files channel."
        )

        return {
            "message_id": copied_message_id,
            "file_id": file_id
        }

    except Exception as e:
        print(
            f"Remote Storage: media upload failed: {e}"
        )
        return None
