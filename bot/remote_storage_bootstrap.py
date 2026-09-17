import os

from bot import remote_storage


STORAGE_CHAT_ID = os.getenv("STORAGE_CHAT_ID")
STORAGE_CHAT_INVITE = os.getenv("STORAGE_CHAT_INVITE", "").strip()


async def start_storage(app):
    """Connect remote storage without requiring a fresh channel post after restart.

    For private channels, Pyrogram bots may not be able to resolve a numeric
    chat id from a cold start. A one-time invite link lets Pyrogram resolve the
    private channel and cache the peer again on every restart.
    """

    if not STORAGE_CHAT_ID:
        return await remote_storage.start_storage(app)

    if not STORAGE_CHAT_INVITE:
        print(
            "Remote Storage: STORAGE_CHAT_INVITE is not configured; "
            "falling back to channel-post discovery."
        )
        return await remote_storage.start_storage(app)

    try:
        target_id = int(STORAGE_CHAT_ID)
    except (TypeError, ValueError):
        print(
            "Remote Storage: STORAGE_CHAT_ID is invalid."
        )
        return False

    remote_storage._storage_app = app

    print(
        "Remote Storage: resolving private storage channel from invite link..."
    )

    try:
        await remote_storage._register_storage_observer(app)
    except Exception as e:
        print(
            f"Remote Storage: observer registration error: {e}"
        )
        return False

    chat = None

    try:
        chat = await app.get_chat(STORAGE_CHAT_INVITE)

        # Pyrogram returns ChatPreview when the account is not a member yet.
        # In that case, try joining once and then resolve the full Chat object.
        if chat and type(chat).__name__ == "ChatPreview":
            try:
                chat = await app.join_chat(STORAGE_CHAT_INVITE)
            except Exception as join_error:
                print(
                    "Remote Storage: invite resolved to a preview and join failed: "
                    f"{join_error}"
                )

                try:
                    chat = await app.get_chat(STORAGE_CHAT_INVITE)
                except Exception:
                    chat = None

    except Exception as e:
        print(
            f"Remote Storage: invite-link resolution failed: {e}"
        )
        chat = None

    if not chat:
        print(
            "Remote Storage: could not resolve the storage channel automatically."
        )
        print(
            "Remote Storage: verify STORAGE_CHAT_INVITE is a valid invite link "
            "and the bot is a member/admin of the channel."
        )
        return False

    if getattr(chat, "id", None) != target_id:
        print(
            "Remote Storage: invite link points to a different chat than STORAGE_CHAT_ID."
        )
        return False

    remote_storage._storage_chat = chat
    remote_storage._storage_started = True

    ready_event = getattr(
        remote_storage,
        "_storage_ready_event",
        None
    )

    if ready_event and not ready_event.is_set():
        ready_event.set()

    print(
        "Remote Storage connected successfully via invite link: "
        f"{chat.id}"
    )

    return True
