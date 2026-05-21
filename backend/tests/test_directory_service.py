from app.schemas.config import DirectoryConfig, Template, TransferMode
from app.schemas.domain.media_types import MediaType
from app.services.domain.directory.service import DirectoryService


def test_resolve_library_target_accepts_registered_copy_transfer_mode(monkeypatch):
    service = DirectoryService()
    directory = DirectoryConfig(
        id="dir-1",
        name="Movies",
        path="/library/movies",
        media_type=MediaType.movie,
        transfer_mode=TransferMode.COPY,
    )
    template = Template(file_template="{title}")

    monkeypatch.setattr(
        "app.services.domain.directory.service.settings_service.get_directory_by_id",
        lambda directory_id: directory,
    )
    monkeypatch.setattr(
        "app.services.domain.directory.service.settings_service.get_template_by_directory_id",
        lambda directory_id: template,
    )

    target = service.resolve_library_target("dir-1")

    assert target.transfer_mode == TransferMode.COPY
    assert target.library_path == "/library/movies"
