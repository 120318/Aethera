from app.services.application.commands.contract import CommandHandler
from app.services.application.commands.handlers.download import register_download_command_handlers
from app.services.application.commands.handlers.directory_integrity import register_directory_integrity_command_handlers
from app.services.application.commands.handlers.library import register_library_command_handlers
from app.services.application.commands.handlers.profile import register_profile_command_handlers
from app.services.application.commands.handlers.search import register_search_command_handlers
from app.services.application.commands.handlers.subscription import register_subscription_command_handlers

__all__ = [
    "CommandHandler",
    "register_download_command_handlers",
    "register_directory_integrity_command_handlers",
    "register_library_command_handlers",
    "register_profile_command_handlers",
    "register_search_command_handlers",
    "register_subscription_command_handlers",
]
