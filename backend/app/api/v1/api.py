from fastapi import APIRouter

from app.api.v1 import actions, alerts, auth, calendar, commands, config, discover, events, addons, library, logs, media, media_management, resource, scheduler, subscription, task
from app.api.v1.config.test_directory import router as test_directory_router
from app.api.v1.resource import download_history, parser

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(resource.router, tags=["resources"])
api_router.include_router(parser.router, tags=["parser"])
# include media sub-routers
api_router.include_router(media.router, tags=["media"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(subscription.router, tags=["subscription"])
api_router.include_router(calendar.router, tags=["calendar"])
api_router.include_router(discover.router, tags=["discover"])
api_router.include_router(download_history.router, tags=["download-history"])
api_router.include_router(config.router, tags=["config"])
# include new library and task routers
api_router.include_router(library.router, tags=["library"])
api_router.include_router(task.router, tags=["task"])
api_router.include_router(commands.router, tags=["commands"])
api_router.include_router(events.router, tags=["events"])
api_router.include_router(actions.router, tags=["actions"])
api_router.include_router(alerts.router, tags=["alerts"])
api_router.include_router(logs.router, tags=["logs"])
api_router.include_router(addons.router, tags=["addons"])
api_router.include_router(media_management.router, tags=["media-management"])
api_router.include_router(scheduler.router, tags=["scheduler"])
# Internal note.
api_router.include_router(test_directory_router, tags=["config"])
