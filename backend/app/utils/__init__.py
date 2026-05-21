"""
text
"""
from app.utils.torrent_utils import get_torrent_hash, extract_hash_from_magnet, calculate_torrent_hash
from app.utils.title_parser import build_loose_tmdb_search_title, build_tmdb_search_title, parse_tv_title
from app.utils.validation import is_directory_writable, validate_directory_for_writing


def safe_name(name: str) -> str:
    """text/text
    
    text，text,text,text
    
    Args:
        name: text
        
    Returns:
        str: text
    """
    if not name:
        return ""
    
    # Internal note.
    return ''.join(c for c in name if c.isalnum() or c in (' ', '.', '-', '_')).strip()


__all__ = [
    'get_torrent_hash',
    'extract_hash_from_magnet',
    'calculate_torrent_hash',
    'parse_tv_title',
    'build_tmdb_search_title',
    'build_loose_tmdb_search_title',
    'is_directory_writable',
    'validate_directory_for_writing',
    'safe_name',
]
