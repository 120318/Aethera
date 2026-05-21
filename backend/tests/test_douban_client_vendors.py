import pytest

from app.clients.douban import DoubanClient
from app.schemas.domain.media_types import MediaType


def test_douban_vendor_keeps_external_provider_deep_link() -> None:
    client = DoubanClient()

    vendor = client._to_vendor(
        "Sample",
        "https://img9.doubanio.com/f/frodo/pics/vendors/tencent.png",
        "douban://douban.com/goToWXMiniProgram?path=preload_play/play/index?cid=mzc002007tp60ap&vid=w41025my54z",
        "qq",
    )

    assert vendor is not None
    assert vendor.name == "Sample"
    assert vendor.id == "qq"
    assert vendor.url is not None
    assert "cid=mzc002007tp60ap" in vendor.url


def test_douban_vendor_filters_source_links_without_external_identity() -> None:
    client = DoubanClient()

    vendor = client._to_vendor(None, None, "https://movie.douban.com/subject/36939912/", None)

    assert vendor is None


@pytest.mark.asyncio
async def test_douban_search_uses_smart_box_results(monkeypatch) -> None:
    client = DoubanClient()

    async def fake_get(url, params, headers, error_message):
        return {
            "smart_box": [
                {
                    "layout": "subject",
                    "target": {
                        "id": "35517044",
                        "title": "低智商犯罪",
                        "year": "2026",
                        "rating": {"count": 0, "max": 10, "star_count": 0, "value": 0},
                        "cover_url": "https://example.test/poster.jpg",
                        "card_subtitle": "中国大陆 / 剧情 犯罪",
                    },
                    "target_type": "tv",
                }
            ],
            "subjects": {"items": []},
        }

    monkeypatch.setattr(client, "_get", fake_get)

    items = await client.search_movie("低智商犯罪")

    assert len(items) == 1
    assert items[0].provider_id == "35517044"
    assert items[0].title == "低智商犯罪"
    assert items[0].year == 2026
    assert items[0].media_type == MediaType.tv
