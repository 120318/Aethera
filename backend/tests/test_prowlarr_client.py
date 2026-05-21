from datetime import datetime

from app.clients.prowlarr import ProwlarrClient
from app.schemas.config import ProwlarrConfig
from app.clients.torznab import parse_torznab_xml


def test_prowlarr_client_maps_enabled_torrent_indexer_to_site():
    client = ProwlarrClient(
        ProwlarrConfig(id="prowlarr-1", name="Prowlarr", url="http://prowlarr:9696", api_key="key")
    )

    site = client._to_site(
        {
            "id": 7,
            "name": "M-Team",
            "enable": True,
            "protocol": "torrent",
            "privacy": "private",
            "description": "PT",
        }
    )

    assert site is not None
    assert site.id == "7"
    assert site.name == "M-Team"
    assert site.type == "private"


def test_prowlarr_client_ignores_disabled_or_non_torrent_indexers():
    client = ProwlarrClient()

    assert client._to_site({"id": 7, "name": "Off", "enable": False, "protocol": "torrent"}) is None
    assert client._to_site({"id": 8, "name": "NZB", "enable": True, "protocol": "usenet"}) is None


def test_prowlarr_capabilities_are_derived_from_categories():
    client = ProwlarrClient()

    caps = client._to_metadata_capabilities(
        {
            "supportsSearch": True,
            "categories": [
                {"id": 2000, "name": "Movies"},
                {"id": 5000, "name": "TV"},
            ],
        }
    )

    assert caps.supports_q is True
    assert caps.supports_imdbid is False
    assert caps.supports_doubanid is False
    assert caps.supports_movie is True
    assert caps.supports_tv is True


def test_shared_torznab_caps_parser_maps_search_params():
    from app.clients.torznab import parse_torznab_caps_xml

    caps = parse_torznab_caps_xml(
        """
        <caps>
          <searching>
            <search available="yes" supportedParams="q,imdbid,doubanid" />
          </searching>
          <categories>
            <category id="2000" name="Movies" />
            <category id="5000" name="TV" />
          </categories>
        </caps>
        """
    )

    assert caps.supports_q is True
    assert caps.supports_imdbid is True
    assert caps.supports_doubanid is True
    assert caps.supports_movie is True
    assert caps.supports_tv is True


def test_shared_torznab_parser_maps_prowlarr_feed_result():
    xml = f"""
    <rss>
      <channel>
        <item>
          <title>Example.Movie.2024.1080p.BluRay.x264-GROUP</title>
          <guid>guid-1</guid>
          <link>https://example.com/detail/1</link>
          <comments>https://example.com/torrent/1</comments>
          <pubDate>{datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")}</pubDate>
          <description>desc</description>
          <enclosure url="https://example.com/download/1.torrent" length="1073741824" type="application/x-bittorrent" />
          <torznab:attr xmlns:torznab="http://torznab.com/schemas/2015/feed" name="seeders" value="12" />
          <torznab:attr xmlns:torznab="http://torznab.com/schemas/2015/feed" name="peers" value="3" />
          <torznab:attr xmlns:torznab="http://torznab.com/schemas/2015/feed" name="imdbid" value="tt1234567" />
        </item>
      </channel>
    </rss>
    """

    results = parse_torznab_xml(xml, default_site="7")

    assert len(results) == 1
    assert results[0].site == "7"
    assert results[0].title == "Example.Movie.2024.1080p.BluRay.x264-GROUP"
    assert results[0].seeders == 12
    assert results[0].download_url == "https://example.com/download/1.torrent"
    assert results[0].source_imdbid == "tt1234567"
