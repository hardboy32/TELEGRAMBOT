from bot import remote_storage


async def start_storage(app):
    """Start remote storage through the automatic Bot API based connector."""
    return await remote_storage.start_storage(app)
