from __future__ import annotations

from dataclasses import dataclass
import html
import unicodedata

from app.services.integration.danmu.models import DanmuComment

PLAY_RES_X = 1920
PLAY_RES_Y = 1080
ASS_START_X = PLAY_RES_X


@dataclass(frozen=True)
class _PlacedComment:
    comment: DanmuComment
    lane: int
    text_width: int


def _normalize_font_size(font_size: int) -> int:
    return min(max(int(font_size or 60), 18), 96)


def _normalize_font_opacity_percent(font_opacity_percent: int) -> int:
    return min(max(int(font_opacity_percent or 80), 30), 100)


def _normalize_scroll_duration(duration_seconds: int) -> int:
    return min(max(int(duration_seconds or 20), 5), 35)


def _normalize_density_percent(density_percent: int) -> int:
    return min(max(int(density_percent or 20), 10), 100)


def _normalize_display_area(display_area: str) -> str:
    return "full" if display_area == "full" else "top"


def _lane_count(font_size: int, display_area: str) -> int:
    lane_height = _lane_height(font_size)
    area_height = 1000 if _normalize_display_area(display_area) == "full" else 480
    return max(int(area_height // lane_height), 1)


def _lane_height(font_size: int) -> int:
    return font_size + 10


def _text_width(text: str, font_size: int) -> int:
    width_units = 0.0
    for char in text or "":
        if unicodedata.east_asian_width(char) in {"F", "W"}:
            width_units += 1.0
        elif char.isspace():
            width_units += 0.35
        else:
            width_units += 0.55
    return max(int(width_units * font_size), font_size)


def _required_lane_gap_seconds(
    *,
    previous_width: int,
    next_width: int,
    duration_seconds: int,
    density_percent: int,
    font_size: int,
) -> float:
    density = _normalize_density_percent(density_percent)
    safety_gap = font_size * (2.5 - (density / 100 * 2.0))
    return duration_seconds * (max(previous_width, next_width) + safety_gap) / (PLAY_RES_X + previous_width)


def _layout_comments(
    comments: list[DanmuComment],
    *,
    font_size: int = 60,
    scroll_duration_seconds: int = 20,
    density_percent: int = 20,
    display_area: str = "top",
) -> list[_PlacedComment]:
    normalized_font_size = _normalize_font_size(font_size)
    duration = _normalize_scroll_duration(scroll_duration_seconds)
    lanes = _lane_count(normalized_font_size, display_area)
    lane_last_start: list[float | None] = [None] * lanes
    lane_last_width: list[int] = [0] * lanes
    placed: list[_PlacedComment] = []
    sorted_comments = sorted(comments, key=lambda comment: max(float(comment.time_seconds), 0.0))

    for comment in sorted_comments:
        start_time = max(float(comment.time_seconds), 0.0)
        text_width = _text_width(comment.text, normalized_font_size)
        selected_lane: int | None = None
        selected_wait: float | None = None
        for lane in range(lanes):
            previous_start = lane_last_start[lane]
            if previous_start is None:
                selected_lane = lane
                selected_wait = 0.0
                break
            required_gap = _required_lane_gap_seconds(
                previous_width=lane_last_width[lane],
                next_width=text_width,
                duration_seconds=duration,
                density_percent=density_percent,
                font_size=normalized_font_size,
            )
            wait = start_time - previous_start
            if wait >= required_gap and (selected_wait is None or wait > selected_wait):
                selected_lane = lane
                selected_wait = wait
        if selected_lane is None:
            continue
        lane_last_start[selected_lane] = start_time
        lane_last_width[selected_lane] = text_width
        placed.append(_PlacedComment(comment=comment, lane=selected_lane, text_width=text_width))
    return placed


def _xml_color(value: str | None) -> int:
    color = str(value or "").strip().lstrip("#")
    if len(color) != 6:
        return 16777215
    try:
        return int(color, 16)
    except ValueError:
        return 16777215


def build_xml(
    comments: list[DanmuComment],
    *,
    font_size: int = 60,
    scroll_duration_seconds: int = 20,
    density_percent: int = 20,
    display_area: str = "top",
) -> str:
    normalized_font_size = _normalize_font_size(font_size)
    rows = ['<?xml version="1.0" encoding="UTF-8"?>', "<i>"]
    for placed in _layout_comments(
        comments,
        font_size=font_size,
        scroll_duration_seconds=scroll_duration_seconds,
        density_percent=density_percent,
        display_area=display_area,
    ):
        comment = placed.comment
        time_value = max(float(comment.time_seconds), 0.0)
        text = html.escape(comment.text or "", quote=False)
        color = _xml_color(comment.color)
        rows.append(f'<d p="{time_value:.3f},1,{normalized_font_size},{color},0,0,0,0">{text}</d>')
    rows.append("</i>")
    return "\n".join(rows)


def _ass_time(seconds: float) -> str:
    normalized = max(float(seconds), 0.0)
    hours = int(normalized // 3600)
    minutes = int((normalized % 3600) // 60)
    secs = int(normalized % 60)
    centiseconds = int((normalized - int(normalized)) * 100)
    return f"{hours:d}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def _ass_escape(value: str) -> str:
    return (value or "").replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")


def _ass_alpha_color(opacity_percent: int, color: str = "FFFFFF") -> str:
    normalized_opacity = _normalize_font_opacity_percent(opacity_percent)
    alpha = round(255 * (100 - normalized_opacity) / 100)
    return f"&H{alpha:02X}{color}"


def build_ass(
    comments: list[DanmuComment],
    *,
    font_size: int = 60,
    font_opacity_percent: int = 80,
    scroll_duration_seconds: int = 20,
    density_percent: int = 20,
    display_area: str = "top",
) -> str:
    normalized_font_size = _normalize_font_size(font_size)
    primary_color = _ass_alpha_color(font_opacity_percent)
    duration = _normalize_scroll_duration(scroll_duration_seconds)
    lane_height = _lane_height(normalized_font_size)
    rows = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {PLAY_RES_X}",
        f"PlayResY: {PLAY_RES_Y}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Danmu,Arial,{normalized_font_size},{primary_color},&H000000FF,&H80000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,7,30,30,30,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for placed in _layout_comments(
        comments,
        font_size=font_size,
        scroll_duration_seconds=scroll_duration_seconds,
        density_percent=density_percent,
        display_area=display_area,
    ):
        comment = placed.comment
        start = _ass_time(comment.time_seconds)
        end = _ass_time(comment.time_seconds + duration)
        y = 40 + placed.lane * lane_height
        end_x = -placed.text_width
        text = _ass_escape(comment.text)
        rows.append(f"Dialogue: 0,{start},{end},Danmu,,0,0,0,,{{\\move({ASS_START_X},{y},{end_x},{y})}}{text}")
    return "\n".join(rows)
