import pytest

from app.clients.jackett import JackettClient


pytestmark = [pytest.mark.drift]


def test_parse_caps_infers_movie_support_from_torznab_categories():
    caps = JackettClient()._parse_caps_xml(
        """
        <caps>
          <searching><search available="yes" supportedParams="q,imdbid" /></searching>
          <categories>
            <category id="2000" name="Movies" />
          </categories>
        </caps>
        """
    )

    assert caps.supports_movie is True
    assert caps.supports_tv is False


def test_parse_caps_infers_tv_support_from_torznab_categories():
    caps = JackettClient()._parse_caps_xml(
        """
        <caps>
          <searching><search available="yes" supportedParams="q" /></searching>
          <categories>
            <category id="5070" name="Anime" />
          </categories>
        </caps>
        """
    )

    assert caps.supports_movie is False
    assert caps.supports_tv is True


def test_parse_caps_defaults_to_all_media_types_when_categories_are_missing():
    caps = JackettClient()._parse_caps_xml(
        """
        <caps>
          <searching><search available="yes" supportedParams="q" /></searching>
        </caps>
        """
    )

    assert caps.supports_movie is True
    assert caps.supports_tv is True
