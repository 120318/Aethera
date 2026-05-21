"""
text
"""
import base64
from typing import Optional

import bencodepy
import hashlib
import re

def extract_hash_from_magnet(magnet_url: str) -> Optional[str]:
    """
    texthash
    
    Args:
        magnet_url: text
        
    Returns:
        texthash（40text），None
    """
    if not magnet_url or not magnet_url.startswith('magnet:'):
        return None
    
    # Internal note.
    match = re.search(r'btih:([a-fA-F0-9]{40})', magnet_url, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    
    # Internal note.
    match = re.search(r'btih:([A-Z2-7]{32})', magnet_url, re.IGNORECASE)
    if match:
        # Internal note.
        try:
            hash_bytes = base64.b32decode(match.group(1).upper())
            return hash_bytes.hex().lower()
        except:
            pass
    
    return None


def calculate_torrent_hash(torrent_data: bytes) -> Optional[str]:
    """
    textinfo hash
    
    Args:
        torrent_data: text
        
    Returns:
        texthash（40text），None
    """
    try:
        # Internal note.
        torrent_dict = bencodepy.decode(torrent_data)
        
        # Internal note.
        if b'info' not in torrent_dict:
            return None
        
        info = torrent_dict[b'info']
        
        # Internal note.
        info_encoded = bencodepy.encode(info)
        info_hash = hashlib.sha1(info_encoded).hexdigest().lower()
        
        return info_hash
        
    except Exception as e:
        print(f"Error calculating torrent hash: {e}")
        return None


def get_torrent_hash(link: str, torrent_data: Optional[bytes] = None) -> Optional[str]:
    """
    text：texthash
    
    Args:
        link: text（textHTTPtext）
        torrent_data: text，text
        
    Returns:
        texthash，None
    """
    # Internal note.
    if link.startswith('magnet:'):
        return extract_hash_from_magnet(link)
    
    # Internal note.
    if torrent_data:
        return calculate_torrent_hash(torrent_data)
    
    return None


def calculate_torrent_total_size(torrent_data: bytes) -> Optional[int]:
    """
    text（text）.

    text.
    text None text.
    """
    try:
        torrent_dict = bencodepy.decode(torrent_data)
        if b'info' not in torrent_dict:
            return None
        info = torrent_dict[b'info']

        # Internal note.
        if b'length' in info:
            return int(info[b'length'])

        # Internal note.
        if b'files' in info:
            files = info[b'files']
            total = 0
            for f in files:
                if b'length' in f:
                    total += int(f[b'length'])
            return total if total > 0 else None

        return None
    except Exception:
        return None
