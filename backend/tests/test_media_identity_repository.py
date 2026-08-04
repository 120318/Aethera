import json

from sqlalchemy import text

from app.db.repositories.media_identity_repository import MediaIdentityRepository
from app.db.sql.session import SessionLocal
from app.schemas.media_id import MediaID


def test_merge_media_id_retargets_source_external_mapping():
    source = MediaID.parse("douban:movie:111")
    target = MediaID.parse("tmdb:movie:456")

    with SessionLocal.begin() as session:
        session.execute(
            text(
                """
                INSERT INTO media_external_mappings
                (media_type, media_id, tmdb_id, imdb_id, douban_id, season_number, updated_at)
                VALUES ('movie', :target, 456, null, '111', 0, 1)
                """
            ),
            {"target": str(target)},
        )

    MediaIdentityRepository().merge_media_id(source, target)

    with SessionLocal() as session:
        row = (
            session.execute(
                text(
                    """
                SELECT media_id, tmdb_id, douban_id
                FROM media_external_mappings
                WHERE douban_id = '111' AND media_type = 'movie'
                """
                )
            )
            .mappings()
            .one()
        )

    assert row["media_id"] == str(target)
    assert row["tmdb_id"] == 456
    assert row["douban_id"] == "111"


def test_merge_media_id_drops_source_external_mapping_when_target_season_exists():
    source = MediaID.parse("tmdb:tv:123456789")
    target = MediaID.parse("tmdb:tv:987654321")

    with SessionLocal.begin() as session:
        session.execute(
            text(
                """
                INSERT INTO media_external_mappings
                (media_type, media_id, tmdb_id, imdb_id, douban_id, season_number, updated_at)
                VALUES
                ('tv', :target, 987654321, 'tt456', 'target-season-1', 1, 1),
                ('tv', :source, 123456789, 'tt123', 'source-season-1', 1, 1),
                ('tv', :source, 123456789, 'tt123', 'source-season-3', 3, 1)
                """
            ),
            {"source": str(source), "target": str(target)},
        )

    MediaIdentityRepository().merge_media_id(source, target)

    with SessionLocal() as session:
        rows = (
            session.execute(
                text(
                    """
                    SELECT media_id, tmdb_id, douban_id, season_number
                    FROM media_external_mappings
                    WHERE media_id IN (:source, :target)
                    ORDER BY season_number, douban_id
                    """
                ),
                {"source": str(source), "target": str(target)},
            )
            .mappings()
            .all()
        )

    assert [dict(row) for row in rows] == [
        {"media_id": str(target), "tmdb_id": 987654321, "douban_id": "target-season-1", "season_number": 1},
        {"media_id": str(target), "tmdb_id": 987654321, "douban_id": "source-season-3", "season_number": 3},
    ]


def test_merge_media_id_preserves_missing_target_season_mapping_fields():
    source = MediaID.parse("tmdb:tv:123456788")
    target = MediaID.parse("tmdb:tv:987654320")

    with SessionLocal.begin() as session:
        session.execute(
            text(
                """
                INSERT INTO media_external_mappings
                (media_type, media_id, tmdb_id, imdb_id, douban_id, season_number,
                 episode_count_override, updated_at)
                VALUES
                ('tv', :target, 987654320, null, null, 2, null, 1),
                ('tv', :source, 123456788, 'tt123', 'source-season-2', 2, 12, 1)
                """
            ),
            {"source": str(source), "target": str(target)},
        )

    MediaIdentityRepository().merge_media_id(source, target)

    with SessionLocal() as session:
        row = (
            session.execute(
                text(
                    """
                    SELECT media_id, tmdb_id, imdb_id, douban_id, episode_count_override
                    FROM media_external_mappings
                    WHERE media_id = :target AND season_number = 2
                    """
                ),
                {"target": str(target)},
            )
            .mappings()
            .one()
        )

    assert dict(row) == {
        "media_id": str(target),
        "tmdb_id": 987654320,
        "imdb_id": "tt123",
        "douban_id": "source-season-2",
        "episode_count_override": 12,
    }


def test_merge_media_id_does_not_replace_prefix_media_ids_in_embedded_text_or_json():
    source = MediaID.parse("tmdb:movie:1")
    target = MediaID.parse("tmdb:movie:456")
    action_id = "identity-merge-prefix-action"

    with SessionLocal.begin() as session:
        session.execute(
            text(
                """
                INSERT INTO actions
                (id, ts, kind, action_name, status, actor, trigger, source, target_type, target_id,
                 media_id, media_season_number, media_title, media_year, task_id, subscription_id,
                 correlation_id, message_key, message_params_json, error, search_text, duration_ms, meta_json)
                VALUES
                (:id, '2026-05-10T00:00:00', 'operation', 'test', 'completed', 'system', 'manual',
                 'system', 'media', :source, :source, null, null, null, null, null, null, null,
                 '{}', null, :search_text, null, :meta_json)
                """
            ),
            {
                "id": action_id,
                "source": str(source),
                "search_text": "exact tmdb:movie:1 prefix tmdb:movie:10",
                "meta_json": json.dumps(
                    {
                        "media_id": str(source),
                        "tmdb_id": 1,
                        "unrelated_media_id": "tmdb:movie:10",
                        "nested": {"media_id": "tmdb:movie:10", "tmdb_id": 10},
                    }
                ),
            },
        )

    MediaIdentityRepository().merge_media_id(source, target)

    with SessionLocal() as session:
        row = (
            session.execute(
                text("SELECT search_text, meta_json, media_id, target_id FROM actions WHERE id = :id"),
                {"id": action_id},
            )
            .mappings()
            .one()
        )

    meta = json.loads(row["meta_json"])
    assert row["media_id"] == str(target)
    assert row["target_id"] == str(source)
    assert row["search_text"] == "exact tmdb:movie:456 prefix tmdb:movie:10"
    assert meta["media_id"] == str(target)
    assert meta["tmdb_id"] == 456
    assert meta["unrelated_media_id"] == "tmdb:movie:10"
    assert meta["nested"] == {"media_id": "tmdb:movie:10", "tmdb_id": 10}
