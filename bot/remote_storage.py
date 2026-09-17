import os
import json
import asyncio
import sqlite3
import zipfile
import shutil
from datetime import datetime

import aiohttp


DB_PATH = "data/cafe_hermes.db"
CONFIG_PATH = "config.json"
STATE_MARKER = "CAFE_HERMES_STATE"
STATE_ARCHIVE = "data/.remote_state.zip"

STORAGE_CHAT_ID = os.getenv("STORAGE_CHAT_ID")
BOT_TOKEN = os.getenv("BOT_TOKEN")

_storage_app = None
_storage_started = False
_storage_chat_id = None

_sync_task = None
_sync_lock = asyncio.Lock()

_dirty = False
_last_db_mtime = None
_last_config_mtime = None
_watcher_task = None

_state_message_id = None


def storage_enabled():
    return bool(STORAGE_CHAT_ID and BOT_TOKEN)


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


async def _bot_api(method, data=None, multipart=None):
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not configured.")

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    timeout = aiohttp.ClientTimeout(total=60)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        if multipart is not None:
            request = session.post(url, data=multipart)
        else:
            request = session.post(url, json=data or {})

        async with request as response:
            payload = await response.json(content_type=None)

            if not payload.get("ok"):
                description = payload.get("description", "Telegram API error")
                raise RuntimeError(description)

            return payload.get("result")


async def _get_storage_chat():
    global _storage_chat_id

    try:
        target_id = int(STORAGE_CHAT_ID)
    except (TypeError, ValueError):
        raise RuntimeError("STORAGE_CHAT_ID is invalid.")

    chat = await _bot_api(
        "getChat",
        {"chat_id": target_id}
    )

    if not chat or chat.get("id") != target_id:
        raise RuntimeError("Telegram returned a different storage chat.")

    _storage_chat_id = target_id
    return chat


async def start_storage(app):
    global _storage_app
    global _storage_started
    global _storage_chat_id

    _storage_app = app

    if not STORAGE_CHAT_ID:
        print("Remote Storage: STORAGE_CHAT_ID is not configured.")
        return False

    if not BOT_TOKEN:
        print("Remote Storage: BOT_TOKEN is not configured.")
        return False

    try:
        print("Remote Storage: resolving private storage channel automatically...")

        chat = await _get_storage_chat()
        _storage_chat_id = chat["id"]
        _storage_started = True

        print(
            "Remote Storage connected automatically: "
            f"{_storage_chat_id}"
        )

        return True

    except Exception as e:
        _storage_started = False
        _storage_chat_id = None
        print(f"Remote Storage connection error: {e}")
        print(
            "Remote Storage: make sure the bot is a member/admin of the private channel."
        )
        return False


async def stop_storage():
    global _storage_started
    global _storage_app
    global _storage_chat_id
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
    _storage_chat_id = None
    _storage_started = False
    _dirty = False
    _state_message_id = None


def _chat_id():
    if _storage_chat_id is not None:
        return _storage_chat_id
    return int(STORAGE_CHAT_ID)


def _sanitized_config():
    if not os.path.exists(CONFIG_PATH):
        return None

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return None

        for key in ("api_id", "api_hash", "bot_token"):
            data.pop(key, None)

        return data

    except Exception as e:
        print(f"Remote config snapshot error: {e}")
        return None


