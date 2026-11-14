from app.schemas.domain.resource_attributes import ResourceAttributes
from app.schemas.domain.torrent import TorrentFileItem, TorrentMetadata
from app.services.domain.resource.torrent_file_policy import library_download_file_indices


def _metadata(names):
    return TorrentMetadata(hash="test", name="Example", size=100, files=[
        TorrentFileItem(index=index, filename=name, size=10, attrs=ResourceAttributes(episodes=[]))
        for index, name in enumerate(names)
    ])


def test_download_selection_filters_only_obvious_junk_and_keeps_companions():
    metadata = _metadata([
        "Example.mkv", "Example.zh.srt", "fonts/font.ttf", "poster.jpg", "movie.nfo",
        "README.TXT", "site.url", "checksums.sfv", "sample/Example.mkv", "Example.Sample.mkv", "extras.zip",
    ])
    assert library_download_file_indices(metadata, None) == [0, 1, 2, 3, 4]
    assert library_download_file_indices(metadata, [0, 6]) == [0]


def test_original_disc_support_files_are_never_filtered():
    metadata = _metadata(["BDMV/index.bdmv", "BDMV/STREAM/00001.m2ts", "BDMV/META/manifest.xml", "CERTIFICATE/readme.txt"])
    metadata.attrs = ResourceAttributes(package_layout="BDMV", episodes=[])
    assert library_download_file_indices(metadata, None) == [0, 1, 2, 3]


def test_unknown_episode_and_extension_are_not_assumed_to_be_junk():
    metadata = _metadata(["未解析正片.mkv", "Unknown.aux"])
    assert library_download_file_indices(metadata, None) == [0, 1]
