SCOPE_SEPARATOR = "::"


def scoped_site_id(indexer_id: str, site_id: str) -> str:
    return f"{indexer_id}{SCOPE_SEPARATOR}{site_id}"


def split_scoped_site_id(site_id: str) -> tuple[str | None, str]:
    indexer_id, separator, raw_site_id = site_id.partition(SCOPE_SEPARATOR)
    if not separator:
        return None, site_id
    return indexer_id, raw_site_id
