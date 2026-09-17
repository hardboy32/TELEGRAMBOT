import os

from bot import remote_storage


STORAGE_CHAT_ID = os.getenv("STORAGE_CHAT_ID")
STORAGE_CHAT_INVITE = os.getenv("STORAGE_CHAT_INVITE", "").strip()


async def start_storage(app):
    """Start remote storage using bot-compatible channel discovery.

    Telegram bots cannot use the invite-link check method that Pyrogram may
    invoke for private invite links. The storage module already has a
    bot-compatible fallback: observe channel posts and learn the private
    channel from the incoming message.
    """

    # Keep the environment variable accepted for compatibility, but do not
    # try to resolve it through Telegram's invite-check API.
    if STORAGE_CHAT_INVITE:
        print(
            "Remote Storage: invite link provided; bot-compatible channel "
            "discovery will be used instead."
        )

    return await remote_storage.start_storage(app)
