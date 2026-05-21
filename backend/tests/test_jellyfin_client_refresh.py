import unittest
from unittest.mock import AsyncMock

from app.clients.jellyfin import JellyfinClient
from app.schemas.config import JellyfinConfig, PathMapping


class TestJellyfinClientRefresh(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_path_maps_local_path_and_posts_updated_media(self):
        client = JellyfinClient(
            JellyfinConfig(
                id="jf1",
                name="jf",
                url="http://localhost:8096",
                api_key="token",
            )
        )
        client.apply_changes = AsyncMock(return_value=True)

        ok = await client.refresh_path("/app/library/movies/Marvel/Avatar")

        self.assertTrue(ok)
        client.apply_changes.assert_awaited_once()
        change = client.apply_changes.await_args.args[0][0]
        self.assertEqual(change.target_path, "/app/library/movies/Marvel/Avatar")

    async def test_refresh_path_returns_false_when_notify_and_global_refresh_fail(self):
        client = JellyfinClient(
            JellyfinConfig(
                id="jf1",
                name="jf",
                url="http://localhost:8096",
                api_key="token",
            )
        )
        client.apply_changes = AsyncMock(return_value=False)

        ok = await client.refresh_path("/other/path/show")

        self.assertFalse(ok)
        client.apply_changes.assert_awaited_once()

    async def test_resolve_detail_link_falls_back_to_parent_media_folder(self):
        client = JellyfinClient(
            JellyfinConfig(
                id="jf1",
                name="jf",
                url="http://localhost:8096",
                api_key="token",
                path_mappings=[
                    PathMapping(remote_path="/media2", local_path="/data/library"),
                ],
            )
        )
        lookups = []

        async def fake_find_item_by_path(media_path, *, include_item_types="Movie,Episode,Video"):
            lookups.append((media_path, include_item_types))
            if media_path == "/media2/tv/咱们结婚吧 (2013)" and include_item_types == "Movie,Series,Season,Folder":
                return {"Id": "series-1"}
            return None

        client._find_item_by_path = fake_find_item_by_path
        client._build_web_detail_url = AsyncMock(return_value="http://localhost:8096/web/index.html#!/details?id=series-1")

        link = await client.resolve_detail_link(
            "/data/library/tv/咱们结婚吧 (2013)/Season 01/咱们结婚吧 - S01E01.mp4"
        )

        self.assertEqual(link.detail_url, "http://localhost:8096/web/index.html#!/details?id=series-1")
        self.assertEqual(
            lookups,
            [
                ("/media2/tv/咱们结婚吧 (2013)/Season 01/咱们结婚吧 - S01E01.mp4", "Movie,Episode,Video"),
                ("/media2/tv/咱们结婚吧 (2013)/Season 01", "Movie,Series,Season,Folder"),
                ("/media2/tv/咱们结婚吧 (2013)", "Movie,Series,Season,Folder"),
            ],
        )
