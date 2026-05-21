import asyncio
import logging
from pathlib import Path

from app.schemas.config import DanmuAddonConfig
from app.services.integration.danmu.models import DanmuFetchResult


logger = logging.getLogger("app.application.danmu.duration")


class DanmuDurationGuard:
    async def has_duration_mismatch(
        self,
        video_path: Path,
        result: DanmuFetchResult,
        config: DanmuAddonConfig,
    ) -> bool:
        video_duration = await self.probe_video_duration_seconds(video_path)
        source_duration = result.source_duration_seconds
        if video_duration is None or source_duration is None:
            return False
        diff = abs(float(video_duration) - float(source_duration))
        tolerance = float(config.duration_tolerance_seconds)
        if diff <= tolerance:
            return False
        logger.warning(
            "Danmu skipped: duration mismatch path=%s provider=%s source=%s video_duration=%.3f source_duration=%.3f diff=%.3f tolerance=%.3f",
            video_path,
            result.provider,
            result.source_id,
            video_duration,
            source_duration,
            diff,
            tolerance,
        )
        return True

    async def probe_video_duration_seconds(self, video_path: Path) -> float | None:
        try:
            process = await asyncio.create_subprocess_exec(
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as exc:
            logger.warning("Danmu duration check skipped: ffprobe unavailable error=%s", exc)
            return None
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            logger.warning(
                "Danmu duration check skipped: ffprobe failed path=%s error=%s",
                video_path,
                stderr.decode("utf-8", errors="ignore").strip(),
            )
            return None
        try:
            duration = float(stdout.decode("utf-8", errors="ignore").strip())
        except ValueError:
            return None
        return duration if duration > 0 else None


danmu_duration_guard = DanmuDurationGuard()
