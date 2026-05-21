import os
import stat
import shutil
import logging
import uuid
from pathlib import Path
from typing import Union, List, Optional

logger = logging.getLogger("app.utils.fs")

DIRECTORY_MODE = 0o775
SIDECAR_FILE_MODE = 0o664


def _missing_directory_chain(path: Path) -> list[Path]:
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        parent = current.parent
        if parent == current:
            break
        current = parent
    return list(reversed(missing))


def _chmod_created(path: Path, mode: int, *, preserve_special_bits: bool = False) -> None:
    try:
        target_mode = mode
        if preserve_special_bits:
            target_mode |= path.stat().st_mode & (stat.S_ISUID | stat.S_ISGID | stat.S_ISVTX)
        os.chmod(path, target_mode)
    except OSError as exc:
        logger.warning("Failed to chmod %s to %s: %s", path, oct(mode), exc)


def ensure_directory(path: Union[str, Path], mode: int = DIRECTORY_MODE) -> None:
    """Internal helper."""
    target = Path(path)
    missing = _missing_directory_chain(target)
    target.mkdir(parents=True, exist_ok=True)
    for created_path in missing:
        if created_path.is_dir():
            _chmod_created(created_path, mode, preserve_special_bits=True)


def write_text_file(path: Union[str, Path], content: str, *, encoding: str = "utf-8", mode: int = SIDECAR_FILE_MODE) -> None:
    target = Path(path)
    existed = target.exists()
    ensure_directory(target.parent)
    target.write_text(content, encoding=encoding)
    if not existed:
        _chmod_created(target, mode)


class FileSystemProvider:
    """Internal helper."""

    @staticmethod
    def exists(path: Union[str, Path]) -> bool:
        """Internal helper."""
        return Path(path).exists()

    @staticmethod
    def is_file(path: Union[str, Path]) -> bool:
        """Internal helper."""
        return Path(path).is_file()

    @staticmethod
    def is_dir(path: Union[str, Path]) -> bool:
        """Internal helper."""
        return Path(path).is_dir()

    @staticmethod
    def mkdir(path: Union[str, Path], exist_ok: bool = True, parents: bool = True) -> None:
        """Internal helper."""
        if parents and exist_ok:
            ensure_directory(path)
            return
        Path(path).mkdir(parents=parents, exist_ok=exist_ok)

    @staticmethod
    def remove(path: Union[str, Path]) -> bool:
        """Internal helper."""
        p = Path(path)
        try:
            if p.is_file():
                os.remove(p)
            elif p.is_dir():
                shutil.rmtree(p)
            return True
        except Exception as e:
            logger.error(f"Failed to remove {path}: {e}")
            return False

    @staticmethod
    def hardlink(src: Union[str, Path], dst: Union[str, Path]) -> bool:
        """Internal helper."""
        try:
            src_path = Path(src)
            dst_path = Path(dst)
            
            ensure_directory(dst_path.parent)
            
            if dst_path.exists():
                os.remove(dst_path)
                
            os.link(src_path, dst_path)
            return True
        except Exception as e:
            logger.error(f"Failed to hardlink {src} to {dst}: {e}")
            return False

    @staticmethod
    def copy(src: Union[str, Path], dst: Union[str, Path]) -> bool:
        """Internal helper."""
        tmp_path: Path | None = None
        try:
            src_path = Path(src)
            dst_path = Path(dst)

            ensure_directory(dst_path.parent)

            tmp_path = dst_path.with_name(f".{dst_path.name}.{uuid.uuid4().hex}.tmp")
            shutil.copy2(src_path, tmp_path)
            os.replace(tmp_path, dst_path)
            return True
        except Exception as e:
            logger.error(f"Failed to copy {src} to {dst}: {e}")
            if tmp_path and tmp_path.exists():
                try:
                    os.remove(tmp_path)
                except OSError as cleanup_error:
                    logger.warning(f"Failed to remove temporary copy {tmp_path}: {cleanup_error}")
            return False

    @staticmethod
    def move(src: Union[str, Path], dst: Union[str, Path]) -> bool:
        """Internal helper."""
        try:
            src_path = Path(src)
            dst_path = Path(dst)
            ensure_directory(dst_path.parent)
            shutil.move(str(src_path), str(dst_path))
            return True
        except Exception as e:
            logger.error(f"Failed to move {src} to {dst}: {e}")
            return False

    @staticmethod
    def get_size(path: Union[str, Path]) -> int:
        """Internal helper."""
        p = Path(path)
        if p.is_file():
            return p.stat().st_size
        elif p.is_dir():
            return sum(f.stat().st_size for f in p.glob('**/*') if f.is_file())
        return 0

    @staticmethod
    def list_dir(path: Union[str, Path]) -> List[str]:
        """Internal helper."""
        p = Path(path)
        if p.is_dir():
            return [str(item) for item in p.iterdir()]
        return []

# Internal note.
fs_provider = FileSystemProvider()
