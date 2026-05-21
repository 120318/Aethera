from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from app.schemas.domain.media import EpisodeInfo, MediaFullInfo, SeasonDetails


def normalize_runtime(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    matched = re.search(r"\d+", text)
    return matched.group(0) if matched else ""


def fill_text_if_empty(current: str | None, fallback: str | None) -> str:
    current_value = (current or "").strip()
    return current_value or (fallback or "")


def public_rating_for_nfo(media: MediaFullInfo) -> str | None:
    rating = media.vote_average
    if rating is None or rating <= 0:
        return None
    if media.douban_id and (media.rating_source or "").lower() != "douban":
        return None
    return f"{rating:g}"


def build_movie_nfo(media: MediaFullInfo, *, tmdb_id: int | None = None) -> str:
    root = ET.Element("movie")
    _fill_common_nfo(root, media, tmdb_id=tmdb_id)
    return _to_xml(root)


def build_tvshow_nfo(media: MediaFullInfo, *, tmdb_id: int | None = None) -> str:
    root = ET.Element("tvshow")
    _fill_common_nfo(root, media, tmdb_id=tmdb_id)
    ET.SubElement(root, "season").text = "-1"
    ET.SubElement(root, "episode").text = "-1"
    return _to_xml(root)


def build_season_nfo(
    media: MediaFullInfo,
    season_details: SeasonDetails,
) -> str:
    season_number = season_details.season_number
    root = ET.Element("season")
    ET.SubElement(root, "seasonnumber").text = str(season_number)
    ET.SubElement(root, "title").text = season_details.name or f"Season {season_number}"
    overview = season_details.overview or ""
    ET.SubElement(root, "plot").text = overview
    ET.SubElement(root, "outline").text = overview
    air_date = season_details.air_date or ""
    if air_date:
        ET.SubElement(root, "premiered").text = air_date
        ET.SubElement(root, "releasedate").text = air_date
    if season_details.id:
        uniqueid = ET.SubElement(root, "uniqueid", type="tmdb", default="true")
        uniqueid.text = str(season_details.id)
    runtime = normalize_runtime(media.duration)
    if runtime:
        ET.SubElement(root, "runtime").text = runtime
    return _to_xml(root)


def build_episode_nfo(
    media: MediaFullInfo,
    season_number: int,
    episode_number: int,
    episode_info: EpisodeInfo | None,
    season_details: SeasonDetails | None,
    *,
    tmdb_id: int | None = None,
) -> str:
    ep_name = episode_info.title if episode_info else None
    ep_overview = episode_info.overview if episode_info else None
    ep_air_date = episode_info.air_date if episode_info else None
    ep_runtime = episode_info.runtime if episode_info else None
    if season_details and (not ep_name or not ep_overview):
        for episode in season_details.episodes or []:
            if episode.episode_number != episode_number:
                continue
            ep_name = fill_text_if_empty(ep_name or "", episode.title or "")
            ep_overview = fill_text_if_empty(ep_overview or "", episode.overview or "")
            ep_air_date = fill_text_if_empty(ep_air_date or "", episode.air_date or "")
            if ep_runtime is None:
                ep_runtime = episode.runtime
            break

    root = ET.Element("episodedetails")
    ET.SubElement(root, "title").text = ep_name or ""
    ET.SubElement(root, "showtitle").text = media.title or ""
    ET.SubElement(root, "season").text = str(season_number)
    ET.SubElement(root, "episode").text = str(episode_number)
    ET.SubElement(root, "plot").text = ep_overview or ""
    ET.SubElement(root, "aired").text = ep_air_date or ""
    runtime_source = str(ep_runtime) if ep_runtime is not None else media.duration
    runtime = normalize_runtime(runtime_source)
    if runtime:
        ET.SubElement(root, "runtime").text = runtime
    if tmdb_id:
        uniqueid = ET.SubElement(root, "uniqueid", type="tmdb", default="true")
        uniqueid.text = str(episode_info.id if episode_info else f"tmdb-{tmdb_id}-{season_number}-{episode_number}")
    return _to_xml(root)


def _fill_common_nfo(root: ET.Element, media: MediaFullInfo, *, tmdb_id: int | None) -> None:
    ET.SubElement(root, "title").text = media.title or ""
    ET.SubElement(root, "originaltitle").text = media.original_title or ""
    ET.SubElement(root, "plot").text = media.overview or ""
    ET.SubElement(root, "outline").text = media.overview or ""
    release_date = media.release_date or media.first_air_date
    if release_date:
        ET.SubElement(root, "premiered").text = release_date
        ET.SubElement(root, "releasedate").text = release_date
        if "-" in release_date:
            ET.SubElement(root, "year").text = release_date.split("-")[0]
    if tmdb_id:
        uniqueid = ET.SubElement(root, "uniqueid", type="tmdb", default="true")
        uniqueid.text = str(tmdb_id)
    if media.imdb_id:
        uniqueid = ET.SubElement(root, "uniqueid", type="imdb")
        uniqueid.text = str(media.imdb_id)
    if media.tvdb_id:
        uniqueid = ET.SubElement(root, "uniqueid", type="tvdb")
        uniqueid.text = str(media.tvdb_id)
    runtime = normalize_runtime(media.duration)
    if runtime:
        ET.SubElement(root, "runtime").text = runtime
    rating = public_rating_for_nfo(media)
    if rating:
        ET.SubElement(root, "rating").text = rating
    for genre in media.genres or []:
        ET.SubElement(root, "genre").text = genre
    for studio in media.studios or []:
        ET.SubElement(root, "studio").text = studio
    for actor in media.actors or []:
        actor_el = ET.SubElement(root, "actor")
        ET.SubElement(actor_el, "name").text = actor.name or ""
        ET.SubElement(actor_el, "role").text = actor.character or ""
        if actor.avatar and actor.avatar.large:
            ET.SubElement(actor_el, "thumb").text = actor.avatar.large
    for director in media.directors or []:
        ET.SubElement(root, "director").text = director.name or ""


def _to_xml(root: ET.Element) -> str:
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)
    return ET.tostring(root, encoding="unicode", xml_declaration=False)
