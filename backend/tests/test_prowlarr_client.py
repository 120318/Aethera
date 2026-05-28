from datetime import datetime

from app.clients.prowlarr import ProwlarrClient
from app.schemas.config import ProwlarrConfig
from app.clients.torznab import build_torznab_search_params, parse_torznab_xml
from app.schemas.integration.site_models import SiteSearchCapabilities


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
    assert caps.supports_search is True
    assert caps.supports_movie_search is False
    assert caps.supports_tv_search is False
    assert caps.supports_movie is True
    assert caps.supports_tv is True


def test_prowlarr_torznab_tv_id_search_uses_tvsearch_mode_and_season():
    client = ProwlarrClient(
        ProwlarrConfig(id="prowlarr-1", name="Prowlarr", url="http://prowlarr:9696", api_key="key")
    )

    params = client._build_torznab_search_params("tt36982480", "tv", "imdbid", 1)

    assert params == {
        "apikey": "key",
        "t": "tvsearch",
        "imdbid": "tt36982480",
        "cat": "5000",
        "season": "1",
    }


def test_prowlarr_torznab_tv_title_search_uses_tvsearch_mode_and_season():
    client = ProwlarrClient(
        ProwlarrConfig(id="prowlarr-1", name="Prowlarr", url="http://prowlarr:9696", api_key="key")
    )

    params = client._build_torznab_search_params("耀眼", "tv", "q", 1)

    assert params == {
        "apikey": "key",
        "t": "tvsearch",
        "q": "耀眼",
        "cat": "5000",
        "season": "1",
    }


def test_shared_torznab_search_params_map_search_modes():
    params = build_torznab_search_params(
        api_key="key",
        query="36513446",
        search_param="doubanid",
        category="tv",
        search_type="search",
    )

    assert params == {
        "apikey": "key",
        "t": "search",
        "doubanid": "36513446",
        "cat": "5000",
    }


def test_prowlarr_torznab_movie_title_search_falls_back_to_generic_search_when_movie_mode_unavailable():
    client = ProwlarrClient(
        ProwlarrConfig(id="prowlarr-1", name="Prowlarr", url="http://prowlarr:9696", api_key="key")
    )

    params = client._build_torznab_search_params(
        "The Shawshank Redemption",
        "movie",
        "q",
        None,
        SiteSearchCapabilities(supports_search=True, supports_movie_search=False),
    )

    assert params == {
        "apikey": "key",
        "t": "search",
        "q": "The Shawshank Redemption",
        "cat": "2000",
    }


def test_prowlarr_torznab_movie_id_search_does_not_fall_back_to_generic_search():
    client = ProwlarrClient(
        ProwlarrConfig(id="prowlarr-1", name="Prowlarr", url="http://prowlarr:9696", api_key="key")
    )

    params = client._build_torznab_search_params(
        "tt0111161",
        "movie",
        "imdbid",
        None,
        SiteSearchCapabilities(supports_search=True, supports_movie_search=False),
    )

    assert params is None


def test_prowlarr_torznab_movie_id_search_skips_generic_id_search_even_when_caps_advertise_id_param():
    client = ProwlarrClient(
        ProwlarrConfig(id="prowlarr-1", name="Prowlarr", url="http://prowlarr:9696", api_key="key")
    )

    params = client._build_torznab_search_params(
        "tt0111161",
        "movie",
        "imdbid",
        None,
        SiteSearchCapabilities(
            supports_search=True,
            supports_movie_search=False,
            supports_imdbid=True,
        ),
    )

    assert params is None


def test_prowlarr_torznab_tv_id_search_skips_param_not_supported_by_tvsearch():
    client = ProwlarrClient(
        ProwlarrConfig(id="prowlarr-1", name="Prowlarr", url="http://prowlarr:9696", api_key="key")
    )

    params = client._build_torznab_search_params(
        "36513446",
        "tv",
        "doubanid",
        1,
        SiteSearchCapabilities(
            supports_search=True,
            supports_tv_search=True,
            search_params={"q", "doubanid"},
            tv_search_params={"q", "season", "imdbid"},
            supports_doubanid=True,
        ),
    )

    assert params is None


def test_prowlarr_torznab_tv_title_fallback_omits_season_without_tvsearch():
    client = ProwlarrClient(
        ProwlarrConfig(id="prowlarr-1", name="Prowlarr", url="http://prowlarr:9696", api_key="key")
    )

    params = client._build_torznab_search_params(
        "Game of Thrones S01",
        "tv",
        "q",
        1,
        SiteSearchCapabilities(supports_search=True, supports_tv_search=False),
    )

    assert params == {
        "apikey": "key",
        "t": "search",
        "q": "Game of Thrones S01",
        "cat": "5000",
    }


def test_prowlarr_torznab_movie_id_search_uses_movie_mode():
    client = ProwlarrClient(
        ProwlarrConfig(id="prowlarr-1", name="Prowlarr", url="http://prowlarr:9696", api_key="key")
    )

    params = client._build_torznab_search_params("tt1234567", "movie", "imdbid", None)

    assert params == {
        "apikey": "key",
        "t": "movie",
        "imdbid": "tt1234567",
        "cat": "2000",
    }


def test_prowlarr_plain_search_only_uses_search_mode_without_media_category():
    client = ProwlarrClient(
        ProwlarrConfig(id="prowlarr-1", name="Prowlarr", url="http://prowlarr:9696", api_key="key")
    )

    params = client._build_torznab_search_params("耀眼", None, "q", None)

    assert params == {
        "apikey": "key",
        "t": "search",
        "q": "耀眼",
    }


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
    assert caps.supports_search is True
    assert caps.supports_movie_search is False
    assert caps.supports_tv_search is False
    assert caps.supports_movie is True
    assert caps.supports_tv is True


def test_shared_torznab_caps_parser_maps_available_search_types():
    from app.clients.torznab import parse_torznab_caps_xml

    caps = parse_torznab_caps_xml(
        """
        <caps>
          <searching>
            <search available="yes" supportedParams="q" />
            <tv-search available="yes" supportedParams="q,season,ep,imdbid" />
            <movie-search available="no" supportedParams="q,imdbid" />
          </searching>
        </caps>
        """
    )

    assert caps.supports_search is True
    assert caps.supports_tv_search is True
    assert caps.supports_movie_search is False
    assert caps.supports_imdbid is True
    assert caps.search_params == {"q"}
    assert caps.tv_search_params == {"q", "season", "ep", "imdbid"}
    assert caps.movie_search_params == set()


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
