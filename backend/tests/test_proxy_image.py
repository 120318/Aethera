import pytest
from fastapi import HTTPException

from app.api.v1.media.proxy_image import _parse_image_url


@pytest.mark.parametrize(
    "hostname",
    [
        "qnmob1-sign.doubanio.com",
        "qnmob2-sign.doubanio.com",
        "qnmob3-sign.doubanio.com",
    ],
)
def test_parse_image_url_accepts_douban_signed_image_hosts(hostname):
    parsed, parsed_hostname = _parse_image_url(f"https://{hostname}/view/photo/large/public/example.jpg")

    assert parsed.hostname == hostname
    assert parsed_hostname == hostname


def test_parse_image_url_rejects_host_with_allowed_name_as_prefix():
    with pytest.raises(HTTPException) as exc_info:
        _parse_image_url("https://qnmob3-sign.doubanio.com.example.org/poster.jpg")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "disallowed host"
