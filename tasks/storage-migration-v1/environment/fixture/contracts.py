def normalize_title(title):
    if not isinstance(title, str) or not title.strip():
        raise ValueError("title must be nonblank text")
    return title.strip()