def _create_state_archive():
    if not os.path.exists(DB_PATH):
        return None

    config = _sanitized_config()
    if config is None:
        return None

    os.makedirs("data", exist_ok=True)

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

        with open(config_snapshot_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        with zipfile.ZipFile(
            STATE_ARCHIVE,
            "w",
            compression=zipfile.ZIP_DEFLATED
        ) as archive:
            archive.write(snapshot_path, arcname="cafe_hermes.db")
            archive.write(config_snapshot_path, arcname="config.json")

        return STATE_ARCHIVE

    except Exception as e:
        print(f"Remote state archive error: {e}")
        return None

    finally:
        for path in (snapshot_path, config_snapshot_path):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass


def _cleanup_extract():
    try:
        shutil.rmtree("data/.remote_state_extract", ignore_errors=True)
    except Exception:
        pass


def _cleanup_archive():
    try:
        if os.path.exists(STATE_ARCHIVE):
            os.remove(STATE_ARCHIVE)
    except Exception:
        pass


async def _get_state_message():
    global _state_message_id

    if not _storage_started:
        return None

    try:
        chat = await _get_storage_chat()
    except Exception as e:
        print(f"Remote Storage: getChat failed while checking state: {e}")
        return None

    pinned = chat.get("pinned_message") if isinstance(chat, dict) else None

    if pinned:
        caption = pinned.get("caption") or pinned.get("text") or ""
        if caption.startswith(STATE_MARKER):
            _state_message_id = pinned.get("message_id")
            if _state_message_id is None:
                _state_message_id = pinned.get("id")
            return pinned

    return None


async def _send_document(archive_path, caption):
    form = aiohttp.FormData()
    form.add_field("chat_id", str(_chat_id()))
    form.add_field("caption", caption)

    with open(archive_path, "rb") as document:
        form.add_field(
            "document",
            document,
            filename=os.path.basename(archive_path),
            content_type="application/zip"
        )
        result = await _bot_api("sendDocument", multipart=form)

    return result


async def _edit_document(message_id, archive_path, caption):
    form = aiohttp.FormData()
    form.add_field("chat_id", str(_chat_id()))
    form.add_field("message_id", str(message_id))
    form.add_field(
        "media",
        json.dumps({
            "type": "document",
            "media": "attach://statefile",
            "caption": caption
        })
    )

    with open(archive_path, "rb") as document:
        form.add_field(
            "statefile",
            document,
            filename=os.path.basename(archive_path),
            content_type="application/zip"
        )
        result = await _bot_api("editMessageMedia", multipart=form)

    return result


async def _pin_message(message_id):
    return await _bot_api(
        "pinChatMessage",
        {
            "chat_id": _chat_id(),
            "message_id": message_id,
            "disable_notification": True
        }
    )


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
            existing_id = existing.get("message_id", existing.get("id"))
            try:
                edited = await _edit_document(
                    existing_id,
                    archive_path,
                    caption
                )

                _state_message_id = (
                    edited.get("message_id", edited.get("id", existing_id))
                    if edited else existing_id
                )

                print("Remote Storage: state message updated.")
                return True

            except Exception as e:
                print(f"Remote Storage: state message edit failed: {e}")

        sent = await _send_document(
            archive_path,
            caption
        )

        if not sent:
            return False

        _state_message_id = sent.get("message_id", sent.get("id"))

        try:
            await _pin_message(_state_message_id)
        except Exception as e:
            print(f"Remote Storage: pin failed: {e}")

        print("Remote Storage: new state message created.")
        return True

    except Exception as e:
        print(f"Remote Storage: state upload error: {e}")
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
        print("Remote Storage: sync started.")

        result = await _create_or_replace_state()

        if result:
            print("Remote Storage: sync completed.")
        else:
            _dirty = True
            print("Remote Storage: sync failed.")

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

    _sync_task = loop.create_task(_sync_worker())


async def _sync_worker():
    global _sync_task
    global _dirty

    try:
        await asyncio.sleep(1.5)

        while _storage_started and _dirty:
            await sync_all(force=False)

            if _dirty:
                await asyncio.sleep(1)

    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"Remote sync worker error: {e}")
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
            print(f"Remote watcher error: {e}")
            await asyncio.sleep(5)


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

    _watcher_task = loop.create_task(_watch_files())
    print("Remote Storage watcher started.")


async def _download_document(message, destination):
    document = message.get("document") if isinstance(message, dict) else None
    if not document:
        raise RuntimeError("Pinned state message does not contain a document.")

    file_id = document.get("file_id")
    if not file_id:
        raise RuntimeError("Pinned state document file_id is missing.")

    file_info = await _bot_api(
        "getFile",
        {"file_id": file_id}
    )

    file_path = file_info.get("file_path") if file_info else None
    if not file_path:
        raise RuntimeError("Telegram did not return a file path.")

    url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    timeout = aiohttp.ClientTimeout(total=120)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise RuntimeError(
                    f"Telegram file download failed with HTTP {response.status}."
                )

            with open(destination, "wb") as output:
                while True:
                    chunk = await response.content.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)


async def restore_from_remote():
    if not _storage_started:
        return False

    print("Remote Storage: checking remote state...")

    message = await _get_state_message()

    if not message:
        print("Remote Storage: no pinned state backup found.")
        return False

    os.makedirs("data", exist_ok=True)

    temp_archive = "data/.remote_state_restore.zip"
    extract_root = "data/.remote_state_extract"

    _cleanup_extract()

    try:
        await _download_document(
            message,
            temp_archive
        )

        if not os.path.exists(temp_archive):
            return False

        os.makedirs(extract_root, exist_ok=True)

        with zipfile.ZipFile(temp_archive, "r") as archive:
            names = set(archive.namelist())

            if not {"cafe_hermes.db", "config.json"}.issubset(names):
                raise RuntimeError("Remote state archive is incomplete.")

            archive.extract("cafe_hermes.db", extract_root)
            archive.extract("config.json", extract_root)

        extracted_db = "data/.remote_state_extract/cafe_hermes.db"
        extracted_config = "data/.remote_state_extract/config.json"

        if not os.path.exists(extracted_db):
            raise RuntimeError("Restored database is missing.")

        if not os.path.exists(extracted_config):
            raise RuntimeError("Restored config is missing.")

        with open(extracted_config, "r", encoding="utf-8") as f:
            restored_config = json.load(f)

        if not isinstance(restored_config, dict):
            raise RuntimeError("Restored config is invalid.")

        if os.path.exists(DB_PATH):
            try:
                os.replace(DB_PATH, "data/cafe_hermes_before_restore.db")
            except Exception:
                pass

        os.replace(extracted_db, DB_PATH)
        os.replace(extracted_config, CONFIG_PATH)

        print("Remote state restored successfully.")
        return True

    except Exception as e:
        print(f"Remote state restore error: {e}")
        return False

    finally:
        try:
            if os.path.exists(temp_archive):
                os.remove(temp_archive)
        except Exception:
            pass

        _cleanup_extract()
