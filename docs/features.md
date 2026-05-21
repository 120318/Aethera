# Features

Aethera is a self-hosted media workflow application focused on the full path from media metadata to local files.

The core workflow is:

1. Use TMDB metadata to identify movies, TV shows, seasons, and episodes.
2. Search configured indexers for matching release resources.
3. Send selected resources to a configured downloader.
4. Track tasks and finished downloads.
5. Inspect and manage the mounted media library.
6. Optionally refresh or synchronize a media server.

## Media Subscription

- Follow media items and seasons.
- Track subscription state and upcoming work.
- Run subscription tasks manually or through the scheduler.

## Discovery And Search

- Search TMDB-backed media metadata.
- Search configured resource indexers.
- Compare resources with parsed quality, version, source, and release attributes.

## Download Workflow

- Configure download clients in the application UI.
- Transfer selected resources to the default downloader.
- Track active tasks and finished download history.

## Library Management

- Mount a host media root into the container at `/data`.
- Inspect local media files and directory usage.
- Manage file placement and directory integrity workflows.
- Optionally connect a media server for refresh and sync workflows.

## Configuration

- Store application settings in SQLite.
- Configure directories, downloaders, indexers, media servers, quality profiles, tags, and naming templates in the UI.
- Keep runtime data under `AETHERA_CONFIG_PATH`, outside Git.

## Disabled Experimental Integrations

OIDC login and Telegram notifications are currently disabled by default because they are experimental and not release-tested.
