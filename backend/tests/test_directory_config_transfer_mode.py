from app.api.v1.config.directories.add import DirectoryAddRequest
from app.api.v1.config.directories.update import DirectoryUpdateRequest
from app.schemas.config import TransferMode
from app.schemas.domain.media_types import MediaType


def test_directory_add_request_defaults_to_hardlink_transfer_mode():
    request = DirectoryAddRequest(
        name="Movies",
        path="/library/movies",
        download_path="/downloads/movies",
        media_type=MediaType.movie,
    )

    assert request.transfer_mode == TransferMode.HARDLINK


def test_directory_update_request_accepts_copy_transfer_mode():
    request = DirectoryUpdateRequest(
        id="dir-1",
        name="Movies",
        path="/library/movies",
        download_path="/downloads/movies",
        media_type=MediaType.movie,
        enabled=True,
        is_default=True,
        transfer_mode=TransferMode.COPY,
    )

    assert request.transfer_mode == TransferMode.COPY
