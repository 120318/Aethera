import re
from urllib.parse import urlparse, parse_qs

from app.clients.jackett import JackettClient


jackett_service = JackettClient()


def test_build_torznab_feed_basic():
    url = jackett_service.build_torznab_feed("tt1234567", indexers=["site1", "site2"])
    parsed = urlparse(url)
    # basic sanity
    assert parsed.scheme in ("http", "https")
    qs = parse_qs(parsed.query)
    assert qs.get('t', [None])[0] == 'search'
    assert qs.get('q', [None])[0] == 'tt1234567'
    assert 'tracker' in qs and qs['tracker'][0] == 'site1,site2'


def test_build_torznab_feed_no_indexers():
    url = jackett_service.build_torznab_feed("some-query", indexers=None)
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    assert qs.get('q', [None])[0] == 'some-query'
    assert 'tracker' not in qs
