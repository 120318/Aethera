import logging
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)


def is_directory_writable(directory: str) -> bool:
    """
    text
    
    Args:
        directory: text
        
    Returns:
        text
    """
    try:
        path = Path(directory)
        # Internal note.
        if not path.exists() or not path.is_dir():
            return False
        
        # Internal note.
        temp_file = path / ".temp_write_test"
        temp_file.touch()
        temp_file.unlink()
        
        return True
    except Exception as e:
        logger.exception("Directory writability validation failed: %s", e)
        return False


def validate_directory_for_writing(directory: str) -> Union[bool, str]:
    """
    text
    
    Args:
        directory: text
        
    Returns:
        text True，text
    """
    try:
        path = Path(directory)
        
        if not path.exists():
            return "Directory does not exist"
            
        if not path.is_dir():
            return "Path is not a valid directory"
            
        if not is_directory_writable(directory):
            return "Directory is not writable"
            
        return True
    except Exception as e:
        return f"Validation failed: {str(e)}"
