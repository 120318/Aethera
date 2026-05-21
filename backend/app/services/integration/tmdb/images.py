def to_tmdb_image_url(path: str | None, size: str = "original") -> str | None:
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"https://image.tmdb.org/t/p/{size}{path}"
